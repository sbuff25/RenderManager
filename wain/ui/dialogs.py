"""
Wain UI Dialogs
===============

Modal dialogs for adding jobs and configuring settings.
v2.15.65 - Simplified Vantage (just load and render)
"""

import os
import asyncio
from typing import Optional, Dict, Any

from nicegui import ui

from wain.config import ENGINE_COLORS, AVAILABLE_LOGOS, ENGINE_ICONS, ASSET_VERSION, BLENDER_DENOISER_FROM_INTERNAL
from wain.models import RenderJob
from wain.app import render_app
from wain.utils.file_dialogs import open_file_dialog_async, open_folder_dialog_async


def _accent_btn_style(color: str) -> str:
    """Accent button style with engine-colored glow (v2.19.0)."""
    c = color.lstrip('#')
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return (f'background-color: {color} !important; border-radius: 6px; '
            f'box-shadow: 0 2px 10px rgba({r},{g},{b},0.4);')


def _unreal_options(candidates, current) -> list:
    """Dropdown options for probed UE asset paths, keeping any manual value visible."""
    opts = list(candidates or [])
    if current and current not in opts:
        opts.insert(0, current)
    return opts


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
        'engine_type': 'blender', 'name': '', 'file_path': '', 'output_folder': '',
        'output_name': 'render_', 'output_format': 'PNG', 'camera': 'Scene Default',
        'is_animation': False, 'frame_start': 1, 'frame_end': 250,
        'res_width': 1920, 'res_height': 1080, 'base_res_width': 1920, 'base_res_height': 1080,
        'submit_paused': False, 'overwrite_existing': True,
        'distribute': False,  # Split animation across multiple workers
        'target_worker': '',  # "" = any, "local" = this machine, or worker_id
        # Marmoset-specific
        'render_type': 'still', 'samples': 256, 'render_passes': ['beauty'],
        # Blender-specific
        'blender_denoiser': 'OptiX',
        # Vantage-specific
        'vantage_use_custom': False,  # Toggle for custom settings
        'vantage_samples': 100,
        'vantage_denoiser': 'nvidia',  # nvidia, oidn, off
        # Unreal-specific (v2.21.0) - soft object paths for MRQ
        'unreal_map': '', 'unreal_sequence': '', 'unreal_preset': '',
        'unreal_extra_args': '', 'unreal_show_preview': True,
        'unreal_maps': [], 'unreal_sequences': [], 'unreal_presets': [],
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
    format_select = None
    engine_buttons = {}
    accent_elements = {}
    generic_section_ref = {'element': None}  # generic controls, hidden for Unreal

    ENGINE_FORMAT_OPTIONS = {
        'blender': ['PNG', 'JPEG', 'OpenEXR', 'TIFF'],
        'marmoset': ['PNG', 'JPEG', 'TGA', 'PSD', 'PSD (16-bit)', 'EXR (16-bit)', 'EXR (32-bit)'],
        'vantage': ['PNG', 'JPEG', 'OpenEXR', 'TIFF'],
        'unreal': ['Preset', 'EXR', 'PNG', 'JPEG'],  # MRQ preset governs actual output
    }
    
    def get_current_scale():
        if form['base_res_width'] > 0 and form['base_res_height'] > 0:
            return form['res_width'] / form['base_res_width']
        return 1.0
    
    def apply_scale(scale: float):
        nonlocal res_w_input, res_h_input, res_scale_container
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
        nonlocal format_select
        form['engine_type'] = eng_type
        accent_color = ENGINE_COLORS.get(eng_type, "#71717a")

        for et, btn in engine_buttons.items():
            if et == eng_type:
                btn.style(f'background-color: {ENGINE_COLORS.get(et, "#71717a")} !important; color: white !important;')
            else:
                btn.style('background-color: transparent !important; color: #52525b !important;')

        # Update format dropdown for this engine
        if format_select:
            new_formats = ENGINE_FORMAT_OPTIONS.get(eng_type, ['PNG', 'JPEG'])
            format_select.options = new_formats
            if form['output_format'] not in new_formats:
                form['output_format'] = new_formats[0]
                format_select.value = new_formats[0]
            format_select.update()

        # Unreal: the MRQ preset/sequence govern naming, format, resolution,
        # camera, and frame range - hide the generic controls entirely
        if generic_section_ref.get('element'):
            generic_section_ref['element'].set_visibility(eng_type != 'unreal')

        if 'submit_btn' in accent_elements:
            accent_elements['submit_btn'].style(_accent_btn_style(accent_color))
        if 'engine_settings' in accent_elements:
            accent_elements['engine_settings'].refresh()
    
    with ui.dialog().props('transition-show="jump-up" transition-hide="jump-down" transition-duration="150"') as dialog, ui.card().style('width: 600px; max-width: 95vw; padding: 0;'):
        with ui.row().classes('w-full items-center justify-between p-4'):
            ui.label('Add Render Job').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm')
        
        with ui.column().classes('w-full p-4 gap-3').style('max-height: 70vh; overflow-y: auto;'):
            with ui.row().classes('w-full items-center gap-2'):
                ui.label('Engine:').classes('text-gray-400 w-20')
                with ui.row().classes('gap-2'):
                    for engine in render_app.engine_registry.get_available():
                        engine_logo = AVAILABLE_LOGOS.get(engine.engine_type)
                        is_selected = engine.engine_type == form['engine_type']
                        eng_type = engine.engine_type
                        accent_color = ENGINE_COLORS.get(eng_type, "#71717a")
                        
                        if is_selected:
                            btn_style = f'background-color: {accent_color} !important; color: white !important;'
                        else:
                            btn_style = 'background-color: transparent !important; color: #52525b !important;'
                        
                        with ui.button(on_click=lambda et=eng_type: select_engine(et)).props('flat dense').style(btn_style) as btn:
                            with ui.row().classes('items-center gap-2'):
                                if engine_logo:
                                    ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-5 h-5 object-contain')
                                else:
                                    ui.icon(ENGINE_ICONS.get(eng_type, 'help')).classes('text-lg')
                                ui.label(engine.name).classes('text-sm')
                        engine_buttons[engine.engine_type] = btn
            
            name_input = ui.input('Job Name', placeholder='Enter job name').classes('w-full')
            name_input.bind_value(form, 'name')
            
            ui.label('Scene File:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full gap-2 items-center'):
                file_input = ui.input(placeholder=r'C:\path\to\scene').classes('flex-grow')
                file_input.bind_value(form, 'file_path')
                
                def probe_scene(file_path: str):
                    nonlocal camera_select, res_w_input, res_h_input, frame_start_input, frame_end_input, anim_checkbox
                    detected = render_app.engine_registry.detect_engine_for_file(file_path)
                    if not detected:
                        status_label.set_text('Unknown file type')
                        return
                    
                    select_engine(detected.engine_type)
                    status_label.set_text('Probing scene...')
                    status_label.classes(replace='text-xs text-yellow-500')
                    
                    async def do_probe_async():
                        nonlocal camera_select, res_w_input, res_h_input, frame_start_input, frame_end_input, anim_checkbox
                        loop = asyncio.get_event_loop()
                        info = await loop.run_in_executor(None, lambda: detected.get_scene_info(file_path))
                        
                        # Update resolution (ALL engines including Vantage)
                        if info.get('resolution_x') and res_w_input:
                            res_w_input.value = info['resolution_x']
                            form['res_width'] = info['resolution_x']
                            form['base_res_width'] = info['resolution_x']
                        if info.get('resolution_y') and res_h_input:
                            res_h_input.value = info['resolution_y']
                            form['res_height'] = info['resolution_y']
                            form['base_res_height'] = info['resolution_y']
                        if res_scale_container:
                            res_scale_container.refresh()
                        
                        # Update cameras (NOW INCLUDING VANTAGE - parsed from .vantage file)
                        if camera_select is not None:
                            cameras = info.get('cameras', [])
                            if cameras:
                                camera_select.options = cameras
                                active_cam = info.get('active_camera', cameras[0])
                                if active_cam in cameras:
                                    camera_select.value = active_cam
                                    form['camera'] = active_cam
                                camera_select.update()
                            elif detected.engine_type != 'vantage':
                                # Non-Vantage: default to Scene Default
                                camera_select.options = ['Scene Default']
                                camera_select.value = 'Scene Default'
                                camera_select.update()
                        
                        # Update frame range (NOW INCLUDING VANTAGE - parsed from .vantage file)
                        if info.get('frame_start') and frame_start_input:
                            frame_start_input.value = info['frame_start']
                            form['frame_start'] = info['frame_start']
                        if info.get('frame_end') and info['frame_end'] > 1 and frame_end_input:
                            frame_end_input.value = info['frame_end']
                            form['frame_end'] = info['frame_end']
                        
                        has_anim = info.get('has_animation', False) or info.get('frame_end', 1) > info.get('frame_start', 1)
                        if has_anim and anim_checkbox:
                            anim_checkbox.value = True
                            form['is_animation'] = True
                        
                        # Samples for Marmoset/Blender
                        if info.get('samples') and detected.engine_type in ['marmoset', 'blender']:
                            form['samples'] = info['samples']
                        
                        # Vantage-specific: populate samples and denoiser from INI
                        if detected.engine_type == 'vantage':
                            if info.get('samples'):
                                form['vantage_samples'] = info['samples']
                            if info.get('denoiser_name'):
                                form['vantage_denoiser'] = info['denoiser_name']
                            # Store animation FPS for reference
                            if info.get('animation_fps'):
                                form['vantage_fps'] = info['animation_fps']
                        
                        # Unreal-specific: probed asset candidates for MRQ (v2.21.0)
                        if detected.engine_type == 'unreal':
                            form['unreal_maps'] = info.get('maps', [])
                            form['unreal_sequences'] = info.get('sequences', [])
                            form['unreal_presets'] = info.get('presets', [])
                            # Auto-select when there's exactly one candidate
                            if len(form['unreal_maps']) == 1 and not form['unreal_map']:
                                form['unreal_map'] = form['unreal_maps'][0]
                            if len(form['unreal_sequences']) == 1 and not form['unreal_sequence']:
                                form['unreal_sequence'] = form['unreal_sequences'][0]
                            if len(form['unreal_presets']) == 1 and not form['unreal_preset']:
                                form['unreal_preset'] = form['unreal_presets'][0]

                        # Update engine settings section
                        if 'engine_settings' in accent_elements:
                            accent_elements['engine_settings'].refresh()

                        # Status message
                        if detected.engine_type == 'unreal':
                            ver = info.get('engine_version', '?')
                            status_label.set_text(
                                f"UE {ver}: {len(form['unreal_maps'])} maps, "
                                f"{len(form['unreal_sequences'])} sequences, "
                                f"{len(form['unreal_presets'])} MRQ presets found")
                        elif detected.engine_type == 'vantage':
                            res_str = f"{info.get('resolution_x', '?')}x{info.get('resolution_y', '?')}"
                            samples = info.get('samples', '?')
                            frames = info.get('frame_end', 1)
                            fps = info.get('animation_fps', 30)
                            if frames > 1:
                                status_label.set_text(f'Vantage: {res_str}, {samples} smp, {frames} frames @ {fps}fps')
                            else:
                                status_label.set_text(f'Vantage: {res_str}, {samples} samples')
                        elif detected.engine_type == 'marmoset':
                            res_str = f"{info.get('resolution_x', '?')}x{info.get('resolution_y', '?')}"
                            n_cameras = len(info.get('cameras', []))
                            samples = info.get('samples', '?')
                            cam_text = f"{n_cameras} camera{'s' if n_cameras != 1 else ''}"
                            status_label.set_text(f'Marmoset: {res_str}, {samples} smp, {cam_text}')
                        else:
                            status_label.set_text(f'Scene loaded: {info.get("resolution_x", "?")}x{info.get("resolution_y", "?")}')
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
            
            # Generic render controls - hidden for Unreal, where the MRQ preset
            # and sequence govern naming, format, resolution, camera, and frames
            with ui.column().classes('w-full gap-3') as generic_render_section:
                with ui.row().classes('w-full gap-2'):
                    ui.input('Prefix', value='render_').bind_value(form, 'output_name').classes('flex-grow')
                    format_select = ui.select(
                        ENGINE_FORMAT_OPTIONS.get(form['engine_type'], ['PNG', 'JPEG']),
                        value='PNG', label='Format'
                    ).bind_value(form, 'output_format').classes('w-28')

                # Resolution (only used by non-Vantage engines)
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

                # Camera
                camera_select = ui.select(['Scene Default'], value='Scene Default', label='Camera').classes('w-full')
                camera_select.bind_value(form, 'camera')

                # Animation frames
                with ui.row().classes('w-full items-center gap-3'):
                    anim_checkbox = ui.checkbox('Animation').props('dense')
                    anim_checkbox.bind_value(form, 'is_animation')
                    frame_start_input = ui.number('Start', value=1, min=1).classes('w-20')
                    frame_start_input.bind_value(form, 'frame_start')
                    ui.label('to').classes('text-gray-400')
                    frame_end_input = ui.number('End', value=250, min=1).classes('w-20')
                    frame_end_input.bind_value(form, 'frame_end')

            generic_render_section.set_visibility(form['engine_type'] != 'unreal')
            generic_section_ref['element'] = generic_render_section
            
            # Engine-specific settings section
            @ui.refreshable
            def engine_settings_section():
                if form['engine_type'] == 'vantage':
                    ui.separator()
                    ui.label('Vantage HQ Settings').classes('text-sm font-bold').style('color: #77b22a;')
                    
                    # Toggle for custom settings
                    def toggle_custom(e):
                        form['vantage_use_custom'] = e.value
                        engine_settings_section.refresh()
                    
                    ui.checkbox('Use Custom Settings', value=form['vantage_use_custom'], on_change=toggle_custom).props('dense').classes('mt-1')
                    
                    if form['vantage_use_custom']:
                        # Custom settings - will be applied to vantage.ini before render
                        with ui.column().classes('w-full gap-2 pl-6 mt-2'):
                            ui.label('These settings will override your Vantage defaults:').classes('text-xs text-zinc-400')
                            
                            with ui.row().classes('w-full items-center gap-2'):
                                ui.label('Resolution:').classes('text-sm text-gray-400 w-20')
                                ui.label(f'{form["res_width"]} × {form["res_height"]}').classes('text-sm text-white')
                                ui.label('(from above)').classes('text-xs text-zinc-500')
                            
                            with ui.row().classes('w-full items-center gap-2'):
                                ui.number('Samples', value=form['vantage_samples'], min=1, max=65536).bind_value(form, 'vantage_samples').classes('w-28')
                                ui.select(
                                    options=[
                                        {'label': 'NVIDIA OptiX AI', 'value': 'nvidia'},
                                        {'label': 'Intel OIDN', 'value': 'oidn'},
                                        {'label': 'Off', 'value': 'off'},
                                    ],
                                    value=form['vantage_denoiser'],
                                    label='Denoiser'
                                ).bind_value(form, 'vantage_denoiser').classes('w-40')
                            
                            with ui.row().classes('w-full items-center gap-2 mt-1'):
                                ui.icon('warning').classes('text-amber-500')
                                ui.label('A backup of vantage.ini will be created before modifying.').classes('text-xs text-amber-500')
                    else:
                        # Default mode - use scene settings
                        with ui.row().classes('w-full items-center gap-2 pl-6 mt-1'):
                            ui.icon('info').classes('text-zinc-400')
                            ui.label('Will use the HQ settings already configured in Vantage.').classes('text-xs text-zinc-400')
                
                elif form['engine_type'] == 'marmoset':
                    ui.separator()
                    ui.label('Marmoset Settings').classes('text-sm font-bold').style('color: #ef0343;')
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.select(options=['still', 'turntable', 'animation'], value=form.get('render_type', 'still'), label='Render Type').bind_value(form, 'render_type').classes('w-32')
                        ui.number('Samples', value=form.get('samples', 256), min=1, max=4096).bind_value(form, 'samples').classes('w-24')

                    # Render Passes
                    ui.separator()
                    ui.label('Render Passes').classes('text-sm font-bold').style('color: #ef0343;')
                    ui.label('Select passes to render (at least one required)').classes('text-xs text-zinc-400')

                    marmoset_engine = render_app.engine_registry.get('marmoset')
                    if marmoset_engine:
                        # Group passes by category
                        categories = {}
                        for p in marmoset_engine.RENDER_PASSES:
                            cat = p['category']
                            if cat not in categories:
                                categories[cat] = []
                            categories[cat].append(p)

                        def _make_pass_toggle(pass_id):
                            def toggle(e):
                                if e.value:
                                    if pass_id not in form['render_passes']:
                                        form['render_passes'].append(pass_id)
                                else:
                                    if pass_id in form['render_passes'] and len(form['render_passes']) > 1:
                                        form['render_passes'].remove(pass_id)
                                    elif len(form['render_passes']) <= 1:
                                        e.sender.value = True
                            return toggle

                        for cat_name, passes in categories.items():
                            ui.label(cat_name).classes('text-xs text-zinc-500 font-bold mt-1')
                            with ui.row().classes('w-full flex-wrap gap-x-3 gap-y-0'):
                                for p in passes:
                                    is_checked = p['id'] in form['render_passes']
                                    ui.checkbox(p['name'], value=is_checked, on_change=_make_pass_toggle(p['id'])).props('dense').classes('text-xs')

                elif form['engine_type'] == 'unreal':
                    ui.separator()
                    ui.label('Movie Render Queue').classes('text-sm font-bold').style('color: #0d8de3;')
                    if not (form['unreal_maps'] or form['unreal_sequences'] or form['unreal_presets']):
                        ui.label('Browse a .uproject above — maps, sequences, and MRQ presets will populate these dropdowns.').classes('text-xs text-zinc-400')

                    ui.select(_unreal_options(form['unreal_maps'], form['unreal_map']),
                              label='Map', with_input=True, new_value_mode='add-unique') \
                        .bind_value(form, 'unreal_map').props('dense outlined').classes('w-full')
                    ui.select(_unreal_options(form['unreal_sequences'], form['unreal_sequence']),
                              label='Level Sequence', with_input=True, new_value_mode='add-unique') \
                        .bind_value(form, 'unreal_sequence').props('dense outlined').classes('w-full')
                    ui.select(_unreal_options(form['unreal_presets'], form['unreal_preset']),
                              label='MRQ Preset', with_input=True, new_value_mode='add-unique') \
                        .bind_value(form, 'unreal_preset').props('dense outlined').classes('w-full')
                    ui.input('Extra Args', placeholder='-dpcvars=... (optional)').bind_value(form, 'unreal_extra_args').classes('w-full')
                    ui.checkbox('Show preview window while rendering', value=form['unreal_show_preview']) \
                        .props('dense').bind_value(form, 'unreal_show_preview') \
                        .tooltip('Renders in a visible game window so you can watch frames as they finish. '
                                 'Uncheck for fully headless (offscreen) rendering on unattended workers.')

                    with ui.row().classes('w-full items-center gap-2 mt-1'):
                        ui.icon('info').classes('text-zinc-400')
                        ui.label('Resolution, format, and frame range come from the MRQ preset and sequence - '
                                 'Wain detects the sequence length automatically while rendering. '
                                 'Set Output Folder to the preset\'s Output Directory so progress can be tracked.').classes('text-xs text-zinc-400')

            accent_elements['engine_settings'] = engine_settings_section
            engine_settings_section()
            
            ui.separator()
            with ui.row().classes('w-full gap-4 items-center'):
                ui.checkbox('Overwrite Existing', value=True).props('dense').bind_value(form, 'overwrite_existing')
                ui.checkbox('Submit as Paused').props('dense').bind_value(form, 'submit_paused')
                if render_app.network_mode and render_app.db:
                    ui.checkbox('Distribute').props('dense').bind_value(form, 'distribute').tooltip('Split animation frames across all available workers')
                    ui.element('div').classes('flex-1')  # spacer
                    worker_options = {'': 'Any Worker', 'local': 'Local (This Machine)'}
                    workers = render_app.db.get_workers()
                    for w in workers:
                        if not w.get('is_stale'):
                            worker_options[w['worker_id']] = w['worker_id']
                    ui.select(worker_options, value='', label='Render On').props('dense outlined').classes('w-48').bind_value(form, 'target_worker')
        
        with ui.row().classes('w-full justify-end gap-2 p-4 border-t border-zinc-700'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            
            def submit():
                if not form['file_path'] or not form['output_folder']:
                    return

                # Unreal jobs can't start without the three MRQ asset paths
                if form['engine_type'] == 'unreal':
                    if not (form['unreal_map'] and form['unreal_sequence'] and form['unreal_preset']):
                        ui.notify('Unreal jobs need a Map, Level Sequence, and MRQ Preset', type='warning')
                        return

                engine_settings = {}
                if form['engine_type'] == 'vantage':
                    if form['vantage_use_custom']:
                        engine_settings = {
                            'use_custom_settings': True,
                            'width': int(form['res_width']),
                            'height': int(form['res_height']),
                            'samples': int(form['vantage_samples']),
                            'denoiser': form['vantage_denoiser'],
                        }
                    else:
                        engine_settings = {'use_custom_settings': False}
                elif form['engine_type'] == 'marmoset':
                    # Build full pass data for the render script
                    marmoset_eng = render_app.engine_registry.get('marmoset')
                    render_pass_data = []
                    if marmoset_eng:
                        pass_lookup = {p["id"]: p for p in marmoset_eng.RENDER_PASSES}
                        for pid in form.get('render_passes', ['beauty']):
                            if pid in pass_lookup:
                                p = pass_lookup[pid]
                                render_pass_data.append({"id": p["id"], "name": p["name"], "pass": p["pass"]})
                    engine_settings = {
                        "render_type": form.get('render_type', 'still'),
                        "samples": int(form.get('samples', 256)),
                        "render_passes": form.get('render_passes', ['beauty']),
                        "render_pass_data": render_pass_data,
                    }
                elif form['engine_type'] == 'unreal':
                    engine_settings = {
                        "map_path": form['unreal_map'].strip(),
                        "sequence_path": form['unreal_sequence'].strip(),
                        "preset_path": form['unreal_preset'].strip(),
                        "extra_args": form['unreal_extra_args'].strip(),
                        "show_preview": bool(form['unreal_show_preview']),
                    }
                    # MRQ preset/sequence govern format and frames; the real
                    # frame count is auto-detected from the render log at runtime
                    form['is_animation'] = True
                    form['frame_start'] = 1
                    form['frame_end'] = 1
                    form['output_format'] = 'Preset'
                    form['distribute'] = False  # frame-chunking can't override an MRQ preset
                    # Resolution is governed by the MRQ preset; detected from
                    # the first rendered frame at render time
                    form['res_width'] = 0
                    form['res_height'] = 0

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
                    target_worker=form.get('target_worker', ''),
                )
                
                # Distribute: split animation across workers
                if (form['distribute'] and form['is_animation']
                        and render_app.network_mode and render_app.db):
                    workers = render_app.db.get_workers()
                    active_workers = [w for w in workers if not w.get('is_stale')]
                    worker_count = len(active_workers) + 1  # +1 for server
                    job.status = 'queued'
                    render_app.add_distributed_job(job, worker_count=worker_count)
                else:
                    render_app.add_job(job)
                dialog.close()
            
            initial_accent = ENGINE_COLORS.get(form['engine_type'], "#ea7600")
            submit_btn = ui.button('Submit Job', on_click=submit).style(_accent_btn_style(initial_accent))
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
        # Engine-specific (restored from job)
        'render_type': job.engine_settings.get('render_type', 'still'),
        'samples': job.engine_settings.get('samples', 256),
        'render_passes': list(job.engine_settings.get('render_passes', ['beauty'])),
        'vantage_use_custom': job.engine_settings.get('use_custom_settings', False),
        'vantage_samples': job.engine_settings.get('samples', 100),
        'vantage_denoiser': job.engine_settings.get('denoiser', 'nvidia'),
        # Unreal-specific (v2.21.0)
        'unreal_map': job.engine_settings.get('map_path', ''),
        'unreal_sequence': job.engine_settings.get('sequence_path', ''),
        'unreal_preset': job.engine_settings.get('preset_path', ''),
        'unreal_extra_args': job.engine_settings.get('extra_args', ''),
        'unreal_show_preview': job.engine_settings.get('show_preview', True),
    }
    
    with ui.dialog().props('transition-show="jump-up" transition-hide="jump-down" transition-duration="150"') as dialog, ui.card().style('width: 600px; max-width: 95vw; padding: 0;'):
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
            
            edit_format_options = {
                'blender': ['PNG', 'JPEG', 'OpenEXR', 'TIFF'],
                'marmoset': ['PNG', 'JPEG', 'TGA', 'PSD', 'PSD (16-bit)', 'EXR (16-bit)', 'EXR (32-bit)'],
                'vantage': ['PNG', 'JPEG', 'OpenEXR', 'TIFF'],
                'unreal': ['Preset', 'EXR', 'PNG', 'JPEG'],
            }
            # Generic render controls - not shown for Unreal, where the MRQ
            # preset/sequence govern naming, format, camera, and frame range
            edit_camera_select = None
            if job.engine_type != 'unreal':
                with ui.row().classes('w-full gap-2'):
                    ui.input('Prefix', value=form['output_name']).bind_value(form, 'output_name').classes('flex-grow')
                    ui.select(
                        edit_format_options.get(job.engine_type, ['PNG', 'JPEG']),
                        value=form['output_format'], label='Format'
                    ).bind_value(form, 'output_format').classes('w-28')

                # Camera dropdown — start with current value, probe scene in background
                current_cam = form['camera'] or 'Scene Default'
                camera_options = [current_cam] if current_cam != 'Scene Default' else ['Scene Default']

                def _on_camera_change(e):
                    form['camera'] = e.value

                edit_camera_select = ui.select(
                    camera_options, value=current_cam, label='Camera',
                    on_change=_on_camera_change,
                ).classes('w-full')

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

            # Engine-specific settings section
            if job.engine_type == 'marmoset':
                ui.separator()
                ui.label('Marmoset Settings').classes('text-sm font-bold').style('color: #ef0343;')
                with ui.row().classes('w-full items-center gap-2'):
                    ui.select(options=['still', 'turntable', 'animation'], value=form.get('render_type', 'still'), label='Render Type').bind_value(form, 'render_type').classes('w-32')
                    ui.number('Samples', value=form.get('samples', 256), min=1, max=4096).bind_value(form, 'samples').classes('w-24')

                # Render Passes
                ui.separator()
                ui.label('Render Passes').classes('text-sm font-bold').style('color: #ef0343;')
                ui.label('Select passes to render (at least one required)').classes('text-xs text-zinc-400')

                marmoset_engine = render_app.engine_registry.get('marmoset')
                if marmoset_engine:
                    categories = {}
                    for p in marmoset_engine.RENDER_PASSES:
                        cat = p['category']
                        if cat not in categories:
                            categories[cat] = []
                        categories[cat].append(p)

                    def _make_pass_toggle(pass_id):
                        def toggle(e):
                            if e.value:
                                if pass_id not in form['render_passes']:
                                    form['render_passes'].append(pass_id)
                            else:
                                if pass_id in form['render_passes'] and len(form['render_passes']) > 1:
                                    form['render_passes'].remove(pass_id)
                                elif len(form['render_passes']) <= 1:
                                    e.sender.value = True
                        return toggle

                    for cat_name, passes in categories.items():
                        ui.label(cat_name).classes('text-xs text-zinc-500 font-bold mt-1')
                        with ui.row().classes('w-full flex-wrap gap-x-3 gap-y-0'):
                            for p in passes:
                                is_checked = p['id'] in form['render_passes']
                                ui.checkbox(p['name'], value=is_checked, on_change=_make_pass_toggle(p['id'])).props('dense').classes('text-xs')

            elif job.engine_type == 'vantage':
                ui.separator()
                ui.label('Vantage HQ Settings').classes('text-sm font-bold').style('color: #77b22a;')

                def toggle_custom(e):
                    form['vantage_use_custom'] = e.value
                    edit_engine_settings.refresh()

                ui.checkbox('Use Custom Settings', value=form['vantage_use_custom'], on_change=toggle_custom).props('dense').classes('mt-1')

                @ui.refreshable
                def edit_engine_settings():
                    if form['vantage_use_custom']:
                        with ui.column().classes('w-full gap-2 pl-6 mt-2'):
                            ui.label('These settings will override your Vantage defaults:').classes('text-xs text-zinc-400')

                            with ui.row().classes('w-full items-center gap-2'):
                                ui.label('Resolution:').classes('text-sm text-gray-400 w-20')
                                ui.label(f'{form["res_width"]} × {form["res_height"]}').classes('text-sm text-white')
                                ui.label('(from above)').classes('text-xs text-zinc-500')

                            with ui.row().classes('w-full items-center gap-2'):
                                ui.number('Samples', value=form['vantage_samples'], min=1, max=65536).bind_value(form, 'vantage_samples').classes('w-28')
                                ui.select(
                                    options=[
                                        {'label': 'NVIDIA OptiX AI', 'value': 'nvidia'},
                                        {'label': 'Intel OIDN', 'value': 'oidn'},
                                        {'label': 'Off', 'value': 'off'},
                                    ],
                                    value=form['vantage_denoiser'],
                                    label='Denoiser'
                                ).bind_value(form, 'vantage_denoiser').classes('w-40')

                            with ui.row().classes('w-full items-center gap-2 mt-1'):
                                ui.icon('warning').classes('text-amber-500')
                                ui.label('A backup of vantage.ini will be created before modifying.').classes('text-xs text-amber-500')
                    else:
                        with ui.row().classes('w-full items-center gap-2 pl-6 mt-1'):
                            ui.icon('info').classes('text-zinc-400')
                            ui.label('Will use the HQ settings already configured in Vantage.').classes('text-xs text-zinc-400')

                edit_engine_settings()

            elif job.engine_type == 'unreal':
                ui.separator()
                ui.label('Movie Render Queue').classes('text-sm font-bold').style('color: #0d8de3;')
                unreal_map_select = ui.select(_unreal_options([], form['unreal_map']),
                                              label='Map', with_input=True, new_value_mode='add-unique') \
                    .bind_value(form, 'unreal_map').props('dense outlined').classes('w-full')
                unreal_seq_select = ui.select(_unreal_options([], form['unreal_sequence']),
                                              label='Level Sequence', with_input=True, new_value_mode='add-unique') \
                    .bind_value(form, 'unreal_sequence').props('dense outlined').classes('w-full')
                unreal_preset_select = ui.select(_unreal_options([], form['unreal_preset']),
                                                 label='MRQ Preset', with_input=True, new_value_mode='add-unique') \
                    .bind_value(form, 'unreal_preset').props('dense outlined').classes('w-full')
                ui.input('Extra Args', placeholder='-dpcvars=... (optional)').bind_value(form, 'unreal_extra_args').classes('w-full')

                async def probe_unreal_candidates():
                    """Re-probe the .uproject so the dropdowns offer all assets."""
                    eng = render_app.engine_registry.get('unreal')
                    if not eng or not os.path.exists(job.file_path):
                        return
                    try:
                        loop = asyncio.get_event_loop()
                        info = await loop.run_in_executor(None, lambda: eng.get_scene_info(job.file_path))
                        unreal_map_select.options = _unreal_options(info.get('maps', []), form['unreal_map'])
                        unreal_seq_select.options = _unreal_options(info.get('sequences', []), form['unreal_sequence'])
                        unreal_preset_select.options = _unreal_options(info.get('presets', []), form['unreal_preset'])
                        unreal_map_select.update()
                        unreal_seq_select.update()
                        unreal_preset_select.update()
                    except Exception:
                        pass

                asyncio.create_task(probe_unreal_candidates())
                ui.checkbox('Show preview window while rendering', value=form['unreal_show_preview']) \
                    .props('dense').bind_value(form, 'unreal_show_preview') \
                    .tooltip('Renders in a visible game window so you can watch frames as they finish. '
                             'Uncheck for fully headless (offscreen) rendering on unattended workers.')
                with ui.row().classes('w-full items-center gap-2 mt-1'):
                    ui.icon('info').classes('text-zinc-400')
                    ui.label('Resolution, format, and frame range come from the MRQ preset and sequence - '
                             'Wain detects the sequence length automatically while rendering. '
                             'Output Folder must match the preset\'s Output Directory for progress tracking.').classes('text-xs text-zinc-400')

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

                # Rebuild engine_settings from form
                if job.engine_type == 'marmoset':
                    marmoset_eng = render_app.engine_registry.get('marmoset')
                    render_pass_data = []
                    if marmoset_eng:
                        pass_lookup = {p["id"]: p for p in marmoset_eng.RENDER_PASSES}
                        for pid in form.get('render_passes', ['beauty']):
                            if pid in pass_lookup:
                                p = pass_lookup[pid]
                                render_pass_data.append({"id": p["id"], "name": p["name"], "pass": p["pass"]})
                    job.engine_settings = {
                        "render_type": form.get('render_type', 'still'),
                        "samples": int(form.get('samples', 256)),
                        "render_passes": form.get('render_passes', ['beauty']),
                        "render_pass_data": render_pass_data,
                    }
                elif job.engine_type == 'vantage':
                    if form.get('vantage_use_custom'):
                        job.engine_settings = {
                            'use_custom_settings': True,
                            'width': int(form['res_width']),
                            'height': int(form['res_height']),
                            'samples': int(form['vantage_samples']),
                            'denoiser': form['vantage_denoiser'],
                        }
                    else:
                        job.engine_settings = {'use_custom_settings': False}
                elif job.engine_type == 'unreal':
                    job.engine_settings = {
                        'map_path': form['unreal_map'].strip(),
                        'sequence_path': form['unreal_sequence'].strip(),
                        'preset_path': form['unreal_preset'].strip(),
                        'extra_args': form['unreal_extra_args'].strip(),
                        'show_preview': bool(form['unreal_show_preview']),
                    }

                job.camera = form.get('camera', '')

                render_app.save_config()
                if render_app.network_mode and render_app.db:
                    render_app.db.update_job(job.id,
                        name=job.name, file_path=job.file_path,
                        output_folder=job.output_folder, output_name=job.output_name,
                        output_format=job.output_format,
                        res_width=job.res_width, res_height=job.res_height,
                        is_animation=job.is_animation,
                        frame_start=job.frame_start, frame_end=job.frame_end,
                        camera=job.camera, overwrite_existing=job.overwrite_existing,
                        engine_settings=job.engine_settings)
                render_app.log(f"Updated: {job.name}")
                ui.notify('Job updated', type='positive')
                if render_app.queue_container:
                    render_app.queue_container.refresh()
                dialog.close()
            
            def resubmit():
                save_changes()
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
                job.total_passes = 0
                job.pass_total_frames = 0
                job.status_message = ""
                job.assigned_to = None
                render_app.save_config()
                if render_app.network_mode and render_app.db:
                    render_app.db.update_job(job.id,
                        status='queued', progress=0,
                        current_frame=0, rendering_frame=0,
                        error_message='', accumulated_seconds=0,
                        elapsed_time='', assigned_to=None)
                ui.notify('Job resubmitted', type='positive')
                if render_app.queue_container:
                    render_app.queue_container.refresh()
                if render_app.stats_container:
                    render_app.stats_container.refresh()
            
            if job.status in ['completed', 'failed']:
                ui.button('Resubmit', icon='refresh', on_click=resubmit).style(_accent_btn_style(accent_color))
            else:
                ui.button('Save', on_click=save_changes).style(_accent_btn_style(accent_color))
    
    dialog.open()

    # Probe scene cameras in background after dialog is fully built
    async def _probe_cameras():
        if edit_camera_select is None:  # Unreal: no camera field (preset governs)
            return
        engine = render_app.engine_registry.get(job.engine_type)
        if not engine or not form['file_path']:
            return
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, lambda: engine.get_scene_info(form['file_path']))
        except Exception:
            return
        cameras = info.get('cameras', [])
        if cameras:
            edit_camera_select.options = cameras
            if form['camera'] in cameras:
                edit_camera_select.value = form['camera']
            else:
                edit_camera_select.value = cameras[0]
                form['camera'] = cameras[0]
            edit_camera_select.update()

    asyncio.create_task(_probe_cameras())


async def show_settings_dialog():
    with ui.dialog().props('transition-show="jump-up" transition-hide="jump-down" transition-duration="150"') as dialog, ui.card().style('width: 550px; max-width: 95vw; padding: 0;'):
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

            # Network Mode Section
            ui.separator()
            with ui.card().classes('w-full p-3'):
                with ui.row().classes('items-center gap-2 mb-2'):
                    ui.icon('lan').classes('text-xl').style('color: #22c55e;')
                    ui.label('Network Mode').classes('font-bold')

                ui.label(
                    'Enable to share the render queue with network workers. '
                    'Jobs will be stored in a SQLite database and a REST API will be available.'
                ).classes('text-xs text-zinc-400 mb-2')

                @ui.refreshable
                def network_status_label():
                    if render_app.network_mode:
                        ui.label('Workers can connect to this machine on port 8080').classes('text-xs text-green-500')
                    else:
                        ui.label('Currently running in standalone mode (JSON-backed)').classes('text-xs text-zinc-500')

                def toggle_network(e):
                    if e.value:
                        db = getattr(render_app, '_db_instance', None) or render_app.db
                        if not db:
                            from wain.config import DATABASE_FILE
                            from wain.network.database import JobDatabase
                            db = JobDatabase(DATABASE_FILE)
                            render_app._db_instance = db
                        render_app.enable_network_mode(db, migrate_jobs=True)

                        # Register API routes so local workers can connect immediately
                        if not getattr(render_app, '_api_routes_registered', False):
                            from nicegui import app as nicegui_app
                            from wain.config import AUTH_TOKEN_FILE
                            from wain.network.auth import load_or_create_token
                            from wain.network.server import register_api_routes

                            api_token = load_or_create_token(AUTH_TOKEN_FILE)
                            register_api_routes(nicegui_app, db, render_app, api_token=api_token)
                            render_app._api_routes_registered = True
                            render_app.log(f"API token: {api_token}")
                            render_app.log("Workers use: --token <token>")
                    else:
                        render_app.disable_network_mode()

                    # Refresh the network panel in the main UI
                    if hasattr(render_app, 'network_panel'):
                        render_app.network_panel.refresh()
                    if render_app.queue_container:
                        render_app.queue_container.refresh()
                    if render_app.stats_container:
                        render_app.stats_container.refresh()
                    network_status_label.refresh()

                    if e.value:
                        ui.notify(
                            'Network mode enabled — restart Wain for workers to connect',
                            type='positive',
                            timeout=5000,
                        )
                    else:
                        ui.notify('Network mode disabled', type='positive')

                ui.switch(
                    'Enable Network Mode',
                    value=render_app.network_mode,
                    on_change=toggle_network,
                )
                network_status_label()

        with ui.row().classes('w-full justify-end p-4 border-t border-zinc-700'):
            ui.button('Close', on_click=dialog.close).props('flat')

    dialog.open()
