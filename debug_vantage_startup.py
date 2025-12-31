#!/usr/bin/env python3
"""
Vantage Startup Debug Monitor
==============================

Comprehensive logging of everything that happens during Vantage startup.
Use this with a LARGE SCENE to understand the full loading process.

What it monitors:
- Window title changes (loading indicators, progress %)
- Window responsiveness (can we enumerate elements?)
- UI element counts (buttons, checkboxes, panes)
- Specific controls (Pause Rendering, Lights panel, etc.)
- Process CPU/memory usage
- Time to various milestones

Usage:
    python debug_vantage_startup.py "C:/path/to/large_scene.vantage"
    
Or run without arguments to just monitor an already-open Vantage.

Output:
    - Console output with timestamps
    - vantage_startup_log.txt with full details

https://github.com/Spencer-Sliffe/Wain
"""

import sys
import os
import time
import subprocess
import argparse
from datetime import datetime

# Log file
LOG_FILE = "vantage_startup_log.txt"
log_file_handle = None

def log(msg, level="INFO"):
    """Log message with timestamp to console and file."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    elapsed = time.time() - start_time if 'start_time' in globals() else 0
    line = f"[{timestamp}] [{elapsed:7.2f}s] [{level:5}] {msg}"
    print(line)
    if log_file_handle:
        log_file_handle.write(line + "\n")
        log_file_handle.flush()

def get_process_info(process_name="vantage.exe"):
    """Get CPU and memory usage for Vantage process."""
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
            if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                cpu = proc.cpu_percent(interval=0.1)
                mem_mb = proc.info['memory_info'].rss / (1024 * 1024) if proc.info['memory_info'] else 0
                return cpu, mem_mb
    except ImportError:
        pass
    except Exception:
        pass
    return None, None

def find_vantage_window(desktop):
    """Find Vantage main window."""
    for win in desktop.windows():
        try:
            class_name = win.element_info.class_name or ""
            if "LavinaMainWindow" in class_name:
                return win
        except:
            pass
    
    # Fallback by title
    for win in desktop.windows():
        try:
            title = win.window_text().lower()
            if "vantage" in title:
                return win
        except:
            pass
    return None

def count_elements(window, control_type, timeout=2.0):
    """Count elements of a type with timeout."""
    try:
        start = time.time()
        count = 0
        for elem in window.descendants(control_type=control_type):
            if time.time() - start > timeout:
                return count, True  # Timed out
            count += 1
        return count, False
    except Exception as e:
        return -1, False

def check_specific_controls(window):
    """Check for specific controls that indicate readiness."""
    results = {
        'pause_rendering': False,
        'lights_panel': False,
        'scene_panel': False,
        'camera_panel': False,
        'environment_panel': False,
        'start_button': False,
        'menu_bar': False,
    }
    
    try:
        # Quick search with timeout
        search_start = time.time()
        
        for elem in window.descendants():
            if time.time() - search_start > 3.0:
                break
            
            try:
                name = (elem.element_info.name or "").lower()
                ctrl_type = elem.element_info.control_type or ""
                auto_id = (elem.element_info.automation_id or "").lower()
                
                if "pause rendering" in name and ctrl_type == "CheckBox":
                    results['pause_rendering'] = True
                elif name == "lights" and ctrl_type in ["Pane", "TabItem", "TreeItem"]:
                    results['lights_panel'] = True
                elif name == "scene" and ctrl_type in ["Pane", "TabItem", "TreeItem"]:
                    results['scene_panel'] = True
                elif name == "camera" and ctrl_type in ["Pane", "TabItem", "TreeItem"]:
                    results['camera_panel'] = True
                elif name == "environment" and ctrl_type in ["Pane", "TabItem", "TreeItem"]:
                    results['environment_panel'] = True
                elif "start" in name and ctrl_type == "Button":
                    results['start_button'] = True
                elif auto_id == "primarybutton":
                    results['start_button'] = True
                elif ctrl_type == "MenuBar":
                    results['menu_bar'] = True
            except:
                pass
    except Exception as e:
        log(f"Error checking controls: {e}", "WARN")
    
    return results

def test_window_responsiveness(window):
    """Test how quickly we can interact with the window."""
    try:
        start = time.time()
        # Try to get children (fast operation)
        children = list(window.children())
        child_time = time.time() - start
        
        # Try to get window title (should be instant)
        start = time.time()
        title = window.window_text()
        title_time = time.time() - start
        
        # Try to enumerate some descendants (slower)
        start = time.time()
        count = 0
        for elem in window.descendants(control_type="Button"):
            count += 1
            if count >= 10 or time.time() - start > 2.0:
                break
        button_time = time.time() - start
        
        return {
            'children_count': len(children),
            'children_time': child_time,
            'title': title,
            'title_time': title_time,
            'button_count': count,
            'button_time': button_time,
            'responsive': child_time < 1.0 and button_time < 2.0
        }
    except Exception as e:
        return {
            'error': str(e),
            'responsive': False
        }

def parse_title_for_loading(title):
    """Parse window title for loading indicators."""
    title_lower = title.lower()
    
    result = {
        'is_loading': False,
        'progress_pct': None,
        'scene_name': None,
        'indicators': []
    }
    
    # Check for loading indicators
    if "loading" in title_lower:
        result['is_loading'] = True
        result['indicators'].append("'loading' in title")
    
    if "importing" in title_lower:
        result['is_loading'] = True
        result['indicators'].append("'importing' in title")
    
    if "initializing" in title_lower:
        result['is_loading'] = True
        result['indicators'].append("'initializing' in title")
    
    if "please wait" in title_lower:
        result['is_loading'] = True
        result['indicators'].append("'please wait' in title")
    
    # Check for percentage
    import re
    pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', title)
    if pct_match:
        result['progress_pct'] = float(pct_match.group(1))
        result['is_loading'] = True
        result['indicators'].append(f"progress: {result['progress_pct']}%")
    
    # Extract scene name
    if ".vantage" in title_lower:
        # Try to extract filename
        match = re.search(r'[\\/]?([^\\/]+\.vantage)', title, re.IGNORECASE)
        if match:
            result['scene_name'] = match.group(1)
    
    return result

def main():
    global start_time, log_file_handle
    
    parser = argparse.ArgumentParser(description='Monitor Vantage startup process')
    parser.add_argument('scene_file', nargs='?', help='Path to .vantage scene file to open')
    parser.add_argument('--duration', type=int, default=300, help='How long to monitor (seconds, default 300)')
    parser.add_argument('--interval', type=float, default=1.0, help='Polling interval (seconds, default 1.0)')
    args = parser.parse_args()
    
    # Open log file
    log_file_handle = open(LOG_FILE, 'w', encoding='utf-8')
    
    start_time = time.time()
    
    log("=" * 70)
    log("VANTAGE STARTUP DEBUG MONITOR")
    log("=" * 70)
    log(f"Log file: {os.path.abspath(LOG_FILE)}")
    log(f"Duration: {args.duration}s, Interval: {args.interval}s")
    
    if args.scene_file:
        log(f"Scene file: {args.scene_file}")
    else:
        log("No scene file specified - will monitor existing Vantage instance")
    
    log("")
    
    # Check for pywinauto
    try:
        from pywinauto import Desktop
    except ImportError:
        log("ERROR: pywinauto not installed. Run: pip install pywinauto", "ERROR")
        return
    
    # Check for psutil (optional)
    has_psutil = False
    try:
        import psutil
        has_psutil = True
        log("psutil available - will monitor CPU/memory")
    except ImportError:
        log("psutil not available - skipping CPU/memory monitoring (pip install psutil)")
    
    log("")
    
    # Find Vantage executable
    vantage_exe = None
    search_paths = [
        r"C:\Program Files\Chaos\Vantage\vantage.exe",
        r"C:\Program Files\Chaos Group\Vantage\vantage.exe",
        r"C:\Program Files\Chaos\Vantage 3\vantage.exe",
    ]
    for path in search_paths:
        if os.path.exists(path):
            vantage_exe = path
            break
    
    if vantage_exe:
        log(f"Found Vantage: {vantage_exe}")
    else:
        log("Vantage executable not found in standard locations", "WARN")
    
    log("")
    log("=" * 70)
    log("STARTING MONITOR")
    log("=" * 70)
    log("")
    
    # Launch Vantage if scene file provided
    if args.scene_file and vantage_exe:
        if not os.path.exists(args.scene_file):
            log(f"Scene file not found: {args.scene_file}", "ERROR")
            return
        
        log(f"Launching Vantage with scene: {os.path.basename(args.scene_file)}")
        try:
            subprocess.Popen([vantage_exe, args.scene_file], 
                           creationflags=subprocess.DETACHED_PROCESS)
            log("Launch command sent")
        except Exception as e:
            log(f"Launch error: {e}", "ERROR")
            return
    
    # Monitoring state
    last_title = ""
    last_controls = {}
    window_found_time = None
    scene_loaded_time = None
    milestones = []
    
    def record_milestone(name):
        elapsed = time.time() - start_time
        milestones.append((elapsed, name))
        log(f"*** MILESTONE: {name} ***", "MILE")
    
    # Main monitoring loop
    poll_count = 0
    
    while time.time() - start_time < args.duration:
        poll_count += 1
        elapsed = time.time() - start_time
        
        try:
            desktop = Desktop(backend="uia")
            window = find_vantage_window(desktop)
            
            if not window:
                if poll_count % 5 == 1:  # Log every 5 polls
                    log("Waiting for Vantage window...")
                time.sleep(args.interval)
                continue
            
            # Window found!
            if window_found_time is None:
                window_found_time = elapsed
                record_milestone(f"Window found ({elapsed:.1f}s)")
            
            # Get window title
            try:
                title = window.window_text()
            except:
                title = "(could not read title)"
            
            # Parse title for loading info
            title_info = parse_title_for_loading(title)
            
            # Log title changes
            if title != last_title:
                log(f"TITLE: '{title}'")
                if title_info['is_loading']:
                    log(f"  Loading indicators: {title_info['indicators']}")
                if title_info['scene_name']:
                    log(f"  Scene: {title_info['scene_name']}")
                last_title = title
            
            # Get process info
            if has_psutil:
                cpu, mem = get_process_info()
                if cpu is not None:
                    # Only log significant CPU activity
                    if poll_count % 10 == 0 or cpu > 50:
                        log(f"PROCESS: CPU={cpu:.1f}%, Memory={mem:.0f}MB")
            
            # Test responsiveness
            resp = test_window_responsiveness(window)
            
            if 'error' in resp:
                log(f"RESPONSIVENESS: Error - {resp['error']}", "WARN")
            else:
                responsive_str = "YES" if resp['responsive'] else "NO"
                log(f"RESPONSIVE: {responsive_str} | children={resp['children_count']} ({resp['children_time']:.2f}s) | buttons={resp['button_count']} ({resp['button_time']:.2f}s)")
            
            # Check specific controls
            controls = check_specific_controls(window)
            
            # Log control changes
            for key, value in controls.items():
                if value and not last_controls.get(key, False):
                    record_milestone(f"Control appeared: {key}")
            
            # Summary of available controls
            available = [k for k, v in controls.items() if v]
            if available:
                log(f"CONTROLS: {', '.join(available)}")
            
            last_controls = controls.copy()
            
            # Check if scene appears loaded
            if not title_info['is_loading'] and resp.get('responsive', False):
                if controls.get('pause_rendering') or controls.get('menu_bar'):
                    if scene_loaded_time is None:
                        scene_loaded_time = elapsed
                        record_milestone(f"Scene appears LOADED ({elapsed:.1f}s)")
            
            # Count elements (every 10 polls to avoid slowdown)
            if poll_count % 10 == 0:
                log("--- Element counts ---")
                for ctrl_type in ["Button", "CheckBox", "Edit", "Pane"]:
                    count, timed_out = count_elements(window, ctrl_type, timeout=1.0)
                    timeout_str = " (timed out)" if timed_out else ""
                    log(f"  {ctrl_type}: {count}{timeout_str}")
            
            log("")
            
        except Exception as e:
            log(f"Error during monitoring: {e}", "ERROR")
        
        time.sleep(args.interval)
    
    # Summary
    log("")
    log("=" * 70)
    log("MONITORING COMPLETE - SUMMARY")
    log("=" * 70)
    log("")
    
    log(f"Total monitoring time: {time.time() - start_time:.1f}s")
    log(f"Total polls: {poll_count}")
    log("")
    
    if milestones:
        log("MILESTONES:")
        for elapsed, name in milestones:
            log(f"  [{elapsed:7.2f}s] {name}")
    else:
        log("No milestones recorded")
    
    log("")
    log(f"Window found: {window_found_time:.1f}s" if window_found_time else "Window never found")
    log(f"Scene loaded: {scene_loaded_time:.1f}s" if scene_loaded_time else "Scene never detected as loaded")
    
    if window_found_time and scene_loaded_time:
        load_time = scene_loaded_time - window_found_time
        log(f"Load time (after window): {load_time:.1f}s")
    
    log("")
    log(f"Full log saved to: {os.path.abspath(LOG_FILE)}")
    log("=" * 70)
    
    if log_file_handle:
        log_file_handle.close()

if __name__ == "__main__":
    main()
