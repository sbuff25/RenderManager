"""
Wane UI Dialogs
===============

Modal dialogs for adding jobs and configuring settings.
"""

import os
import threading
from typing import Optional, Dict, Any

from nicegui import ui

from wane.config import ENGINE_COLORS, ENGINE_LOGOS, ASSET_VERSION
from wane.models import RenderJob
from wane.app import render_app
from wane.utils.file_dialogs import open_file_dialog_async, open_folder_dialog_async

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
    
    ENGINE_ACCENT_COLORS = {"blender": "#ea7600", "marmoset": "#ef0343"}
    
    def select_engine(eng_type):
        form['engine_type'] = eng_type
        accent_color = ENGINE_ACCENT_COLORS.get(eng_type, "#3b82f6")
        
        for et, btn in engine_buttons.items():
            if et == eng_type:
                btn.classes(replace='px-3 py-2 rounded engine-btn-selected')
                btn.style(f'background-color: {ENGINE_ACCENT_COLORS.get(et, "#3b82f6")} !important; color: white !important;')
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
                        accent_color = ENGINE_ACCENT_COLORS.get(eng_type, "#3b82f6")
                        
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
                
                def browse_file():
                    def on_file_selected(result):
                        if result:
                            file_input.value = result
                            if not form['name']:
                                name_input.value = os.path.splitext(os.path.basename(result))[0]
                            detected = render_app.engine_registry.detect_engine_for_file(result)
                            if detected:
                                select_engine(detected.engine_type)
                            if not form['output_folder']:
                                output_input.value = os.path.dirname(result)
                    
                    filters = render_app.engine_registry.get_all_file_filters()
                    open_file_dialog_async("Select Scene File", filters, None, on_file_selected)
                
                ui.button('Browse', icon='folder_open', on_click=browse_file).props('flat dense')
            
            with ui.row().classes('w-full items-center gap-2'):
                status_label = ui.label('').classes('text-xs text-gray-500')
            
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
                    status='paused' if form['submit_paused'] else 'queued',
                    engine_settings=engine_settings,
                )
                
                render_app.add_job(job)
                dialog.close()
            
            initial_accent = ENGINE_ACCENT_COLORS.get(form['engine_type'], "#ea7600")
            submit_btn = ui.button('Submit Job', on_click=submit).classes('engine-accent').style(f'background-color: {initial_accent} !important;')
            accent_elements['submit_btn'] = submit_btn
    
    dialog.open()


async def show_settings_dialog():
    with ui.dialog() as dialog, ui.card().style('width: 550px; max-width: 95vw; padding: 0;').classes('settings-dialog'):
        with ui.row().classes('w-full items-center justify-between p-4 border-b border-zinc-700'):
            ui.label('Settings').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm').classes('text-zinc-400')
        
        with ui.column().classes('w-full p-4 gap-4'):
            for engine in render_app.engine_registry.get_all():
                engine_logo = ENGINE_LOGOS.get(engine.engine_type)
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
                                ui.badge(v)
                                ui.label(p).classes('text-xs text-gray-500 truncate').style('max-width: 350px')
                    else:
                        ui.label('No installations detected').classes('text-sm text-gray-500')
        
        with ui.row().classes('w-full justify-end p-4 border-t border-zinc-700'):
            ui.button('Close', on_click=dialog.close).props('flat')
    
    dialog.open()
