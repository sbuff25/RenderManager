"""
Wain UI Components
==================

Reusable UI components for the render queue.
"""

import os
import subprocess
import sys

from nicegui import ui

from wain.config import STATUS_CONFIG, ENGINE_COLORS, AVAILABLE_LOGOS, ENGINE_ICONS, ASSET_VERSION
from wain.app import render_app


# Status accent colors for stat card icon chips (v2.19.0)
STAT_CHIP_COLORS = {
    'blue': '#3b82f6',
    'yellow': '#eab308',
    'green': '#22c55e',
    'red': '#ef4444',
}

# Network monitor accent (v2.22.0) - cyan, distinct from status colors
NETWORK_CHIP_COLOR = '#06b6d4'


def create_stat_card(title: str, status: str, icon: str, color: str):
    count = sum(1 for j in render_app.jobs if j.status == status)
    chip_color = STAT_CHIP_COLORS.get(color, '#a1a1aa')
    with ui.row().classes('items-center gap-3'):
        with ui.element('div').classes('stat-icon-chip').style(f'background-color: {chip_color}1f;'):
            ui.icon(icon).classes('text-2xl').style(f'color: {chip_color};')
        with ui.column().classes('gap-0'):
            ui.label(title).classes('text-xs text-zinc-500')
            ui.label(str(count)).classes('text-2xl font-bold text-white')


def create_network_card():
    """Live network throughput card (v2.22.0).

    Shows the busiest adapter's up/down rate, session totals and an upload
    sparkline - built for watching project syncs to render nodes. Click the
    card to cycle adapters manually. Self-updating via its own 1s timer.
    """
    from wain.utils.netmon import NetMonitor, fmt_rate, fmt_bytes, PSUTIL_AVAILABLE

    mon = NetMonitor()

    with ui.card().classes('stat-card').style('cursor: pointer; min-width: 230px;') as card:
        if not PSUTIL_AVAILABLE:
            with ui.row().classes('items-center gap-3'):
                with ui.element('div').classes('stat-icon-chip').style(f'background-color: {NETWORK_CHIP_COLOR}1f;'):
                    ui.icon('swap_vert').classes('text-2xl').style(f'color: {NETWORK_CHIP_COLOR};')
                with ui.column().classes('gap-0'):
                    ui.label('Network').classes('text-xs text-zinc-500')
                    ui.label('pip install psutil').classes('text-xs text-zinc-400')
            return

        with ui.row().classes('items-center gap-3 w-full'):
            with ui.element('div').classes('stat-icon-chip').style(f'background-color: {NETWORK_CHIP_COLOR}1f;'):
                ui.icon('swap_vert').classes('text-2xl').style(f'color: {NETWORK_CHIP_COLOR};')
            with ui.column().classes('gap-0 flex-grow'):
                adapter_label = ui.label('Network').classes('text-xs text-zinc-500')
                with ui.row().classes('items-baseline gap-2'):
                    up_label = ui.label('0 KB/s').classes('text-lg font-bold text-white')
                    down_label = ui.label('').classes('text-xs text-zinc-500')
                total_label = ui.label('').classes('text-xs text-zinc-500')

        spark = ui.echart({
            'grid': {'left': 0, 'right': 0, 'top': 2, 'bottom': 0},
            'xAxis': {'type': 'category', 'show': False},
            'yAxis': {'type': 'value', 'show': False},
            'series': [{
                'type': 'line', 'data': [], 'showSymbol': False, 'smooth': True,
                'lineStyle': {'width': 1.5, 'color': NETWORK_CHIP_COLOR},
                'areaStyle': {'color': NETWORK_CHIP_COLOR, 'opacity': 0.15},
            }],
            'animation': False,
        }).classes('w-full').style('height: 30px;')

        def _tick():
            mon.sample()
            name = mon.selected or 'Network'
            # Keep adapter names short in the card
            adapter_label.set_text(name if len(name) <= 26 else name[:24] + '…')
            up_label.set_text('▲ ' + fmt_rate(mon.up_bps))
            down_label.set_text('▼ ' + fmt_rate(mon.down_bps))
            total_label.set_text(f'sent {fmt_bytes(mon.session_sent)} · recv {fmt_bytes(mon.session_recv)}')
            spark.options['series'][0]['data'] = [round(v / 1024, 1) for v in mon.up_history]
            spark.update()

        card.on('click', lambda: (mon.cycle(), _tick()))
        card.tooltip('Live network throughput - click to cycle adapters')
        ui.timer(1.0, _tick)


def open_folder(path: str):
    """Open a folder in the system file explorer."""
    if not path or not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            return
    
    try:
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])
    except Exception as e:
        print(f"[Wain] Could not open folder: {e}")


def create_job_card(job):
    from wain.ui.dialogs import show_edit_job_dialog
    
    config = STATUS_CONFIG.get(job.status, STATUS_CONFIG["queued"])
    engine = render_app.engine_registry.get(job.engine_type)
    engine_color = ENGINE_COLORS.get(job.engine_type, "#888")
    
    engine_logo = AVAILABLE_LOGOS.get(job.engine_type)
    engine_icon = ENGINE_ICONS.get(job.engine_type, "help")
    
    # v2.19.0 — engine accent bar on left edge
    # v2.25.2 — cards are drag-reorderable: drop a card onto another to place
    # it above that card. Order persists as claim priority (top = first).
    card = ui.card().classes('w-full job-card-draggable') \
        .style(f'border-left: 3px solid {engine_color};') \
        .props('draggable=true')
    card.on('dragstart', lambda j=job: setattr(render_app, '_drag_job_id', j.id))
    card.on('dragover.prevent', lambda: None)
    card.on('dragenter', lambda c=card: c.classes(add='job-card-drop-target'))
    card.on('dragleave', lambda c=card: c.classes(remove='job-card-drop-target'))
    card.on('drop', lambda j=job: render_app.reorder_job(
        getattr(render_app, '_drag_job_id', None), j.id))
    with card:
        with ui.row().classes('w-full items-center gap-3'):
            if engine_logo:
                ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-8 h-8 object-contain')
            else:
                ui.icon(engine_icon).classes('text-2xl').style(f'color: {engine_color}')
            with ui.column().classes('flex-grow gap-0'):
                ui.label(job.name or "Untitled").classes('font-semibold text-[15px]')
                ui.label(job.file_name).classes('text-xs text-zinc-500')
            
            # v2.19.0 — badges get a thin matching border + letter spacing
            _badge_classes = 'px-2.5 py-1 rounded-md text-xs font-bold'
            _badge_spacing = 'letter-spacing: 0.6px;'
            if job.is_distributed:
                with ui.element('div').classes(_badge_classes).style(
                        f'background-color: rgba(34,197,94,0.15); color: #22c55e; '
                        f'border: 1px solid rgba(34,197,94,0.25); {_badge_spacing}'):
                    ui.label(f'{job.chunk_count} CHUNKS')
            if job.status == "rendering":
                _ec = engine_color.lstrip('#')
                _r, _g, _b = int(_ec[0:2], 16), int(_ec[2:4], 16), int(_ec[4:6], 16)
                with ui.element('div').classes(_badge_classes).style(
                        f'background-color: rgba(255,255,255,0.1); color: {engine_color}; '
                        f'border: 1px solid rgba({_r},{_g},{_b},0.25); {_badge_spacing}'):
                    ui.label(job.status.upper())
            elif job.status == "paused":
                with ui.element('div').classes(_badge_classes).style(
                        f'background-color: rgba(161,161,170,0.15); color: #a1a1aa; '
                        f'border: 1px solid rgba(161,161,170,0.25); {_badge_spacing}'):
                    ui.label(job.status.upper())
            else:
                _text_400 = {'blue': '96,165,250', 'yellow': '250,204,21', 'orange': '251,146,60',
                             'green': '74,222,128', 'red': '248,113,113'}
                _rgb = _text_400.get(config["color"], '161,161,170')
                with ui.element('div').classes(
                        f'{_badge_classes} bg-{config["bg"]} text-{config["color"]}-400').style(
                        f'border: 1px solid rgba({_rgb},0.25); {_badge_spacing}'):
                    ui.label(job.status.upper())
            
            if job.status == "rendering":
                ui.button(icon='pause', on_click=lambda j=job: render_app.handle_action('pause', j)).props('flat round dense').classes(f'job-action-btn-engine job-action-btn-engine-{job.engine_type}')
            elif job.status in ["queued", "paused"]:
                ui.button(icon='play_arrow', on_click=lambda j=job: render_app.handle_action('start', j)).props('flat round dense').classes('job-action-btn text-zinc-400')
            elif job.status in ["failed", "completed"]:
                ui.button(icon='refresh', on_click=lambda j=job: render_app.handle_action('retry', j)).props('flat round dense').classes('job-action-btn text-zinc-400').tooltip('Resubmit')

            if job.status != "rendering":
                ui.button(icon='edit', on_click=lambda j=job: show_edit_job_dialog(j)).props('flat round dense').classes('job-action-btn text-zinc-400').tooltip('Edit')
            
            if job.output_folder:
                ui.button(icon='folder_open', on_click=lambda j=job: open_folder(j.output_folder)).props('flat round dense').classes('job-action-btn text-zinc-400').tooltip('Open Output Folder')
            
            if job.status == "rendering":
                ui.button(icon='delete', on_click=lambda j=job: render_app.handle_action('delete', j)).props('flat round dense').classes(f'job-action-btn-engine job-action-btn-engine-{job.engine_type}')
            else:
                ui.button(icon='delete', on_click=lambda j=job: render_app.handle_action('delete', j)).props('flat round dense').classes('job-action-btn-danger text-zinc-500')
        
        if job.progress > 0 or job.status in ["rendering", "paused", "completed", "failed"]:
            status_class = f'custom-progress-{job.status}'
            engine_class = f'custom-progress-engine-{job.engine_type}'
            progress_width = max(1, job.progress)
            
            ui.html(f'''
                <div class="custom-progress-container {status_class} {engine_class}">
                    <div class="custom-progress-track">
                        <div class="custom-progress-fill" id="progress-fill-{job.id}" data-target="{progress_width}" style="width: {progress_width}%;"></div>
                    </div>
                    <div class="custom-progress-label" id="progress-label-{job.id}">{job.progress}%</div>
                </div>
            ''', sanitize=False).classes('w-full mt-2')
        
        engine_name = engine.name if engine else job.engine_type
        info_parts = [engine_name, job.resolution_display]
        if job.assigned_to:
            info_parts.append(f"Worker: {job.assigned_to}")
        if job.elapsed_time:
            info_parts.append(f"Time: {job.elapsed_time}")
        
        progress_parts = []
        if job.total_passes > 1 and job.current_pass:
            progress_parts.append(f"{job.current_pass} ({job.current_pass_num}/{job.total_passes})")
        if job.is_animation:
            if job.display_frame > 0:
                progress_parts.append(f"Frame {job.display_frame}/{job.frame_end}")
        if job.samples_display:
            progress_parts.append(job.samples_display)
        
        render_progress = " | ".join(progress_parts)
        
        ui.html(f'''
            <div id="job-info-{job.id}" class="text-xs text-gray-500 mt-2">
                {" | ".join(info_parts)}<span id="job-render-progress-{job.id}">{(" | " + render_progress) if render_progress else ""}</span>
            </div>
        ''', sanitize=False)
        
        # Status message - shows current activity for rendering jobs, and
        # cancel/pause progress ("Stopping on X..." -> "Paused at frame N")
        if job.status_message and job.status in ["rendering", "queued", "paused"]:
            ui.html(f'''
                <div id="job-status-msg-{job.id}" class="job-status-message">
                    {job.status_message}
                </div>
            ''', sanitize=False)

        # Chunk detail panel for distributed jobs
        if job.is_distributed and render_app.network_mode and render_app.db:
            chunks = render_app._chunk_cache.get(job.id, [])
            if chunks:
                import socket
                server_hostname = socket.gethostname()
                done = sum(1 for c in chunks if c.status == "completed")
                chunk_colors = {
                    "completed": "#22c55e", "rendering": engine_color,
                    "claimed": "#eab308", "failed": "#ef4444",
                    "paused": "#a1a1aa", "queued": "#52525b",
                }
                # Split chunks into server vs worker groups
                server_chunks = [c for c in chunks if c.assigned_to and c.assigned_to.lower() == server_hostname.lower()]
                worker_chunks = [c for c in chunks if c.assigned_to and c.assigned_to.lower() != server_hostname.lower()]
                unassigned_chunks = [c for c in chunks if not c.assigned_to]

                def _render_chunk_row(c):
                    color = chunk_colors.get(c.status, "#52525b")
                    progress_text = f"{c.progress}%" if c.status in ("rendering", "claimed") else ""
                    with ui.row().classes('w-full items-center gap-2 py-0.5').style('min-height: 24px;'):
                        ui.label(f"{c.frame_start}-{c.frame_end}").classes('text-xs text-zinc-400').style('width: 60px;')
                        with ui.element('div').classes('px-1.5 py-0.5 rounded text-xs font-bold').style(f'background-color: {color}22; color: {color}; min-width: 70px; text-align: center;'):
                            ui.label(c.status.upper())
                        if progress_text:
                            ui.label(progress_text).classes('text-xs text-zinc-500')

                is_open = render_app._expansion_states.get(job.id, False)
                expansion = ui.expansion(f'Chunk Details ({done}/{len(chunks)} done)', value=is_open).classes('w-full mt-1').style('font-size: 0.75rem;')
                expansion.on_value_change(lambda e, jid=job.id: render_app._expansion_states.update({jid: e.value}))
                with expansion:
                    if server_chunks:
                        ui.label(f'Server ({server_hostname})').classes('text-xs font-bold text-zinc-300 mt-1')
                        for c in server_chunks:
                            _render_chunk_row(c)
                    if worker_chunks:
                        # Group by worker
                        workers = {}
                        for c in worker_chunks:
                            workers.setdefault(c.assigned_to, []).append(c)
                        for worker_name, wchunks in workers.items():
                            ui.label(f'Worker ({worker_name})').classes('text-xs font-bold text-zinc-300 mt-1')
                            for c in wchunks:
                                _render_chunk_row(c)
                    if unassigned_chunks:
                        ui.label('Queued').classes('text-xs font-bold text-zinc-500 mt-1')
                        for c in unassigned_chunks:
                            _render_chunk_row(c)
