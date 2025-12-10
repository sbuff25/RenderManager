"""
Wain UI Dialogs
===============

Modal dialogs for adding jobs and configuring settings.
"""

import os
import asyncio
import subprocess
import threading
from typing import Optional, Dict, Any

from nicegui import ui

from wain.config import ENGINE_COLORS, ENGINE_LOGOS, ASSET_VERSION
from wain.models import RenderJob
from wain.app import render_app
from wain.utils.file_dialogs import open_file_dialog_async, open_folder_dialog_async

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
        'submit_paused': False,
        'overwrite_existing': True,
        # Marmoset-specific
        'render_type': 'still',
        'renderer': 'Ray Tracing',
        'samples': 256,
        'shadow_quality': 'High',
        'use_transparency': False,
        'denoise_mode': 'gpu',
        'video_format': 'PNG Sequence',
        'turntable_frames': 120,
        'render_passes': ['beauty'],
    }
    
    camera_select = None
    res_w_input = None
    res_h_input = None
    frame_start_input = None
    frame_end_input = None
    anim_checkbox = None
    status_label = None
    output_input = None
    name_input = None
    engine_buttons = {}
    accent_elements = {}
    
    def select_engine(eng_type):
        form['engine_type'] = eng_type
        accent_color = ENGINE_COLORS.get(eng_type, "#3b82f6")
        
        for et, btn in engine_buttons.items():
            if et == eng_type:
                btn.classes(replace='px-3 py-2 rounded engine-btn-selected')
                btn.style(f'background-color: {ENGINE_COLORS.get(et, "#3b82f6")} !important; color: white !important;')
            else:
                btn.classes(replace='px-3 py-2 rounded engine-btn-unselected')
                btn.style('background-color: transparent !important; color: #52525b !important;')
        
        if 'submit_btn' in accent_elements:
            accent_elements['submit_btn'].style(f'background-color: {accent_color} !important;')
        
        if 'marmoset_settings' in accent_elements:
            accent_elements['marmoset_settings'].refresh()
    
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
                        engine_logo = ENGINE_LOGOS.get(engine.engine_type)
                        is_selected = engine.engine_type == form['engine_type']
                        eng_type = engine.engine_type
                        accent_color = ENGINE_COLORS.get(eng_type, "#3b82f6")
                        
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
                                ui.label(engine.name).classes('text-sm')
                        engine_buttons[engine.engine_type] = btn
            
            name_input = ui.input('Job Name', placeholder='Enter job name').classes('w-full')
            name_input.bind_value(form, 'name')
            
            ui.label('Scene File:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full gap-2 items-center'):
                file_input = ui.input(placeholder=r'C:\path\to\scene').classes('flex-grow')
                file_input.bind_value(form, 'file_path')
                
                def probe_scene(file_path: str):
                    """Probe scene file and update form with scene settings."""
                    detected = render_app.engine_registry.detect_engine_for_file(file_path)
                    if not detected:
                        status_label.set_text('Unknown file type')
                        return
                    
                    # Switch to detected engine
                    select_engine(detected.engine_type)
                    status_label.set_text('Probing scene...')
                    status_label.classes(replace='text-xs text-yellow-500')
                    
                    async def do_probe_async():
                        """Run probe in executor and update UI."""
                        loop = asyncio.get_event_loop()
                        
                        def blocking_probe():
                            print(f"[Wain] Starting probe for: {file_path}")
                            info = detected.get_scene_info(file_path)
                            print(f"[Wain] Probe returned: {info}")
                            return info
                        
                        try:
                            # Run blocking probe in thread pool
                            info = await loop.run_in_executor(None, blocking_probe)
                            
                            # Now we're back on the UI thread - safe to update UI
                            # Resolution
                            if info.get('resolution_x'):
                                res_w_input.value = info['resolution_x']
                                form['res_width'] = info['resolution_x']
                            if info.get('resolution_y'):
                                res_h_input.value = info['resolution_y']
                                form['res_height'] = info['resolution_y']
                            
                            # Cameras
                            cameras = info.get('cameras', ['Scene Default'])
                            if cameras:
                                camera_select.options = cameras
                                active_cam = info.get('active_camera', cameras[0])
                                if active_cam in cameras:
                                    camera_select.value = active_cam
                                    form['camera'] = active_cam
                                camera_select.update()
                            
                            # Frames
                            if info.get('frame_start'):
                                frame_start_input.value = info['frame_start']
                                form['frame_start'] = info['frame_start']
                            if info.get('frame_end'):
                                frame_end_input.value = info['frame_end']
                                form['frame_end'] = info['frame_end']
                            
                            # Samples
                            if info.get('samples'):
                                form['samples'] = info['samples']
                                # Refresh marmoset settings if visible
                                if 'marmoset_settings' in accent_elements:
                                    accent_elements['marmoset_settings'].refresh()
                            
                            # Marmoset-specific
                            if detected.engine_type == 'marmoset':
                                if info.get('has_turntable'):
                                    form['render_type'] = 'turntable'
                                if info.get('turntable_frames'):
                                    form['turntable_frames'] = info['turntable_frames']
                                    form['frame_end'] = info['turntable_frames']
                                    frame_end_input.value = info['turntable_frames']
                                if info.get('renderer'):
                                    form['renderer'] = info['renderer']
                                # Refresh marmoset settings section
                                if 'marmoset_settings' in accent_elements:
                                    accent_elements['marmoset_settings'].refresh()
                            
                            # Check if animation
                            has_anim = info.get('has_animation', False)
                            if not has_anim and info.get('frame_start') and info.get('frame_end'):
                                has_anim = info['frame_end'] > info['frame_start']
                            if has_anim:
                                anim_checkbox.value = True
                                form['is_animation'] = True
                            
                            # Status message
                            res_str = f"{info.get('resolution_x', '?')}x{info.get('resolution_y', '?')}"
                            samples_str = f"{info.get('samples', '?')} samples"
                            
                            # Check if we got real data or just defaults
                            if info.get('cameras') and len(info.get('cameras', [])) > 0:
                                status_label.set_text(f'Scene loaded: {res_str}, {samples_str}')
                                status_label.classes(replace='text-xs text-green-500')
                            else:
                                status_label.set_text(f'Using defaults: {res_str}, {samples_str}')
                                status_label.classes(replace='text-xs text-orange-500')
                                
                        except Exception as e:
                            print(f"[Wain] Probe error: {e}")
                            err_msg = str(e)[:50] if str(e) else 'Unknown error'
                            status_label.set_text(f'Probe failed: {err_msg}')
                            status_label.classes(replace='text-xs text-red-500')
                    
                    # Schedule the async probe
                    asyncio.create_task(do_probe_async())
                
                def browse_file():
                    def on_file_selected(result):
                        if result:
                            file_input.value = result
                            if not form['name']:
                                name_input.value = os.path.splitext(os.path.basename(result))[0]
                            if not form['output_folder']:
                                output_input.value = os.path.dirname(result)
                            # Probe scene for settings
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
            
            with ui.row().classes('w-full items-center gap-2'):
                res_w_input = ui.number('Width', value=1920, min=1).classes('w-24')
                res_w_input.bind_value(form, 'res_width')
                ui.label('x').classes('text-gray-400')
                res_h_input = ui.number('Height', value=1080, min=1).classes('w-24')
                res_h_input.bind_value(form, 'res_height')
            
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
            
            # Marmoset Settings Section
            @ui.refreshable
            def marmoset_settings():
                if form['engine_type'] == 'marmoset':
                    ui.separator()
                    ui.label('Marmoset Settings').classes('text-sm font-bold text-gray-400')
                    
                    with ui.row().classes('w-full items-center gap-2'):
                        render_type_select = ui.select(
                            options=['still', 'turntable', 'animation'],
                            value=form.get('render_type', 'still'),
                            label='Render Type',
                            on_change=lambda e: accent_elements.get('marmoset_settings') and accent_elements['marmoset_settings'].refresh()
                        ).classes('w-36')
                        render_type_select.bind_value(form, 'render_type')
                        
                        ui.select(options=['Ray Tracing', 'Hybrid', 'Raster'], value=form.get('renderer', 'Ray Tracing'), label='Renderer').bind_value(form, 'renderer').classes('w-32')
                    
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.number('Samples', value=form.get('samples', 256), min=1, max=4096).bind_value(form, 'samples').classes('w-24')
                        ui.select(options=['Low', 'High', 'Mega'], value=form.get('shadow_quality', 'High'), label='Shadows').bind_value(form, 'shadow_quality').classes('w-24')
                        ui.select(options=['off', 'cpu', 'gpu'], value=form.get('denoise_mode', 'gpu'), label='Denoise').bind_value(form, 'denoise_mode').classes('w-24')
                    
                    ui.checkbox('Transparent Background').props('dense').bind_value(form, 'use_transparency')
                    
                    # RENDER PASSES
                    ui.label('Render Passes').classes('text-sm text-gray-400 mt-2')
                    
                    marmoset_engine = render_app.engine_registry.get('marmoset')
                    all_passes = marmoset_engine.RENDER_PASSES if marmoset_engine else []
                    pass_options = {p['id']: p['name'] for p in all_passes}
                    
                    def on_passes_change(e):
                        if not e.value:
                            form['render_passes'] = ['beauty']
                        else:
                            form['render_passes'] = list(e.value)
                        # Refresh to update render count display
                        accent_elements.get('marmoset_settings') and accent_elements['marmoset_settings'].refresh()
                    
                    passes_select = ui.select(
                        options=pass_options,
                        value=form.get('render_passes', ['beauty']),
                        label='Select Passes',
                        multiple=True,
                        on_change=on_passes_change
                    ).classes('w-full').props('use-chips')
                    
                    # Calculate and show total render count
                    num_passes = len(form.get('render_passes', ['beauty']))
                    render_type = form.get('render_type', 'still')
                    
                    if render_type == 'still':
                        total_renders = num_passes
                        frames_text = "1 frame"
                    elif render_type == 'turntable':
                        frames = int(form.get('turntable_frames', 120))
                        total_renders = frames * num_passes
                        frames_text = f"{frames} frames"
                    else:  # animation
                        frames = int(form.get('frame_end', 250)) - int(form.get('frame_start', 1)) + 1
                        total_renders = frames * num_passes
                        frames_text = f"{frames} frames"
                    
                    ui.label(f'{num_passes} pass{"es" if num_passes != 1 else ""} × {frames_text} = {total_renders} total renders').classes('text-xs text-gray-500')
                    
                    if form.get('render_type') == 'turntable':
                        with ui.row().classes('w-full items-center gap-2 mt-1'):
                            turntable_input = ui.number('Turntable Frames', value=form.get('turntable_frames', 120), min=1).classes('w-36')
                            turntable_input.bind_value(form, 'turntable_frames')
                            turntable_input.on('change', lambda: accent_elements.get('marmoset_settings') and accent_elements['marmoset_settings'].refresh())
                            ui.select(options=['PNG Sequence', 'JPEG Sequence', 'TGA Sequence', 'MP4'], value=form.get('video_format', 'PNG Sequence'), label='Output Format').bind_value(form, 'video_format').classes('w-36')
            
            accent_elements['marmoset_settings'] = marmoset_settings
            marmoset_settings()
            
            ui.separator()
            with ui.row().classes('w-full gap-4'):
                ui.checkbox('Overwrite Existing', value=True).props('dense').bind_value(form, 'overwrite_existing').tooltip('Overwrite previously rendered files')
                ui.checkbox('Submit as Paused').props('dense').bind_value(form, 'submit_paused')
        
        with ui.row().classes('w-full justify-end gap-2 p-4 border-t border-zinc-700'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            
            def submit():
                if not form['file_path'] or not form['output_folder']:
                    print("Missing file path or output folder")
                    return
                
                if form['engine_type'] == 'marmoset':
                    engine_settings = {
                        "render_type": form.get('render_type', 'still'),
                        "renderer": form.get('renderer', 'Ray Tracing'),
                        "samples": int(form.get('samples', 256)),
                        "shadow_quality": form.get('shadow_quality', 'High'),
                        "use_transparency": form.get('use_transparency', False),
                        "denoise_mode": form.get('denoise_mode', 'gpu'),
                        "denoise_quality": "high",
                        "denoise_strength": 1.0,
                        "video_format": form.get('video_format', 'PNG Sequence'),
                        "turntable_frames": int(form.get('turntable_frames', 120)),
                        "turntable_clockwise": True,
                        "render_passes": form.get('render_passes', ['beauty']),
                    }
                    
                    is_anim = form['is_animation']
                    frame_start = int(form['frame_start'])
                    frame_end = int(form['frame_end'])
                    
                    if form.get('render_type') == 'turntable':
                        is_anim = True
                        frame_end = int(form.get('turntable_frames', 120))
                        frame_start = 1
                    elif form.get('render_type') == 'animation':
                        is_anim = True
                else:
                    engine_settings = {"use_scene_settings": True, "samples": 128}
                    is_anim = form['is_animation']
                    frame_start = int(form['frame_start'])
                    frame_end = int(form['frame_end'])
                
                job = RenderJob(
                    name=form['name'] or "Untitled",
                    engine_type=form['engine_type'],
                    file_path=form['file_path'],
                    output_folder=form['output_folder'],
                    output_name=form['output_name'],
                    output_format=form['output_format'],
                    camera=form['camera'],
                    is_animation=is_anim,
                    frame_start=frame_start,
                    frame_end=frame_end,
                    original_start=frame_start,
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
    
    accent_color = ENGINE_COLORS.get(job.engine_type, "#3b82f6")
    
    # Pre-populate form from job
    form = {
        'engine_type': job.engine_type,
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
        # Marmoset-specific from engine_settings
        'render_type': job.get_setting('render_type', 'still'),
        'renderer': job.get_setting('renderer', 'Ray Tracing'),
        'samples': job.get_setting('samples', 256),
        'shadow_quality': job.get_setting('shadow_quality', 'High'),
        'use_transparency': job.get_setting('use_transparency', False),
        'denoise_mode': job.get_setting('denoise_mode', 'gpu'),
        'video_format': job.get_setting('video_format', 'PNG Sequence'),
        'turntable_frames': job.get_setting('turntable_frames', 120),
        'render_passes': job.get_setting('render_passes', ['beauty']),
    }
    
    accent_elements = {}
    
    with ui.dialog() as dialog, ui.card().style('width: 600px; max-width: 95vw; padding: 0;').classes('accent-dialog'):
        with ui.row().classes('w-full items-center justify-between p-4'):
            ui.label('Edit Job').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm')
        
        with ui.column().classes('w-full p-4 gap-3').style('max-height: 70vh; overflow-y: auto;'):
            # Engine display (read-only)
            with ui.row().classes('w-full items-center gap-2'):
                ui.label('Engine:').classes('text-gray-400 w-20')
                engine_logo = ENGINE_LOGOS.get(job.engine_type)
                with ui.row().classes('items-center gap-2 px-3 py-2 rounded').style(f'background-color: {accent_color}; color: white;'):
                    if engine_logo:
                        ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-5 h-5 object-contain')
                    engine = render_app.engine_registry.get(job.engine_type)
                    ui.label(engine.name if engine else job.engine_type).classes('text-sm')
            
            name_input = ui.input('Job Name', value=form['name']).classes('w-full')
            name_input.bind_value(form, 'name')
            
            ui.label('Scene File:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full gap-2 items-center'):
                file_input = ui.input(value=form['file_path']).classes('flex-grow')
                file_input.bind_value(form, 'file_path')
                
                def browse_file():
                    def on_file_selected(result):
                        if result:
                            file_input.value = result
                    engine = render_app.engine_registry.get(job.engine_type)
                    filters = engine.get_file_dialog_filter() if engine else [("All Files", "*.*")]
                    open_file_dialog_async("Select Scene File", filters, None, on_file_selected)
                
                ui.button('Browse', icon='folder_open', on_click=browse_file).props('flat dense')
            
            ui.label('Output Folder:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full gap-2 items-center'):
                output_input = ui.input(value=form['output_folder']).classes('flex-grow')
                output_input.bind_value(form, 'output_folder')
                
                def browse_output():
                    def on_folder_selected(result):
                        if result:
                            output_input.value = result
                    open_folder_dialog_async("Select Output Folder", None, on_folder_selected)
                
                ui.button('Browse', icon='folder_open', on_click=browse_output).props('flat dense')
            
            with ui.row().classes('w-full gap-2'):
                ui.input('Prefix', value=form['output_name']).bind_value(form, 'output_name').classes('flex-grow')
                ui.select(['PNG', 'JPEG', 'OpenEXR', 'TIFF'], value=form['output_format'], label='Format').bind_value(form, 'output_format').classes('w-28')
            
            with ui.row().classes('w-full items-center gap-2'):
                res_w_input = ui.number('Width', value=form['res_width'], min=1).classes('w-24')
                res_w_input.bind_value(form, 'res_width')
                ui.label('x').classes('text-gray-400')
                res_h_input = ui.number('Height', value=form['res_height'], min=1).classes('w-24')
                res_h_input.bind_value(form, 'res_height')
            
            camera_select = ui.select([form['camera']], value=form['camera'], label='Camera').classes('w-full')
            camera_select.bind_value(form, 'camera')
            
            with ui.row().classes('w-full items-center gap-3'):
                anim_checkbox = ui.checkbox('Animation', value=form['is_animation']).props('dense')
                anim_checkbox.bind_value(form, 'is_animation')
                frame_start_input = ui.number('Start', value=form['frame_start'], min=1).classes('w-20')
                frame_start_input.bind_value(form, 'frame_start')
                ui.label('to').classes('text-gray-400')
                frame_end_input = ui.number('End', value=form['frame_end'], min=1).classes('w-20')
                frame_end_input.bind_value(form, 'frame_end')
            
            # Marmoset Settings Section
            @ui.refreshable
            def marmoset_settings():
                if form['engine_type'] == 'marmoset':
                    ui.separator()
                    ui.label('Marmoset Settings').classes('text-sm font-bold text-gray-400')
                    
                    with ui.row().classes('w-full items-center gap-2'):
                        render_type_select = ui.select(
                            options=['still', 'turntable', 'animation'],
                            value=form.get('render_type', 'still'),
                            label='Render Type',
                            on_change=lambda e: accent_elements.get('marmoset_settings') and accent_elements['marmoset_settings'].refresh()
                        ).classes('w-36')
                        render_type_select.bind_value(form, 'render_type')
                        
                        ui.select(options=['Ray Tracing', 'Hybrid', 'Raster'], value=form.get('renderer', 'Ray Tracing'), label='Renderer').bind_value(form, 'renderer').classes('w-32')
                    
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.number('Samples', value=form.get('samples', 256), min=1, max=4096).bind_value(form, 'samples').classes('w-24')
                        ui.select(options=['Low', 'High', 'Mega'], value=form.get('shadow_quality', 'High'), label='Shadows').bind_value(form, 'shadow_quality').classes('w-24')
                        ui.select(options=['off', 'cpu', 'gpu'], value=form.get('denoise_mode', 'gpu'), label='Denoise').bind_value(form, 'denoise_mode').classes('w-24')
                    
                    ui.checkbox('Transparent Background', value=form.get('use_transparency', False)).props('dense').bind_value(form, 'use_transparency')
                    
                    # Render passes
                    ui.label('Render Passes').classes('text-sm text-gray-400 mt-2')
                    
                    marmoset_engine = render_app.engine_registry.get('marmoset')
                    all_passes = marmoset_engine.RENDER_PASSES if marmoset_engine else []
                    pass_options = {p['id']: p['name'] for p in all_passes}
                    
                    def on_passes_change(e):
                        if not e.value:
                            form['render_passes'] = ['beauty']
                        else:
                            form['render_passes'] = list(e.value)
                        accent_elements.get('marmoset_settings') and accent_elements['marmoset_settings'].refresh()
                    
                    ui.select(
                        options=pass_options,
                        value=form.get('render_passes', ['beauty']),
                        label='Select Passes',
                        multiple=True,
                        on_change=on_passes_change
                    ).classes('w-full').props('use-chips')
                    
                    # Calculate total render count
                    num_passes = len(form.get('render_passes', ['beauty']))
                    render_type = form.get('render_type', 'still')
                    
                    if render_type == 'still':
                        total_renders = num_passes
                        frames_text = "1 frame"
                    elif render_type == 'turntable':
                        frames = int(form.get('turntable_frames', 120))
                        total_renders = frames * num_passes
                        frames_text = f"{frames} frames"
                    else:
                        frames = int(form.get('frame_end', 250)) - int(form.get('frame_start', 1)) + 1
                        total_renders = frames * num_passes
                        frames_text = f"{frames} frames"
                    
                    ui.label(f'{num_passes} pass{"es" if num_passes != 1 else ""} × {frames_text} = {total_renders} total renders').classes('text-xs text-gray-500')
                    
                    if form.get('render_type') == 'turntable':
                        with ui.row().classes('w-full items-center gap-2 mt-1'):
                            turntable_input = ui.number('Turntable Frames', value=form.get('turntable_frames', 120), min=1).classes('w-36')
                            turntable_input.bind_value(form, 'turntable_frames')
                            turntable_input.on('change', lambda: accent_elements.get('marmoset_settings') and accent_elements['marmoset_settings'].refresh())
                            ui.select(options=['PNG Sequence', 'JPEG Sequence', 'TGA Sequence', 'MP4'], value=form.get('video_format', 'PNG Sequence'), label='Output Format').bind_value(form, 'video_format').classes('w-36')
            
            accent_elements['marmoset_settings'] = marmoset_settings
            marmoset_settings()
            
            # Options
            ui.separator()
            ui.checkbox('Overwrite Existing', value=form.get('overwrite_existing', True)).props('dense').bind_value(form, 'overwrite_existing').tooltip('Overwrite previously rendered files')
            
            # Status info
            ui.separator()
            status_text = f"Status: {job.status.upper()}"
            if job.progress > 0:
                status_text += f" ({job.progress}%)"
            if job.elapsed_time:
                status_text += f" | Time: {job.elapsed_time}"
            ui.label(status_text).classes('text-sm text-gray-500')
        
        with ui.row().classes('w-full justify-end gap-2 p-4 border-t border-zinc-700'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            
            def apply_form_to_job(target_job):
                """Apply form values to job object."""
                target_job.name = form['name'] or "Untitled"
                target_job.file_path = form['file_path']
                target_job.output_folder = form['output_folder']
                target_job.output_name = form['output_name']
                target_job.output_format = form['output_format']
                target_job.camera = form['camera']
                target_job.res_width = int(form['res_width'])
                target_job.res_height = int(form['res_height'])
                target_job.overwrite_existing = form.get('overwrite_existing', True)
                
                if form['engine_type'] == 'marmoset':
                    target_job.engine_settings = {
                        "render_type": form.get('render_type', 'still'),
                        "renderer": form.get('renderer', 'Ray Tracing'),
                        "samples": int(form.get('samples', 256)),
                        "shadow_quality": form.get('shadow_quality', 'High'),
                        "use_transparency": form.get('use_transparency', False),
                        "denoise_mode": form.get('denoise_mode', 'gpu'),
                        "denoise_quality": "high",
                        "denoise_strength": 1.0,
                        "video_format": form.get('video_format', 'PNG Sequence'),
                        "turntable_frames": int(form.get('turntable_frames', 120)),
                        "turntable_clockwise": True,
                        "render_passes": form.get('render_passes', ['beauty']),
                    }
                    
                    target_job.is_animation = form['is_animation']
                    target_job.frame_start = int(form['frame_start'])
                    target_job.frame_end = int(form['frame_end'])
                    
                    if form.get('render_type') == 'turntable':
                        target_job.is_animation = True
                        target_job.frame_end = int(form.get('turntable_frames', 120))
                        target_job.frame_start = 1
                    elif form.get('render_type') == 'animation':
                        target_job.is_animation = True
                else:
                    target_job.is_animation = form['is_animation']
                    target_job.frame_start = int(form['frame_start'])
                    target_job.frame_end = int(form['frame_end'])
                
                target_job.original_start = target_job.frame_start
            
            def save_changes():
                """Save changes without changing status."""
                apply_form_to_job(job)
                render_app.save_config()
                render_app.log(f"Updated: {job.name}")
                if render_app.queue_container:
                    render_app.queue_container.refresh()
                dialog.close()
            
            def resubmit():
                """Save changes and resubmit job."""
                apply_form_to_job(job)
                # Reset progress
                job.status = 'queued'
                job.progress = 0
                job.current_frame = 0
                job.rendering_frame = 0
                job.error_message = ""
                job.accumulated_seconds = 0
                job.elapsed_time = ""
                job.current_sample = 0
                job.total_samples = 0
                job.current_pass = ""
                job.current_pass_num = 0
                job.pass_frame = 0
                render_app.save_config()
                render_app.log(f"Resubmitted: {job.name}")
                if render_app.queue_container:
                    render_app.queue_container.refresh()
                if render_app.stats_container:
                    render_app.stats_container.refresh()
                dialog.close()
            
            # Show different buttons based on status
            if job.status in ['completed', 'failed']:
                ui.button('Resubmit', icon='refresh', on_click=resubmit).style(f'background-color: {accent_color} !important;')
            elif job.status in ['queued', 'paused']:
                ui.button('Save', on_click=save_changes).props('flat').classes('text-zinc-300')
                ui.button('Save & Queue', icon='play_arrow', on_click=resubmit).style(f'background-color: {accent_color} !important;')
            else:
                # Rendering - shouldn't be editable but show save anyway
                ui.button('Save', on_click=save_changes).style(f'background-color: {accent_color} !important;')
    
    dialog.open()


async def show_settings_dialog():
    with ui.dialog() as dialog, ui.card().style('width: 550px; max-width: 95vw; padding: 0;').classes('settings-dialog'):
        with ui.row().classes('w-full items-center justify-between p-4 border-b border-zinc-700'):
            ui.label('Settings').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm').classes('text-zinc-400')
        
        with ui.column().classes('w-full p-4 gap-4'):
            for engine in render_app.engine_registry.get_all():
                engine_logo = ENGINE_LOGOS.get(engine.engine_type)
                engine_color = ENGINE_COLORS.get(engine.engine_type, "#3f3f46")
                
                with ui.card().classes('w-full p-3'):
                    with ui.row().classes('items-center gap-2 mb-2'):
                        if engine_logo:
                            ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-6 h-6 object-contain')
                        ui.label(engine.name).classes('font-bold')
                        status = "[OK] Available" if engine.is_available else "[X] Not Found"
                        ui.label(status).classes('text-sm text-zinc-400' if engine.is_available else 'text-sm text-zinc-600')
                    
                    if engine.installed_versions:
                        for v, p in sorted(engine.installed_versions.items(), reverse=True):
                            with ui.row().classes('items-center gap-2 mb-1'):
                                ui.badge(v).style(f'background-color: {engine_color} !important; color: white !important;')
                                ui.label(p).classes('text-xs text-gray-500 truncate').style('max-width: 350px')
                    else:
                        ui.label('No installations detected').classes('text-sm text-gray-500')
        
        with ui.row().classes('w-full justify-end p-4 border-t border-zinc-700'):
            ui.button('Close', on_click=dialog.close).props('flat')
    
    dialog.open()
