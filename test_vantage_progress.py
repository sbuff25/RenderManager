"""
Vantage Progress Reader Test
=============================

This script continuously reads and displays progress from Vantage's
"Rendering HQ Sequence" window. Run this WHILE a render is in progress
to verify that Wain can accurately track progress.

Usage:
1. Start a render in Vantage (sequence/animation recommended)
2. Run: python test_vantage_progress.py
3. Watch the progress update in real-time
4. Press Ctrl+C to stop

This will help us understand the exact UI structure and ensure
accurate progress tracking.
"""

import time
import sys
import re


def find_progress_window(desktop):
    """Find Vantage 'Rendering HQ Sequence' window."""
    for win in desktop.windows():
        try:
            title = win.window_text()
            if "rendering hq" in title.lower() or "rendering high quality" in title.lower():
                return win, title
        except:
            pass
    
    # Fallback: any window with "rendering" in title
    for win in desktop.windows():
        try:
            title = win.window_text().lower()
            if "rendering" in title:
                return win, title
        except:
            pass
    
    return None, None


def read_all_ui_elements(window):
    """Read all text elements, progress bars, and buttons from the window."""
    elements = {
        "texts": [],
        "progress_bars": [],
        "buttons": [],
    }
    
    # Get all text elements
    for child in window.descendants(control_type="Text"):
        try:
            name = child.element_info.name or ""
            if name.strip():
                elements["texts"].append(name.strip())
        except:
            pass
    
    # Get all progress bars
    for child in window.descendants(control_type="ProgressBar"):
        try:
            name = child.element_info.name or ""
            value = None
            try:
                value = child.get_value()
            except:
                pass
            elements["progress_bars"].append({"name": name, "value": value})
        except:
            pass
    
    # Get all buttons
    for child in window.descendants(control_type="Button"):
        try:
            name = child.element_info.name or ""
            enabled = child.is_enabled()
            elements["buttons"].append({"name": name, "enabled": enabled})
        except:
            pass
    
    return elements


def parse_progress(elements):
    """Parse progress information from UI elements."""
    result = {
        "total_progress": None,
        "frame_progress": None,
        "current_frame": None,
        "total_frames": None,
        "status": "unknown",
    }
    
    texts = elements["texts"]
    
    # Parse text elements looking for sections
    in_frame_section = False
    in_total_section = False
    
    for i, text in enumerate(texts):
        text_lower = text.lower()
        
        # Detect section headers
        if text_lower == "frame":
            in_frame_section = True
            in_total_section = False
            continue
        elif text_lower == "total":
            in_total_section = True
            in_frame_section = False
            continue
        
        # Parse frame count: "X / Y"
        frame_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
        if frame_match:
            result["current_frame"] = int(frame_match.group(1))
            result["total_frames"] = int(frame_match.group(2))
            continue
        
        # Parse percentage: "XX %" or "XX.X %"
        pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if pct_match:
            pct = float(pct_match.group(1))
            if in_total_section:
                result["total_progress"] = pct
            elif in_frame_section:
                result["frame_progress"] = pct
            continue
        
        # Check for status text
        if "complete" in text_lower or "finished" in text_lower:
            result["status"] = "complete"
        elif "cancel" in text_lower or "abort" in text_lower:
            result["status"] = "cancelled"
    
    # Try progress bars as fallback
    progress_bars = elements["progress_bars"]
    for i, pb in enumerate(progress_bars):
        if pb["value"] is not None:
            val = float(pb["value"])
            if i == 0 and result["frame_progress"] is None:
                result["frame_progress"] = val
            elif i == 1 and result["total_progress"] is None:
                result["total_progress"] = val
            elif result["total_progress"] is None:
                result["total_progress"] = val
    
    # Determine status
    if result["total_progress"] is not None:
        if result["total_progress"] >= 100:
            result["status"] = "complete"
        else:
            result["status"] = "rendering"
    
    return result


def main():
    print("=" * 70)
    print("  Vantage Progress Reader Test")
    print("=" * 70)
    print()
    
    try:
        from pywinauto import Desktop
    except ImportError:
        print("ERROR: pywinauto not installed")
        print("Run: pip install pywinauto")
        return
    
    print("Looking for Vantage render progress window...")
    print("Start a render in Vantage if you haven't already.")
    print("Press Ctrl+C to stop monitoring.")
    print()
    print("-" * 70)
    
    last_progress = None
    poll_count = 0
    
    try:
        while True:
            poll_count += 1
            desktop = Desktop(backend="uia")
            window, title = find_progress_window(desktop)
            
            if not window:
                print(f"\r[{poll_count:4d}] Waiting for progress window...", end="", flush=True)
                time.sleep(1.0)
                continue
            
            # Read UI elements
            elements = read_all_ui_elements(window)
            
            # Parse progress
            progress = parse_progress(elements)
            
            # Build status line
            status_parts = []
            
            if progress["total_progress"] is not None:
                status_parts.append(f"Total: {progress['total_progress']:.1f}%")
            
            if progress["current_frame"] is not None:
                frame_str = f"Frame: {progress['current_frame']}"
                if progress["total_frames"]:
                    frame_str += f"/{progress['total_frames']}"
                status_parts.append(frame_str)
            
            if progress["frame_progress"] is not None:
                status_parts.append(f"Frame%: {progress['frame_progress']:.1f}%")
            
            status_parts.append(f"Status: {progress['status']}")
            
            status_line = " | ".join(status_parts)
            
            # Only print if changed
            if status_line != last_progress:
                print(f"\r[{poll_count:4d}] {status_line}" + " " * 20)
                last_progress = status_line
                
                # Show raw elements periodically for debugging
                if poll_count == 1 or poll_count % 30 == 0:
                    print()
                    print("  Raw UI elements detected:")
                    print(f"    Texts: {elements['texts'][:10]}")
                    print(f"    Progress bars: {elements['progress_bars']}")
                    print(f"    Buttons: {[b['name'] for b in elements['buttons'] if b['name']]}")
                    print()
            else:
                print(f"\r[{poll_count:4d}] {status_line}", end="", flush=True)
            
            # Check for completion
            if progress["status"] == "complete":
                print()
                print()
                print("=" * 70)
                print("  RENDER COMPLETE!")
                print("=" * 70)
                break
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print()
        print()
        print("Stopped by user.")
    
    print()
    print("Done.")


if __name__ == "__main__":
    main()
