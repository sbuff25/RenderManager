# Wain Design Draft — MRQ Overrides & Project Sync

Target versions: v2.25.0 (Unreal per-job overrides), v2.26.0 (project sync).
Drafted 2026-07-22, status: NOT implemented — design only.

---

## Feature 1 — Per-job MRQ overrides (frame range, output dir, naming)

### Problem

MRQ's stock command line (`-MoviePipelineConfig=<preset>`) executes the preset
verbatim. Wain therefore cannot set output directory, file name format, or —
critically — frame range per job. Consequences today:

- The job's "Output Folder" field is only a *watch* path for progress counting;
  if it disagrees with the preset, progress silently freezes at 0 (happened
  2026-07-21: preset wrote to `Saved/MovieRenders/...`, job watched an empty
  custom folder).
- "Distribute" is disabled for Unreal jobs — no frame chunking, no multi-GPU,
  no multi-worker splits.
- Every output change is an editor round-trip + project re-sync.

### Approach: MoviePipelinePythonHostExecutor

UE ships a supported hook for exactly this: a Python executor class that owns
job construction in `-game` mode. Wain launches:

```
UnrealEditor-Cmd.exe <project> <map> -game
    -MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor
    -ExecutorPythonClass=/Engine/PythonTypes.WainMRQExecutor
    -windowed -resx=1280 -resy=720 -log -stdout -FullStdOutLogOutput
    -unattended [-RenderOffscreen]
    -WainSequence=/Game/Garage
    -WainPreset=/Game/KochRenderPreset
    -WainOutputDir="W:/Renders/Koch/GarageSequence/V03"
    -WainFileName="{sequence_name}.{frame_number}"
    -WainStartFrame=0 -WainEndFrame=975
```

`WainMRQExecutor` (a ~120-line Python script) subclasses
`unreal.MoviePipelinePythonHostExecutor`:

1. Parse `-Wain*` args from `unreal.SystemLibrary.get_command_line()`.
2. Build a `MoviePipelineQueue` job: map + sequence, `set_configuration()`
   from the preset asset (all quality settings/cvars come from the preset,
   untouched).
3. `find_or_add_setting_by_class(MoviePipelineOutputSetting)` and override
   only what Wain supplied:
   - `output_directory` (FDirectoryPath)
   - `file_name_format`
   - `use_custom_playback_range = True`, `custom_start_frame`,
     `custom_end_frame` (only when both Wain frame args present)
   - optional `output_resolution`
4. Execute; on `on_executor_finished`, request exit
   (`unreal.SystemLibrary.quit_game` / executor host quit) with clean code.

**Division of labor:** preset = quality (cvars, AA, passes, EXR settings);
Wain = logistics (where, which frames, what name). Preset assets are never
modified — no .uasset writing anywhere.

### Script delivery: UE_PYTHONPATH, not project content

The script must NOT live in the project's `Content/Python/`:
- robocopy `/MIR` sync would delete a worker-side copy not present locally;
- polluting the artist project with farm tooling is wrong anyway.

Instead the worker sets `UE_PYTHONPATH=<wain install>/wain/engines/ue_scripts`
in the child process env. UE's PythonScriptPlugin (enabled by default in
editor builds; `-game` runs the editor binary) appends that to `sys.path` and
`init_unreal.py` there registers the executor class. Zero project footprint,
ships with Wain via git pull.

Preflight check: engine probes `PythonScriptPlugin` availability by looking
for `Engine/Plugins/Experimental/PythonScriptPlugin` (or trusting default-on);
if the override launch fails with "ExecutorPythonClass not found", fall back
to the legacy command and surface a job warning.

### Wain-side changes

- `unreal.py`: build override command when any override present; legacy
  command otherwise (battle-tested path stays default).
- Job dialog (Unreal): Output Folder becomes a real, writable field again
  (it now *controls* output). Add optional "Frame range override" row
  (start/end, blank = whole sequence). Autofill-from-preset remains the
  default value.
- Progress: unchanged (file counting). When a custom range is set, total
  frames are known upfront — skip log calibration. Without it, existing
  auto-detection continues to work (log lines are identical under the
  Python executor).
- Distribute: re-enable for Unreal when overrides available. Existing chunk
  infrastructure already carries per-chunk `frame_start/frame_end`; chunks
  render to `<output>/chunk_<n>/` or share one folder (EXR names collide-free
  since frame numbers are absolute).
- Multi-GPU: worker gains `--gpu N` flag → appends `-graphicsadapter=N` to UE
  jobs it claims. Two workers on one box (`Karen-GPU0`, `Karen-GPU1`).
  **Documented hard requirement: workers must run in a console session
  (Parsec), never RDP — RDP fronts the virtual "Microsoft Remote Display
  Adapter" and produces black frames (proven 2026-07-21).**

### Validation plan (in order)

1. Local, single frame, output-dir override only → file lands in override dir.
2. Local, frame range 10–20 → exactly 11 frames, correct numbering.
3. Karen, same tests via worker.
4. Two chunks on Karen (one worker, sequential) → seam frame continuity check
   (motion blur/temporal history at chunk boundaries: verify chunk N's first
   frame matches a continuous render's same frame; MRQ warm-up should handle
   it — the preset's 64 warm-up frames apply per shot/chunk start).
5. Distribute across 5090 + A6000 — cross-GPU consistency A/B before
   trusting mixed-machine sequences (Lumen mode differences, driver variance).

### Open questions

- Chunk-boundary temporal history: warm-up count sufficient for Lumen
  accumulation at arbitrary mid-shot starts? Test #4 answers this; if seams
  show, chunk on shot boundaries only (shot ranges are already parsed from
  the log / could be probed via the executor).
- `quit on finish` behavior in `-game` python executor: verify exit code 0
  path so Wain's completion logic stays clean.

---

## Feature 2 — Project sync inside Wain (replaces RenderBox_PullProject.bat)

### Problem

Sync is a manual bat on the render box. Failure modes seen in production:
stale presets rendered silently (2026-07-21), tunnel death mid-copy, no
visibility from the Wain UI, user must RDP/Parsec in just to sync.

### Model: worker-pulled, server-orchestrated

Keep the proven pull topology (worker reads the server's SMB share — the
`KochProject` share already exists and robocopy over it is battle-tested).
Wain adds orchestration + visibility:

- **Server config (per project):** source share path
  (`\\192.168.3.2\KochProject`), excludes (default: `Saved`, `Intermediate`,
  `.vs`, `.git`, `.claude`, `*.log`), and per-worker destination — which is
  exactly the worker's existing `--path-map` entry; no new mapping concept.
- **Trigger:** "Sync" button on the worker row in the UI (and optional
  "Verify sync before render" checkbox per job). Server piggybacks the
  command on the heartbeat response: `{"sync": {"source": ..., "dest": ...,
  "excludes": [...]}}`.
- **Worker executes:** spawns robocopy with the bat's proven flags
  (`/MIR /FFT /MT:2 /R:1 /W:10` + excludes), parses stdout for per-file
  lines and the summary table, reports progress via the existing progress
  API channel (files copied / total, bytes, current file). Self-healing
  retry loop ported from the bat (60s wait, capped retries), state machine:
  `syncing -> verifying -> current | failed`.
- **UI:** worker row shows sync state + last-synced timestamp; a progress
  bar during sync; the v2.22 network card already visualizes throughput.
  Job cards targeting a stale worker show a badge ("project changed since
  last sync") — cheap heuristic: newest mtime under local Content/Config
  vs worker's last-sync timestamp.

### Performance note (VPN reality)

A full-tree verify over the tunnel costs 10–15 min in metadata round-trips
(measured). Offer two modes:
- **Quick sync** (default): `Content` + `Config` + `.uproject` only — catches
  presets/scene changes, minutes not tens of minutes.
- **Full mirror**: whole tree with `/MIR` (deletions propagate), for
  structural changes.

### Safety rails

- Never sync while that worker is rendering (queue the request; run when
  idle). Server enforces.
- Sync is one-way, server → worker, always. Worker-side edits are
  explicitly unsupported (documented; /MIR will eat them).
- Failure surfaces as a worker status, not a silent bat window on a remote
  box.

### Sequencing

1. v2.25.0: Feature 1 (executor + overrides + distribute + `--gpu`).
2. v2.26.0: Feature 2 (sync orchestration), reusing the worker command
   channel added in v2.25.
3. Later: "Deliver To" (worker→server frame trickle-back) completes the
   loop: sync in, render, frames out — all from the Wain UI.
