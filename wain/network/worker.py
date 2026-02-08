"""
Wain Worker Client
==================

Headless worker that polls a Wain server for render jobs,
claims them, renders locally, and reports progress back.
"""

import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from wain.config import (
    PROGRESS_REPORT_INTERVAL,
    WORKER_HEARTBEAT_INTERVAL,
    WORKER_POLL_INTERVAL,
)
from wain.engines.registry import EngineRegistry
from wain.models import RenderJob


class WorkerClient:
    """Headless render worker that connects to a Wain server."""

    def __init__(self, server_url: str, worker_id: Optional[str] = None,
                 path_map: Optional[tuple] = None):
        self.server_url = server_url.rstrip("/")
        if not self.server_url.startswith("http"):
            self.server_url = f"http://{self.server_url}"

        self.worker_id = worker_id or socket.gethostname()
        self.hostname = socket.gethostname()
        self.ip_address = self._get_local_ip()
        self.path_map = path_map  # (from_prefix, to_prefix) e.g. ("F:", "Z:")

        self.engine_registry = EngineRegistry()
        self.supported_engines = ["blender"]  # Phase 1: Blender only
        self.capabilities = self._build_capabilities()

        self.running = True
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._current_job: Optional[RenderJob] = None
        self._current_engine = None
        self._last_progress_report = 0.0
        self._render_done = threading.Event()
        self._render_result: Dict[str, Any] = {}

    # ====================================================================
    # Main Loop
    # ====================================================================

    def run(self):
        """Main worker loop. Blocks until shutdown."""
        print(f"[Worker] Starting worker '{self.worker_id}'")
        print(f"[Worker] Server: {self.server_url}")
        print(f"[Worker] Hostname: {self.hostname} ({self.ip_address})")
        print(f"[Worker] Supported engines: {self.supported_engines}")

        # Verify server connectivity
        if not self._verify_server():
            print("[Worker] Cannot connect to server. Exiting.")
            return

        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()

        print("[Worker] Ready. Polling for jobs...")

        try:
            while self.running:
                try:
                    job_data = self._poll_for_job()
                    if job_data:
                        self._render_job(job_data)
                    else:
                        time.sleep(WORKER_POLL_INTERVAL)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"[Worker] Error in poll loop: {e}")
                    time.sleep(10)
        except KeyboardInterrupt:
            print("\n[Worker] Shutting down...")
        finally:
            self.stop()

    def stop(self):
        """Graceful shutdown."""
        self.running = False
        if self._current_engine:
            try:
                self._current_engine.cancel_render()
            except Exception:
                pass
        print("[Worker] Stopped.")

    # ====================================================================
    # Server Communication
    # ====================================================================

    def _api_call(self, method: str, path: str,
                  body: Optional[Dict] = None,
                  timeout: int = 15) -> Optional[Dict]:
        """Make an API call to the server. Returns parsed JSON or None."""
        url = f"{self.server_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None

        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read().decode("utf-8"))
                return error_body
            except Exception:
                return None
        except Exception as e:
            print(f"[Worker] API error ({method} {path}): {e}")
            return None

    def _verify_server(self) -> bool:
        """Check that the server is reachable."""
        print(f"[Worker] Connecting to {self.server_url}...")
        result = self._api_call("GET", "/api/status")
        if result and result.get("app") == "Wain":
            print(f"[Worker] Connected to Wain server v{result.get('version')}")
            print(f"[Worker] Server has {result.get('queued_jobs', 0)} queued job(s)")
            return True
        print("[Worker] Failed to connect to server")
        return False

    # ====================================================================
    # Heartbeat
    # ====================================================================

    def _heartbeat_loop(self):
        """Background thread: sends heartbeat at regular intervals."""
        while self.running:
            self._send_heartbeat()
            time.sleep(WORKER_HEARTBEAT_INTERVAL)

    def _send_heartbeat(self):
        """Send heartbeat to server."""
        job_id = self._current_job.id if self._current_job else None
        status = "rendering" if self._current_job else "idle"

        self._api_call("POST", "/api/workers/heartbeat", {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "status": status,
            "current_job_id": job_id,
            "capabilities": self.capabilities,
        })

    # ====================================================================
    # Job Polling and Claiming
    # ====================================================================

    def _poll_for_job(self) -> Optional[Dict]:
        """Try to claim the next available job from the server."""
        result = self._api_call("POST", "/api/jobs/claim-next", {
            "worker_id": self.worker_id,
            "supported_engines": self.supported_engines,
        })

        if result and result.get("claimed"):
            job_data = result["job"]
            print(f"[Worker] Claimed job '{job_data.get('name', job_data['id'])}'"
                  f" ({job_data['engine_type']})")
            return job_data
        return None

    # ====================================================================
    # Rendering
    # ====================================================================

    def _render_job(self, job_data: Dict):
        """Render a claimed job locally using the appropriate engine."""
        job = RenderJob.from_dict(job_data)

        # Remap paths for this worker's drive mapping
        job.file_path = self._remap_path(job.file_path)
        job.output_folder = self._remap_path(job.output_folder)

        self._current_job = job
        self._render_done.clear()
        self._render_result = {"status": None, "error": None}
        self._last_progress_report = 0.0

        engine = self.engine_registry.get(job.engine_type)
        if engine is None:
            error = f"Engine '{job.engine_type}' not available"
            print(f"[Worker] {error}")
            self._report_error(job.id, error)
            self._current_job = None
            return

        self._current_engine = engine

        # Update server: job is now rendering
        self._api_call("PUT", f"/api/jobs/{job.id}/progress", {
            "worker_id": self.worker_id,
            "status": "rendering",
            "status_message": f"Rendering on {self.worker_id}",
        })

        print(f"[Worker] Starting render: {job.file_path}")
        print(f"[Worker] Output: {job.output_folder}")

        start_frame = job.frame_start
        if job.original_start > 0:
            start_frame = job.original_start

        def on_progress(frame, msg=""):
            self._handle_progress(job, frame, msg)

        def on_complete():
            self._render_result["status"] = "completed"
            self._render_done.set()

        def on_error(err):
            self._render_result["status"] = "failed"
            self._render_result["error"] = str(err)
            self._render_done.set()

        def on_log(msg):
            print(f"[Worker] {msg}")

        try:
            engine.start_render(
                job, start_frame,
                on_progress, on_complete, on_error, on_log,
            )

            # Wait for render to finish
            self._render_done.wait()

            if self._render_result["status"] == "completed":
                print(f"[Worker] Job '{job.name or job.id}' completed")
                self._report_complete(job.id)
            else:
                error = self._render_result.get("error", "Unknown error")
                print(f"[Worker] Job '{job.name or job.id}' failed: {error}")
                self._report_error(job.id, error)

        except Exception as e:
            print(f"[Worker] Render exception: {e}")
            self._report_error(job.id, str(e))

        self._current_job = None
        self._current_engine = None

    def _handle_progress(self, job: RenderJob, frame: int, msg: str):
        """Handle progress callback from engine, throttle API reports."""
        now = time.time()

        # Update local job state
        if frame >= 0:
            job.rendering_frame = frame
            if frame > job.current_frame:
                job.current_frame = frame

        # Calculate progress percentage
        if job.is_animation and job.frame_end > job.frame_start:
            total = job.frame_end - job.frame_start + 1
            done = max(0, job.current_frame - job.frame_start)
            job.progress = min(int((done / total) * 100), 99)
        elif frame == -1:
            # Single frame complete signal
            job.progress = 100

        # Parse sample info from Blender output
        if msg:
            import re
            sample_match = re.search(r'Sample\s+(\d+)/(\d+)', msg)
            if sample_match:
                job.current_sample = int(sample_match.group(1))
                job.total_samples = int(sample_match.group(2))

            tile_match = re.search(r'Tile\s+(\d+)/(\d+)', msg)
            if tile_match:
                job.current_tile = int(tile_match.group(1))
                job.total_tiles = int(tile_match.group(2))

        # Throttle API calls
        if now - self._last_progress_report < PROGRESS_REPORT_INTERVAL:
            return
        self._last_progress_report = now

        self._api_call("PUT", f"/api/jobs/{job.id}/progress", {
            "worker_id": self.worker_id,
            "progress": job.progress,
            "current_frame": job.current_frame,
            "rendering_frame": job.rendering_frame,
            "status": "rendering",
            "status_message": msg[:200] if msg else "",
            "current_sample": job.current_sample,
            "total_samples": job.total_samples,
            "current_tile": job.current_tile,
            "total_tiles": job.total_tiles,
        })

    def _report_complete(self, job_id: str):
        """Report job completion to server."""
        self._api_call("PUT", f"/api/jobs/{job_id}/complete", {
            "worker_id": self.worker_id,
        })

    def _report_error(self, job_id: str, error_message: str):
        """Report job failure to server."""
        self._api_call("PUT", f"/api/jobs/{job_id}/error", {
            "worker_id": self.worker_id,
            "error_message": error_message,
        })

    # ====================================================================
    # Utility
    # ====================================================================

    def _remap_path(self, path: str) -> str:
        """Remap a file path using the configured path mapping."""
        if not self.path_map or not path:
            return path
        from_prefix, to_prefix = self.path_map
        if path.upper().startswith(from_prefix.upper()):
            return to_prefix + path[len(from_prefix):]
        return path

    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _build_capabilities(self) -> Dict[str, Any]:
        """Build capabilities dict for this worker."""
        caps: Dict[str, Any] = {"engines": self.supported_engines}

        # Detect installed Blender versions
        blender = self.engine_registry.get("blender")
        if blender:
            try:
                versions = blender.scan_installed_versions()
                if versions:
                    caps["blender_versions"] = list(versions.keys())
            except Exception:
                pass

        return caps
