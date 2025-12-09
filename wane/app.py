"""
Wane Application
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

from wane.config import CONFIG_FILE
from wane.models import RenderJob, AppSettings
from wane.engines.registry import EngineRegistry

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
        self.job_count_container = None  # Job count display
        # Flags for thread-safe UI updates
        self._ui_needs_update = False
        self._render_finished = False
        self._log_needs_update = False
        self._progress_updates = []  # Queue of (job_id, progress, elapsed, frame, frames_display) for JS updates
        self.load_config()
    
    def log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_messages.append(f"[{ts}] {message}")
        if len(self.log_messages) > 100:
            self.log_messages = self.log_messages[-100:]
        # Set flag instead of calling refresh from potentially background thread
        self._log_needs_update = True
    
    def add_job(self, job):
        self.jobs.insert(0, job)
        self.save_config()
        self.log(f"Added: {job.name}")
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
        if self.job_count_container: self.job_count_container.refresh()
    
    def handle_action(self, action: str, job):
        self.log(f"{action.capitalize()}: {job.name}")
        
        if action == "start":
            job.status = "queued"
        elif action == "pause":
            if self.current_job and self.current_job.id == job.id:
                if self.render_start_time:
                    job.accumulated_seconds += int((datetime.now() - self.render_start_time).total_seconds())
                engine = self.engine_registry.get(job.engine_type)
                if engine: engine.cancel_render()
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
            # Reset progress to initial position based on where job starts in timeline
            if job.is_animation and job.frame_end > 0 and job.original_start > 1:
                job.progress = int(((job.original_start - 1) / job.frame_end) * 100)
            else:
                job.progress = 0
        elif action == "delete":
            if self.current_job and self.current_job.id == job.id:
                engine = self.engine_registry.get(job.engine_type)
                if engine: engine.cancel_render()
                self.current_job = None
            self.jobs = [j for j in self.jobs if j.id != job.id]
        
        self.save_config()
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
        if self.job_count_container: self.job_count_container.refresh()
    
    def process_queue(self):
        """Called by timer - handles queue processing and UI updates"""
        now = datetime.now()
        
        # Always update elapsed time for current rendering job (real-time timer)
        if self.current_job and self.current_job.status == "rendering" and self.render_start_time:
            total_secs = self.current_job.accumulated_seconds
            total_secs += int((now - self.render_start_time).total_seconds())
            h, rem = divmod(total_secs, 3600)
            m, s = divmod(rem, 60)
            elapsed = f"{h}:{m:02d}:{s:02d}"
            self.current_job.elapsed_time = elapsed
            
            # Push time update via JS (always, for real-time display)
            try:
                safe_frames = self.current_job.frames_display.replace('"', '\\"').replace("'", "\\'")
                safe_samples = self.current_job.samples_display.replace('"', '\\"').replace("'", "\\'")
                safe_pass = self.current_job.pass_display.replace('"', '\\"').replace("'", "\\'")
                ui.run_javascript(f'''
                    window.updateJobProgress && window.updateJobProgress("{self.current_job.id}", {self.current_job.progress}, "{elapsed}", "{safe_frames}", "{safe_samples}", "{safe_pass}");
                ''')
            except:
                pass
        
        # Handle additional progress updates via JavaScript (no full UI refresh - smooth!)
        if self._progress_updates:
            updates = self._progress_updates.copy()
            self._progress_updates.clear()
            
            for job_id, progress, elapsed, frame, frames_display, samples_display, pass_display in updates:
                # Update progress bar and label via JS - much smoother than full refresh
                try:
                    # Escape any quotes in displays
                    safe_frames = frames_display.replace('"', '\\"').replace("'", "\\'")
                    safe_samples = samples_display.replace('"', '\\"').replace("'", "\\'")
                    safe_pass = pass_display.replace('"', '\\"').replace("'", "\\'")
                    ui.run_javascript(f'''
                        window.updateJobProgress && window.updateJobProgress("{job_id}", {progress}, "{elapsed}", "{safe_frames}", "{safe_samples}", "{safe_pass}");
                    ''')
                except:
                    pass
        
        # Only do full UI refresh when status changes (render finished/failed)
        if self._ui_needs_update:
            if self._render_finished:
                # Always update immediately when render finishes
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
        
        # Log updates - skip during active render to prevent UI flicker
        # Only update log when no render is active, or every 5 seconds during render
        if self._log_needs_update:
            log_interval = 5.0 if self.current_job else 2.0
            if not hasattr(self, '_last_log_update') or \
               (now - self._last_log_update).total_seconds() >= log_interval:
                self._log_needs_update = False
                self._last_log_update = now
                if self.log_container:
                    try: self.log_container.refresh()
                    except: pass
        
        # Process queue - start next job if none running
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
            if self.job_count_container: self.job_count_container.refresh()
            return
        
        self.current_job = job
        job.status = "rendering"
        self.render_start_time = datetime.now()
        
        start_frame = job.frame_start
        if job.is_animation and job.current_frame > 0:
            start_frame = job.current_frame + 1
        
        if job.original_start == 0:
            job.original_start = job.frame_start
        
        # Set initial progress based on where we're starting in the timeline
        if job.is_animation and job.frame_end > 0:
            # Progress = (start_frame - 1) / total_frames
            # e.g., starting at frame 526 of 1500 = 525/1500 = 35%
            initial_frame = start_frame - 1 if start_frame > 1 else 0
            job.progress = int((initial_frame / job.frame_end) * 100)
        
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
        self.log(f"Starting: {job.name}")
        
        # Flag to signal UI needs update (checked by timer)
        self._ui_needs_update = False
        self._last_ui_update = datetime.now()
        
        def on_progress(frame, msg):
            # For Marmoset multi-pass rendering, the progress monitor handles progress directly
            # Skip the Blender-specific frame calculation for Marmoset jobs
            if job.engine_type == "marmoset":
                # Progress is managed by the MarmosetEngine's progress monitor
                # which sets job.progress based on total files / expected files
                # Just update the elapsed time here
                total_secs = job.accumulated_seconds
                if self.render_start_time:
                    total_secs += int((datetime.now() - self.render_start_time).total_seconds())
                h, rem = divmod(total_secs, 3600)
                m, s = divmod(rem, 60)
                job.elapsed_time = f"{h}:{m:02d}:{s:02d}"
                
                # Queue JS update
                self._progress_updates.append((job.id, job.progress, job.elapsed_time, job.current_frame, job.frames_display, job.samples_display, job.pass_display))
                return
            
            # Blender-specific progress handling below
            # Always try to parse sample progress from output (for both animation and single frame)
            sample_match = re.search(r'Sample (\d+)/(\d+)', msg)
            if sample_match:
                job.current_sample = int(sample_match.group(1))
                job.total_samples = int(sample_match.group(2))
            
            # Calculate progress based on frame position in ENTIRE timeline
            if job.is_animation:
                if frame > 0:
                    # Frame started - track it for display, but don't mark as complete yet
                    job.rendering_frame = frame
                
                if frame == -1:
                    # Frame saved/complete - NOW mark the rendering_frame as completed
                    if job.rendering_frame > 0:
                        job.current_frame = job.rendering_frame
                        # Reset sample counter for next frame
                        job.current_sample = 0
                    # Progress = completed frame / total frames in timeline
                    job.progress = min(int((job.current_frame / job.frame_end) * 100), 99)
                elif job.rendering_frame > 0:
                    # Update progress based on rendering_frame + sample progress
                    # Use (rendering_frame - 1) as base since current frame isn't done yet
                    frame_progress = 0
                    if job.current_sample > 0 and job.total_samples > 0:
                        frame_progress = job.current_sample / job.total_samples
                    # Progress based on (frames_before_current + partial_current) / total_frames
                    effective_frame = (job.rendering_frame - 1) + frame_progress
                    job.progress = min(int((effective_frame / job.frame_end) * 100), 99)
            else:
                # Single frame render - progress based on samples/status
                if frame == -1:  # Saved/complete signal
                    job.progress = 99
                elif sample_match:
                    # Use sample progress for single frames
                    job.progress = min(int((job.current_sample / job.total_samples) * 100), 99)
                elif "Sample" in msg or "Path Tracing" in msg:
                    # Increment gradually if we can't parse
                    job.progress = min(job.progress + 1, 95)
                elif frame > 0:
                    job.progress = min(job.progress + 5, 95)
            
            total_secs = job.accumulated_seconds
            if self.render_start_time:
                total_secs += int((datetime.now() - self.render_start_time).total_seconds())
            h, rem = divmod(total_secs, 3600)
            m, s = divmod(rem, 60)
            job.elapsed_time = f"{h}:{m:02d}:{s:02d}"
            
            # Queue JS update instead of full UI refresh (much smoother)
            self._progress_updates.append((job.id, job.progress, job.elapsed_time, job.current_frame, job.frames_display, job.samples_display, job.pass_display))
        
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
            "camera": j.camera, "engine_settings": j.engine_settings,
            "elapsed_time": j.elapsed_time, "accumulated_seconds": j.accumulated_seconds,
            "error_message": j.error_message,
            "current_sample": j.current_sample, "total_samples": j.total_samples,
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
                        camera=jd.get("camera", "Scene Default"), engine_settings=jd.get("engine_settings", {}),
                        elapsed_time=jd.get("elapsed_time", ""), accumulated_seconds=jd.get("accumulated_seconds", 0),
                        error_message=jd.get("error_message", ""),
                        current_sample=jd.get("current_sample", 0), total_samples=jd.get("total_samples", 0),
                    ))
            except: pass


render_app = RenderApp()
