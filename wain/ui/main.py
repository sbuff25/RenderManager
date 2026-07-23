"""
Wain UI - Main Page
The primary application page layout and UI.
"""

import os
import sys
from nicegui import ui, app

from wain.config import DARK_THEME, AVAILABLE_LOGOS, ASSET_VERSION, APP_VERSION
from wain.app import render_app
from wain.ui.components import create_stat_card, create_job_card, create_network_card
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

        /* v2.19.3 visual polish — surfaces
           GPU compositing is on by default (see __main__.py), so shadows and
           gradients are fine. If running with --software-ui, expect these to
           cost CPU paint time. Avoid background-attachment:fixed regardless —
           it forces full-page repaints on scroll even with GPU in QtWebEngine. */
        /* html must be dark too — it's the layer that shows through during
           GPU surface creation (white flash when menus/popups open) */
        html { background: #121212; }
        body.body--dark { background: linear-gradient(180deg, #161618 0%, #0e0e10 100%) !important; }
        .q-card {
            background: #1d1d1d !important;
            border: 1px solid #27272a;
            border-radius: 10px !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4) !important;
        }
        .q-header { border-bottom: 1px solid #27272a; }
        .q-dialog__inner > .q-card {
            border-radius: 12px !important;
            border: 1px solid #303036;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6) !important;
        }
        .wain-wordmark { font-size: 18px; font-weight: 700; color: #ffffff; letter-spacing: 0.01em; }
        .wain-version-chip {
            background: #27272a; color: #71717a; font-size: 11px; font-weight: 500;
            padding: 3px 8px; border-radius: 10px; line-height: 1;
        }
        .stat-icon-chip {
            width: 42px; height: 42px; border-radius: 10px;
            display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }
        .log-expansion { border: 1px solid #27272a; border-radius: 10px; overflow: hidden; }
        /* SortableJS drag states (v2.25.2) - cosmetic queue reordering */
        .job-card-draggable { cursor: grab; }
        .job-card-draggable:active { cursor: grabbing; }
        .job-card-ghost { opacity: 0.35; border: 1px dashed #52525b !important; }
        .job-card-chosen { box-shadow: 0 8px 24px rgba(0,0,0,0.5) !important; transform: scale(1.01); }
        
        /* Hide NiceGUI reconnection notification - we're a desktop app */
        .q-notification, .q-notifications, .nicegui-reconnecting, 
        div[class*="reconnect"], div[class*="connection"] {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
        }
        
        .header-btn, .header-btn.q-btn { color: #a1a1aa !important; background-color: transparent !important; }
        .header-btn:hover, .header-btn.q-btn:hover { color: #ffffff !important; background-color: rgba(255, 255, 255, 0.1) !important; }
        .header-btn-primary, .header-btn-primary.q-btn {
            background: linear-gradient(180deg, #4a4a52 0%, #3a3a40 100%) !important;
            border: 1px solid #52525b !important;
            border-radius: 6px !important;
            color: #ffffff !important;
        }
        .header-btn-primary:hover, .header-btn-primary.q-btn:hover { background: linear-gradient(180deg, #56565e 0%, #46464c 100%) !important; }
        
        .job-action-btn:hover { color: #ffffff !important; background-color: rgba(255, 255, 255, 0.1) !important; }
        .job-action-btn-danger:hover { color: #f87171 !important; background-color: rgba(239, 68, 68, 0.15) !important; }
        .job-action-btn-engine-blender { color: #ea7600 !important; }
        .job-action-btn-engine-blender:hover { color: #ffffff !important; background-color: rgba(234, 118, 0, 0.2) !important; }
        .job-action-btn-engine-marmoset { color: #ef0343 !important; }
        .job-action-btn-engine-marmoset:hover { color: #ffffff !important; background-color: rgba(239, 3, 67, 0.2) !important; }
        .job-action-btn-engine-vantage { color: #77b22a !important; }
        .job-action-btn-engine-vantage:hover { color: #ffffff !important; background-color: rgba(119, 178, 42, 0.2) !important; }
        
        /* New wagon logo is dark-friendly full art — no invert needed (v2.19.0) */
        img[src*="wain_logo"] { border-radius: 8px; }
        
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #18181b; border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: #3f3f46; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #52525b; }
        
        .custom-progress-container { width: 100%; display: flex; flex-direction: column; gap: 4px; min-height: 30px; }
        .custom-progress-track { width: 100%; height: 10px; background: rgba(255, 255, 255, 0.08); border-radius: 5px; overflow: hidden; position: relative; }
        .custom-progress-fill { height: 100%; border-radius: 5px; position: relative; background: #71717a; will-change: width; transform: translateZ(0); }
        .custom-progress-label { text-align: center; font-size: 14px; color: #a1a1aa; }

        /* v2.19.3 — gradient fills with engine glows (GPU compositing handles
           the animated-width + blur combination fine) */
        .custom-progress-rendering.custom-progress-engine-blender .custom-progress-fill {
            background: linear-gradient(90deg, #ea7600 0%, #f1a659 100%);
            box-shadow: 0 0 6px rgba(234, 118, 0, 0.45);
        }
        .custom-progress-rendering.custom-progress-engine-marmoset .custom-progress-fill {
            background: linear-gradient(90deg, #ef0343 0%, #f55b85 100%);
            box-shadow: 0 0 6px rgba(239, 3, 67, 0.45);
        }
        .custom-progress-rendering.custom-progress-engine-vantage .custom-progress-fill {
            background: linear-gradient(90deg, #77b22a 0%, #a6cd74 100%);
            box-shadow: 0 0 6px rgba(119, 178, 42, 0.45);
        }
        .custom-progress-queued .custom-progress-fill { background: linear-gradient(90deg, #52525b 0%, #797981 100%); }
        .custom-progress-paused .custom-progress-fill { background: linear-gradient(90deg, #a1a1aa 0%, #c2c2c8 100%); }
        .custom-progress-completed .custom-progress-fill {
            background: linear-gradient(90deg, #22c55e 0%, #6fd996 100%);
            box-shadow: 0 0 6px rgba(34, 197, 94, 0.45);
        }
        .custom-progress-failed .custom-progress-fill {
            background: linear-gradient(90deg, #ef4444 0%, #f58585 100%);
            box-shadow: 0 0 6px rgba(239, 68, 68, 0.45);
        }
        
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

        /* Smooth dialog rendering */
        .q-dialog__inner > .q-card {
            will-change: transform, opacity;
            contain: content;
        }
        .q-dialog__backdrop {
            transition: opacity 150ms ease !important;
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
                if (info) {
                    var baseText = info.textContent;
                    if (renderProgress) baseText = baseText.replace(renderProgress.textContent, '').trim();
                    if (elapsed) {
                        if (baseText.includes('Time:')) baseText = baseText.replace(/Time: [0-9:]+/, 'Time: ' + elapsed);
                        else baseText = baseText + ' | Time: ' + elapsed;
                    }

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
            
            let frameToggle = false;
            function animateProgressBars() {
                // Skip animation when a dialog is open to free up frame budget
                if (document.querySelector('.q-dialog')) {
                    requestAnimationFrame(animateProgressBars);
                    return;
                }
                // v2.19.1 — run at half frame rate; style writes/paints are the
                // expensive part, and 30fps is indistinguishable for progress bars
                frameToggle = !frameToggle;
                if (frameToggle) {
                    requestAnimationFrame(animateProgressBars);
                    return;
                }
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
                        let step = diff * 0.12;  // doubled: loop runs at half rate (v2.19.1)
                        if (Math.abs(step) < 0.3 && Math.abs(diff) > 0.3) step = diff > 0 ? 0.3 : -0.3;
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
        with ui.row().classes('items-center gap-3'):
            wain_logo = AVAILABLE_LOGOS.get('wain')
            if wain_logo:
                ui.image(f'/logos/{wain_logo}?{ASSET_VERSION}').classes('w-10 h-10 object-contain rounded-lg')
            ui.label('Wain').classes('wain-wordmark')
            ui.label(f'v{APP_VERSION}').classes('wain-version-chip')
        
        with ui.row().classes('gap-2'):
            ui.button('Settings', icon='settings', on_click=show_settings_dialog).props('flat').classes('header-btn text-zinc-400')
            ui.button('Add Job', icon='add', on_click=show_add_job_dialog).props('flat').classes('header-btn-primary')
    
    with ui.column().classes('responsive-container gap-4'):
        with ui.row().classes('w-full gap-4 flex-wrap items-stretch'):
            @ui.refreshable
            def stats_section():
                with ui.row().classes('gap-4 flex-wrap'):
                    with ui.card().classes('stat-card'): create_stat_card('Rendering', 'rendering', 'play_circle', 'blue')
                    with ui.card().classes('stat-card'): create_stat_card('Queued', 'queued', 'schedule', 'yellow')
                    with ui.card().classes('stat-card'): create_stat_card('Completed', 'completed', 'check_circle', 'green')
                    with ui.card().classes('stat-card'): create_stat_card('Failed', 'failed', 'error', 'red')

            render_app.stats_container = stats_section
            stats_section()
            # Live network throughput (v2.22.0) - outside the refreshable so
            # its timer/chart survive queue refreshes
            create_network_card()
        
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Render Queue').classes('text-xl font-bold')
            @ui.refreshable
            def job_count():
                ui.label(f'{len(render_app.jobs)} jobs').classes('text-gray-400')
            render_app.job_count_container = job_count
            job_count()
        
        # Smooth drag-to-reorder (v2.25.2): the card column is a SortableJS
        # list - cards animate out of the way while dragging. Cosmetic only.
        ui.add_body_html(f'<script src="/logos/Sortable.min.js?{ASSET_VERSION}"></script>')

        _SORTABLE_INIT_JS = '''
            (function () {
                const el = document.getElementById('wain-job-queue');
                if (!el || !window.Sortable) return;
                if (el._wainSortable) { el._wainSortable.destroy(); }
                el._wainSortable = Sortable.create(el, {
                    animation: 220,
                    easing: 'cubic-bezier(0.25, 1, 0.5, 1)',
                    ghostClass: 'job-card-ghost',
                    chosenClass: 'job-card-chosen',
                    // Buttons/inputs never initiate a drag (but still click
                    // normally) - prevents pause/play/delete misfires while
                    // grabbing a card
                    filter: '.q-btn, button, a, input, .q-checkbox, .q-select',
                    preventOnFilter: false,
                    // Small hold-to-drag delay so quick clicks are never
                    // interpreted as drags
                    delay: 120,
                    delayOnTouchOnly: false,
                    onEnd: function (evt) {
                        if (evt.oldIndex !== evt.newIndex) {
                            emitEvent('wain_job_reorder', {o: evt.oldIndex, n: evt.newIndex});
                        }
                    },
                });
            })();
        '''

        ui.on('wain_job_reorder',
              lambda e: render_app.reorder_job_index(e.args.get('o'), e.args.get('n')))

        @ui.refreshable
        def queue_list():
            if not render_app.jobs:
                with ui.card().classes('w-full'):
                    with ui.column().classes('w-full items-center py-10'):
                        wagon_logo = AVAILABLE_LOGOS.get('wain')
                        if wagon_logo:
                            ui.image(f'/logos/{wagon_logo}?{ASSET_VERSION}').classes('w-28 h-28 object-contain').style('opacity: 0.35;')
                        else:
                            ui.icon('inbox').classes('text-6xl text-gray-600')
                        ui.label('The wagon is empty').classes('text-lg font-bold text-zinc-400 mt-3')
                        ui.label('Click "Add Job" to load it up').classes('text-sm text-gray-500')
            else:
                with ui.column().classes('w-full gap-4').props('id=wain-job-queue'):
                    for job in render_app.jobs:
                        create_job_card(job)
                # (Re)attach SortableJS after this refresh lands in the DOM
                ui.timer(0.15, lambda: ui.run_javascript(_SORTABLE_INIT_JS), once=True)

        render_app.queue_container = queue_list
        queue_list()
        
        with ui.expansion('Log', icon='terminal').classes('w-full log-expansion'):
            with ui.row().classes('w-full items-center justify-between mb-2'):
                ui.label('Render Log').classes('text-sm text-gray-400')
                with ui.row().classes('gap-2'):
                    def save_log_to_file():
                        from wain.config import RENDER_LOG_FILE
                        log_text = '\n'.join(render_app.log_messages[-500:])
                        log_path = RENDER_LOG_FILE
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
    
    # Workers panel (refreshable — shows/hides based on network mode)
    @ui.refreshable
    def network_panel():
        if not render_app.network_mode:
            return

        with ui.column().classes('w-full gap-2 mt-4'):
            @ui.refreshable
            def workers_section():
                workers = render_app.db.get_workers() if render_app.db else []
                connected = [w for w in workers if not w.get("is_stale") and w.get("status") != "offline"]
                offline = [w for w in workers if w.get("is_stale") or w.get("status") == "offline"]

                with ui.row().classes('w-full items-center justify-between'):
                    ui.label('Workers').classes('text-xl font-bold')
                    with ui.row().classes('gap-3 items-center'):
                        if connected:
                            ui.label(f'{len(connected)} connected').style('color: #22c55e; font-size: 14px;')
                        if offline:
                            ui.label(f'{len(offline)} offline').style('color: #71717a; font-size: 14px;')

                if not workers:
                    with ui.card().classes('w-full'):
                        with ui.column().classes('w-full items-center py-4'):
                            ui.icon('devices').classes('text-4xl text-gray-600')
                            ui.label('No workers connected').classes('text-gray-400 mt-2')
                            ui.label('Start a worker with: python -m wain --worker --server <this-ip>:8080').classes('text-gray-500 text-sm')
                else:
                    for w in workers:
                        is_stale = w.get("is_stale", False)
                        w_status = w.get("status", "offline")

                        # Determine visual state
                        if w_status == "offline" or is_stale:
                            icon_name = 'cloud_off'
                            icon_color = '#71717a'    # Gray
                            status_text = 'OFFLINE'
                            status_color = '#71717a'
                            border_color = '#27272a'
                        elif w_status == "rendering":
                            icon_name = 'cloud_done'
                            icon_color = '#22c55e'    # Green
                            status_text = 'RENDERING'
                            status_color = '#22c55e'
                            border_color = '#166534'
                        else:
                            # idle / connected
                            icon_name = 'cloud_done'
                            icon_color = '#3b82f6'    # Blue
                            status_text = 'CONNECTED'
                            status_color = '#3b82f6'
                            border_color = '#1e3a5f'

                        with ui.card().classes('w-full').style(f'border-left: 3px solid {border_color};'):
                            with ui.row().classes('w-full items-center gap-3 px-4 py-2'):
                                ui.icon(icon_name).style(f'color: {icon_color}; font-size: 24px;')
                                with ui.column().classes('gap-0 flex-1'):
                                    ui.label(w.get("worker_id", "Unknown")).classes('font-bold text-white')
                                    detail = f'{w.get("hostname", "")} ({w.get("ip_address", "")})'
                                    ui.label(detail).classes('text-sm text-gray-400')
                                    # Show last heartbeat time for offline workers
                                    if w_status == "offline" or is_stale:
                                        last_hb = w.get("last_heartbeat", "")
                                        if last_hb:
                                            ui.label(f'Last seen: {last_hb}').classes('text-xs text-gray-600')
                                with ui.column().classes('gap-0 items-end'):
                                    ui.label(status_text).style(
                                        f'color: {status_color}; font-size: 12px; font-weight: 600; '
                                        f'letter-spacing: 0.05em;'
                                    )
                                    if w.get("current_job_id") and w_status == "rendering":
                                        ui.label(f'Job: {w["current_job_id"]}').classes('text-xs text-gray-500')

            render_app.workers_container = workers_section
            workers_section()

    render_app.network_panel = network_panel
    network_panel()

    # Periodic timers — callbacks are safe when network mode is off
    def _periodic_workers_refresh():
        if render_app.network_mode and render_app.workers_container:
            try:
                render_app.workers_container.refresh()
            except Exception:
                pass

    ui.timer(5.0, _periodic_workers_refresh)
    ui.timer(2.0, render_app.sync_from_db)
    ui.timer(0.25, render_app.process_queue)

    render_app.log(f"Wain v{APP_VERSION} started")
    if render_app.network_mode:
        render_app.log("Network mode enabled — REST API active")

    for engine in render_app.engine_registry.get_all():
        if engine.is_available:
            render_app.log(f"Found: {engine.version_display}")
        else:
            render_app.log(f"Not found: {engine.name}")
    render_app.log(f"Loaded {len(render_app.jobs)} jobs")
