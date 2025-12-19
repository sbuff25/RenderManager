#!/usr/bin/env python3
"""
Vantage Progress Window Explorer v2
===================================

The progress dialog in Vantage 3.x is a CHILD window inside the main
Vantage window, not a separate top-level window. This script searches
within the Vantage window to find it.

Usage:
1. Start a render in Vantage (HQ Render)
2. Run: python explore_progress_window.py
3. Review the output

https://github.com/Spencer-Sliffe/Wain
"""

import sys
import time


def find_vantage_window(desktop):
    """Find the main Vantage window."""
    for win in desktop.windows():
        try:
            class_name = win.element_info.class_name or ""
            if "LavinaMainWindow" in class_name:
                return win
            title = win.window_text().lower()
            if "vantage" in title:
                return win
        except:
            pass
    return None


def main():
    print("=" * 70)
    print("  Vantage Progress Window Explorer v2")
    print("=" * 70)
    print()
    
    try:
        from pywinauto import Desktop
    except ImportError:
        print("ERROR: pywinauto not installed")
        print("Run: pip install pywinauto")
        return
    
    desktop = Desktop(backend="uia")
    
    # Find main Vantage window
    print("Looking for Vantage window...")
    vantage = find_vantage_window(desktop)
    
    if not vantage:
        print("ERROR: Vantage window not found!")
        return
    
    print(f"Found: {vantage.window_text()}")
    print()
    
    # ========================================
    # SEARCH FOR PROGRESS DIALOG ELEMENTS
    # ========================================
    print("=" * 70)
    print("  SEARCHING FOR PROGRESS DIALOG INSIDE VANTAGE")
    print("=" * 70)
    print()
    
    # Look for child windows first
    print("-" * 70)
    print("  CHILD WINDOWS")
    print("-" * 70)
    
    try:
        children = vantage.children()
        for i, child in enumerate(children):
            try:
                ct = child.element_info.control_type
                name = child.element_info.name or ""
                class_name = child.element_info.class_name or ""
                
                marker = ""
                if "render" in name.lower() or "render" in class_name.lower():
                    marker = " <<< PROGRESS?"
                if ct == "Window":
                    marker = " <<< CHILD WINDOW"
                
                print(f"  [{i}] type={ct} name='{name}' class='{class_name}'{marker}")
            except:
                pass
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    
    # Look for Window-type descendants (dialogs)
    print("-" * 70)
    print("  WINDOW-TYPE DESCENDANTS (dialogs)")
    print("-" * 70)
    
    progress_dialog = None
    try:
        for child in vantage.descendants(control_type="Window"):
            try:
                name = child.element_info.name or ""
                class_name = child.element_info.class_name or ""
                print(f"  Window: '{name}' class='{class_name}'")
                
                if "render" in name.lower():
                    progress_dialog = child
                    print(f"         ^^^ THIS LOOKS LIKE THE PROGRESS DIALOG!")
            except:
                pass
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    
    # Look for Pane-type descendants that might be the dialog
    print("-" * 70)
    print("  PANE-TYPE DESCENDANTS (panels)")
    print("-" * 70)
    
    try:
        panes = list(vantage.descendants(control_type="Pane"))[:20]
        for i, pane in enumerate(panes):
            try:
                name = pane.element_info.name or ""
                class_name = pane.element_info.class_name or ""
                if name or "render" in class_name.lower():
                    print(f"  [{i}] Pane: '{name}' class='{class_name}'")
            except:
                pass
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    
    # ========================================
    # SEARCH FOR SPECIFIC PROGRESS ELEMENTS
    # ========================================
    print("=" * 70)
    print("  SEARCHING FOR PROGRESS-RELATED TEXT ELEMENTS")
    print("=" * 70)
    print()
    
    # Search ALL text elements for progress-related content
    print("-" * 70)
    print("  ALL TEXT containing 'render', 'frame', 'elapsed', '%', '/'")
    print("-" * 70)
    
    progress_texts = []
    try:
        for child in vantage.descendants(control_type="Text"):
            try:
                name = child.element_info.name or ""
                if name.strip():
                    name_lower = name.lower()
                    is_progress = any(x in name_lower for x in ["render", "frame", "elapsed", "remain", "total", "sequence", "hq"])
                    is_progress = is_progress or "%" in name or "/" in name
                    
                    if is_progress:
                        progress_texts.append(name.strip())
                        print(f"  '{name.strip()}'")
            except:
                pass
    except Exception as e:
        print(f"  Error: {e}")
    
    if not progress_texts:
        print("  No progress-related text found!")
    
    print()
    
    # ========================================
    # SEARCH FOR PROGRESS BARS
    # ========================================
    print("-" * 70)
    print("  ALL PROGRESS BARS IN VANTAGE")
    print("-" * 70)
    
    try:
        progress_bars = list(vantage.descendants(control_type="ProgressBar"))
        if progress_bars:
            for i, pb in enumerate(progress_bars):
                try:
                    name = pb.element_info.name or "(no name)"
                    auto_id = pb.element_info.automation_id or ""
                    
                    value = None
                    try:
                        value = pb.get_value()
                    except:
                        pass
                    
                    print(f"  [{i}] name='{name}' value={value} id='{auto_id}'")
                except Exception as e:
                    print(f"  [{i}] Error: {e}")
        else:
            print("  No progress bars found!")
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    
    # ========================================
    # SEARCH FOR PAUSE/ABORT BUTTONS
    # ========================================
    print("-" * 70)
    print("  BUTTONS (looking for Pause, Abort, Cancel, Stop)")
    print("-" * 70)
    
    try:
        for child in vantage.descendants(control_type="Button"):
            try:
                name = child.element_info.name or ""
                if name:
                    name_lower = name.lower()
                    is_control = any(x in name_lower for x in ["pause", "abort", "cancel", "stop", "resume"])
                    
                    if is_control:
                        enabled = child.is_enabled()
                        auto_id = child.element_info.automation_id or ""
                        print(f"  '{name}' enabled={enabled} id='{auto_id}' <<< CONTROL BUTTON")
            except:
                pass
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    
    # ========================================
    # DUMP ALL TEXT ELEMENTS (for reference)
    # ========================================
    print("=" * 70)
    print("  ALL TEXT ELEMENTS IN VANTAGE (first 50)")
    print("=" * 70)
    
    try:
        all_texts = []
        for child in vantage.descendants(control_type="Text"):
            try:
                name = child.element_info.name or ""
                if name.strip():
                    all_texts.append(name.strip())
            except:
                pass
        
        for i, text in enumerate(all_texts[:50]):
            marker = ""
            if "%" in text:
                marker = " <<< PERCENTAGE"
            elif "/" in text:
                marker = " <<< POSSIBLE FRAME COUNT"
            elif any(x in text.lower() for x in ["elapsed", "remain", "frame", "total"]):
                marker = " <<< PROGRESS LABEL"
            print(f"  [{i:2d}] '{text}'{marker}")
        
        if len(all_texts) > 50:
            print(f"  ... and {len(all_texts) - 50} more")
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    
    # ========================================
    # LIVE MONITORING
    # ========================================
    print("=" * 70)
    print("  LIVE MONITORING (10 seconds)")
    print("  Watching for changing values...")
    print("=" * 70)
    print()
    
    for tick in range(20):
        try:
            # Refresh
            desktop = Desktop(backend="uia")
            vantage = find_vantage_window(desktop)
            
            if not vantage:
                print(f"  [{tick}] Vantage window lost!")
                break
            
            # Collect progress-like values
            values = []
            
            # Get text with % or /
            for child in vantage.descendants(control_type="Text"):
                try:
                    name = child.element_info.name or ""
                    if "%" in name or "/" in name:
                        values.append(name.strip())
                except:
                    pass
            
            # Get progress bar values
            pb_vals = []
            for pb in vantage.descendants(control_type="ProgressBar"):
                try:
                    val = pb.get_value()
                    pb_vals.append(str(val))
                except:
                    pb_vals.append("?")
            
            print(f"  [{tick:2d}] Text: {values}  ProgressBars: {pb_vals}")
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  [{tick}] Error: {e}")
    
    print()
    print("=" * 70)
    print("  DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
