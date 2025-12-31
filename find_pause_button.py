#!/usr/bin/env python3
"""
Vantage Pause Button Finder
===========================

This script helps identify the exact name/ID of the viewport pause button.

Run this with Vantage open, and it will:
1. List ALL toolbar buttons with their names and positions
2. Highlight buttons in the area you indicated (top toolbar)
3. Let you click a button and see its details

Usage:
    python find_pause_button.py

https://github.com/Spencer-Sliffe/Wain
"""

import time
import sys

def main():
    print("=" * 70)
    print("  Vantage Pause Button Finder")
    print("=" * 70)
    print()
    
    try:
        from pywinauto import Desktop
    except ImportError:
        print("ERROR: pywinauto not installed")
        print("Run: pip install pywinauto")
        return
    
    # Find Vantage window
    print("Looking for Vantage window...")
    desktop = Desktop(backend="uia")
    
    vantage = None
    for win in desktop.windows():
        try:
            class_name = win.element_info.class_name or ""
            title = win.window_text() or ""
            if "LavinaMainWindow" in class_name or "vantage" in title.lower():
                vantage = win
                print(f"Found: {title}")
                break
        except:
            pass
    
    if not vantage:
        print("ERROR: Vantage window not found!")
        print("Make sure Vantage is running.")
        return
    
    print()
    print("=" * 70)
    print("  ALL BUTTONS (sorted by vertical position, then horizontal)")
    print("=" * 70)
    print()
    
    # Collect all buttons with their positions
    buttons = []
    try:
        for btn in vantage.descendants(control_type="Button"):
            try:
                name = btn.element_info.name or ""
                auto_id = btn.element_info.automation_id or ""
                class_name = btn.element_info.class_name or ""
                
                rect = btn.element_info.rectangle
                x = rect.left
                y = rect.top
                w = rect.width()
                h = rect.height()
                
                buttons.append({
                    'name': name,
                    'auto_id': auto_id,
                    'class': class_name,
                    'x': x,
                    'y': y,
                    'w': w,
                    'h': h,
                    'control': btn
                })
            except:
                pass
    except Exception as e:
        print(f"Error enumerating buttons: {e}")
        return
    
    # Sort by Y position (top to bottom), then X position (left to right)
    buttons.sort(key=lambda b: (b['y'], b['x']))
    
    # Group by approximate Y position (toolbar rows)
    print("TOOLBAR BUTTONS (top 200 pixels of window):")
    print("-" * 70)
    
    toolbar_buttons = [b for b in buttons if b['y'] < 200]
    
    for i, btn in enumerate(toolbar_buttons):
        # Highlight buttons that might be play/pause related
        marker = ""
        name_lower = btn['name'].lower()
        id_lower = btn['auto_id'].lower()
        
        if any(x in name_lower or x in id_lower for x in ['pause', 'play', 'stop', 'render', 'viewport']):
            marker = " *** LIKELY CANDIDATE ***"
        elif btn['w'] > 20 and btn['w'] < 50 and btn['h'] > 20 and btn['h'] < 50:
            # Small square buttons are often toolbar icons
            marker = " (toolbar icon size)"
        
        print(f"[{i:2d}] pos=({btn['x']:4d},{btn['y']:3d}) size={btn['w']:2d}x{btn['h']:2d}")
        print(f"     name='{btn['name']}'")
        if btn['auto_id']:
            print(f"     id='{btn['auto_id']}'")
        if marker:
            print(f"     {marker}")
        print()
    
    print()
    print("=" * 70)
    print("  ALL BUTTONS WITH 'RENDER' OR 'PAUSE' OR 'PLAY' IN NAME/ID")
    print("=" * 70)
    print()
    
    found_any = False
    for btn in buttons:
        name_lower = btn['name'].lower()
        id_lower = btn['auto_id'].lower()
        
        if any(x in name_lower or x in id_lower for x in ['pause', 'play', 'stop', 'render', 'viewport', 'preview']):
            found_any = True
            print(f"Name: '{btn['name']}'")
            print(f"  ID: '{btn['auto_id']}'")
            print(f"  Class: '{btn['class']}'")
            print(f"  Position: ({btn['x']}, {btn['y']}) Size: {btn['w']}x{btn['h']}")
            print()
    
    if not found_any:
        print("No obvious pause/play buttons found by name.")
        print("The button might have a generic name or no name at all.")
    
    print()
    print("=" * 70)
    print("  TOGGLE BUTTONS (CheckBox type - often used for on/off toggles)")
    print("=" * 70)
    print()
    
    try:
        for cb in vantage.descendants(control_type="CheckBox"):
            try:
                name = cb.element_info.name or ""
                auto_id = cb.element_info.automation_id or ""
                rect = cb.element_info.rectangle
                
                # Only show checkboxes in toolbar area
                if rect.top < 200:
                    state = "ON" if cb.get_toggle_state() else "OFF"
                    print(f"[{state}] '{name}' id='{auto_id}' pos=({rect.left},{rect.top})")
            except:
                pass
    except:
        pass
    
    print()
    print("=" * 70)
    print("  INTERACTIVE MODE - Click a button to identify it")
    print("=" * 70)
    print()
    print("Instructions:")
    print("1. Position your mouse over the pause button in Vantage")
    print("2. Press Enter here, then quickly click the button")
    print("3. The script will try to detect which element was clicked")
    print()
    
    input("Press Enter when ready to detect a click...")
    
    print("You have 5 seconds to click the button...")
    
    # Get focused element after click
    time.sleep(5)
    
    try:
        desktop = Desktop(backend="uia")
        focused = desktop.get_focus()
        if focused:
            print()
            print("FOCUSED ELEMENT AFTER CLICK:")
            print(f"  Name: '{focused.element_info.name}'")
            print(f"  ID: '{focused.element_info.automation_id}'")
            print(f"  Type: '{focused.element_info.control_type}'")
            print(f"  Class: '{focused.element_info.class_name}'")
    except Exception as e:
        print(f"Could not get focused element: {e}")
    
    print()
    print("=" * 70)
    print("  DONE")
    print("=" * 70)
    print()
    print("Look for buttons near position that matches where you see the pause button.")
    print("The button in your screenshot appears to be around x=855-875 based on the red box.")
    print()
    print("Once you identify the button, tell me its name or automation_id")
    print("and I'll update Wain to click it directly.")


if __name__ == "__main__":
    main()
