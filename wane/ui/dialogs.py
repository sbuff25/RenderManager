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
    """Simple Add Job dialog with all fields visible."""
    
    # Form state
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
        # Marmoset-specific settings
        'render_type': 'still',           # still, turntable, animation
        'renderer': 'Ray Tracing',        # Ray Tracing, Hybrid, Raster
        'samples': 256,
        'shadow_quality': 'High',         # Low, High, Mega
        'use_transparency': False,
        'denoise_mode': 'gpu',            # off, cpu, gpu
        'video_format': 'PNG Sequence',
        'turntable_frames': 120,
        'render_passes': ['beauty'],      # List of pass IDs to render
    }
    
    # UI references for scene info updates
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
    accent_elements = {}  # Elements that change color with engine selection
    marmoset_settings_container = None  # Reference to Marmoset settings panel for refresh
    
    # Engine-specific colors
    ENGINE_ACCENT_COLORS = {
        "blender": "#ea7600",
        "marmoset": "#ef0343",
    }
    
    def select_engine(eng_type):
        """Update the engine selection, button styles, and accent colors with animation"""
        form['engine_type'] = eng_type
        accent_color = ENGINE_ACCENT_COLORS.get(eng_type, "#3b82f6")
        
        # Update engine selector buttons
        for et, btn in engine_buttons.items():
            if et == eng_type:
                btn.classes(replace='px-3 py-2 rounded engine-btn-selected')
                btn.style(f'''
                    background-color: {ENGINE_ACCENT_COLORS.get(et, "#3b82f6")} !important;
                    color: white !important;
                    transition: all 0.3s ease;
                ''')
            else:
                btn.classes(replace='px-3 py-2 rounded engine-btn-unselected')
                btn.style(f'''
                    background-color: transparent !important;
                    color: #52525b !important;
                    transition: all 0.3s ease;
                ''')
        
        # Update header gradient bar
        if 'header_bar' in accent_elements:
            accent_elements['header_bar'].style(f'''
                height: 3px;
                background: linear-gradient(90deg, transparent 0%, {accent_color} 50%, transparent 100%);
                transition: background 0.4s ease-in-out;
            ''')
        
        # Update submit button with animated color transition
        if 'submit_btn' in accent_elements:
            accent_elements['submit_btn'].style(f'''
                background-color: {accent_color} !important;
                transition: all 0.4s ease-in-out !important;
            ''')
        
        # Refresh Marmoset settings section (show/hide based on engine)
        if 'marmoset_settings' in accent_elements:
            accent_elements['marmoset_settings'].refresh()
        
        # Update CSS variable for all form elements (inputs, checkboxes, selects, etc.)
        ui.run_javascript(f'''
            const dialog = document.querySelector('.accent-dialog');
            if (dialog) {{
                dialog.style.setProperty('--q-primary', '{accent_color}');
                
                // Force repaint for transition
                dialog.classList.add('accent-transition');
                setTimeout(() => dialog.classList.remove('accent-transition'), 400);
            }}
        ''')
    
    with ui.dialog() as dialog, ui.card().style(
        'width: 600px; max-width: 95vw; padding: 0;'
    ).classes('accent-dialog'):
        # Add CSS for dynamic accent colors on all form elements
        ui.html(f'''
            <style>
                .accent-dialog {{
                    --q-primary: {ENGINE_ACCENT_COLORS.get(form["engine_type"], "#ea7600")};
                }}
                
                /* Engine selector button styles */
                .accent-dialog .engine-btn-unselected {{
                    background-color: transparent !important;
                    transition: all 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-unselected .q-btn__content,
                .accent-dialog .engine-btn-unselected .q-btn__content * {{
                    color: #52525b !important;
                    background-color: transparent !important;
                    transition: color 0.3s ease, opacity 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-unselected img {{
                    opacity: 0.4;
                    transition: opacity 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-unselected:hover {{
                    background-color: rgba(255, 255, 255, 0.08) !important;
                }}
                
                .accent-dialog .engine-btn-unselected:hover .q-btn__content,
                .accent-dialog .engine-btn-unselected:hover .q-btn__content * {{
                    color: #a1a1aa !important;
                }}
                
                .accent-dialog .engine-btn-unselected:hover img {{
                    opacity: 0.7;
                }}
                
                .accent-dialog .engine-btn-selected {{
                    transition: all 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-selected .q-btn__content,
                .accent-dialog .engine-btn-selected .q-btn__content * {{
                    color: white !important;
                    background-color: transparent !important;
                    transition: color 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-selected img {{
                    opacity: 1;
                    transition: opacity 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-selected:hover {{
                    filter: brightness(1.15);
                }}
                
                /* Submit button hover */
                .accent-dialog .engine-accent {{
                    transition: all 0.3s ease;
                }}
                
                .accent-dialog .engine-accent:hover {{
                    filter: brightness(1.15);
                    transform: translateY(-1px);
                }}
                
                .accent-dialog .engine-accent:active {{
                    filter: brightness(0.95);
                    transform: translateY(0);
                }}
                
                /* Input field styles */
                .accent-dialog .q-field--focused .q-field__control:after {{
                    border-color: var(--q-primary) !important;
                }}
                
                .accent-dialog .q-field:hover:not(.q-field--focused) .q-field__control:before {{
                    border-color: rgba(255, 255, 255, 0.3) !important;
                }}
                
                .accent-dialog .q-field--focused .q-field__label {{
                    color: var(--q-primary) !important;
                    transition: color 0.4s ease-in-out;
                }}
                
                /* Checkbox styles */
                .accent-dialog .q-checkbox:hover .q-checkbox__bg {{
                    border-color: var(--q-primary) !important;
                }}
                
                .accent-dialog .q-checkbox__inner--truthy .q-checkbox__bg {{
                    background-color: var(--q-primary) !important;
                    border-color: var(--q-primary) !important;
                    transition: background-color 0.4s ease-in-out, border-color 0.4s ease-in-out;
                }}
                
                .accent-dialog .q-checkbox__bg {{
                    transition: background-color 0.4s ease-in-out, border-color 0.4s ease-in-out;
                }}
                
                /* Toggle styles */
                .accent-dialog .q-toggle:hover .q-toggle__track {{
                    opacity: 0.7;
                }}
                
                .accent-dialog .q-toggle__inner--truthy .q-toggle__track {{
                    background-color: var(--q-primary) !important;
                    opacity: 0.5;
                    transition: background-color 0.4s ease-in-out;
                }}
                
                .accent-dialog .q-toggle__inner--truthy .q-toggle__thumb {{
                    background-color: var(--q-primary) !important;
                    transition: background-color 0.4s ease-in-out;
                }}
                
                /* Select styles */
                .accent-dialog .q-select:hover:not(.q-field--focused) .q-field__control:before {{
                    border-color: rgba(255, 255, 255, 0.3) !important;
                }}
                
                .accent-dialog .q-select--focused .q-field__control:after {{
                    border-color: var(--q-primary) !important;
                    transition: border-color 0.4s ease-in-out;
                }}
                
                .accent-dialog .q-field__control:after {{
                    transition: border-color 0.4s ease-in-out;
                }}
                
                /* Flat button styles (Browse, icons) */
                .accent-dialog .q-btn--flat {{
                    color: var(--q-primary) !important;
                    transition: all 0.3s ease-in-out;
                }}
                
                .accent-dialog .q-btn--flat:hover {{
                    background-color: rgba(255, 255, 255, 0.1) !important;
                    filter: brightness(1.2);
                }}
                
                /* Separator styles */
                .accent-dialog .accent-separator {{
                    background: linear-gradient(90deg, transparent, var(--q-primary), transparent);
                    height: 1px;
                    transition: background 0.4s ease-in-out;
                }}
            </style>
        ''', sanitize=False)
        
        # Header with accent gradient bar
        with ui.column().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between p-4'):
                ui.label('Add Render Job').classes('text-lg font-bold')
                ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm')
            # Accent gradient line under header
            initial_color = ENGINE_ACCENT_COLORS.get(form["engine_type"], "#ea7600")
            header_bar = ui.element('div').classes('w-full').style(f'''
                height: 3px;
                background: linear-gradient(90deg, transparent 0%, {initial_color} 50%, transparent 100%);
                transition: background 0.4s ease-in-out;
            ''')
            accent_elements['header_bar'] = header_bar
        
        # Store dialog reference for CSS updates
        accent_elements['dialog'] = dialog
        
        # Form content - let dialog handle scrolling naturally
        with ui.column().classes('w-full p-4 gap-3').style('max-height: 70vh; overflow-y: auto;'):
            
            # Engine selector with logos
            with ui.row().classes('w-full items-center gap-2'):
                ui.label('Engine:').classes('text-gray-400 w-20')
                
                with ui.row().classes('gap-2'):
                    for engine in render_app.engine_registry.get_available():
                        engine_logo = ENGINE_LOGOS.get(engine.engine_type)
                        
                        is_selected = engine.engine_type == form['engine_type']
                        
                        # Capture engine type in closure
                        eng_type = engine.engine_type
                        accent_color = ENGINE_ACCENT_COLORS.get(eng_type, "#3b82f6")
                        
                        if is_selected:
                            btn_class = 'px-3 py-2 rounded engine-btn-selected'
                            btn_style = f'background-color: {accent_color} !important; color: white !important; transition: all 0.3s ease;'
                        else:
                            btn_class = 'px-3 py-2 rounded engine-btn-unselected'
                            btn_style = 'background-color: transparent !important; color: #52525b !important; transition: all 0.3s ease;'
                        
                        with ui.button(on_click=lambda et=eng_type: select_engine(et)).props('flat dense').classes(btn_class).style(btn_style) as btn:
                            with ui.row().classes('items-center gap-2'):
                                if engine_logo:
                                    ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-5 h-5 object-contain')
                                ui.label(engine.name).classes('text-sm')
                        engine_buttons[engine.engine_type] = btn
            
            # Job name
            name_input = ui.input('Job Name', placeholder='Enter job name').classes('w-full')
            name_input.bind_value(form, 'name')
            
            # Scene file with browse button
            ui.label('Scene File:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full gap-2 items-center'):
                file_input = ui.input(placeholder=r'C:\path\to\scene.blend').classes('flex-grow')
                file_input.bind_value(form, 'file_path')
                ui.button('Browse', icon='folder_open', on_click=lambda: browse_file()).props('flat dense')
            
            # Scene info status and manual reload button
            with ui.row().classes('w-full items-center gap-2'):
                status_label = ui.label('').classes('text-xs text-gray-500')
                ui.button('Reload Scene Info', icon='refresh', on_click=lambda: load_scene_data(form['file_path'])).props('flat dense size=sm')
            
            # Function to load scene data (used by browse_file, on_file_blur, and manual button)
            def load_scene_data(path: str):
                """Load scene info from file and populate form fields."""
                if not path or not os.path.exists(path):
                    status_label.set_text('File not found')
                    return
                
                engine = render_app.engine_registry.get(form['engine_type'])
                if not engine:
                    status_label.set_text('No engine')
                    return
                
                status_label.set_text('Loading...')
                
                # Run in background thread to avoid blocking UI
                def do_load():
                    try:
                        return engine.get_scene_info(path)
                    except Exception as e:
                        print(f"Scene info error: {e}")
                        return None
                
                def apply_scene_info(info):
                    if info:
                        try:
                            cameras = info.get('cameras', ['Scene Default'])
                            camera_select.options = cameras
                            camera_select.value = info.get('active_camera', cameras[0] if cameras else 'Scene Default')
                            res_w_input.value = info.get('resolution_x', 1920)
                            res_h_input.value = info.get('resolution_y', 1080)
                            frame_start_input.value = info.get('frame_start', 1)
                            frame_end_input.value = info.get('frame_end', 250)
                            if info.get('frame_end', 1) > info.get('frame_start', 1):
                                anim_checkbox.value = True
                            
                            # Update Marmoset-specific settings from scene
                            if form['engine_type'] == 'marmoset':
                                # Set turntable frames from scene if available
                                if info.get('turntable_frames'):
                                    form['turntable_frames'] = info['turntable_frames']
                                elif info.get('total_frames', 1) > 1:
                                    form['turntable_frames'] = info['total_frames']
                                
                                # Set samples from scene
                                if info.get('video_samples'):
                                    form['samples'] = info['video_samples']
                                elif info.get('samples'):
                                    form['samples'] = info['samples']
                                
                                # Check for turntable or animation
                                if info.get('has_turntable'):
                                    form['render_type'] = 'turntable'
                                elif info.get('has_animation'):
                                    form['render_type'] = 'animation'
                                
                                # Capture available render passes from scene
                                if info.get('available_render_passes'):
                                    form['scene_available_passes'] = info['available_render_passes']
                                    # Reset selected passes to only include available ones
                                    available = set(info['available_render_passes'])
                                    # Map our internal IDs to actual pass names and filter
                                    # Always include 'beauty' if 'Full Quality' is available
                                    if 'Full Quality' in available:
                                        form['render_passes'] = ['beauty']
                                    else:
                                        form['render_passes'] = []
                                
                                # Refresh Marmoset settings panel to show updated values
                                if marmoset_settings_container:
                                    try:
                                        marmoset_settings_container.refresh()
                                    except:
                                        pass
                            
                            status_label.set_text('[OK] Loaded')
                        except Exception as e:
                            print(f"Apply scene info error: {e}")
                            status_label.set_text('Error')
                    else:
                        status_label.set_text('Failed')
                
                # Use the same polling pattern as file dialogs
                result_holder = {'done': False, 'info': None}
                
                def background_load():
                    result_holder['info'] = do_load()
                    result_holder['done'] = True
                
                threading.Thread(target=background_load, daemon=True).start()
                
                def check_load_result():
                    if result_holder['done']:
                        apply_scene_info(result_holder['info'])
                    else:
                        ui.timer(0.1, check_load_result, once=True)
                
                ui.timer(0.1, check_load_result, once=True)
            
            # Browse file handler
            def browse_file():
                def on_file_selected(result):
                    if result:
                        file_input.value = result
                        # Auto-fill other fields
                        if not form['name']:
                            name_input.value = os.path.splitext(os.path.basename(result))[0]
                        detected = render_app.engine_registry.detect_engine_for_file(result)
                        if detected:
                            select_engine(detected.engine_type)
                        if not form['output_folder']:
                            output_input.value = os.path.dirname(result)
                        # Auto-load scene data
                        load_scene_data(result)
                
                filters = render_app.engine_registry.get_all_file_filters()
                initial = os.path.dirname(form['file_path']) if form['file_path'] else None
                open_file_dialog_async("Select Scene File", filters, initial, on_file_selected)
            
            # Auto-fill and auto-load on blur (when user pastes path)
            def on_file_blur():
                path = form['file_path']
                if path and os.path.exists(path):
                    if not form['name']:
                        name_input.value = os.path.splitext(os.path.basename(path))[0]
                    detected = render_app.engine_registry.detect_engine_for_file(path)
                    if detected:
                        select_engine(detected.engine_type)
                    if not form['output_folder']:
                        output_input.value = os.path.dirname(path)
                    # Auto-load scene data
                    load_scene_data(path)
            
            file_input.on('blur', on_file_blur)
            
            # Accent separator
            ui.element('div').classes('accent-separator w-full my-2')
            
            # Output folder with browse button
            ui.label('Output Folder:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full gap-2 items-center'):
                output_input = ui.input(placeholder=r'C:\path\to\output').classes('flex-grow')
                output_input.bind_value(form, 'output_folder')
                
                def browse_output():
                    def on_folder_selected(result):
                        if result:
                            output_input.value = result
                    
                    initial = form['output_folder'] if form['output_folder'] else os.path.dirname(form['file_path']) if form['file_path'] else None
                    open_folder_dialog_async("Select Output Folder", initial, on_folder_selected)
                
                ui.button('Browse', icon='folder_open', on_click=browse_output).props('flat dense')
            
            # Prefix and format
            with ui.row().classes('w-full gap-2'):
                ui.input('Prefix', value='render_').bind_value(form, 'output_name').classes('flex-grow')
                ui.select(['PNG', 'JPEG', 'OpenEXR', 'TIFF'], value='PNG', label='Format').bind_value(form, 'output_format').classes('w-28')
            
            # Resolution
            with ui.row().classes('w-full items-center gap-2'):
                res_w_input = ui.number('Width', value=1920, min=1).classes('w-24')
                res_w_input.bind_value(form, 'res_width')
                ui.label('x').classes('text-gray-400')
                res_h_input = ui.number('Height', value=1080, min=1).classes('w-24')
                res_h_input.bind_value(form, 'res_height')
            
            # Camera
            camera_select = ui.select(['Scene Default'], value='Scene Default', label='Camera').classes('w-full')
            camera_select.bind_value(form, 'camera')
            
            # Animation
            with ui.row().classes('w-full items-center gap-3'):
                anim_checkbox = ui.checkbox('Animation').props('dense')
                anim_checkbox.bind_value(form, 'is_animation')
                frame_start_input = ui.number('Start', value=1, min=1).classes('w-20')
                frame_start_input.bind_value(form, 'frame_start')
                ui.label('to').classes('text-gray-400')
                frame_end_input = ui.number('End', value=250, min=1).classes('w-20')
                frame_end_input.bind_value(form, 'frame_end')
            
            # ============================================================
            # MARMOSET-SPECIFIC SETTINGS (shown only for Marmoset engine)
            # ============================================================
            
            @ui.refreshable
            def marmoset_settings():
                if form['engine_type'] == 'marmoset':
                    ui.element('div').classes('accent-separator w-full my-2')
                    ui.label('Marmoset Settings').classes('text-sm font-bold text-gray-400')
                    
                    # Render type selector
                    with ui.row().classes('w-full items-center gap-2'):
                        def on_render_type_change(e):
                            if 'marmoset_settings' in accent_elements:
                                accent_elements['marmoset_settings'].refresh()
                        
                        render_type_select = ui.select(
                            options=['still', 'turntable', 'animation'],
                            value=form.get('render_type', 'still'),
                            label='Render Type',
                            on_change=on_render_type_change
                        ).classes('w-36')
                        render_type_select.bind_value(form, 'render_type')
                        
                        renderer_select = ui.select(
                            options=['Ray Tracing', 'Hybrid', 'Raster'],
                            value=form.get('renderer', 'Ray Tracing'),
                            label='Renderer'
                        ).classes('w-32')
                        renderer_select.bind_value(form, 'renderer')
                    
                    # Quality settings
                    with ui.row().classes('w-full items-center gap-2'):
                        samples_input = ui.number('Samples', value=form.get('samples', 256), min=1, max=4096).classes('w-24')
                        samples_input.bind_value(form, 'samples')
                        
                        shadow_select = ui.select(
                            options=['Low', 'High', 'Mega'],
                            value=form.get('shadow_quality', 'High'),
                            label='Shadows'
                        ).classes('w-24')
                        shadow_select.bind_value(form, 'shadow_quality')
                        
                        denoise_select = ui.select(
                            options=['off', 'cpu', 'gpu'],
                            value=form.get('denoise_mode', 'gpu'),
                            label='Denoise'
                        ).classes('w-24')
                        denoise_select.bind_value(form, 'denoise_mode')
                    
                    # Transparency checkbox
                    ui.checkbox('Transparent Background').props('dense').bind_value(form, 'use_transparency')
                    
                    # Render Passes section
                    with ui.row().classes('w-full items-center justify-between mt-2'):
                        ui.label('Render Passes').classes('text-sm text-gray-400')
                        
                        # Open in Toolbag button - lets user quickly add passes
                        def open_scene_in_toolbag():
                            if form.get('file_path') and os.path.exists(form['file_path']):
                                marmoset_eng = render_app.engine_registry.get('marmoset')
                                if marmoset_eng:
                                    marmoset_eng.open_file_in_app(form['file_path'])
                                    render_app.log(f"Opened in Toolbag: {form['file_path']}")
                        
                        ui.button('Open in Toolbag', icon='launch', on_click=open_scene_in_toolbag).props('flat dense size=sm').classes('text-xs').tooltip('Open scene in Toolbag to add render passes')
                    
                    # Get available passes from engine
                    marmoset_engine = render_app.engine_registry.get('marmoset')
                    all_passes = marmoset_engine.RENDER_PASSES if marmoset_engine else []
                    
                    # Filter to only passes available in the loaded scene
                    scene_passes = form.get('scene_available_passes', [])
                    if scene_passes:
                        # Build options only for passes that exist in the scene
                        # Map scene pass names to our internal pass definitions
                        pass_options = {}
                        for p in all_passes:
                            # Check if this pass exists in scene (by "pass" name which is what Toolbag uses)
                            pass_name = p['pass'] if p['pass'] else 'Full Quality'
                            if pass_name in scene_passes:
                                pass_options[p['id']] = p['name']
                        
                        with ui.row().classes('w-full items-center gap-2'):
                            ui.icon('check_circle').classes('text-green-500 text-sm')
                            ui.label(f'{len(scene_passes)} passes available in scene').classes('text-xs text-green-500')
                    else:
                        # No scene loaded yet - show all passes but warn user
                        pass_options = {p['id']: p['name'] for p in all_passes}
                        with ui.row().classes('w-full items-center gap-2'):
                            ui.icon('info').classes('text-yellow-500 text-sm')
                            ui.label('Load a scene to see available passes').classes('text-xs text-yellow-500')
                    
                    # Multi-select for render passes
                    def on_passes_change(e):
                        # Ensure at least beauty is selected
                        if not e.value:
                            form['render_passes'] = ['beauty']
                        else:
                            form['render_passes'] = list(e.value)
                    
                    passes_select = ui.select(
                        options=pass_options,
                        value=form.get('render_passes', ['beauty']),
                        label='Select Passes',
                        multiple=True,
                        on_change=on_passes_change
                    ).classes('w-full').props('use-chips')
                    
                    # Show selected pass count and help text
                    pass_count = len(form.get('render_passes', ['beauty']))
                    ui.label(f'{pass_count} pass{"es" if pass_count != 1 else ""} selected').classes('text-xs text-gray-500')
                    
                    # Help text about adding passes
                    with ui.expansion('Need more passes?', icon='help_outline').classes('w-full text-xs mt-1').props('dense'):
                        ui.markdown('''
**To add render passes:**
1. Click "Open in Toolbag" above
2. In Toolbag: **Render â†’ Render Passes**
3. Click **"Add New"** and select passes
4. Save the scene (Ctrl+S)
5. Click **"Reload Scene Info"** in Wane

*Marmoset's API doesn't support adding passes programmatically, so they must be added manually in Toolbag first.*
                        ''').classes('text-xs text-gray-400')
                    
                    # Turntable-specific settings (show when turntable selected)
                    if form.get('render_type') == 'turntable':
                        with ui.row().classes('w-full items-center gap-2 mt-1'):
                            turntable_frames = ui.number('Turntable Frames', value=form.get('turntable_frames', 120), min=1).classes('w-36')
                            turntable_frames.bind_value(form, 'turntable_frames')
                            
                            video_format_select = ui.select(
                                options=['PNG Sequence', 'JPEG Sequence', 'TGA Sequence', 'MP4'],
                                value=form.get('video_format', 'PNG Sequence'),
                                label='Output Format'
                            ).classes('w-36')
                            video_format_select.bind_value(form, 'video_format')
                    
                    # Animation-specific video format (show when animation selected)
                    elif form.get('render_type') == 'animation':
                        with ui.row().classes('w-full items-center gap-2 mt-1'):
                            video_format_select = ui.select(
                                options=['PNG Sequence', 'JPEG Sequence', 'TGA Sequence', 'MP4'],
                                value=form.get('video_format', 'PNG Sequence'),
                                label='Output Format'
                            ).classes('w-36')
                            video_format_select.bind_value(form, 'video_format')
            
            marmoset_settings_container = marmoset_settings
            accent_elements['marmoset_settings'] = marmoset_settings
            marmoset_settings()
            
            # Accent separator
            ui.element('div').classes('accent-separator w-full my-2')
            
            # Submit paused
            ui.checkbox('Submit as Paused').props('dense').bind_value(form, 'submit_paused')
        
        # Footer
        with ui.row().classes('w-full justify-end gap-2 p-4 border-t border-zinc-700'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            
            def submit():
                if not form['file_path']:
                    print("Missing file path")
                    return
                if not form['output_folder']:
                    print("Missing output folder")
                    return
                
                # Build engine settings based on engine type
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
                    
                    # Adjust frame settings for turntable
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
                # Set initial progress based on frame range position in timeline
                if job.is_animation and job.frame_end > 0 and job.frame_start > 1:
                    job.progress = int(((job.frame_start - 1) / job.frame_end) * 100)
                render_app.add_job(job)
                dialog.close()
            
            initial_accent = ENGINE_ACCENT_COLORS.get(form['engine_type'], "#ea7600")
            submit_btn = ui.button('Submit Job', on_click=submit).classes('engine-accent').style(f'''
                background-color: {initial_accent} !important;
                transition: background-color 0.4s ease-in-out, transform 0.2s ease !important;
            ''')
            accent_elements['submit_btn'] = submit_btn
    
    dialog.open()


async def show_settings_dialog():
    with ui.dialog() as dialog, ui.card().style('width: 550px; max-width: 95vw; padding: 0;').classes('settings-dialog'):
        # Header
        with ui.row().classes('w-full items-center justify-between p-4 border-b border-zinc-700'):
            ui.label('Settings').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm').classes('text-zinc-400 settings-close-btn')
        
        # Content
        with ui.column().classes('w-full p-4 gap-4'):
            for engine in render_app.engine_registry.get_all():
                engine_logo = ENGINE_LOGOS.get(engine.engine_type)
                with ui.card().classes('w-full p-3 settings-engine-card'):
                    with ui.row().classes('items-center gap-2 mb-2'):
                        if engine_logo:
                            ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-6 h-6 object-contain')
                        ui.label(engine.name).classes('font-bold')
                        status = "[OK] Available" if engine.is_available else "[X] Not Found"
                        color = "text-zinc-400" if engine.is_available else "text-zinc-600"
                        ui.label(status).classes(f'{color} text-sm')
                    
                    if engine.installed_versions:
                        for v, p in sorted(engine.installed_versions.items(), reverse=True):
                            with ui.row().classes('items-center gap-2 mb-1'):
                                ui.badge(v).classes('version-badge').style('background-color: #3f3f46 !important; color: #e4e4e7 !important;')
                                ui.label(p).classes('text-xs text-gray-500 truncate').style('max-width: 350px')
                    else:
                        ui.label('No installations detected').classes('text-sm text-gray-500 mb-2')
                    
                    # Add custom path with browse button
                    with ui.row().classes('w-full gap-2 items-center'):
                        path_input = ui.input(placeholder='Path to executable...').classes('flex-grow text-xs')
                        
                        def browse_exe(eng=engine, inp=path_input):
                            def on_exe_selected(result):
                                if result:
                                    inp.value = result
                            
                            open_file_dialog_async(
                                f"Select {eng.name} Executable",
                                [('Executable', '*.exe'), ('All Files', '*.*')],
                                None,
                                on_exe_selected
                            )
                        
                        def add_custom(eng=engine, inp=path_input):
                            path = inp.value
                            if path and os.path.exists(path):
                                version = eng.add_custom_path(path)
                                if version:
                                    print(f"Added {eng.name} {version}")
                                    inp.value = ''
                            else:
                                print(f"Path not found: {path}")
                        
                        ui.button('Browse', icon='folder_open', on_click=lambda e=engine, i=path_input: browse_exe(e, i)).props('flat dense size=sm').classes('settings-action-btn')
                        ui.button('Add', icon='add', on_click=lambda e=engine, i=path_input: add_custom(e, i)).props('flat dense size=sm').classes('settings-action-btn')
        
        # Footer
        with ui.row().classes('w-full justify-end p-4 border-t border-zinc-700'):
            ui.button('Close', on_click=dialog.close).props('flat').classes('settings-close-btn-footer')
    
    dialog.open()


# ============================================================================
# MAIN PAGE
