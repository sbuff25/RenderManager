"""
Wain MRQ Executor (v2.25.0)
===========================

Loaded by Unreal's PythonScriptPlugin via the UE_PYTHONPATH env var that
Wain sets on the render subprocess - this file never lives inside the
user's project (a mirrored project sync would delete it).

Launch contract (built by wain/engines/unreal.py):

    UnrealEditor-Cmd.exe <project> <map> -game
        -MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor
        -ExecutorPythonClass=/Engine/PythonTypes.WainMRQExecutor
        -WainMap=/Game/...  -WainSequence=/Game/...  -WainPreset=/Game/...
        [-WainOutputDir=...] [-WainFileName=...]
        [-WainStartFrame=N -WainEndFrame=N] [-WainResX=N -WainResY=N]

The MRQ preset supplies ALL quality settings untouched; Wain overrides
only logistics (where, which frames, what name) on the in-memory job.

https://github.com/sbuff25/RenderManager
"""

import unreal


@unreal.uclass()
class WainMRQExecutor(unreal.MoviePipelinePythonHostExecutor):
    # NOTE: the base class already owns 'pipeline_queue' - re-declaring it
    # breaks generate_class ("cannot override a property from the base type")
    wain_pipeline = unreal.uproperty(unreal.MoviePipeline)

    def _post_init(self):
        self.wain_pipeline = None

    # ------------------------------------------------------------------
    @unreal.ufunction(override=True)
    def execute_delayed(self, in_queue):
        _tokens, _switches, params = unreal.SystemLibrary.parse_command_line(
            unreal.SystemLibrary.get_command_line())

        seq_path = params.get("WainSequence", "")
        preset_path = params.get("WainPreset", "")
        if not seq_path or not preset_path:
            unreal.log_error("[Wain] Missing -WainSequence or -WainPreset - aborting")
            self._finish(False)
            return

        preset = unreal.load_asset(preset_path)
        if preset is None:
            unreal.log_error(f"[Wain] Could not load MRQ preset: {preset_path}")
            self._finish(False)
            return

        self.pipeline_queue = unreal.new_object(unreal.MoviePipelineQueue, outer=self)
        job = self.pipeline_queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
        job.job_name = params.get("WainJobName", "Wain Render")
        job.sequence = unreal.SoftObjectPath(seq_path)
        map_path = params.get("WainMap", "")
        if map_path:
            job.map = unreal.SoftObjectPath(map_path)
        job.set_configuration(preset)

        # ---- Wain's logistics overrides (quality stays with the preset) ----
        config = job.get_configuration()
        out = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)

        out_dir = params.get("WainOutputDir", "")
        if out_dir:
            d = unreal.DirectoryPath()
            d.path = out_dir.replace("\\", "/")
            out.output_directory = d

        name_fmt = params.get("WainFileName", "")
        if name_fmt:
            out.file_name_format = name_fmt

        f_start = params.get("WainStartFrame")
        f_end = params.get("WainEndFrame")
        if f_start is not None and f_end is not None:
            out.use_custom_playback_range = True
            out.custom_start_frame = int(f_start)
            # Wain's -WainEndFrame is INCLUSIVE (users think "last frame
            # rendered"); MRQ's custom range end is exclusive - validated
            # empirically: 0-2 exclusive rendered exactly frames 0000-0001
            out.custom_end_frame = int(f_end) + 1

        res_x = params.get("WainResX")
        res_y = params.get("WainResY")
        if res_x and res_y:
            out.output_resolution = unreal.IntPoint(int(res_x), int(res_y))

        # Write frames synchronously at each shot boundary. This project's
        # MRQ finalization can crash (D3D12/Niagara teardown) - async EXR
        # writes still in flight would be lost with them. Wain already
        # treats "crash after all frames on disk" as a completed render.
        try:
            out.flush_disk_writes_per_shot = True
        except Exception as e:
            unreal.log_warning(f"[Wain] Could not enable per-shot flush: {e}")

        range_txt = f"{f_start}-{f_end}" if f_start is not None else "(full)"
        unreal.log(
            f"[Wain] Executor: seq={seq_path} preset={preset_path} "
            f"out={out_dir or '(preset)'} name={name_fmt or '(preset)'} "
            f"range={range_txt}")

        self.wain_pipeline = unreal.new_object(
            self.target_pipeline_class,
            outer=self.get_last_loaded_world(),
            base_type=unreal.MoviePipeline)
        self.wain_pipeline.on_movie_pipeline_work_finished_delegate.add_function_unique(
            self, "on_wain_pipeline_finished")
        self.wain_pipeline.initialize(job)

    # ------------------------------------------------------------------
    @unreal.ufunction(ret=None, params=[unreal.MoviePipelineOutputData])
    def on_wain_pipeline_finished(self, results):
        success = bool(results.success)
        unreal.log(f"[Wain] Pipeline finished, success={success}")
        self.wain_pipeline = None
        self._finish(success)

    def _finish(self, success):
        try:
            self.on_executor_finished_impl()
        except Exception as e:
            unreal.log_error(f"[Wain] on_executor_finished_impl failed: {e}")
        try:
            unreal.SystemLibrary.quit_game(
                self.get_last_loaded_world(), None,
                unreal.QuitPreference.QUIT, False)
        except Exception as e:
            unreal.log_error(f"[Wain] quit_game failed: {e}")
