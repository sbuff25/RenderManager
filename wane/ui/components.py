"""
Wane UI Components
==================

Reusable UI components for the render queue.
"""

from nicegui import ui

from wane.config import STATUS_CONFIG, ENGINE_COLORS, ENGINE_LOGOS, ASSET_VERSION
from wane.app import render_app


def create_stat_card(title: str, status: str, icon: str, color: str):
    """
    Create a statistics card showing job count for a status.
    
    Args:
        title: Card title (e.g., "Rendering")
        status: Job status to count (e.g., "rendering")
        icon: Material icon name
        color: Tailwind color class (unused in current desaturated design)
    """
    count = sum(1 for j in render_app.jobs if j.status == status)
    with ui.row().classes('items-center gap-3'):
        # Use white/gray icons for desaturated 2-tone look
        ui.icon(icon).classes('text-3xl text-zinc-400')
        with ui.column().classes('gap-0'):
            ui.label(title).classes('text-sm text-gray-500')
            ui.label(str(count)).classes('text-2xl font-bold text-white')


def create_job_card(job):
    """
    Create a job card with status, progress, and action buttons.
    
    Args:
        job: RenderJob instance
    """
    config = STATUS_CONFIG.get(job.status, STATUS_CONFIG["queued"])
    engine = render_app.engine_registry.get(job.engine_type)
    engine_color = ENGINE_COLORS.get(job.engine_type, "#888")
    engine_logo = ENGINE_LOGOS.get(job.engine_type)
    
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center gap-3'):
            # Engine logo
            if engine_logo:
                ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-8 h-8 object-contain')
            else:
                ui.icon(engine.icon if engine else 'help').classes('text-2xl').style(f'color: {engine_color}')
            with ui.column().classes('flex-grow gap-0'):
                ui.label(job.name or "Untitled").classes('font-bold')
                ui.label(job.file_name).classes('text-sm text-gray-400')
            
            # Status badge - engine color when rendering, neutral when paused, standard otherwise
            if job.status == "rendering":
                # Use engine-specific color for rendering status
                with ui.element('div').classes(f'px-2 py-1 rounded text-xs font-bold status-badge status-badge-engine-{job.engine_type}').style(f'background-color: rgba(255,255,255,0.1); color: {engine_color};'):
                    ui.label(job.status.upper())
            elif job.status == "paused":
                # Neutral gray for paused
                with ui.element('div').classes('px-2 py-1 rounded text-xs font-bold status-badge').style('background-color: rgba(161,161,170,0.15); color: #a1a1aa;'):
                    ui.label(job.status.upper())
            else:
                # Standard colors for queued, completed, failed
                with ui.element('div').classes(f'px-2 py-1 rounded bg-{config["bg"]} text-{config["color"]}-400 text-xs font-bold status-badge'):
                    ui.label(job.status.upper())
            
            # Action buttons - engine themed when rendering, neutral otherwise
            if job.status == "rendering":
                ui.button(icon='pause', on_click=lambda j=job: render_app.handle_action('pause', j)).props('flat round dense').classes(f'job-action-btn-engine job-action-btn-engine-{job.engine_type}')
            elif job.status in ["queued", "paused"]:
                ui.button(icon='play_arrow', on_click=lambda j=job: render_app.handle_action('start', j)).props('flat round dense').classes('job-action-btn text-zinc-400')
            elif job.status == "failed":
                ui.button(icon='refresh', on_click=lambda j=job: render_app.handle_action('retry', j)).props('flat round dense').classes('job-action-btn text-zinc-400')
            
            # Delete button - engine themed when rendering, neutral otherwise
            if job.status == "rendering":
                ui.button(icon='delete', on_click=lambda j=job: render_app.handle_action('delete', j)).props('flat round dense').classes(f'job-action-btn-engine job-action-btn-engine-{job.engine_type}')
            else:
                ui.button(icon='delete', on_click=lambda j=job: render_app.handle_action('delete', j)).props('flat round dense').classes('job-action-btn-danger text-zinc-500')
        
        if job.progress > 0 or job.status in ["rendering", "paused", "completed", "failed"]:
            # Custom HTML progress bar - full control, no unwanted text
            status_class = f'custom-progress-{job.status}'
            engine_class = f'custom-progress-engine-{job.engine_type}'
            progress_width = max(1, job.progress)  # At least 1% width so it's visible
            
            # Set initial width inline AND data-target for JS animation
            # This prevents flash on refresh - bar starts at correct width
            ui.html(f'''
                <div class="custom-progress-container {status_class} {engine_class}">
                    <div class="custom-progress-track">
                        <div class="custom-progress-fill" 
                             id="progress-fill-{job.id}" 
                             data-target="{progress_width}"
                             style="width: {progress_width}%;"></div>
                    </div>
                    <div class="custom-progress-label" id="progress-label-{job.id}">{job.progress}%</div>
                </div>
            ''', sanitize=False).classes('w-full mt-2')
        
        engine_name = engine.name if engine else job.engine_type
        info_parts = [engine_name, job.resolution_display]
        if job.elapsed_time:
            info_parts.append(f"Time: {job.elapsed_time}")
        
        # Build render progress info (pass/frame/samples) - show when rendering OR paused with data
        progress_parts = []
        
        # Show pass info for multi-pass renders (Marmoset)
        if job.total_passes > 1 and job.current_pass:
            progress_parts.append(f"{job.current_pass} ({job.current_pass_num}/{job.total_passes})")
        
        # Show frame info - use pass_frame for per-pass display or display_frame for overall
        if job.is_animation:
            if job.total_passes > 1 and job.pass_frame > 0:
                # Multi-pass: show per-pass frame count
                progress_parts.append(f"Frame {job.pass_frame}/{job.pass_total_frames}")
            elif job.display_frame > 0:
                # Single pass: show overall frame count
                progress_parts.append(f"Frame {job.display_frame}/{job.frame_end}")
        
        if job.samples_display:
            progress_parts.append(f"Sample {job.samples_display}")
        render_progress = " | ".join(progress_parts)
        
        # Use HTML with ID so we can update via JS
        ui.html(f'''
            <div id="job-info-{job.id}" class="text-sm text-gray-500 mt-2">
                {" | ".join(info_parts)}<span id="job-render-progress-{job.id}">{(" | " + render_progress) if render_progress else ""}</span>
            </div>
        ''', sanitize=False)
