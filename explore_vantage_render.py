"""
Vantage Render Panel Explorer
=============================

Run this while Vantage is RENDERING to discover the exact names of UI controls in:
1. Main Vantage window (High Quality Render panel)
2. Rendering HQ Sequence progress window

This helps identify the correct control names for:
- Total progress percentage
- Frame progress percentage  
- Current frame / total frames
- Stop/Pause buttons

Usage:
1. Open Vantage with a scene
2. Start a render (so the progress window appears)
3. Run this script: python explore_vantage_render.py
"""

import time
import sys

def main():
    print("=" * 70)
    print("  Vantage Render UI Control Explorer")
    print("=" * 70)
    print()
    
    try:
        from pywinauto import Desktop
    except ImportError:
        print("ERROR: pywinauto not installed")
        print("Run: pip install pywinauto")
        return
    
    desktop = Desktop(backend="uia")
    
    # ================================================================
    # FIND ALL VANTAGE-RELATED WINDOWS
    # ================================================================
    print("Searching for Vantage windows...")
    print()
    
    vantage_main = None
    progress_window = None
    
    for win in desktop.windows():
        try:
            title = win.window_text()
            class_name = win.element_info.class_name or ""
            
            if not title:
                continue
            
            title_lower = title.lower()
            
            # Check for main Vantage window
            if "vantage" in title_lower and "LavinaMainWindow" in class_name:
                vantage_main = win
                print(f"[MAIN] {title}")
            
            # Check for Rendering HQ Sequence window
            if "rendering hq" in title_lower or "rendering high quality" in title_lower:
                progress_window = win
                print(f"[PROGRESS] {title} *** THIS IS THE PROGRESS WINDOW ***")
            elif "rendering" in title_lower:
                print(f"[RENDER?] {title}")
                if not progress_window:
                    progress_window = win
                    
        except Exception as e:
            pass
    
    if not vantage_main and not progress_window:
        print("\nERROR: Could not find any Vantage windows!")
        print("Make sure Vantage is running.")
        return
    
    # ================================================================
    # EXPLORE PROGRESS WINDOW (most important for progress tracking)
    # ================================================================
    if progress_window:
        print()
        print("=" * 70)
        print("  RENDERING HQ SEQUENCE WINDOW CONTROLS")
        print("=" * 70)
        print()
        
        # BUTTONS
        print("BUTTONS:")
        buttons = list(progress_window.descendants(control_type="Button"))
        for i, btn in enumerate(buttons):
            try:
                name = btn.element_info.name or "(no name)"
                enabled = "enabled" if btn.is_enabled() else "disabled"
                highlight = ""
                if name.lower() in ["stop", "pause", "cancel", "abort", "start", "close"]:
                    highlight = " *** CONTROL BUTTON ***"
                print(f"  [{i}] {name:30s} [{enabled}]{highlight}")
            except:
                pass
        
        print()
        print("TEXT ELEMENTS (look for 'Frame', 'Total' and percentages):")
        print("-" * 60)
        texts = list(progress_window.descendants(control_type="Text"))
        
        # Group text elements to identify patterns
        found_frame_section = False
        found_total_section = False
        
        for i, text in enumerate(texts):
            try:
                name = text.element_info.name or ""
                if not name.strip():
                    continue
                
                highlight = ""
                name_lower = name.lower().strip()
                
                # Detect section headers
                if name_lower == "frame":
                    found_frame_section = True
                    found_total_section = False
                    highlight = " <<< FRAME SECTION >>>"
                elif name_lower == "total":
                    found_total_section = True
                    found_frame_section = False
                    highlight = " <<< TOTAL SECTION >>>"
                # Detect values in sections
                elif "%" in name:
                    if found_frame_section:
                        highlight = " *** FRAME PERCENTAGE ***"
                    elif found_total_section:
                        highlight = " *** TOTAL PERCENTAGE ***"
                    else:
                        highlight = " *** PERCENTAGE ***"
                elif "/" in name:
                    highlight = " *** FRAME COUNT (X/Y) ***"
                elif name.strip().isdigit():
                    if found_frame_section:
                        highlight = " (frame related number)"
                    elif found_total_section:
                        highlight = " (total related number)"
                
                print(f"  [{i:2d}] '{name}'{highlight}")
            except:
                pass
        
        print()
        print("PROGRESS BARS:")
        progress_bars = list(progress_window.descendants(control_type="ProgressBar"))
        for i, pb in enumerate(progress_bars):
            try:
                name = pb.element_info.name or "(no name)"
                value = ""
                try:
                    value = pb.get_value()
                except:
                    pass
                note = " (first = likely Frame progress)" if i == 0 else " (second = likely Total progress)" if i == 1 else ""
                print(f"  [{i}] {name:30s} value={value}{note}")
            except:
                pass
    else:
        print()
        print("NOTE: No 'Rendering HQ Sequence' window found.")
        print("Start a render in Vantage first, then run this script again.")
    
    # ================================================================
    # EXPLORE MAIN WINDOW
    # ================================================================
    if vantage_main:
        print()
        print("=" * 70)
        print("  MAIN VANTAGE WINDOW - RENDER PANEL CONTROLS")
        print("=" * 70)
        print()
        
        print("BUTTONS (first 30):")
        buttons = list(vantage_main.descendants(control_type="Button"))[:30]
        for i, btn in enumerate(buttons):
            try:
                name = btn.element_info.name or "(no name)"
                highlight = ""
                if name.lower() in ["start", "browse", "stop", "pause"]:
                    highlight = " *** IMPORTANT ***"
                print(f"  [{i}] {name}{highlight}")
            except:
                pass
        
        print()
        print("EDIT FIELDS (first 20):")
        edits = list(vantage_main.descendants(control_type="Edit"))[:20]
        for i, edit in enumerate(edits):
            try:
                name = edit.element_info.name or "(no name)"
                value = ""
                try:
                    value = edit.get_value() or ""
                    if len(value) > 30:
                        value = value[:30] + "..."
                except:
                    pass
                
                highlight = ""
                if any(x in name.lower() for x in ["width", "height", "frame", "output"]):
                    highlight = " *** IMPORTANT ***"
                
                print(f"  [{i}] {name:30s} = '{value}'{highlight}")
            except:
                pass
    
    print()
    print("=" * 70)
    print("  DONE")
    print("=" * 70)
    print()
    print("Key things Wain looks for in the progress window:")
    print("  1. 'Frame' label followed by 'X / Y' (frame count)")
    print("  2. 'Frame' label followed by 'XX %' (frame progress)")
    print("  3. 'Total' label followed by 'XX %' (overall progress)")
    print("  4. Stop/Pause/Cancel button for stopping renders")


if __name__ == "__main__":
    main()
