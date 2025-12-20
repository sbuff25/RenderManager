"""
Wain UI - Main Page
The primary application page layout and UI.
"""

import os
import sys
from nicegui import ui, app

from wain.config import DARK_THEME, AVAILABLE_LOGOS, ASSET_VERSION, APP_VERSION
from wain.app import render_app
from wain.ui.components import create_stat_card, create_job_card
from wain.ui.dialogs import show_add_job_dialog, show_settings_dialog

@ui.page('/')
def main_page():
    ui.dark_mode().enable()
    ui.colors(**DARK_THEME['colors'])
    
    # Add CSS
    ui.add_head_html('''<style>
        *, *::before, *::after { box-sizing: border-box; }
        .responsive-container { width: 100%; max-width: 100%; padding: 1rem; overflow-x: hidden; }
        .stat-card { min-width: 150px; flex: 1 1 200px; }
        .job-card { width: 100%; }
        
        /* Hide NiceGUI reconnection notification - we're a desktop app */
        .q-notification, .q-notifications, .nicegui-reconnecting, 
        div[class*="reconnect"], div[class*="connection"] {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
        }
        
        .header-btn, .header-btn.q-btn { color: #a1a1aa !important; background-color: transparent !important; }
        .header-btn:hover, .header-btn.q-btn:hover { color: #ffffff !important; background-color: rgba(255, 255, 255, 0.1) !important; }
        .header-btn-primary, .header-btn-primary.q-btn { background-color: #3f3f46 !important; color: #ffffff !important; }
        .header-btn-primary:hover, .header-btn-primary.q-btn:hover { background-color: #52525b !important; }
        
        .job-action-btn:hover { color: #ffffff !important; background-color: rgba(255, 255, 255, 0.1) !important; }
        .job-action-btn-danger:hover { color: #f87171 !important; background-color: rgba(239, 68, 68, 0.15) !important; }
        .job-action-btn-engine-blender { color: #ea7600 !important; }
        .job-action-btn-engine-blender:hover { color: #ffffff !important; background-color: rgba(234, 118, 0, 0.2) !important; }
        .job-action-btn-engine-marmoset { color: #ef0343 !important; }
        .job-action-btn-engine-marmoset:hover { color: #ffffff !important; background-color: rgba(239, 3, 67, 0.2) !important; }
        .job-action-btn-engine-vantage { color: #77b22a !important; }
        .job-action-btn-engine-vantage:hover { color: #ffffff !important; background-color: rgba(119, 178, 42, 0.2) !important; }
        
        img[src*="wain_logo"], img[src*="wain_logo"] { filter: invert(1); border-radius: 8px; }
        
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #18181b; border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: #3f3f46; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #52525b; }
        
        .custom-progress-container { width: 100%; display: flex; flex-direction: column; gap: 4px; min-height: 28px; }
        .custom-progress-track { width: 100%; height: 8px; background: rgba(255, 255, 255, 0.15); border-radius: 4px; overflow: hidden; position: relative; }
        .custom-progress-fill { height: 100%; border-radius: 4px; position: relative; background: #71717a; will-change: width; }
        .custom-progress-label { text-align: center; font-size: 14px; color: #a1a1aa; }
        
        .custom-progress-rendering.custom-progress-engine-blender .custom-progress-fill { background: #ea7600; }
        .custom-progress-rendering.custom-progress-engine-marmoset .custom-progress-fill { background: #ef0343; }
        .custom-progress-rendering.custom-progress-engine-vantage .custom-progress-fill { background: #77b22a; }
        .custom-progress-queued .custom-progress-fill { background: #52525b; }
        .custom-progress-paused .custom-progress-fill { background: #a1a1aa; }
        .custom-progress-completed .custom-progress-fill { background: #22c55e; }
        .custom-progress-failed .custom-progress-fill { background: #ef4444; }
        
        .custom-progress-rendering .custom-progress-fill::after {
            content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.4) 50%, transparent 100%);
            animation: shimmer 2s ease-in-out infinite;
        }
        @keyframes shimmer { 0% { transform: translateX(-100%); opacity: 0; } 50% { opacity: 1; } 100% { transform: translateX(200%); opacity: 0; } }
        
        /* Status message styling with 3-dot loading animation */
        .job-status-message { 
            font-size: 12px; 
            color: #a1a1aa; 
            font-style: italic;
            margin-top: 4px;
        }
        .job-status-message::after {
            content: '';
            animation: dots 1.5s steps(4, end) infinite;
        }
        @keyframes dots {
            0%, 20% { content: ''; }
            40% { content: '.'; }
            60% { content: '..'; }
            80%, 100% { content: '...'; }
        }
    </style>''')
    
    # Add JavaScript for progress animation
    ui.add_head_html('''<script>
        document.addEventListener('DOMContentLoaded', function() {
            const progressState = {};
            window.updateJobProgress = function(jobId, progress, elapsed, framesDisplay, samplesDisplay, passDisplay, statusMsg) {
                const fill = document.getElementById('progress-fill-' + jobId);
                const label = document.getElementById('progress-label-' + jobId);
                const info = document.getElementById('job-info-' + jobId);
                const renderProgress = document.getElementById('job-render-progress-' + jobId);
                const statusMsgEl = document.getElementById('job-status-msg-' + jobId);
                
                if (fill) fill.dataset.target = progress;
                if (label) label.textContent = progress + '%';
                if (info && elapsed) {
                    var baseText = info.textContent;
                    if (renderProgress) baseText = baseText.replace(renderProgress.textContent, '').trim();
                    if (baseText.includes('Time:')) baseText = baseText.replace(/Time: [0-9:]+/, 'Time: ' + elapsed);
                    else baseText = baseText + ' | Time: ' + elapsed;
                    
                    var progressParts = [];
                    if (passDisplay && passDisplay.length > 0) progressParts.push(passDisplay);
                    if (framesDisplay && framesDisplay.length > 0 && framesDisplay.includes('/')) {
                        progressParts.push('Frame ' + framesDisplay);
                    }
                    if (samplesDisplay && samplesDisplay.length > 0) {
                        progressParts.push(samplesDisplay);
                    }
                    var progressText = progressParts.length > 0 ? ' | ' + progressParts.join(' | ') : '';
                    info.innerHTML = baseText + '<span id="job-render-progress-' + jobId + '">' + progressText + '</span>';
                }
                
                // Update status message
                if (statusMsg && statusMsg.length > 0) {
                    if (statusMsgEl) {
                        statusMsgEl.textContent = statusMsg;
                    } else {
                        // Create status message element if it doesn't exist
                        var infoEl = document.getElementById('job-info-' + jobId);
                        if (infoEl && infoEl.parentNode) {
                            var msgDiv = document.createElement('div');
                            msgDiv.id = 'job-status-msg-' + jobId;
                            msgDiv.className = 'job-status-message';
                            msgDiv.textContent = statusMsg;
                            infoEl.parentNode.insertBefore(msgDiv, infoEl.nextSibling);
                        }
                    }
                } else if (statusMsgEl) {
                    statusMsgEl.textContent = '';
                }
            };
            
            function animateProgressBars() {
                document.querySelectorAll('.custom-progress-fill[data-target]').forEach(function(fill) {
                    const id = fill.id;
                    if (!id) return;
                    const target = parseFloat(fill.dataset.target) || 0;
                    
                    if (!(id in progressState)) {
                        const inlineWidth = parseFloat(fill.style.width) || 0;
                        progressState[id] = inlineWidth > 0 ? inlineWidth : target;
                        if (inlineWidth <= 0) fill.style.width = target + '%';
                        return;
                    }
                    
                    const current = progressState[id];
                    const diff = target - current;
                    
                    if (Math.abs(diff) > 0.1) {
                        let step = diff * 0.06;
                        if (Math.abs(step) < 0.15 && Math.abs(diff) > 0.15) step = diff > 0 ? 0.15 : -0.15;
                        progressState[id] = current + step;
                        fill.style.width = progressState[id] + '%';
                    }
                });
                requestAnimationFrame(animateProgressBars);
            }
            requestAnimationFrame(animateProgressBars);
        });
    </script>''')
    
    with ui.header().classes('items-center justify-between px-4 md:px-6 py-3 bg-zinc-900'):
        with ui.row().classes('items-center gap-4'):
            wain_logo = AVAILABLE_LOGOS.get('wain')
            if wain_logo:
                ui.image(f'/logos/{wain_logo}?{ASSET_VERSION}').classes('w-10 h-10 object-contain rounded-lg')
            else:
                ui.label('WAIN').classes('text-xl font-bold text-white')
        
        with ui.row().classes('gap-2'):
            ui.button('Settings', icon='settings', on_click=show_settings_dialog).props('flat').classes('header-btn text-zinc-400')
            ui.button('Add Job', icon='add', on_click=show_add_job_dialog).props('flat').classes('header-btn-primary')
    
    with ui.column().classes('responsive-container gap-4'):
        @ui.refreshable
        def stats_section():
            with ui.row().classes('w-full gap-4 flex-wrap'):
                with ui.card().classes('stat-card'): create_stat_card('Rendering', 'rendering', 'play_circle', 'blue')
                with ui.card().classes('stat-card'): create_stat_card('Queued', 'queued', 'schedule', 'yellow')
                with ui.card().classes('stat-card'): create_stat_card('Completed', 'completed', 'check_circle', 'green')
                with ui.card().classes('stat-card'): create_stat_card('Failed', 'failed', 'error', 'red')
        
        render_app.stats_container = stats_section
        stats_section()
        
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Render Queue').classes('text-xl font-bold')
            @ui.refreshable
            def job_count():
                ui.label(f'{len(render_app.jobs)} jobs').classes('text-gray-400')
            render_app.job_count_container = job_count
            job_count()
        
        @ui.refreshable
        def queue_list():
            if not render_app.jobs:
                with ui.card().classes('w-full'):
                    with ui.column().classes('w-full items-center py-8'):
                        ui.icon('inbox').classes('text-6xl text-gray-600')
                        ui.label('No render jobs').classes('text-xl text-gray-400 mt-4')
                        ui.label('Click "Add Job" to get started').classes('text-gray-500')
            else:
                for job in render_app.jobs:
                    create_job_card(job)
        
        render_app.queue_container = queue_list
        queue_list()
        
        with ui.expansion('Log', icon='terminal').classes('w-full log-expansion'):
            with ui.row().classes('w-full items-center justify-between mb-2'):
                ui.label('Render Log').classes('text-sm text-gray-400')
                with ui.row().classes('gap-2'):
                    def save_log_to_file():
                        log_text = '\n'.join(render_app.log_messages[-500:])
                        log_path = os.path.join(os.getcwd(), 'wain_render_log.txt')
                        try:
                            with open(log_path, 'w', encoding='utf-8') as f:
                                f.write(log_text)
                            if sys.platform == 'win32':
                                os.startfile(log_path)
                            render_app.log(f"Log saved: {log_path}")
                        except Exception as e:
                            render_app.log(f"Save failed: {e}")
                    
                    def clear_log():
                        render_app.log_messages.clear()
                        render_app.log("Log cleared")
                        if render_app.log_container:
                            render_app.log_container.refresh()
                    
                    ui.button('Save Log to File', icon='save', on_click=save_log_to_file).props('flat dense').classes('text-zinc-300')
                    ui.button(icon='delete_sweep', on_click=clear_log).props('flat dense size=sm').classes('text-zinc-500').tooltip('Clear')
            
            @ui.refreshable
            def log_display():
                with ui.scroll_area().classes('w-full h-48 bg-zinc-900 rounded border border-zinc-700'):
                    with ui.column().classes('p-2 gap-0 font-mono text-xs w-full'):
                        for msg in render_app.log_messages[-100:]:
                            ui.label(msg).classes('text-gray-400 select-all cursor-text whitespace-pre-wrap break-all')
            
            render_app.log_container = log_display
            log_display()
    
    ui.timer(0.25, render_app.process_queue)
    
    render_app.log(f"Wain v{APP_VERSION} started")
    
    for engine in render_app.engine_registry.get_all():
        if engine.is_available:
            render_app.log(f"Found: {engine.version_display}")
        else:
            render_app.log(f"Not found: {engine.name}")
    render_app.log(f"Loaded {len(render_app.jobs)} jobs")
