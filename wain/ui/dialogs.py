"""
Wain UI Dialogs
===============

Modal dialogs for adding jobs and configuring settings.
v2.10.0 - Added engine settings schema support
"""

import os
import asyncio
from typing import Optional, Dict, Any

from nicegui import ui

from wain.config import ENGINE_COLORS, AVAILABLE_LOGOS, ENGINE_ICONS, ASSET_VERSION, BLENDER_DENOISER_FROM_INTERNAL
from wain.models import RenderJob
from wain.app import render_app
from wain.utils.file_dialogs import open_file_dialog_async, open_folder_dialog_async


def _normalize_denoiser_value(value: str) -> str:
    """Normalize denoiser value to match dropdown options."""
    if value is None:
        return 'OpenImageDenoise'
    normalized = BLENDER_DENOISER_FROM_INTERNAL.get(value.upper(), None)
    if normalized:
        return normalized
    if value in ['OpenImageDenoise', 'OptiX']:
        return value
    return 'OpenImageDenoise'


async def show_add_job_dialog():
    """Add Job dialog with all fields visible."""
    
    form = {
        'engine_type': 'blender',
        'name': '',
        'file_path': '',
        'output_folder': '',
        'output_name': 'render_',
        'output_format': 'PNG',
        'camera': 'Scene Default',
        'is_animation': False,
        'frame_start': 1,
        'frame_end': 250,
        'res_width': 1920,
        'res_height': 1080,
        'base_res_width': 1920,
        'base_res_height': 1080,
        'submit_paused': False,
        'overwrite_existing': True,
        # Vantage-specific
        'vantage_samples': 256,
        'vantage_denoiser': 'nvidia',
        'vantage_quality': 'high',
        # Marmoset-specific
        'render_type': 'still',
        'samples': 256,
        'render_passes': ['beauty'],
        # Blender-specific
        'blender_denoiser': 'OptiX',
    }
    
    camera_select = None
    res_w_input = None
    res_h_input = None
    res_scale_container = None
    frame_start_input = None
    frame_end_input = None
    anim_checkbox = None
    status_label = None
    output_input = None
    name_input = None
    engine_buttons = {}
    accent_elements = {}
    
    def get_current_scale():
        if form['base_res_width'] > 0 and form['base_res_height'] > 0:
            return form['res_width'] / form['base_res_width']
        return 1.0
    
    def apply_scale(scale: float):
        new_w = max(1, int(form['base_res_width'] * scale))
        new_h = max(1, int(form['base_res_height'] * scale))
        form['res_width'] = new_w
        form['res_height'] = new_h
        if res_w_input:
            res_w_input.value = new_w
        if res_h_input:
            res_h_input.value = new_h
        if res_scale_container:
            res_scale_container.refresh()
    
    def select_engine(eng_type):
        form['engine_type'] = eng_type
        accent_color = ENGINE_COLORS.get(eng_type, "#71717a")
        
        for et, btn in engine_buttons.items():
            if et == eng_type:
                btn.classes(replace='px-3 py-2 rounded engine-btn-selected')
                btn.style(f'background-color: {ENGINE_COLORS.get(et, "#71717a")} !important; color: white !important;')
            else:
                btn.classes(replace='px-3 py-2 rounded engine-btn-unselected')
                btn.style('background-color: transparent !important; color: #52525b !important;')
        
        if 'submit_btn' in accent_elements:
            accent_elements['submit_btn'].style(f'background-color: {accent_color} !important;')
        
        if 'engine_settings' in accent_elements:
            accent_elements['engine_settings'].refresh()
    
    with ui.dialog() as dialog, ui.card().style('width: 600px; max-width: 95vw; padding: 0;').classes('accent-dialog'):
        with ui.row().classes('w-full items-center justify-between p-4'):
            ui.label('Add Render Job').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm')
        
        with ui.column().classes('w-full p-4 gap-3').style('max-height: 70vh; overflow-y: auto;'):
            # Engine selector
            with ui.row().classes('w-full items-center gap-2'):
                ui.label('Engine:').classes('text-gray-400 w-20')
                with ui.row().classes('gap-2'):
                    for engine in render_app.engine_registry.get_available():
                        engine_logo = AVAILABLE_LOGOS.get(engine.engine_type)
                        is_selected = engine.engine_type == form['engine_type']
                        eng_type = engine.engine_type
                        accent_color = ENGINE_COLORS.get(eng_type, "#71717a")
                        
                        if is_selected:
                            btn_class = 'px-3 py-2 rounded engine-btn-selected'
                            btn_style = f'background-color: {accent_color} !important; color: white !important;'
                        else:
                            btn_class = 'px-3 py-2 rounded engine-btn-unselected'
                            btn_style = 'background-color: transparent !important; color: #52525b !important;'
                        
                        with ui.button(on_click=lambda et=eng_type: select_engine(et)).props('flat dense').classes(btn_class).style(btn_style) as btn:
                            with ui.row().classes('items-center gap-2'):
                                if engine_logo:
                                    ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-5 h-5 object-contain')
                                else:
                                    engine_icon = ENGINE_ICONS.get(eng_type, 'help')
                                    ui.icon(engine_icon).classes('text-lg')
                                ui.label(engine.name).classes('text-sm')
                        engine_buttons[engine.engine_type] = btn
            
            name_input = ui.input('Job Name', placeholder='Enter job name').classes('w-full')
            name_input.bind_value(form, 'name')
            
            ui.label('Scene File:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full gap-2 items-center'):
                file_input = ui.input(placeholder=r'C:\path\to\scene').classes('flex-grow')
                file_input.bind_value(form, 'file_path')
                
                def probe_scene(file_path: str):
                    detected = render_app.engine_registry.detect_engine_for_file(file_path)
                    if not detected:
                        status_label.set_text('Unknown file type')
                        return
                    
                    select_engine(detected.engine_type)
                    status_label.set_text('Probing scene...')
                    status_label.classes(replace='text-xs text-yellow-500')
                    
                    async def do_probe_async():
                        loop = asyncio.get_event_loop()
                        info = await loop.run_in_executor(None, lambda: detected.get_scene_info(file_path))
                        
                        if info.get('resolution_x'):
                            res_w_input.value = info['resolution_x']
                            form['res_width'] = info['resolution_x']
                            form['base_res_width'] = info['resolution_x']
                        if info.get('resolution_y'):
                            res_h_input.value = info['resolution_y']
                            form['res_height'] = info['resolution_y']
                            form['base_res_height'] = info['resolution_y']
                        if res_scale_container:
                            res_scale_container.refresh()
                        
                        cameras = info.get('cameras', ['Scene Default'])
                        if cameras:
                            camera_select.options = cameras
                            active_cam = info.get('active_camera', cameras[0])
                            if active_cam in cameras:
                                camera_select.value = active_cam
                                form['camera'] = active_cam
                            camera_select.update()
                        
                        if info.get('frame_start'):
                            frame_start_input.value = info['frame_start']
                            form['frame_start'] = info['frame_start']
                        if info.get('frame_end'):
                            frame_end_input.value = info['frame_end']
                            form['frame_end'] = info['frame_end']
                        
                        has_anim = info.get('has_animation', False)
                        if not has_anim and info.get('frame_end', 1) > info.get('frame_start', 1):
                            has_anim = True
                        if has_anim:
                            anim_checkbox.value = True
                            form['is_animation'] = True
                        
                        res_str = f"{info.get('resolution_x', '?')}x{info.get('resolution_y', '?')}"
                        status_label.set_text(f'Scene loaded: {res_str}')
                        status_label.classes(replace='text-xs text-green-500')
                    
                    asyncio.create_task(do_probe_async())
                
                def browse_file():
                    def on_file_selected(result):
                        if result:
                            file_input.value = result
                            if not form['name']:
                                name_input.value = os.path.splitext(os.path.basename(result))[0]
                            if not form['output_folder']:
                                output_input.value = os.path.dirname(result)
                            probe_scene(result)
                    
                    filters = render_app.engine_registry.get_all_file_filters()
                    open_file_dialog_async("Select Scene File", filters, None, on_file_selected)
                
                ui.button('Browse', icon='folder_open', on_click=browse_file).props('flat dense')
            
            with ui.row().classes('w-full items-center gap-2'):
                status_label = ui.label('Select a scene file to load settings').classes('text-xs text-gray-500 flex-grow')
            
            ui.label('Output Folder:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full gap-2 items-center'):
                output_input = ui.input(placeholder=r'C:\path\to\output').classes('flex-grow')
                output_input.bind_value(form, 'output_folder')
                
                def browse_output():
                    def on_folder_selected(result):
                        if result:
                            output_input.value = result
                    open_folder_dialog_async("Select Output Folder", None, on_folder_selected)
                
                ui.button('Browse', icon='folder_open', on_click=browse_output).props('flat dense')
            
            with ui.row().classes('w-full gap-2'):
                ui.input('Prefix', value='render_').bind_value(form, 'output_name').classes('flex-grow')
                ui.select(['PNG', 'JPEG', 'OpenEXR', 'TIFF'], value='PNG', label='Format').bind_value(form, 'output_format').classes('w-28')
            
            # Resolution
            ui.label('Resolution:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full items-center gap-2'):
                res_w_input = ui.number('Width', value=1920, min=1).classes('w-24')
                res_w_input.bind_value(form, 'res_width')
                ui.label('x').classes('text-gray-400')
                res_h_input = ui.number('Height', value=1080, min=1).classes('w-24')
                res_h_input.bind_value(form, 'res_height')
            
            @ui.refreshable
            def resolution_scale_buttons():
                current_scale = get_current_scale()
                scales = [(0.25, '25%'), (0.5, '50%'), (1.0, '100%'), (1.5, '150%'), (2.0, '200%')]
                with ui.row().classes('w-full items-center gap-1 flex-wrap'):
                    ui.label('Scale:').classes('text-xs text-gray-500 mr-1')
                    for scale, label in scales:
                        is_active = abs(current_scale - scale) < 0.01
                        btn_style = 'background-color: #3f3f46 !important;' if is_active else 'background-color: transparent !important; color: #71717a !important;'
                        ui.button(label, on_click=lambda s=scale: apply_scale(s)).props('flat dense').classes('text-xs px-2 py-1').style(btn_style)
                    ui.label(f'{form["res_width"]}×{form["res_height"]}').classes('text-xs text-gray-500 ml-2')
            
            res_scale_container = resolution_scale_buttons
            resolution_scale_buttons()
            
            camera_select = ui.select(['Scene Default'], value='Scene Default', label='Camera').classes('w-full')
            camera_select.bind_value(form, 'camera')
            
            with ui.row().classes('w-full items-center gap-3'):
                anim_checkbox = ui.checkbox('Animation').props('dense')
                anim_checkbox.bind_value(form, 'is_animation')
                frame_start_input = ui.number('Start', value=1, min=1).classes('w-20')
                frame_start_input.bind_value(form, 'frame_start')
                ui.label('to').classes('text-gray-400')
                frame_end_input = ui.number('End', value=250, min=1).classes('w-20')
                frame_end_input.bind_value(form, 'frame_end')
            
            # Engine-specific settings section
            @ui.refreshable
            def engine_settings_section():
                if form['engine_type'] == 'vantage':
                    ui.separator()
                    ui.label('Vantage Settings').classes('text-sm font-bold text-gray-400')
                    
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.select(
                            options=[('high', 'High'), ('medium', 'Medium'), ('low', 'Low'), ('ultra', 'Ultra')],
                            value=form.get('vantage_quality', 'high'),
                            label='Quality'
                        ).bind_value(form, 'vantage_quality').classes('w-28')
                        
                        ui.number('Samples', value=form.get('vantage_samples', 256), min=1, max=65536).bind_value(form, 'vantage_samples').classes('w-28')
                        
                        ui.select(
                            options=[('nvidia', 'NVIDIA AI'), ('oidn', 'Intel OIDN'), ('off', 'Off')],
                            value=form.get('vantage_denoiser', 'nvidia'),
                            label='Denoiser'
                        ).bind_value(form, 'vantage_denoiser').classes('w-28')
                
                elif form['engine_type'] == 'marmoset':
                    ui.separator()
                    ui.label('Marmoset Settings').classes('text-sm font-bold text-gray-400')
                    
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.select(
                            options=['still', 'turntable', 'animation'],
                            value=form.get('render_type', 'still'),
                            label='Render Type'
                        ).bind_value(form, 'render_type').classes('w-32')
                        
                        ui.number('Samples', value=form.get('samples', 256), min=1, max=4096).bind_value(form, 'samples').classes('w-24')
            
            accent_elements['engine_settings'] = engine_settings_section
            engine_settings_section()
            
            ui.separator()
            with ui.row().classes('w-full gap-4'):
                ui.checkbox('Overwrite Existing', value=True).props('dense').bind_value(form, 'overwrite_existing')
                ui.checkbox('Submit as Paused').props('dense').bind_value(form, 'submit_paused')
        
        with ui.row().classes('w-full justify-end gap-2 p-4 border-t border-zinc-700'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            
            def submit():
                if not form['file_path'] or not form['output_folder']:
                    return
                
                engine_settings = {}
                if form['engine_type'] == 'vantage':
                    engine_settings = {
                        "quality_preset": form.get('vantage_quality', 'high'),
                        "samples": int(form.get('vantage_samples', 256)),
                        "denoiser": form.get('vantage_denoiser', 'nvidia'),
                    }
                elif form['engine_type'] == 'marmoset':
                    engine_settings = {
                        "render_type": form.get('render_type', 'still'),
                        "samples": int(form.get('samples', 256)),
                        "render_passes": form.get('render_passes', ['beauty']),
                    }
                else:
                    engine_settings = {
                        "blender_denoiser": form.get('blender_denoiser', 'OptiX'),
                    }
                
                job = RenderJob(
                    name=form['name'] or "Untitled",
                    engine_type=form['engine_type'],
                    file_path=form['file_path'],
                    output_folder=form['output_folder'],
                    output_name=form['output_name'],
                    output_format=form['output_format'],
                    camera=form['camera'],
                    is_animation=form['is_animation'],
                    frame_start=int(form['frame_start']),
                    frame_end=int(form['frame_end']),
                    original_start=int(form['frame_start']),
                    res_width=int(form['res_width']),
                    res_height=int(form['res_height']),
                    overwrite_existing=form.get('overwrite_existing', True),
                    status='paused' if form['submit_paused'] else 'queued',
                    engine_settings=engine_settings,
                )
                
                render_app.add_job(job)
                dialog.close()
            
            initial_accent = ENGINE_COLORS.get(form['engine_type'], "#ea7600")
            submit_btn = ui.button('Submit Job', on_click=submit).classes('engine-accent').style(f'background-color: {initial_accent} !important;')
            accent_elements['submit_btn'] = submit_btn
    
    dialog.open()


async def show_edit_job_dialog(job):
    """Edit an existing job's settings."""
    accent_color = ENGINE_COLORS.get(job.engine_type, "#71717a")
    
    form = {
        'name': job.name,
        'file_path': job.file_path,
        'output_folder': job.output_folder,
        'output_name': job.output_name,
        'output_format': job.output_format,
        'camera': job.camera,
        'is_animation': job.is_animation,
        'frame_start': job.frame_start,
        'frame_end': job.frame_end,
        'res_width': job.res_width,
        'res_height': job.res_height,
        'overwrite_existing': job.overwrite_existing,
    }
    
    with ui.dialog() as dialog, ui.card().style('width: 600px; max-width: 95vw; padding: 0;'):
        with ui.row().classes('w-full items-center justify-between p-4'):
            ui.label('Edit Job').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm')
        
        with ui.column().classes('w-full p-4 gap-3').style('max-height: 70vh; overflow-y: auto;'):
            # Engine display
            with ui.row().classes('w-full items-center gap-2'):
                ui.label('Engine:').classes('text-gray-400 w-20')
                engine_logo = AVAILABLE_LOGOS.get(job.engine_type)
                with ui.row().classes('items-center gap-2 px-3 py-2 rounded').style(f'background-color: {accent_color}; color: white;'):
                    if engine_logo:
                        ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-5 h-5 object-contain')
                    else:
                        ui.icon(ENGINE_ICONS.get(job.engine_type, 'help')).classes('text-lg')
                    engine = render_app.engine_registry.get(job.engine_type)
                    ui.label(engine.name if engine else job.engine_type).classes('text-sm')
            
            ui.input('Job Name', value=form['name']).bind_value(form, 'name').classes('w-full')
            
            ui.label('Scene File:').classes('text-sm text-gray-400')
            ui.input(value=form['file_path']).bind_value(form, 'file_path').classes('w-full')
            
            ui.label('Output Folder:').classes('text-sm text-gray-400')
            ui.input(value=form['output_folder']).bind_value(form, 'output_folder').classes('w-full')
            
            with ui.row().classes('w-full gap-2'):
                ui.input('Prefix', value=form['output_name']).bind_value(form, 'output_name').classes('flex-grow')
                ui.select(['PNG', 'JPEG', 'OpenEXR', 'TIFF'], value=form['output_format'], label='Format').bind_value(form, 'output_format').classes('w-28')
            
            with ui.row().classes('w-full items-center gap-2'):
                ui.number('Width', value=form['res_width'], min=1).bind_value(form, 'res_width').classes('w-24')
                ui.label('x').classes('text-gray-400')
                ui.number('Height', value=form['res_height'], min=1).bind_value(form, 'res_height').classes('w-24')
            
            with ui.row().classes('w-full items-center gap-3'):
                ui.checkbox('Animation', value=form['is_animation']).props('dense').bind_value(form, 'is_animation')
                ui.number('Start', value=form['frame_start'], min=1).bind_value(form, 'frame_start').classes('w-20')
                ui.label('to').classes('text-gray-400')
                ui.number('End', value=form['frame_end'], min=1).bind_value(form, 'frame_end').classes('w-20')
            
            ui.separator()
            ui.checkbox('Overwrite Existing', value=form['overwrite_existing']).props('dense').bind_value(form, 'overwrite_existing')
            
            # Status info
            ui.separator()
            status_text = f"Status: {job.status.upper()}"
            if job.progress > 0:
                status_text += f" ({job.progress}%)"
            ui.label(status_text).classes('text-sm text-gray-500')
        
        with ui.row().classes('w-full justify-end gap-2 p-4 border-t border-zinc-700'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            
            def save_changes():
                job.name = form['name'] or "Untitled"
                job.file_path = form['file_path']
                job.output_folder = form['output_folder']
                job.output_name = form['output_name']
                job.output_format = form['output_format']
                job.res_width = int(form['res_width'])
                job.res_height = int(form['res_height'])
                job.is_animation = form['is_animation']
                job.frame_start = int(form['frame_start'])
                job.frame_end = int(form['frame_end'])
                job.overwrite_existing = form['overwrite_existing']
                
                render_app.save_config()
                render_app.log(f"Updated: {job.name}")
                if render_app.queue_container:
                    render_app.queue_container.refresh()
                dialog.close()
            
            def resubmit():
                save_changes()
                job.status = 'queued'
                job.progress = 0
                job.current_frame = 0
                job.error_message = ""
                render_app.save_config()
                if render_app.queue_container:
                    render_app.queue_container.refresh()
                if render_app.stats_container:
                    render_app.stats_container.refresh()
            
            if job.status in ['completed', 'failed']:
                ui.button('Resubmit', icon='refresh', on_click=resubmit).style(f'background-color: {accent_color} !important;')
            else:
                ui.button('Save', on_click=save_changes).style(f'background-color: {accent_color} !important;')
    
    dialog.open()


async def show_settings_dialog():
    with ui.dialog() as dialog, ui.card().style('width: 550px; max-width: 95vw; padding: 0;'):
        with ui.row().classes('w-full items-center justify-between p-4 border-b border-zinc-700'):
            ui.label('Settings').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm').classes('text-zinc-400')
        
        with ui.column().classes('w-full p-4 gap-4'):
            for engine in render_app.engine_registry.get_all():
                engine_logo = AVAILABLE_LOGOS.get(engine.engine_type)
                engine_icon = ENGINE_ICONS.get(engine.engine_type, 'help')
                engine_color = ENGINE_COLORS.get(engine.engine_type, "#3f3f46")
                
                with ui.card().classes('w-full p-3'):
                    with ui.row().classes('items-center gap-2 mb-2'):
                        if engine_logo:
                            ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-6 h-6 object-contain')
                        else:
                            ui.icon(engine_icon).classes('text-xl').style(f'color: {engine_color}')
                        ui.label(engine.name).classes('font-bold')
                        status = "[OK] Available" if engine.is_available else "[X] Not Found"
                        ui.label(status).classes('text-sm text-zinc-400' if engine.is_available else 'text-sm text-zinc-600')
                    
                    if engine.installed_versions:
                        for v, p in sorted(engine.installed_versions.items(), reverse=True):
                            with ui.row().classes('items-center gap-2 mb-1'):
                                ui.badge(v).style(f'background-color: {engine_color} !important;')
                                ui.label(p).classes('text-xs text-gray-500 truncate').style('max-width: 350px')
                    else:
                        ui.label('No installations detected').classes('text-sm text-gray-500')
        
        with ui.row().classes('w-full justify-end p-4 border-t border-zinc-700'):
            ui.button('Close', on_click=dialog.close).props('flat')
    
    dialog.open()
