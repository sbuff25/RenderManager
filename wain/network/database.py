"""
Wain Job Database
=================

SQLite database layer for network rendering mode.
Provides thread-safe job persistence and atomic job claiming.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from wain.models import RenderJob


class JobDatabase:
    """Thread-safe SQLite database for job and worker management."""

    def __init__(self, db_path: str = "wain_jobs.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self.initialize()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    def initialize(self):
        """Create tables if they don't exist, and reset worker state."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id                TEXT PRIMARY KEY,
                name              TEXT NOT NULL DEFAULT '',
                engine_type       TEXT NOT NULL DEFAULT 'blender',
                file_path         TEXT NOT NULL DEFAULT '',
                output_folder     TEXT NOT NULL DEFAULT '',
                output_name       TEXT NOT NULL DEFAULT 'render_',
                output_format     TEXT NOT NULL DEFAULT 'PNG',
                status            TEXT NOT NULL DEFAULT 'queued',
                progress          INTEGER NOT NULL DEFAULT 0,
                is_animation      INTEGER NOT NULL DEFAULT 0,
                frame_start       INTEGER NOT NULL DEFAULT 1,
                frame_end         INTEGER NOT NULL DEFAULT 250,
                current_frame     INTEGER NOT NULL DEFAULT 0,
                rendering_frame   INTEGER NOT NULL DEFAULT 0,
                original_start    INTEGER NOT NULL DEFAULT 0,
                res_width         INTEGER NOT NULL DEFAULT 1920,
                res_height        INTEGER NOT NULL DEFAULT 1080,
                camera            TEXT NOT NULL DEFAULT 'Scene Default',
                overwrite_existing INTEGER NOT NULL DEFAULT 1,
                engine_settings   TEXT NOT NULL DEFAULT '{}',
                start_time        TEXT DEFAULT NULL,
                end_time          TEXT DEFAULT NULL,
                elapsed_time      TEXT NOT NULL DEFAULT '',
                accumulated_seconds INTEGER NOT NULL DEFAULT 0,
                error_message     TEXT NOT NULL DEFAULT '',
                status_message    TEXT NOT NULL DEFAULT '',
                current_sample    INTEGER NOT NULL DEFAULT 0,
                total_samples     INTEGER NOT NULL DEFAULT 0,
                current_tile      INTEGER NOT NULL DEFAULT 0,
                total_tiles       INTEGER NOT NULL DEFAULT 1,
                current_pass      TEXT NOT NULL DEFAULT '',
                current_pass_num  INTEGER NOT NULL DEFAULT 0,
                total_passes      INTEGER NOT NULL DEFAULT 1,
                pass_frame        INTEGER NOT NULL DEFAULT 0,
                pass_total_frames INTEGER NOT NULL DEFAULT 0,
                assigned_to       TEXT DEFAULT NULL,
                claimed_at        TEXT DEFAULT NULL,
                target_worker     TEXT NOT NULL DEFAULT '',
                priority          INTEGER NOT NULL DEFAULT 0,
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS workers (
                worker_id         TEXT PRIMARY KEY,
                hostname          TEXT NOT NULL DEFAULT '',
                ip_address        TEXT NOT NULL DEFAULT '',
                status            TEXT NOT NULL DEFAULT 'idle',
                current_job_id    TEXT DEFAULT NULL,
                last_heartbeat    TEXT NOT NULL DEFAULT (datetime('now')),
                capabilities      TEXT NOT NULL DEFAULT '{}',
                registered_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status_priority
                ON jobs(status, priority DESC, created_at ASC);

            CREATE INDEX IF NOT EXISTS idx_workers_heartbeat
                ON workers(last_heartbeat);
        """)
        conn.commit()

        # On server startup, mark all workers as offline (they will
        # re-register via heartbeat when they reconnect).  Also release
        # any jobs that were being rendered — they'll be re-queued.
        self._reset_workers_on_startup(conn)

    def _reset_workers_on_startup(self, conn: sqlite3.Connection):
        """Mark all previously-known workers as offline and re-queue
        their in-flight jobs so nothing gets stuck after a server restart."""
        with self._lock:
            # Mark all workers offline but keep their records so the UI
            # can show "previously connected" workers.
            conn.execute("""
                UPDATE workers
                SET status = 'offline', current_job_id = NULL
            """)
            # Re-queue any jobs that were actively rendering or claimed
            cursor = conn.execute("""
                UPDATE jobs
                SET status = 'queued',
                    assigned_to = NULL,
                    claimed_at = NULL,
                    updated_at = datetime('now')
                WHERE status IN ('claimed', 'rendering')
                  AND assigned_to IS NOT NULL
            """)
            released = cursor.rowcount

            # Fail any jobs stuck in "preparing" (packing was interrupted)
            cursor2 = conn.execute("""
                UPDATE jobs
                SET status = 'failed',
                    error_message = 'Packing interrupted by server restart — please retry',
                    status_message = '',
                    updated_at = datetime('now')
                WHERE status = 'preparing'
            """)
            interrupted = cursor2.rowcount

            conn.commit()

        if released > 0:
            print(f"[Wain] Server restart: re-queued {released} in-flight job(s)")
        if interrupted > 0:
            print(f"[Wain] Server restart: failed {interrupted} job(s) stuck in preparing")

    # ========================================================================
    # Job CRUD
    # ========================================================================

    def add_job(self, job: RenderJob) -> RenderJob:
        """Insert a new job into the database."""
        now = datetime.utcnow().isoformat()
        if not job.created_at:
            job.created_at = now
        job.updated_at = now

        d = job.to_dict()
        # Serialize engine_settings to JSON string for storage
        d["engine_settings"] = json.dumps(d.get("engine_settings", {}))
        d["is_animation"] = int(d["is_animation"])
        d["overwrite_existing"] = int(d["overwrite_existing"])

        cols = ", ".join(d.keys())
        placeholders = ", ".join(f":{k}" for k in d.keys())

        conn = self._get_conn()
        with self._lock:
            conn.execute(f"INSERT INTO jobs ({cols}) VALUES ({placeholders})", d)
            conn.commit()
        return job

    def get_job(self, job_id: str) -> Optional[RenderJob]:
        """Get a single job by ID."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def get_jobs(self, status: Optional[str] = None,
                 engine_type: Optional[str] = None,
                 limit: int = 100) -> List[RenderJob]:
        """List jobs with optional filtering."""
        query = "SELECT * FROM jobs WHERE 1=1"
        params: List[Any] = []

        if status:
            statuses = [s.strip() for s in status.split(",")]
            placeholders = ",".join("?" * len(statuses))
            query += f" AND status IN ({placeholders})"
            params.extend(statuses)

        if engine_type:
            query += " AND engine_type = ?"
            params.append(engine_type)

        query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
        params.append(limit)

        conn = self._get_conn()
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_job(row) for row in rows]

    def get_all_jobs(self) -> List[RenderJob]:
        """Get all jobs ordered by creation time (newest first)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def update_job(self, job_id: str, **fields) -> bool:
        """Update specific fields of a job."""
        if not fields:
            return False

        fields["updated_at"] = datetime.utcnow().isoformat()

        # Serialize engine_settings if present
        if "engine_settings" in fields and isinstance(fields["engine_settings"], dict):
            fields["engine_settings"] = json.dumps(fields["engine_settings"])
        if "is_animation" in fields:
            fields["is_animation"] = int(fields["is_animation"])
        if "overwrite_existing" in fields:
            fields["overwrite_existing"] = int(fields["overwrite_existing"])

        set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values()) + [job_id]

        conn = self._get_conn()
        with self._lock:
            cursor = conn.execute(
                f"UPDATE jobs SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
        return cursor.rowcount > 0

    def delete_job(self, job_id: str) -> bool:
        """Delete a job from the database."""
        conn = self._get_conn()
        with self._lock:
            cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
        return cursor.rowcount > 0

    # ========================================================================
    # Job Claiming (Atomic)
    # ========================================================================

    def claim_next_job(self, worker_id: str,
                       supported_engines: List[str]) -> Optional[RenderJob]:
        """Atomically claim the next available queued job.

        Uses a single UPDATE with a subquery to prevent race conditions.
        Returns the claimed job, or None if no jobs available.
        """
        if not supported_engines:
            return None

        placeholders = ",".join("?" * len(supported_engines))
        now = datetime.utcnow().isoformat()

        conn = self._get_conn()
        with self._lock:
            # Find and claim in one atomic operation
            # Only claim jobs targeted to this worker or to "any" (empty string)
            cursor = conn.execute(f"""
                UPDATE jobs
                SET status = 'claimed',
                    assigned_to = ?,
                    claimed_at = ?,
                    updated_at = ?
                WHERE id = (
                    SELECT id FROM jobs
                    WHERE status = 'queued'
                      AND engine_type IN ({placeholders})
                      AND (target_worker = '' OR target_worker = ?)
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                )
                AND status = 'queued'
                RETURNING *
            """, [worker_id, now, now] + supported_engines + [worker_id])
            row = cursor.fetchone()
            conn.commit()

        if row is None:
            return None
        return self._row_to_job(row)

    def claim_job(self, job_id: str, worker_id: str) -> Optional[RenderJob]:
        """Atomically claim a specific job by ID."""
        now = datetime.utcnow().isoformat()

        conn = self._get_conn()
        with self._lock:
            cursor = conn.execute("""
                UPDATE jobs
                SET status = 'claimed',
                    assigned_to = ?,
                    claimed_at = ?,
                    updated_at = ?
                WHERE id = ?
                  AND status = 'queued'
                RETURNING *
            """, [worker_id, now, now, job_id])
            row = cursor.fetchone()
            conn.commit()

        if row is None:
            return None
        return self._row_to_job(row)

    def release_job(self, job_id: str) -> bool:
        """Release a claimed job back to queued status."""
        return self.update_job(
            job_id,
            status="queued",
            assigned_to=None,
            claimed_at=None,
        )

    # ========================================================================
    # Progress Reporting
    # ========================================================================

    def update_progress(self, job_id: str, worker_id: str,
                        **progress_fields) -> bool:
        """Update job progress. Validates that the worker owns the job."""
        conn = self._get_conn()
        # Verify ownership and current status
        row = conn.execute(
            "SELECT assigned_to, status FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None or row["assigned_to"] != worker_id:
            return False

        # Don't let worker overwrite a server-initiated status change
        # (e.g., worker sending "rendering" after server set "paused")
        db_status = row["status"]
        req_status = progress_fields.get("status")
        if req_status == "rendering" and db_status in ("paused", "failed", "queued"):
            progress_fields.pop("status", None)
            progress_fields.pop("status_message", None)

        if not progress_fields:
            return True

        return self.update_job(job_id, **progress_fields)

    def complete_job(self, job_id: str, worker_id: str) -> bool:
        """Mark a job as completed by its assigned worker."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT assigned_to FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None or row["assigned_to"] != worker_id:
            return False

        return self.update_job(
            job_id,
            status="completed",
            progress=100,
            end_time=datetime.utcnow().isoformat(),
        )

    def fail_job(self, job_id: str, worker_id: str,
                 error_message: str) -> bool:
        """Mark a job as failed by its assigned worker."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT assigned_to FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None or row["assigned_to"] != worker_id:
            return False

        return self.update_job(
            job_id,
            status="failed",
            error_message=error_message,
            end_time=datetime.utcnow().isoformat(),
        )

    # ========================================================================
    # Stale Claim Recovery
    # ========================================================================

    def release_stale_claims(self, stale_timeout_seconds: int = 120) -> int:
        """Release jobs claimed by workers that have gone stale.

        Returns count of released jobs.
        """
        cutoff = (
            datetime.utcnow() - timedelta(seconds=stale_timeout_seconds)
        ).isoformat()

        conn = self._get_conn()
        with self._lock:
            # Find workers that are stale
            stale_workers = conn.execute(
                "SELECT worker_id FROM workers WHERE last_heartbeat < ?",
                (cutoff,),
            ).fetchall()
            stale_ids = [w["worker_id"] for w in stale_workers]

            if not stale_ids:
                return 0

            placeholders = ",".join("?" * len(stale_ids))
            now = datetime.utcnow().isoformat()

            cursor = conn.execute(f"""
                UPDATE jobs
                SET status = 'queued',
                    assigned_to = NULL,
                    claimed_at = NULL,
                    updated_at = ?
                WHERE status IN ('claimed', 'rendering')
                  AND assigned_to IN ({placeholders})
            """, [now] + stale_ids)

            # Mark stale workers as offline
            conn.execute(f"""
                UPDATE workers
                SET status = 'offline', current_job_id = NULL
                WHERE worker_id IN ({placeholders})
            """, stale_ids)

            conn.commit()
        return cursor.rowcount

    # ========================================================================
    # Worker Management
    # ========================================================================

    def update_heartbeat(self, worker_id: str, hostname: str,
                         ip_address: str, status: str,
                         current_job_id: Optional[str],
                         capabilities: Dict[str, Any]) -> None:
        """Register or update a worker's heartbeat."""
        now = datetime.utcnow().isoformat()
        caps_json = json.dumps(capabilities)

        conn = self._get_conn()
        with self._lock:
            conn.execute("""
                INSERT INTO workers (worker_id, hostname, ip_address, status,
                                     current_job_id, last_heartbeat, capabilities)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    hostname = excluded.hostname,
                    ip_address = excluded.ip_address,
                    status = excluded.status,
                    current_job_id = excluded.current_job_id,
                    last_heartbeat = excluded.last_heartbeat,
                    capabilities = excluded.capabilities
            """, [worker_id, hostname, ip_address, status,
                  current_job_id, now, caps_json])
            conn.commit()

    def get_workers(self, stale_timeout_seconds: int = 120) -> List[Dict[str, Any]]:
        """List all workers with stale detection."""
        cutoff = (
            datetime.utcnow() - timedelta(seconds=stale_timeout_seconds)
        ).isoformat()

        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM workers ORDER BY registered_at ASC"
        ).fetchall()

        workers = []
        for row in rows:
            w = dict(row)
            w["is_stale"] = row["last_heartbeat"] < cutoff
            try:
                w["capabilities"] = json.loads(row["capabilities"])
            except (json.JSONDecodeError, TypeError):
                w["capabilities"] = {}
            workers.append(w)
        return workers

    # ========================================================================
    # Migration
    # ========================================================================

    def import_from_json(self, json_path: str) -> int:
        """Import jobs from wain_config.json. Returns count imported."""
        if not os.path.isfile(json_path):
            return 0

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return 0

        jobs_data = data.get("jobs", [])
        count = 0
        for jd in jobs_data:
            try:
                job = RenderJob.from_dict(jd)
                # Don't import rendering jobs — they can't resume
                if job.status == "rendering":
                    job.status = "paused"
                self.add_job(job)
                count += 1
            except Exception:
                continue
        return count

    # ========================================================================
    # Internal Helpers
    # ========================================================================

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> RenderJob:
        """Convert a database row to a RenderJob."""
        d = dict(row)
        # SQLite stores booleans as integers
        d["is_animation"] = bool(d.get("is_animation", 0))
        d["overwrite_existing"] = bool(d.get("overwrite_existing", 1))
        return RenderJob.from_dict(d)
