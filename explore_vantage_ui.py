#!/usr/bin/env python3
"""
Vantage UI Explorer
===================

This script helps debug Vantage UI automation by:
1. Finding the Vantage window
2. Dumping all available UI controls
3. Testing menu navigation
4. Identifying the HQ Render panel controls

Run with Vantage already open to explore its UI structure.
"""

import sys
import time
import argparse

def log(msg):
    print(f"[Explorer] {msg}")

def find_vantage_window(desktop):
    """Find and return the Vantage main window."""
    # Try to find by class name first (most reliable)
    for win in desktop.windows():
        try:
            class_name = win.element_info.class_name or ""
            if "LavinaMainWindow" in class_name:
                return win
        except:
            pass
    
    # Fallback: find by title containing "vantage"
    for win in desktop.windows():
        try:
            title = win.window_text().lower()
            if "vantage" in title:
                return win
        except:
            pass
    
    return None

def dump_all_controls(window):
    """Dump all UI controls in a window."""
    log("=" * 70)
    log("FULL UI CONTROL DUMP")
    log("=" * 70)
    
    try:
        log(f"Window title: {window.window_text()}")
        log(f"Window class: {window.element_info.class_name}")
        log("")
        
        # Count by type
        control_types = {}
        all_elems = list(window.descendants())
        for elem in all_elems:
            try:
                ct = elem.element_info.control_type
                control_types[ct] = control_types.get(ct, 0) + 1
            except:
                pass
        
        log("Control type counts:")
        for ct, count in sorted(control_types.items()):
            log(f"  {ct}: {count}")
        log("")
        
        # Menu bar
        log("MENU BAR:")
        for elem in window.children():
            try:
                ct = elem.element_info.control_type
                name = elem.element_info.name or "(no name)"
                if ct == "MenuBar":
                    log(f"  Found MenuBar: {name}")
                    for menu_item in elem.children():
                        mi_name = menu_item.element_info.name or "(no name)"
                        log(f"    Menu: {mi_name}")
            except:
                pass
        log("")
        
        # Menu items (in case they're accessible)
        log("MENU ITEMS (if visible):")
        for elem in list(window.descendants(control_type="MenuItem"))[:30]:
            try:
                name = elem.element_info.name or "(no name)"
                log(f"  MenuItem: {name}")
            except:
                pass
        log("")
        
        # Buttons
        log("BUTTONS:")
        for elem in list(window.descendants(control_type="Button"))[:50]:
            try:
                name = elem.element_info.name or "(no name)"
                auto_id = elem.element_info.automation_id or ""
                rect = elem.element_info.rectangle
                if name.strip() or auto_id:
                    log(f"  Button: '{name}' id='{auto_id}' rect={rect}")
            except:
                pass
        log("")
        
        # Edit fields
        log("EDIT FIELDS:")
        for elem in list(window.descendants(control_type="Edit"))[:30]:
            try:
                name = elem.element_info.name or "(no name)"
                auto_id = elem.element_info.automation_id or ""
                value = ""
                try:
                    value = str(elem.get_value())[:30] if hasattr(elem, 'get_value') else ""
                except:
                    pass
                log(f"  Edit: '{name}' id='{auto_id}' value='{value}'")
            except:
                pass
        log("")
        
        # Text labels
        log("TEXT LABELS:")
        for elem in list(window.descendants(control_type="Text"))[:50]:
            try:
                name = elem.element_info.name or ""
                if name.strip():
                    log(f"  Text: {name}")
            except:
                pass
        log("")
        
        # Panes
        log("PANES/PANELS:")
        for elem in list(window.descendants(control_type="Pane"))[:20]:
            try:
                name = elem.element_info.name or "(no name)"
                auto_id = elem.element_info.automation_id or ""
                if name.strip() or auto_id:
                    log(f"  Pane: '{name}' id='{auto_id}'")
            except:
                pass
        
        log("=" * 70)
        
    except Exception as e:
        log(f"Error dumping controls: {e}")
        import traceback
        traceback.print_exc()

def test_menu_navigation(window, keyboard):
    """Test different methods of opening the HQ Render panel."""
    log("")
    log("=" * 70)
    log("TESTING MENU NAVIGATION")
    log("=" * 70)
    
    # Method 1: Alt+T
    log("")
    log("Method 1: Trying Alt+T...")
    window.set_focus()
    time.sleep(0.3)
    keyboard.send_keys("%t")
    time.sleep(1.0)
    
    log("After Alt+T - checking for menu popup...")
    from pywinauto import Desktop
    desktop = Desktop(backend="uia")
    
    for win in desktop.windows():
        try:
            ct = win.element_info.control_type
            name = win.window_text()
            if ct == "Menu" or "menu" in name.lower():
                log(f"  Found popup: {name} (type: {ct})")
                for item in win.descendants(control_type="MenuItem"):
                    item_name = item.element_info.name or "(no name)"
                    log(f"    MenuItem: {item_name}")
        except:
            pass
    
    keyboard.send_keys("{ESC}")
    time.sleep(0.3)
    
    # Method 2: Click on menu bar
    log("")
    log("Method 2: Looking for menu bar...")
    menu_bar = None
    for child in window.children():
        try:
            if child.element_info.control_type == "MenuBar":
                menu_bar = child
                log(f"  Found menu bar")
                break
        except:
            pass
    
    if menu_bar:
        log("  Menu bar items:")
        for item in menu_bar.children():
            try:
                name = item.element_info.name or "(no name)"
                log(f"    - {name}")
            except:
                pass
        
        # Try to find Tools menu
        for item in menu_bar.children():
            try:
                name = item.element_info.name or ""
                if "tools" in name.lower():
                    log(f"  Found Tools menu, clicking...")
                    item.click_input()
                    time.sleep(0.8)
                    
                    # Look for dropdown
                    desktop = Desktop(backend="uia")
                    for win in desktop.windows():
                        try:
                            if win.element_info.control_type == "Menu":
                                log("  Menu popup found! Items:")
                                for mi in win.descendants(control_type="MenuItem"):
                                    mi_name = mi.element_info.name or "(no name)"
                                    log(f"    - {mi_name}")
                        except:
                            pass
                    
                    keyboard.send_keys("{ESC}")
                    break
            except:
                pass
    else:
        log("  Menu bar not found!")
    
    log("")
    log("=" * 70)

def main():
    parser = argparse.ArgumentParser(description='Explore Vantage UI')
    parser.add_argument('--dump', action='store_true', help='Dump all UI controls')
    parser.add_argument('--menu', action='store_true', help='Test menu navigation')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    args = parser.parse_args()
    
    if not any([args.dump, args.menu, args.all]):
        args.all = True  # Default to all
    
    try:
        from pywinauto import Desktop, keyboard
    except ImportError:
        print("ERROR: pywinauto not installed. Run: pip install pywinauto")
        sys.exit(1)
    
    log("Looking for Vantage window...")
    desktop = Desktop(backend="uia")
    vantage = find_vantage_window(desktop)
    
    if not vantage:
        log("ERROR: Vantage window not found!")
        log("Please start Vantage first and try again.")
        sys.exit(1)
    
    log(f"Found Vantage: {vantage.window_text()}")
    
    if args.dump or args.all:
        dump_all_controls(vantage)
    
    if args.menu or args.all:
        test_menu_navigation(vantage, keyboard)
    
    log("")
    log("Explorer complete!")

if __name__ == "__main__":
    main()
