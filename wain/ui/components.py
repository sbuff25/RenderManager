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


def create_stat_card(title: str, status: str, icon: str, color: str):
    count = sum(1 for j in render_app.jobs if j.status == status)
    with ui.row().classes('items-center gap-3'):
        ui.icon(icon).classes('text-3xl text-zinc-400')
        with ui.column().classes('gap-0'):
            ui.label(title).classes('text-sm text-gray-500')
            ui.label(str(count)).classes('text-2xl font-bold text-white')


def open_folder(path: str):
    """Open a folder in the system file explorer."""
    if not path or not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
        except:
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
    
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center gap-3'):
            if engine_logo:
                ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-8 h-8 object-contain')
            else:
                ui.icon(engine_icon).classes('text-2xl').style(f'color: {engine_color}')
            with ui.column().classes('flex-grow gap-0'):
                ui.label(job.name or "Untitled").classes('font-bold')
                ui.label(job.file_name).classes('text-sm text-gray-400')
            
            if job.status == "rendering":
                with ui.element('div').classes('px-2 py-1 rounded text-xs font-bold').style(f'background-color: rgba(255,255,255,0.1); color: {engine_color};'):
                    ui.label(job.status.upper())
            elif job.status == "paused":
                with ui.element('div').classes('px-2 py-1 rounded text-xs font-bold').style('background-color: rgba(161,161,170,0.15); color: #a1a1aa;'):
                    ui.label(job.status.upper())
            else:
                with ui.element('div').classes(f'px-2 py-1 rounded bg-{config["bg"]} text-{config["color"]}-400 text-xs font-bold'):
                    ui.label(job.status.upper())
            
            if job.status == "rendering":
                ui.button(icon='pause', on_click=lambda j=job: render_app.handle_action('pause', j)).props('flat round dense').classes(f'job-action-btn-engine job-action-btn-engine-{job.engine_type}')
            elif job.status in ["queued", "paused"]:
                ui.button(icon='play_arrow', on_click=lambda j=job: render_app.handle_action('start', j)).props('flat round dense').classes('job-action-btn text-zinc-400')
            elif job.status == "failed":
                ui.button(icon='refresh', on_click=lambda j=job: render_app.handle_action('retry', j)).props('flat round dense').classes('job-action-btn text-zinc-400').tooltip('Retry')
            
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
            <div id="job-info-{job.id}" class="text-sm text-gray-500 mt-2">
                {" | ".join(info_parts)}<span id="job-render-progress-{job.id}">{(" | " + render_progress) if render_progress else ""}</span>
            </div>
        ''', sanitize=False)
        
        # Status message - shows current activity for rendering jobs
        if job.status_message and job.status in ["rendering", "queued"]:
            ui.html(f'''
                <div id="job-status-msg-{job.id}" class="job-status-message">
                    {job.status_message}
                </div>
            ''', sanitize=False)
