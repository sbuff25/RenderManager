"""
Wain Worker Client
==================

Headless worker that polls a Wain server for render jobs,
claims them, renders locally, and reports progress back.

v2.18.0 — Added token auth, auto-reconnection with exponential backoff,
           and connection state tracking.
"""

import json
import os
import re
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
    WORKER_RECONNECT_BASE_DELAY,
    WORKER_RECONNECT_MAX_DELAY,
    WORKER_RECONNECT_MAX_RETRIES,
)
from wain.engines.registry import EngineRegistry
from wain.models import RenderJob


# ---------------------------------------------------------------------------
# Connection state constants
# ---------------------------------------------------------------------------
CONN_DISCONNECTED = "disconnected"
CONN_CONNECTING = "connecting"
CONN_CONNECTED = "connected"
CONN_RECONNECTING = "reconnecting"


class WorkerClient:
    """Headless render worker that connects to a Wain server.

    Supports:
    - Bearer-token authentication (``--token``)
    - Automatic reconnection with exponential backoff when the server
      goes away (e.g. Wain is closed and reopened).
    - Connection state tracking (disconnected / connecting / connected /
      reconnecting) that can be queried externally.
    """

    def __init__(self, server_url: str, worker_id: Optional[str] = None,
                 path_maps: Optional[List[tuple]] = None,
                 api_token: Optional[str] = None):
        self.server_url = server_url.rstrip("/")
        if not self.server_url.startswith("http"):
            self.server_url = f"http://{self.server_url}"

        self.worker_id = worker_id or socket.gethostname()
        self.hostname = socket.gethostname()
        self.ip_address = self._get_local_ip()
        self.path_maps = path_maps or []
        self.api_token = api_token or ""

        self.engine_registry = EngineRegistry()
        self.supported_engines = ["blender", "marmoset"]
        self.capabilities = self._build_capabilities()

        self.running = True
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._current_job: Optional[RenderJob] = None
        self._current_engine = None
        self._last_progress_report = 0.0
        self._last_cancel_check = 0.0
        self._render_done = threading.Event()
        self._render_result: Dict[str, Any] = {}
        self._log_buffer: List[str] = []
        self._log_lock = threading.Lock()
        self._soft_cancel = False
        self._log_file = self._init_log_file()

        # Connection state -----------------------------------------------
        self._conn_state = CONN_DISCONNECTED
        self._conn_lock = threading.Lock()
        self._reconnect_attempt = 0
        # Consecutive failed API calls (used by heartbeat to detect loss)
        self._consecutive_failures = 0
        self._FAILURE_THRESHOLD = 3  # trigger reconnect after N failures

    # ====================================================================
    # Connection state helpers
    # ====================================================================

    @property
    def connection_state(self) -> str:
        with self._conn_lock:
            return self._conn_state

    def _set_conn_state(self, state: str):
        with self._conn_lock:
            old = self._conn_state
            self._conn_state = state
        if old != state:
            self._log(f"[Worker] Connection: {old} -> {state}")

    # ====================================================================
    # Logging
    # ====================================================================

    def _init_log_file(self):
        """Create a log file in the logs/ directory."""
        from datetime import datetime
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_path = os.path.join(logs_dir, f"worker_{self.worker_id}_{date_str}.log")
        try:
            f = open(log_path, "a", encoding="utf-8")
            f.write(f"\n{'='*60}\n")
            f.write(f"Worker session started: {datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n")
            return f
        except Exception:
            return None

    def _log(self, msg: str):
        """Write to both console and log file."""
        print(msg)
        if self._log_file:
            try:
                from datetime import datetime
                ts = datetime.now().strftime("%H:%M:%S")
                self._log_file.write(f"[{ts}] {msg}\n")
                self._log_file.flush()
            except Exception:
                pass

    # ====================================================================
    # Main Loop
    # ====================================================================

    def run(self):
        """Main worker loop.  Blocks until shutdown.

        On initial startup and whenever the server becomes unreachable the
        worker enters a reconnect loop with exponential backoff.  Once the
        server is available again it resumes polling for jobs.
        """
        self._log(f"[Worker] Starting worker '{self.worker_id}'")
        self._log(f"[Worker] Server: {self.server_url}")
        self._log(f"[Worker] Hostname: {self.hostname} ({self.ip_address})")
        self._log(f"[Worker] Supported engines: {self.supported_engines}")
        if self.api_token:
            self._log(f"[Worker] Auth token: {'*' * 8}...{self.api_token[-4:]}")
        else:
            self._log("[Worker] Auth token: (none)")

        try:
            while self.running:
                # --- Phase 1: connect / reconnect -------------------------
                if not self._connect_with_backoff():
                    # _connect_with_backoff only returns False if self.running
                    # was set to False (shutdown requested)
                    break

                # --- Phase 2: start heartbeat thread ----------------------
                self._start_heartbeat()

                self._log("[Worker] Ready. Polling for jobs...")

                # --- Phase 3: job polling loop ----------------------------
                try:
                    self._poll_loop()
                except KeyboardInterrupt:
                    raise

                # If we exit _poll_loop it means the connection was lost.
                # Loop back to phase 1 (reconnect).
                self._log("[Worker] Server connection lost — will attempt reconnect")

        except KeyboardInterrupt:
            self._log("\n[Worker] Shutting down...")
        finally:
            self.stop()

    def _connect_with_backoff(self) -> bool:
        """Try to connect to the server, retrying with exponential backoff.

        Returns True once connected, or False if ``self.running`` becomes
        False (i.e. the worker was asked to shut down).
        """
        is_first = self._reconnect_attempt == 0
        self._set_conn_state(CONN_CONNECTING if is_first else CONN_RECONNECTING)
        delay = WORKER_RECONNECT_BASE_DELAY

        while self.running:
            if self._verify_server():
                self._reconnect_attempt = 0
                self._consecutive_failures = 0
                self._set_conn_state(CONN_CONNECTED)
                return True

            self._reconnect_attempt += 1
            max_retries = WORKER_RECONNECT_MAX_RETRIES
            if max_retries and self._reconnect_attempt >= max_retries:
                self._log(f"[Worker] Max reconnect attempts ({max_retries}) reached. Exiting.")
                self._set_conn_state(CONN_DISCONNECTED)
                self.running = False
                return False

            self._log(f"[Worker] Retry {self._reconnect_attempt} in {delay}s...")
            # Sleep in small increments so we can react to shutdown quickly
            waited = 0.0
            while waited < delay and self.running:
                time.sleep(min(0.5, delay - waited))
                waited += 0.5

            delay = min(delay * 2, WORKER_RECONNECT_MAX_DELAY)

        return False  # shutdown

    def _poll_loop(self):
        """Poll for jobs until the server becomes unreachable."""
        while self.running:
            try:
                job_data = self._poll_for_job()
                if job_data:
                    self._render_job(job_data)
                else:
                    if self.connection_state != CONN_CONNECTED:
                        # Server went away during polling — break to reconnect
                        return
                    time.sleep(WORKER_POLL_INTERVAL)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                self._log(f"[Worker] Error in poll loop: {e}")
                if self.connection_state != CONN_CONNECTED:
                    return  # break to reconnect
                time.sleep(10)

    def stop(self):
        """Graceful shutdown."""
        self.running = False
        if self._current_engine:
            try:
                self._current_engine.cancel_render()
            except Exception:
                pass
        self._set_conn_state(CONN_DISCONNECTED)
        self._log("[Worker] Stopped.")

    # ====================================================================
    # Heartbeat
    # ====================================================================

    def _start_heartbeat(self):
        """(Re)start the heartbeat background thread."""
        # If a previous thread is still alive, let it finish on its own
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        """Background thread: sends heartbeat at regular intervals.

        If the heartbeat fails too many times in a row, transitions
        connection state to RECONNECTING so the main loop breaks out
        of _poll_loop.
        """
        while self.running and self.connection_state == CONN_CONNECTED:
            ok = self._send_heartbeat()
            if ok:
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._FAILURE_THRESHOLD:
                    self._log(f"[Worker] {self._consecutive_failures} consecutive heartbeat failures")
                    self._set_conn_state(CONN_RECONNECTING)
                    return  # exit thread — main loop will handle reconnect
            time.sleep(WORKER_HEARTBEAT_INTERVAL)

    def _send_heartbeat(self) -> bool:
        """Send heartbeat to server.  Returns True on success."""
        job_id = self._current_job.id if self._current_job else None
        status = "rendering" if self._current_job else "idle"

        result = self._api_call("POST", "/api/workers/heartbeat", {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "status": status,
            "current_job_id": job_id,
            "capabilities": self.capabilities,
        })
        return result is not None and result.get("ok", False)

    # ====================================================================
    # Server Communication
    # ====================================================================

    def _api_call(self, method: str, path: str,
                  body: Optional[Dict] = None,
                  timeout: int = 15) -> Optional[Dict]:
        """Make an API call to the server. Returns parsed JSON or None."""
        url = f"{self.server_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None

        headers: Dict[str, str] = {}
        if data:
            headers["Content-Type"] = "application/json"
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        req = urllib.request.Request(
            url, data=data, method=method, headers=headers,
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self._log("[Worker] ERROR: Authentication failed (401) — check --token value")
            try:
                error_body = json.loads(e.read().decode("utf-8"))
                return error_body
            except Exception:
                return None
        except Exception as e:
            self._log(f"[Worker] API error ({method} {path}): {e}")
            return None

    def _verify_server(self) -> bool:
        """Check that the server is reachable and token (if required) is valid."""
        self._log(f"[Worker] Connecting to {self.server_url}...")
        result = self._api_call("GET", "/api/status")
        if not result or result.get("app") != "Wain":
            self._log("[Worker] Failed to connect to server")
            return False

        self._log(f"[Worker] Connected to Wain server v{result.get('version')}")
        self._log(f"[Worker] Server has {result.get('queued_jobs', 0)} queued job(s)")

        # Check if auth is required
        if result.get("auth_required") and not self.api_token:
            self._log("[Worker] ERROR: Server requires authentication. Use --token <token>")
            self.running = False
            return False

        # Validate the token with an authenticated endpoint
        if self.api_token:
            test = self._api_call("GET", "/api/workers")
            if test is not None and test.get("error") and "Unauthorized" in str(test.get("error", "")):
                self._log("[Worker] ERROR: Token rejected by server. Check --token value.")
                self.running = False
                return False

        return True

    # ====================================================================
    # Job Polling and Claiming
    # ====================================================================

    def _poll_for_job(self) -> Optional[Dict]:
        """Try to claim the next available job from the server."""
        result = self._api_call("POST", "/api/jobs/claim-next", {
            "worker_id": self.worker_id,
            "supported_engines": self.supported_engines,
        })

        if result is None:
            # Network failure — bump failure counter
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._FAILURE_THRESHOLD:
                self._set_conn_state(CONN_RECONNECTING)
            return None

        # Successful API call resets the counter
        self._consecutive_failures = 0

        if result.get("claimed"):
            job_data = result["job"]
            self._log(f"[Worker] Claimed job '{job_data.get('name', job_data['id'])}'"
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

        # Pass path_maps to engine so it can remap internal file references
        if self.path_maps:
            job.engine_settings["path_maps"] = [
                {"from": f, "to": t} for f, t in self.path_maps
            ]

        self._current_job = job
        self._render_done.clear()
        self._render_result = {"status": None, "error": None}
        self._last_progress_report = 0.0
        self._render_start_time = time.time()
        self._soft_cancel = False

        engine = self.engine_registry.get(job.engine_type)
        if engine is None:
            error = f"Engine '{job.engine_type}' not available"
            self._log(f"[Worker] {error}")
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

        self._log(f"[Worker] Starting render: {job.file_path}")
        self._log(f"[Worker] Output: {job.output_folder}")

        start_frame = job.frame_start
        if job.is_animation and job.current_frame > 0:
            start_frame = job.current_frame + 1
        elif job.original_start > 0:
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
            self._log(f"[Worker] {msg}")
            with self._log_lock:
                self._log_buffer.append(str(msg)[:200])

        try:
            engine.start_render(
                job, start_frame,
                on_progress, on_complete, on_error, on_log,
            )

            # Wait for render to finish
            self._render_done.wait()

            if self._render_result["status"] == "completed":
                self._log(f"[Worker] Job '{job.name or job.id}' completed")
                self._report_complete(job.id)
            elif self._render_result["status"] == "cancelled":
                self._log(f"[Worker] Job '{job.name or job.id}' cancelled")
                # Server already set the status, no need to report
            else:
                error = self._render_result.get("error", "Unknown error")
                self._log(f"[Worker] Job '{job.name or job.id}' failed: {error}")
                self._report_error(job.id, error)

        except Exception as e:
            self._log(f"[Worker] Render exception: {e}")
            self._report_error(job.id, str(e))

        self._current_job = None
        self._current_engine = None

    def _handle_progress(self, job: RenderJob, frame: int, msg: str):
        """Handle progress callback from engine, throttle API reports."""
        now = time.time()

        # Update local job state
        if frame >= 0:
            job.rendering_frame = frame
            if frame >= job.current_frame:
                job.current_frame = frame

        # Calculate progress percentage
        if job.is_animation and job.frame_end > job.frame_start:
            total = job.frame_end - job.frame_start + 1
            done = max(0, job.current_frame - job.frame_start)
            job.progress = min(int((done / total) * 100), 99)
        elif frame == -1:
            # Single frame complete signal
            job.progress = 100
        elif not job.is_animation and job.total_samples > 0 and job.current_sample > 0:
            # Single frame: use sample progress
            job.progress = min(int((job.current_sample / job.total_samples) * 100), 99)

        # Parse sample info from Blender output
        if msg:
            sample_match = re.search(r'Sample\s+(\d+)/(\d+)', msg)
            if sample_match:
                job.current_sample = int(sample_match.group(1))
                job.total_samples = int(sample_match.group(2))

            tile_match = re.search(r'Tile\s+(\d+)/(\d+)', msg)
            if tile_match:
                job.current_tile = int(tile_match.group(1))
                job.total_tiles = int(tile_match.group(2))

        # Check if server cancelled/paused this job
        if not self._soft_cancel and self._check_cancellation(job.id):
            self._log(f"[Worker] Job '{job.name or job.id}' paused by server — finishing current frame")
            self._soft_cancel = True

        # If soft cancel is active, stop the render gracefully
        if self._soft_cancel:
            # Blender: wait for current frame to save before stopping
            # Marmoset: no intermediate save point, cancel immediately
            can_stop = (job.engine_type != "blender") or (msg and "Saved:" in msg)
            if can_stop:
                self._log(f"[Worker] Stopping render (paused at frame {job.current_frame})")
                self._flush_log_buffer()
                # Report final position so resume works correctly
                self._api_call("PUT", f"/api/jobs/{job.id}/progress", {
                    "worker_id": self.worker_id,
                    "current_frame": job.current_frame,
                    "rendering_frame": job.rendering_frame,
                    "status": "paused",
                    "status_message": f"Paused at frame {job.current_frame}",
                })
                if self._current_engine:
                    self._current_engine.cancel_render()
                self._render_result["status"] = "cancelled"
                self._render_done.set()
                return

        # Throttle API calls
        if now - self._last_progress_report < PROGRESS_REPORT_INTERVAL:
            return
        self._last_progress_report = now

        self._flush_log_buffer()

        # Compute elapsed time
        total_secs = job.accumulated_seconds + int(now - self._render_start_time)
        h, rem = divmod(total_secs, 3600)
        m, s = divmod(rem, 60)
        elapsed = f"{h}:{m:02d}:{s:02d}"

        self._api_call("PUT", f"/api/jobs/{job.id}/progress", {
            "worker_id": self.worker_id,
            "progress": job.progress,
            "current_frame": job.current_frame,
            "rendering_frame": job.rendering_frame,
            "status": "rendering",
            "status_message": msg[:200] if msg else "",
            "elapsed_time": elapsed,
            "accumulated_seconds": total_secs,
            "current_sample": job.current_sample,
            "total_samples": job.total_samples,
            "current_tile": job.current_tile,
            "total_tiles": job.total_tiles,
            "current_pass": job.current_pass,
            "current_pass_num": job.current_pass_num,
            "total_passes": job.total_passes,
        })

    def _check_cancellation(self, job_id: str) -> bool:
        """Check if the server has cancelled this job. Returns True if cancelled."""
        now = time.time()
        # Only check every 3 seconds to avoid spamming the server
        if now - self._last_cancel_check < 3.0:
            return False
        self._last_cancel_check = now

        result = self._api_call("GET", f"/api/jobs/{job_id}/status")
        if result is None:
            # Server unreachable or job deleted (404) — treat as cancelled
            return True
        if result.get("status") in ("paused", "queued", "failed"):
            return True
        if result.get("error"):
            # Job not found (deleted) — treat as cancelled
            return True
        return False

    def _flush_log_buffer(self):
        """Send buffered log messages to the server."""
        with self._log_lock:
            if not self._log_buffer:
                return
            messages = self._log_buffer[:]
            self._log_buffer.clear()
        self._api_call("POST", "/api/log", {
            "worker_id": self.worker_id,
            "messages": messages,
        })

    def _report_complete(self, job_id: str):
        """Report job completion to server."""
        self._flush_log_buffer()
        self._api_call("PUT", f"/api/jobs/{job_id}/complete", {
            "worker_id": self.worker_id,
        })

    def _report_error(self, job_id: str, error_message: str):
        """Report job failure to server."""
        self._flush_log_buffer()
        self._api_call("PUT", f"/api/jobs/{job_id}/error", {
            "worker_id": self.worker_id,
            "error_message": error_message,
        })

    # ====================================================================
    # Utility
    # ====================================================================

    def _remap_path(self, path: str) -> str:
        """Remap a file path using the configured path mappings."""
        if not self.path_maps or not path:
            return path
        # Normalize to backslashes for consistent comparison
        norm_path = path.replace('/', '\\')
        for from_prefix, to_prefix in self.path_maps:
            norm_from = from_prefix.replace('/', '\\')
            if norm_path.upper().startswith(norm_from.upper()):
                return to_prefix + norm_path[len(norm_from):]
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

        # Detect installed Marmoset versions
        marmoset = self.engine_registry.get("marmoset")
        if marmoset:
            try:
                versions = marmoset.scan_installed_versions()
                if versions:
                    caps["marmoset_versions"] = list(versions.keys())
            except Exception:
                pass

        return caps
