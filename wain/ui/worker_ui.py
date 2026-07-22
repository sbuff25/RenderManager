"""
Wain Worker Dashboard (v2.24.0)
===============================

Compact status window for worker mode - replaces staring at a terminal.
Pure display layer over WorkerClient state: a 1-second timer reads the
client's connection state, current job, stats, and log tail. The client
keeps running in its background thread; the only controls are drain mode,
cancel-current-job, and quit.

https://github.com/sbuff25/RenderManager
"""

import time

from nicegui import ui, app

from wain.config import APP_VERSION, ENGINE_COLORS

CONN_STYLES = {
    "connected":    ("CONNECTED",    "#22c55e"),
    "connecting":   ("CONNECTING",   "#f59e0b"),
    "reconnecting": ("RECONNECTING", "#f59e0b"),
    "disconnected": ("DISCONNECTED", "#ef4444"),
}

CARD_BG = "background-color: #1c1c1f; border: 1px solid #27272a; border-radius: 8px;"


def _fmt_uptime(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def build_worker_ui(client):
    """Build the dashboard page bound to a WorkerClient instance."""
    els = {}
    state = {"log_len": 0}

    with ui.column().classes("w-full p-4 gap-3"):
        # ---- Header ----------------------------------------------------
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-2"):
                ui.label("Wain Worker").classes("text-lg font-bold")
                ui.label(f"v{APP_VERSION}").classes(
                    "text-xs px-2 py-0.5 rounded").style(
                    "background-color: #27272a; color: #a1a1aa;")
            els["conn"] = ui.label("...").classes(
                "text-xs px-2 py-1 rounded font-bold").style(
                "background-color: #27272a; color: #a1a1aa;")

        # ---- Identity --------------------------------------------------
        with ui.column().classes("w-full gap-0"):
            ui.label(f"Server: {client.server_url}").classes("text-xs text-zinc-500")
            ui.label(f"Worker: {client.worker_id} ({client.ip_address})").classes("text-xs text-zinc-500")
            ui.label(f"Engines: {', '.join(client.supported_engines)}").classes("text-xs text-zinc-500")

        # ---- Current job -----------------------------------------------
        with ui.column().classes("w-full p-3 gap-1").style(CARD_BG):
            with ui.row().classes("w-full items-center justify-between"):
                els["job_name"] = ui.label("Idle - waiting for jobs").classes("text-sm font-bold")
                els["job_engine"] = ui.label("").classes("text-xs font-bold")
            els["job_bar"] = ui.linear_progress(value=0.0, show_value=False).classes("w-full")
            with ui.row().classes("w-full items-center justify-between"):
                els["job_frames"] = ui.label("").classes("text-xs text-zinc-400")
                els["job_elapsed"] = ui.label("").classes("text-xs text-zinc-400")
            els["job_status"] = ui.label("").classes("text-xs text-zinc-500")

        # ---- Session stats ----------------------------------------------
        with ui.row().classes("w-full items-center justify-between"):
            els["stat_completed"] = ui.label("Completed: 0").classes("text-xs text-zinc-400")
            els["stat_failed"] = ui.label("Failed: 0").classes("text-xs text-zinc-400")
            els["stat_uptime"] = ui.label("Uptime: 0:00:00").classes("text-xs text-zinc-400")

        # ---- Controls ---------------------------------------------------
        with ui.row().classes("w-full items-center gap-2"):
            ui.switch("Drain mode",
                      on_change=lambda e: setattr(client, "drain_mode", bool(e.value))) \
                .props("dense size=sm") \
                .tooltip("Finish the current job but claim nothing new - "
                         "flip this on before shutting the machine down.")
            ui.element("div").classes("flex-grow")
            ui.button("Cancel job", on_click=client.cancel_current) \
                .props("flat dense color=red-5") \
                .tooltip("Gracefully stop the current render (reports it as paused)")

            def _quit():
                client.running = False
                app.shutdown()

            ui.button("Quit", on_click=_quit).props("flat dense color=grey-6")

        # ---- Log tail ---------------------------------------------------
        els["log"] = ui.log(max_lines=400).classes("w-full").style(
            "height: 230px; font-size: 11px; font-family: Consolas, monospace; "
            "background-color: #0c0c0e; border: 1px solid #27272a; border-radius: 8px;")

    # ---- 1s refresh -----------------------------------------------------
    def refresh():
        # Connection chip
        label, color = CONN_STYLES.get(client.connection_state,
                                       ("UNKNOWN", "#a1a1aa"))
        if client.drain_mode and client.connection_state == "connected":
            label, color = "DRAINING", "#06b6d4"
        els["conn"].set_text(label)
        els["conn"].style(f"background-color: {color}22; color: {color};")

        # Job card
        job = client._current_job
        if job is not None:
            accent = ENGINE_COLORS.get(job.engine_type, "#71717a")
            els["job_name"].set_text(job.name or job.id)
            els["job_engine"].set_text(job.engine_type.upper())
            els["job_engine"].style(f"color: {accent};")
            els["job_bar"].set_value(round((job.progress or 0) / 100.0, 2))
            if job.is_animation and job.frame_end > job.frame_start:
                els["job_frames"].set_text(
                    f"Frame {job.current_frame}/{job.frame_end}  ({job.progress}%)")
            else:
                els["job_frames"].set_text(f"{job.progress}%")
            start = getattr(client, "_render_start_time", None)
            els["job_elapsed"].set_text(
                _fmt_uptime(time.time() - start) if start else "")
            els["job_status"].set_text(job.status_message or "")
        else:
            els["job_name"].set_text(
                "Drain mode - not claiming jobs" if client.drain_mode
                else "Idle - waiting for jobs")
            els["job_engine"].set_text("")
            els["job_bar"].set_value(0.0)
            els["job_frames"].set_text("")
            els["job_elapsed"].set_text("")
            els["job_status"].set_text("")

        # Stats
        els["stat_completed"].set_text(f"Completed: {client.stats['completed']}")
        els["stat_failed"].set_text(f"Failed: {client.stats['failed']}")
        els["stat_uptime"].set_text(f"Uptime: {_fmt_uptime(time.time() - client.started_at)}")

        # Log tail (ring buffer may have been trimmed - resync if so)
        with client._log_lock:
            buf = list(client._ui_log)
        if len(buf) < state["log_len"]:
            state["log_len"] = 0
        for line in buf[state["log_len"]:]:
            els["log"].push(line)
        state["log_len"] = len(buf)

    ui.timer(1.0, refresh)
