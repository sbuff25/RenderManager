#!/usr/bin/env python3
"""
Vantage Startup Debug Monitor v3
=================================

Comprehensive logging of EVERYTHING during Vantage startup with a large scene.
This will help identify exactly when the scene is truly loaded vs when Wain
thinks it can send commands.

v3 Fixes:
- Fixed false window detection (was matching File Explorer windows!)
- Now requires class "LavinaMainWindow" or title STARTING WITH "Chaos Vantage"
- Only pause_rendering checkbox triggers "LOADED" state (menu_bar is unreliable)

What it monitors (every second):
- Window title (loading indicators, percentages, scene name)
- Window class and state
- Whether window is responding to UI queries
- How long UI queries take (slowdown = still loading)
- Specific controls: Pause button, Menu bar, Panels
- Which buttons/controls exist
- CPU usage (if psutil installed)

Usage:
    python debug_vantage_startup.py "C:/path/to/large_scene.vantage"
    python debug_vantage_startup.py  (monitor already-open Vantage)

Output:
    - Real-time console output
    - vantage_startup_log.txt with full details

https://github.com/Spencer-Sliffe/Wain
"""

import sys
import os
import time
import subprocess
import argparse
from datetime import datetime

# Globals
start_time = None
log_handle = None
LOG_FILE = "vantage_startup_log.txt"

def log(msg, level="INFO"):
    """Log with timestamp and elapsed time."""
    global start_time, log_handle
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    elapsed = time.time() - start_time if start_time else 0
    line = f"[{ts}] [{elapsed:7.2f}s] [{level:5}] {msg}"
    print(line)
    if log_handle:
        log_handle.write(line + "\n")
        log_handle.flush()

def find_vantage_exe():
    """Find Vantage executable."""
    paths = [
        r"C:\Program Files\Chaos\Vantage\vantage.exe",
        r"C:\Program Files\Chaos Group\Vantage\vantage.exe",
        r"C:\Program Files\Chaos\Vantage 3\vantage.exe",
        r"C:\Program Files\Chaos\Vantage 2\vantage.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def find_vantage_window(desktop):
    """
    Find main Vantage window.
    
    CRITICAL: Must NOT match File Explorer windows that have "Vantage" in folder name!
    
    Detection priority:
    1. Window class "LavinaMainWindow" (100% reliable for Vantage)
    2. Title STARTS WITH "Chaos Vantage" (not just contains "vantage")
    """
    # Method 1: By class name (most reliable - only Vantage has this)
    for win in desktop.windows():
        try:
            cls = win.element_info.class_name or ""
            if "LavinaMainWindow" in cls:
                return win
        except:
            pass
    
    # Method 2: Title must START WITH "Chaos Vantage"
    # This avoids matching File Explorer windows with folders named "Vantage-ProjectName"
    for win in desktop.windows():
        try:
            title = (win.window_text() or "")
            if title.lower().startswith("chaos vantage"):
                return win
        except:
            pass
    return None

def safe_get_title(window):
    """Get window title safely with timing."""
    try:
        t0 = time.time()
        title = window.window_text() or "(empty)"
        duration = time.time() - t0
        return title, duration
    except Exception as e:
        return f"(error: {e})", 0

def safe_get_children_count(window):
    """Count direct children with timing."""
    try:
        t0 = time.time()
        children = list(window.children())
        duration = time.time() - t0
        return len(children), duration
    except Exception as e:
        return -1, 0

def safe_count_controls(window, control_type, max_time=3.0):
    """Count controls of a type with timeout."""
    try:
        t0 = time.time()
        count = 0
        for elem in window.descendants(control_type=control_type):
            count += 1
            if time.time() - t0 > max_time:
                return count, time.time() - t0, True  # Timed out
        return count, time.time() - t0, False
    except Exception as e:
        return -1, 0, False

def find_specific_controls(window, max_time=5.0):
    """
    Search for specific controls that indicate load state.
    Returns dict of what was found and timing info.
    """
    results = {
        'pause_rendering_checkbox': None,
        'menu_bar': None,
        'start_button': None,
        'toolbar': None,
        'lights_panel': None,
        'any_checkbox': None,
        'any_edit': None,
        'search_time': 0,
        'timed_out': False,
        'total_elements_checked': 0,
    }
    
    try:
        t0 = time.time()
        checked = 0
        
        for elem in window.descendants():
            checked += 1
            if time.time() - t0 > max_time:
                results['timed_out'] = True
                break
            
            try:
                name = (elem.element_info.name or "").lower()
                ctrl_type = elem.element_info.control_type or ""
                auto_id = (elem.element_info.automation_id or "").lower()
                class_name = (elem.element_info.class_name or "").lower()
                
                # Pause Rendering checkbox (key indicator)
                if "pause rendering" in name and ctrl_type == "CheckBox":
                    results['pause_rendering_checkbox'] = elem.element_info.name
                
                # Menu bar
                if ctrl_type == "MenuBar":
                    results['menu_bar'] = True
                
                # Start button (HQ panel open)
                if ctrl_type == "Button" and ("start" in name or auto_id == "primarybutton"):
                    results['start_button'] = elem.element_info.name or auto_id
                
                # Toolbar
                if ctrl_type == "ToolBar":
                    results['toolbar'] = True
                
                # Lights panel
                if "lights" in name and ctrl_type in ["Pane", "TreeItem", "TabItem"]:
                    results['lights_panel'] = True
                
                # Any checkbox (indicates UI is populated)
                if ctrl_type == "CheckBox" and results['any_checkbox'] is None:
                    results['any_checkbox'] = elem.element_info.name
                
                # Any edit field
                if ctrl_type == "Edit" and results['any_edit'] is None:
                    results['any_edit'] = elem.element_info.name
                    
            except:
                pass
        
        results['search_time'] = time.time() - t0
        results['total_elements_checked'] = checked
        
    except Exception as e:
        results['error'] = str(e)
    
    return results

def parse_title(title):
    """Parse window title for loading indicators."""
    import re
    title_lower = title.lower()
    
    info = {
        'raw': title,
        'loading_text': False,
        'percentage': None,
        'scene_file': None,
    }
    
    # Loading indicators in title
    loading_keywords = ['loading', 'importing', 'initializing', 'please wait', 'preparing']
    for kw in loading_keywords:
        if kw in title_lower:
            info['loading_text'] = kw
            break
    
    # Percentage in title
    pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', title)
    if pct_match:
        info['percentage'] = float(pct_match.group(1))
    
    # Scene filename
    file_match = re.search(r'([^\\/]+\.vantage)', title, re.IGNORECASE)
    if file_match:
        info['scene_file'] = file_match.group(1)
    
    return info

def get_cpu_usage():
    """Get Vantage CPU usage if psutil available."""
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'cpu_percent']):
            name = proc.info.get('name', '')
            if name and 'vantage' in name.lower():
                return proc.cpu_percent(interval=0.1)
    except:
        pass
    return None

def main():
    global start_time, log_handle
    
    parser = argparse.ArgumentParser(description='Monitor Vantage startup')
    parser.add_argument('scene', nargs='?', help='Scene file to open')
    parser.add_argument('--duration', type=int, default=600, help='Monitor duration in seconds (default: 600)')
    parser.add_argument('--interval', type=float, default=1.0, help='Poll interval in seconds (default: 1.0)')
    args = parser.parse_args()
    
    start_time = time.time()
    log_handle = open(LOG_FILE, 'w', encoding='utf-8')
    
    log("=" * 80)
    log("VANTAGE STARTUP DEBUG MONITOR v3")
    log("=" * 80)
    log("NOTE: Only 'pause_rendering' checkbox reliably indicates Vantage is ready")
    log(f"Log file: {os.path.abspath(LOG_FILE)}")
    log(f"Monitor duration: {args.duration}s")
    log(f"Poll interval: {args.interval}s")
    if args.scene:
        log(f"Scene file: {args.scene}")
    log("")
    
    # Check pywinauto
    try:
        from pywinauto import Desktop
        log("pywinauto: OK")
    except ImportError:
        log("ERROR: pywinauto not installed. Run: pip install pywinauto", "ERROR")
        return
    
    # Check psutil
    try:
        import psutil
        log("psutil: OK (will monitor CPU)")
    except ImportError:
        log("psutil: Not installed (CPU monitoring disabled)")
    
    # Find Vantage
    vantage_exe = find_vantage_exe()
    if vantage_exe:
        log(f"Vantage exe: {vantage_exe}")
    else:
        log("Vantage exe: Not found in standard paths", "WARN")
    
    log("")
    
    # Launch if scene provided
    if args.scene:
        if not os.path.exists(args.scene):
            log(f"Scene file not found: {args.scene}", "ERROR")
            return
        
        if not vantage_exe:
            log("Cannot launch - Vantage exe not found", "ERROR")
            return
        
        log(f"LAUNCHING: {os.path.basename(args.scene)}")
        subprocess.Popen([vantage_exe, args.scene], creationflags=subprocess.DETACHED_PROCESS)
        log("Launch command sent")
    
    log("")
    log("=" * 80)
    log("MONITORING STARTED - Press Ctrl+C to stop")
    log("=" * 80)
    log("")
    
    # State tracking
    last_title = ""
    window_found_at = None
    ui_responsive_at = None
    pause_button_at = None
    menu_bar_at = None
    milestones = []
    
    def milestone(name):
        elapsed = time.time() - start_time
        milestones.append((elapsed, name))
        log(f">>> MILESTONE: {name}", "MILE")
    
    poll = 0
    try:
        while time.time() - start_time < args.duration:
            poll += 1
            
            desktop = Desktop(backend="uia")
            window = find_vantage_window(desktop)
            
            if not window:
                if poll % 5 == 1:
                    log("Waiting for Vantage window...")
                time.sleep(args.interval)
                continue
            
            # Window found
            if window_found_at is None:
                window_found_at = time.time() - start_time
                milestone(f"Window appeared ({window_found_at:.1f}s)")
            
            # Get title
            title, title_time = safe_get_title(window)
            title_info = parse_title(title)
            
            # Log title changes
            if title != last_title:
                log(f"TITLE CHANGED: '{title}'")
                if title_info['loading_text']:
                    log(f"  -> Loading indicator: '{title_info['loading_text']}'")
                if title_info['percentage'] is not None:
                    log(f"  -> Progress: {title_info['percentage']}%")
                last_title = title
            
            # Get children count (quick responsiveness check)
            child_count, child_time = safe_get_children_count(window)
            
            # Get CPU
            cpu = get_cpu_usage()
            cpu_str = f"{cpu:.0f}%" if cpu is not None else "N/A"
            
            # Quick status line
            responsive = child_time < 0.5
            resp_str = "YES" if responsive else f"SLOW ({child_time:.2f}s)"
            
            log(f"[Poll {poll:4d}] Title time: {title_time:.3f}s | Children: {child_count} ({child_time:.2f}s) | Responsive: {resp_str} | CPU: {cpu_str}")
            
            # Track when UI becomes responsive
            if responsive and ui_responsive_at is None and child_count > 10:
                ui_responsive_at = time.time() - start_time
                milestone(f"UI responsive ({ui_responsive_at:.1f}s)")
            
            # Detailed control search every 5 polls (or if title suggests loaded)
            do_deep_search = (poll % 5 == 0) or (not title_info['loading_text'] and title_info['percentage'] is None)
            
            if do_deep_search:
                log("  Searching for specific controls...")
                controls = find_specific_controls(window, max_time=5.0)
                
                search_info = f"  Search: {controls['total_elements_checked']} elements in {controls['search_time']:.2f}s"
                if controls['timed_out']:
                    search_info += " (TIMED OUT)"
                log(search_info)
                
                # Report findings
                findings = []
                if controls['pause_rendering_checkbox']:
                    findings.append(f"PauseBtn='{controls['pause_rendering_checkbox']}'")
                    if pause_button_at is None:
                        pause_button_at = time.time() - start_time
                        milestone(f"Pause button found ({pause_button_at:.1f}s)")
                
                if controls['menu_bar']:
                    findings.append("MenuBar=YES")
                    if menu_bar_at is None:
                        menu_bar_at = time.time() - start_time
                        milestone(f"Menu bar found ({menu_bar_at:.1f}s)")
                
                if controls['start_button']:
                    findings.append(f"StartBtn='{controls['start_button']}'")
                
                if controls['toolbar']:
                    findings.append("Toolbar=YES")
                
                if controls['lights_panel']:
                    findings.append("LightsPanel=YES")
                
                if controls['any_checkbox']:
                    findings.append(f"Checkbox='{controls['any_checkbox'][:20]}'")
                
                if controls['any_edit']:
                    findings.append(f"Edit='{controls['any_edit'][:20] if controls['any_edit'] else 'unnamed'}'")
                
                if findings:
                    log(f"  Found: {' | '.join(findings)}")
                else:
                    log("  Found: (nothing yet)")
            
            # Determine if scene appears loaded
            # CRITICAL: Only pause_rendering_checkbox is a reliable indicator!
            # menu_bar can exist in File Explorer, so it's NOT reliable
            scene_loaded = (
                not title_info['loading_text'] and
                title_info['percentage'] is None and
                responsive and
                controls.get('pause_rendering_checkbox')  # ONLY this is reliable!
            ) if do_deep_search else False
            
            if scene_loaded:
                log("  *** SCENE APPEARS FULLY LOADED ***", "LOAD")
            
            log("")
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        log("")
        log("Monitoring stopped by user")
    
    # Summary
    log("")
    log("=" * 80)
    log("SUMMARY")
    log("=" * 80)
    log("")
    
    total_time = time.time() - start_time
    log(f"Total monitoring time: {total_time:.1f}s")
    log(f"Total polls: {poll}")
    log("")
    
    log("MILESTONES:")
    if milestones:
        for elapsed, name in milestones:
            log(f"  [{elapsed:7.2f}s] {name}")
    else:
        log("  (none recorded)")
    
    log("")
    log("KEY TIMINGS:")
    log(f"  Window appeared:    {window_found_at:.1f}s" if window_found_at else "  Window appeared:    (never)")
    log(f"  UI responsive:      {ui_responsive_at:.1f}s" if ui_responsive_at else "  UI responsive:      (never)")
    log(f"  Pause button found: {pause_button_at:.1f}s" if pause_button_at else "  Pause button found: (never)")
    log(f"  Menu bar found:     {menu_bar_at:.1f}s" if menu_bar_at else "  Menu bar found:     (never)")
    
    if pause_button_at and window_found_at:
        log("")
        log(f"  TIME FROM WINDOW TO PAUSE BUTTON: {pause_button_at - window_found_at:.1f}s")
        log("  (This is how long Wain should wait before sending commands)")
    
    log("")
    log(f"Full log: {os.path.abspath(LOG_FILE)}")
    log("=" * 80)
    
    if log_handle:
        log_handle.close()

if __name__ == "__main__":
    main()
