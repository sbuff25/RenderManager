"""
Wain Application
================

Main application state and render queue management.
"""

import os
import sys
import json
import re
import uuid
from datetime import datetime
from typing import List, Optional

from nicegui import ui

from wain.config import CONFIG_FILE, APP_VERSION
from wain.models import RenderJob, AppSettings
from wain.engines.registry import EngineRegistry


def sanitize_to_ascii(message: str) -> str:
    if not message:
        return ""
    try:
        return ''.join(c if 32 <= ord(c) < 127 else '?' for c in str(message))
    except Exception:
        return "[encoding error]"


class RenderApp:
    CONFIG_FILE = "wain_config.json"
    
    def __init__(self):
        self.engine_registry = EngineRegistry()
        self.settings = AppSettings()
        self.jobs: List[RenderJob] = []
        self.current_job = None
        self.render_start_time = None
        self.log_messages: List[str] = []
        self.queue_container = None
        self.log_container = None
        self.stats_container = None
        self.job_count_container = None
        self._ui_needs_update = False
        self._render_finished = False
        self._log_needs_update = False
        self._progress_updates = []
        self.load_config()
    
    def log(self, message: str):
        safe_message = sanitize_to_ascii(message)
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_messages.append(f"[{ts}] {safe_message}")
        if len(self.log_messages) > 100:
            self.log_messages = self.log_messages[-100:]
        self._log_needs_update = True
    
    def add_job(self, job):
        self.jobs.insert(0, job)
        self.save_config()
        self.log(f"Added: {job.name}")
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
        if self.job_count_container: self.job_count_container.refresh()
    
    def handle_action(self, action: str, job):
        import threading
        
        self.log(f"{action.capitalize()}: {job.name}")
        
        if action == "start":
            job.status = "queued"
        elif action == "pause":
            if self.current_job and self.current_job.id == job.id:
                if self.render_start_time:
                    job.accumulated_seconds += int((datetime.now() - self.render_start_time).total_seconds())
                engine = self.engine_registry.get(job.engine_type)
                if engine:
                    # Run in background - pause_render is now non-blocking
                    if hasattr(engine, 'pause_render'):
                        engine.pause_render()
                    else:
                        engine.cancel_render()
                self.current_job = None
                self.render_start_time = None
            job.status = "paused"
        elif action == "retry":
            job.status = "queued"
            job.current_frame = 0
            job.rendering_frame = 0
            job.error_message = ""
            job.accumulated_seconds = 0
            job.elapsed_time = ""
            job.current_sample = 0
            job.total_samples = 0
            job.current_pass = ""
            job.current_pass_num = 0
            job.pass_frame = 0
            if job.is_animation and job.frame_end > 0 and job.original_start > 1:
                job.progress = int(((job.original_start - 1) / job.frame_end) * 100)
            else:
                job.progress = 0
        elif action == "delete":
            # Handle engine cleanup
            engine = self.engine_registry.get(job.engine_type)
            if self.current_job and self.current_job.id == job.id:
                if engine:
                    engine.cancel_render()  # Non-blocking, closes Vantage
                self.current_job = None
            elif job.status == "paused" and job.engine_type == "vantage":
                # For paused Vantage jobs, close Vantage
                if engine:
                    engine.cancel_render()  # Non-blocking, closes Vantage
            self.jobs = [j for j in self.jobs if j.id != job.id]
        
        self.save_config()
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
        if self.job_count_container: self.job_count_container.refresh()
    
    def process_queue(self):
        now = datetime.now()
        
        if self.current_job and self.current_job.status == "rendering" and self.render_start_time:
            total_secs = self.current_job.accumulated_seconds + int((now - self.render_start_time).total_seconds())
            h, rem = divmod(total_secs, 3600)
            m, s = divmod(rem, 60)
            elapsed = f"{h}:{m:02d}:{s:02d}"
            self.current_job.elapsed_time = elapsed
            
            job = self.current_job
            status_msg = job.status_message.replace('"', '\\"').replace("'", "\\'") if job.status_message else ""
            try:
                ui.run_javascript(f'window.updateJobProgress && window.updateJobProgress("{job.id}", {job.progress}, "{elapsed}", "{job.frames_display}", "{job.samples_display}", "{job.pass_display}", "{status_msg}");')
            except:
                pass
        
        if self._progress_updates:
            updates = self._progress_updates.copy()
            self._progress_updates.clear()
            for update in updates:
                try:
                    job_id, progress, elapsed, frame, frames_display, samples_display, pass_display = update[:7]
                    status_msg = update[7] if len(update) > 7 else ""
                    status_msg = status_msg.replace('"', '\\"').replace("'", "\\'") if status_msg else ""
                    ui.run_javascript(f'window.updateJobProgress && window.updateJobProgress("{job_id}", {progress}, "{elapsed}", "{frames_display}", "{samples_display}", "{pass_display}", "{status_msg}");')
                except:
                    pass
        
        if self._ui_needs_update and self._render_finished:
            self._ui_needs_update = False
            self._render_finished = False
            if self.queue_container:
                try: self.queue_container.refresh()
                except: pass
            if self.stats_container:
                try: self.stats_container.refresh()
                except: pass
            if self.job_count_container:
                try: self.job_count_container.refresh()
                except: pass
        
        if self._log_needs_update:
            log_interval = 5.0 if self.current_job else 2.0
            if not hasattr(self, '_last_log_update') or (now - self._last_log_update).total_seconds() >= log_interval:
                self._log_needs_update = False
                self._last_log_update = now
                if self.log_container:
                    try: self.log_container.refresh()
                    except: pass
        
        if self.current_job is None:
            for job in self.jobs:
                if job.status == "queued":
                    self.start_render(job)
                    break
    
    def start_render(self, job):
        engine = self.engine_registry.get(job.engine_type)
        if not engine:
            job.status = "failed"
            job.error_message = "Engine not found"
            if self.queue_container: self.queue_container.refresh()
            return
        
        self.current_job = job
        job.status = "rendering"
        self.render_start_time = datetime.now()
        
        start_frame = job.frame_start
        if job.is_animation and job.current_frame > 0:
            start_frame = job.current_frame + 1
        
        if job.original_start == 0:
            job.original_start = job.frame_start
        
        if job.is_animation and job.frame_end > 0:
            initial_frame = start_frame - 1 if start_frame > 1 else 0
            job.progress = int((initial_frame / job.frame_end) * 100)
        
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
        self.log(f"Starting: {job.name}")
        
        def on_progress(frame, msg):
            total_secs = job.accumulated_seconds
            if self.render_start_time:
                total_secs += int((datetime.now() - self.render_start_time).total_seconds())
            h, rem = divmod(total_secs, 3600)
            m, s = divmod(rem, 60)
            job.elapsed_time = f"{h}:{m:02d}:{s:02d}"
            
            # Store status message for UI display
            job.status_message = msg if msg else ""
            
            sample_match = re.search(r'Sample (\d+)/(\d+)', msg)
            if sample_match:
                job.current_sample = int(sample_match.group(1))
                job.total_samples = int(sample_match.group(2))
            
            # For Vantage: engine sets job properties directly, skip recalculation
            # Just queue the UI update with current values
            if job.engine_type == "vantage":
                self._progress_updates.append((job.id, job.progress, job.elapsed_time, job.current_frame, job.frames_display, job.samples_display, job.pass_display, job.status_message))
                return
            
            # For other engines (Blender, Marmoset): calculate progress from frame
            if job.is_animation:
                # CRITICAL: Only update rendering_frame if it's INCREASING
                # Never go backwards - this prevents progress resets
                if frame > 0 and frame > job.rendering_frame:
                    job.rendering_frame = frame
                if frame == -1 and job.rendering_frame > 0:
                    job.current_frame = job.rendering_frame
                    job.current_sample = 0
                    new_progress = min(int((job.current_frame / job.frame_end) * 100), 99)
                    # Only update if progress increases
                    if new_progress > job.progress:
                        job.progress = new_progress
                elif job.rendering_frame > 0:
                    completed_frames = job.rendering_frame - 1
                    new_progress = min(int((completed_frames / job.frame_end) * 100), 99)
                    # Only update if progress increases
                    if new_progress > job.progress:
                        job.progress = new_progress
            else:
                if frame == -1:
                    job.progress = 99
                elif sample_match:
                    new_progress = min(int((job.current_sample / job.total_samples) * 100), 99)
                    if new_progress > job.progress:
                        job.progress = new_progress
            
            self._progress_updates.append((job.id, job.progress, job.elapsed_time, job.current_frame, job.frames_display, job.samples_display, job.pass_display, job.status_message))
        
        def on_complete():
            job.status = "completed"
            job.progress = 100
            self.current_job = None
            self.log(f"Complete: {job.name}")
            self.save_config()
            self._ui_needs_update = True
            self._render_finished = True
        
        def on_error(err):
            job.status = "failed"
            job.error_message = err
            self.current_job = None
            self.log(f"Failed: {job.name} - {err}")
            self.save_config()
            self._ui_needs_update = True
            self._render_finished = True
        
        self._render_finished = False
        engine.start_render(job, start_frame, on_progress, on_complete, on_error, self.log)
    
    def save_config(self):
        data = {"jobs": [{
            "id": j.id, "name": j.name, "engine_type": j.engine_type,
            "file_path": j.file_path, "output_folder": j.output_folder,
            "output_name": j.output_name, "output_format": j.output_format,
            "status": j.status if j.status != "rendering" else "paused",
            "progress": j.progress, "is_animation": j.is_animation,
            "frame_start": j.frame_start, "frame_end": j.frame_end,
            "current_frame": j.current_frame, "rendering_frame": j.rendering_frame,
            "original_start": j.original_start,
            "res_width": j.res_width, "res_height": j.res_height,
            "camera": j.camera, "overwrite_existing": j.overwrite_existing,
            "engine_settings": j.engine_settings,
            "elapsed_time": j.elapsed_time, "accumulated_seconds": j.accumulated_seconds,
            "error_message": j.error_message,
        } for j in self.jobs]}
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except: pass
    
    def load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                for jd in data.get("jobs", []):
                    self.jobs.append(RenderJob(
                        id=jd.get("id", str(uuid.uuid4())[:8]),
                        name=jd.get("name", ""), engine_type=jd.get("engine_type", "blender"),
                        file_path=jd.get("file_path", ""), output_folder=jd.get("output_folder", ""),
                        output_name=jd.get("output_name", "render_"), output_format=jd.get("output_format", "PNG"),
                        status=jd.get("status", "queued"), progress=jd.get("progress", 0),
                        is_animation=jd.get("is_animation", False),
                        frame_start=jd.get("frame_start", 1), frame_end=jd.get("frame_end", 250),
                        current_frame=jd.get("current_frame", 0), rendering_frame=jd.get("rendering_frame", 0),
                        original_start=jd.get("original_start", 0),
                        res_width=jd.get("res_width", 1920), res_height=jd.get("res_height", 1080),
                        camera=jd.get("camera", "Scene Default"),
                        overwrite_existing=jd.get("overwrite_existing", True),
                        engine_settings=jd.get("engine_settings", {}),
                        elapsed_time=jd.get("elapsed_time", ""), accumulated_seconds=jd.get("accumulated_seconds", 0),
                        error_message=jd.get("error_message", ""),
                    ))
            except: pass


render_app = RenderApp()
