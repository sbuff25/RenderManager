"""
Wain REST API Server
====================

REST API endpoints for network rendering mode.
Routes are registered on NiceGUI's Starlette app.

All endpoints (except /api/status) require a Bearer token in the
Authorization header. The token is generated on first server start
and stored in AUTH_TOKEN_FILE.
"""

import asyncio
import json
import time
from typing import Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from wain.config import APP_VERSION, WORKER_STALE_TIMEOUT
from wain.models import RenderJob
from wain.network.auth import verify_token
from wain.network.database import JobDatabase


def register_api_routes(nicegui_app, db: JobDatabase, render_app=None,
                        api_token: str = ""):
    """Register all REST API routes on the NiceGUI app.

    Args:
        api_token: The server's API token. If non-empty, all endpoints
                   (except /api/status) require ``Authorization: Bearer <token>``.
    """

    _start_time = time.time()
    _api_token = api_token

    def _check_auth(request: Request) -> Optional[JSONResponse]:
        """Validate Authorization header. Returns an error response or None."""
        if not _api_token:
            return None  # Auth disabled (standalone / no token configured)
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            if verify_token(token, _api_token):
                return None  # Authenticated
        return JSONResponse(
            {"error": "Unauthorized — invalid or missing API token"},
            status_code=401,
        )

    # ====================================================================
    # Health Check
    # ====================================================================

    @nicegui_app.get("/api/status")
    async def api_status(request: Request) -> JSONResponse:
        """Public health check — no auth required.

        Returns ``auth_required: true`` so workers know they need a token.
        """
        jobs = db.get_all_jobs()
        queued = sum(1 for j in jobs if j.status == "queued")
        rendering = sum(1 for j in jobs if j.status in ("rendering", "claimed"))
        workers = db.get_workers()
        active = sum(1 for w in workers if not w["is_stale"])

        return JSONResponse({
            "app": "Wain",
            "version": APP_VERSION,
            "mode": "server",
            "uptime_seconds": int(time.time() - _start_time),
            "total_jobs": len(jobs),
            "queued_jobs": queued,
            "rendering_jobs": rendering,
            "active_workers": active,
            "auth_required": bool(_api_token),
        })

    # ====================================================================
    # Job Endpoints
    # ====================================================================

    @nicegui_app.get("/api/jobs")
    async def api_list_jobs(request: Request) -> JSONResponse:
        err = _check_auth(request)
        if err:
            return err
        status = request.query_params.get("status")
        engine_type = request.query_params.get("engine_type")
        limit = int(request.query_params.get("limit", 100))

        jobs = db.get_jobs(status=status, engine_type=engine_type, limit=limit)
        return JSONResponse({
            "jobs": [j.to_dict() for j in jobs],
            "total": len(jobs),
        })

    @nicegui_app.post("/api/jobs")
    async def api_create_job(request: Request) -> JSONResponse:
        err = _check_auth(request)
        if err:
            return err
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        try:
            job = RenderJob.from_dict(body)
            job.status = "queued"
            # Route through render_app.add_job() when available so
            # auto-packing and other lifecycle hooks trigger properly.
            if render_app:
                render_app.add_job(job)
            else:
                job = db.add_job(job)
            return JSONResponse(
                {"job": job.to_dict(), "message": "Job created"},
                status_code=201,
            )
        except Exception as e:
            return JSONResponse(
                {"error": f"Failed to create job: {e}"},
                status_code=400,
            )

    @nicegui_app.get("/api/jobs/{job_id}")
    async def api_get_job(request: Request) -> JSONResponse:
        err = _check_auth(request)
        if err:
            return err
        job_id = request.path_params["job_id"]
        job = db.get_job(job_id)
        if job is None:
            return JSONResponse({"error": "Job not found"}, status_code=404)
        return JSONResponse({"job": job.to_dict()})

    @nicegui_app.post("/api/jobs/claim-next")
    async def api_claim_next_job(request: Request) -> JSONResponse:
        err = _check_auth(request)
        if err:
            return err
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        worker_id = body.get("worker_id")
        supported_engines = body.get("supported_engines", ["blender"])

        if not worker_id:
            return JSONResponse(
                {"error": "worker_id required"}, status_code=400
            )

        job = db.claim_next_job(worker_id, supported_engines)
        if job is None:
            return JSONResponse(
                {"claimed": False, "message": "No jobs available"},
                status_code=200,
            )

        return JSONResponse({
            "claimed": True,
            "job": job.to_dict(),
        })

    @nicegui_app.post("/api/jobs/{job_id}/claim")
    async def api_claim_job(request: Request) -> JSONResponse:
        err = _check_auth(request)
        if err:
            return err
        job_id = request.path_params["job_id"]
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        worker_id = body.get("worker_id")
        if not worker_id:
            return JSONResponse(
                {"error": "worker_id required"}, status_code=400
            )

        job = db.claim_job(job_id, worker_id)
        if job is None:
            return JSONResponse({
                "claimed": False,
                "error": "Job already claimed or not available",
            }, status_code=409)

        return JSONResponse({"claimed": True, "job": job.to_dict()})

    @nicegui_app.put("/api/jobs/{job_id}/progress")
    async def api_update_progress(request: Request) -> JSONResponse:
        err = _check_auth(request)
        if err:
            return err
        job_id = request.path_params["job_id"]
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        worker_id = body.get("worker_id")
        if not worker_id:
            return JSONResponse(
                {"error": "worker_id required"}, status_code=400
            )

        # Extract progress fields from the body
        progress_fields = {}
        for key in (
            "progress", "current_frame", "rendering_frame",
            "elapsed_time", "accumulated_seconds",
            "current_sample", "total_samples",
            "current_tile", "total_tiles",
            "current_pass", "current_pass_num", "total_passes",
            "pass_frame", "pass_total_frames",
            "status_message", "status",
        ):
            if key in body:
                progress_fields[key] = body[key]

        ok = db.update_progress(job_id, worker_id, **progress_fields)
        if not ok:
            return JSONResponse(
                {"error": "Job not assigned to this worker"},
                status_code=403,
            )

        return JSONResponse({"ok": True})

    @nicegui_app.put("/api/jobs/{job_id}/complete")
    async def api_complete_job(request: Request) -> JSONResponse:
        err = _check_auth(request)
        if err:
            return err
        job_id = request.path_params["job_id"]
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        worker_id = body.get("worker_id")
        if not worker_id:
            return JSONResponse(
                {"error": "worker_id required"}, status_code=400
            )

        ok = db.complete_job(job_id, worker_id)
        if not ok:
            return JSONResponse(
                {"error": "Job not assigned to this worker"},
                status_code=403,
            )

        return JSONResponse({"ok": True, "status": "completed"})

    @nicegui_app.put("/api/jobs/{job_id}/error")
    async def api_fail_job(request: Request) -> JSONResponse:
        err = _check_auth(request)
        if err:
            return err
        job_id = request.path_params["job_id"]
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        worker_id = body.get("worker_id")
        error_message = body.get("error_message", "Unknown error")

        if not worker_id:
            return JSONResponse(
                {"error": "worker_id required"}, status_code=400
            )

        ok = db.fail_job(job_id, worker_id, error_message)
        if not ok:
            return JSONResponse(
                {"error": "Job not assigned to this worker"},
                status_code=403,
            )

        return JSONResponse({"ok": True, "status": "failed"})

    @nicegui_app.post("/api/jobs/{job_id}/cancel")
    async def api_cancel_job(request: Request) -> JSONResponse:
        """Server requests cancellation of a job being rendered by a worker."""
        err = _check_auth(request)
        if err:
            return err
        job_id = request.path_params["job_id"]
        job = db.get_job(job_id)
        if job is None:
            return JSONResponse({"error": "Job not found"}, status_code=404)

        # Mark the job as cancelled in the database
        db.update_job(job_id, status="paused", status_message="Cancelled by server")
        return JSONResponse({"ok": True, "status": "paused"})

    @nicegui_app.get("/api/jobs/{job_id}/status")
    async def api_job_status(request: Request) -> JSONResponse:
        """Worker polls this to check if its job was cancelled."""
        err = _check_auth(request)
        if err:
            return err
        job_id = request.path_params["job_id"]
        job = db.get_job(job_id)
        if job is None:
            return JSONResponse({"error": "Job not found"}, status_code=404)
        return JSONResponse({"status": job.status})

    # ====================================================================
    # Worker Endpoints
    # ====================================================================

    @nicegui_app.post("/api/workers/heartbeat")
    async def api_worker_heartbeat(request: Request) -> JSONResponse:
        err = _check_auth(request)
        if err:
            return err
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        worker_id = body.get("worker_id")
        if not worker_id:
            return JSONResponse(
                {"error": "worker_id required"}, status_code=400
            )

        db.update_heartbeat(
            worker_id=worker_id,
            hostname=body.get("hostname", ""),
            ip_address=body.get("ip_address", ""),
            status=body.get("status", "idle"),
            current_job_id=body.get("current_job_id"),
            capabilities=body.get("capabilities", {}),
        )

        return JSONResponse({
            "ok": True,
            "server_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    @nicegui_app.get("/api/workers")
    async def api_list_workers(request: Request) -> JSONResponse:
        err = _check_auth(request)
        if err:
            return err
        workers = db.get_workers()
        return JSONResponse({"workers": workers})

    # ====================================================================
    # Worker Log Relay
    # ====================================================================

    @nicegui_app.post("/api/log")
    async def api_worker_log(request: Request) -> JSONResponse:
        """Receive batched log messages from a worker."""
        err = _check_auth(request)
        if err:
            return err
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        worker_id = body.get("worker_id", "unknown")
        messages = body.get("messages", [])

        if render_app and messages:
            for msg in messages[:50]:  # Cap at 50 per batch
                render_app.log(f"[{worker_id}] {msg}")

        return JSONResponse({"ok": True, "received": len(messages)})

    # ====================================================================
    # Background Task: Stale Worker Cleanup
    # ====================================================================

    async def _stale_worker_cleanup():
        """Periodically release jobs from stale workers."""
        while True:
            await asyncio.sleep(60)
            try:
                released = db.release_stale_claims(WORKER_STALE_TIMEOUT)
                if released > 0:
                    print(f"[Wain] Released {released} job(s) from stale workers")
            except Exception as e:
                print(f"[Wain] Stale cleanup error: {e}")

    @nicegui_app.on_event("startup")
    async def _start_cleanup_task():
        asyncio.create_task(_stale_worker_cleanup())

    print("[Wain] REST API routes registered")
