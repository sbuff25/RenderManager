#!/usr/bin/env python3
"""
Vantage UI Analyzer
===================

Comprehensive analysis of Chaos Vantage's UI structure.
Run this with Vantage open to generate a complete map of all UI elements.

Usage:
1. Open Vantage with a scene loaded
2. Open the High Quality Render panel (Ctrl+R or Tools menu)
3. Run: python analyze_vantage_ui.py
4. Check vantage_ui_analysis.txt for results

This will help understand:
- Window class names and titles
- All buttons and their names
- All edit fields and their labels
- Menu structure
- Panel layouts
- Control hierarchy
"""

import sys
import time
import os
from datetime import datetime

# Output file
OUTPUT_FILE = "vantage_ui_analysis.txt"

def log(msg, file=None):
    """Print and optionally write to file."""
    print(msg)
    if file:
        file.write(msg + "\n")

def analyze_control(ctrl, depth=0, file=None):
    """Analyze a single control and its properties."""
    indent = "  " * depth
    try:
        ctrl_type = ctrl.element_info.control_type or "Unknown"
        name = ctrl.element_info.name or ""
        auto_id = ctrl.element_info.automation_id or ""
        class_name = ctrl.element_info.class_name or ""
        
        # Get rectangle if possible
        rect = ""
        try:
            r = ctrl.element_info.rectangle
            rect = f"[{r.left},{r.top} {r.width()}x{r.height()}]"
        except:
            pass
        
        # Get value for editable controls
        value = ""
        if ctrl_type in ["Edit", "ComboBox", "Spinner"]:
            try:
                v = ctrl.get_value()
                if v:
                    value = f" value='{v[:50]}'"
            except:
                pass
        
        # Get checked state for checkboxes
        checked = ""
        if ctrl_type == "CheckBox":
            try:
                checked = f" checked={ctrl.get_toggle_state()}"
            except:
                pass
        
        # Build output line
        line = f"{indent}[{ctrl_type}]"
        if name:
            line += f" name='{name}'"
        if auto_id:
            line += f" id='{auto_id}'"
        if class_name and class_name not in name:
            line += f" class='{class_name}'"
        if rect:
            line += f" {rect}"
        if value:
            line += value
        if checked:
            line += checked
        
        log(line, file)
        return True
    except Exception as e:
        log(f"{indent}[Error reading control: {e}]", file)
        return False

def analyze_window_tree(window, max_depth=6, file=None):
    """Recursively analyze window control tree."""
    def recurse(ctrl, depth):
        if depth > max_depth:
            return
        
        analyze_control(ctrl, depth, file)
        
        try:
            children = ctrl.children()
            for child in children:
                recurse(child, depth + 1)
        except:
            pass
    
    recurse(window, 0)

def find_all_vantage_windows(desktop, file=None):
    """Find all Vantage-related windows."""
    windows = []
    
    log("\n" + "="*80, file)
    log("SCANNING FOR VANTAGE WINDOWS", file)
    log("="*80, file)
    
    for win in desktop.windows():
        try:
            title = win.window_text()
            class_name = win.element_info.class_name or ""
            
            # Check if Vantage-related
            is_vantage = False
            if "vantage" in title.lower():
                is_vantage = True
            if "LavinaMainWindow" in class_name:
                is_vantage = True
            if "rendering" in title.lower():
                is_vantage = True
            if "high quality" in title.lower():
                is_vantage = True
            if "chaos" in title.lower():
                is_vantage = True
            
            if is_vantage:
                windows.append(win)
                log(f"\nFound: '{title}'", file)
                log(f"  Class: {class_name}", file)
                try:
                    rect = win.element_info.rectangle
                    log(f"  Size: {rect.width()}x{rect.height()} at ({rect.left},{rect.top})", file)
                except:
                    pass
        except:
            pass
    
    if not windows:
        log("\nNo Vantage windows found!", file)
        log("Make sure Vantage is running.", file)
    
    return windows

def analyze_buttons(window, file=None):
    """Find and analyze all buttons."""
    log("\n" + "-"*60, file)
    log("BUTTONS", file)
    log("-"*60, file)
    
    buttons = []
    try:
        for btn in window.descendants(control_type="Button"):
            try:
                name = btn.element_info.name or ""
                auto_id = btn.element_info.automation_id or ""
                enabled = btn.is_enabled()
                
                rect = ""
                try:
                    r = btn.element_info.rectangle
                    rect = f"[{r.left},{r.top}]"
                except:
                    pass
                
                buttons.append({
                    "name": name,
                    "id": auto_id,
                    "enabled": enabled,
                    "rect": rect,
                    "control": btn
                })
            except:
                pass
    except:
        pass
    
    # Sort by name for easier reading
    buttons.sort(key=lambda x: x["name"].lower())
    
    for btn in buttons:
        status = "enabled" if btn["enabled"] else "DISABLED"
        line = f"  [{status}] '{btn['name']}'"
        if btn["id"]:
            line += f" (id: {btn['id']})"
        if btn["rect"]:
            line += f" {btn['rect']}"
        
        # Highlight important buttons
        name_lower = btn["name"].lower()
        if any(x in name_lower for x in ["start", "render", "stop", "browse", "output"]):
            line += " *** IMPORTANT ***"
        
        log(line, file)
    
    log(f"\nTotal buttons: {len(buttons)}", file)
    return buttons

def analyze_edit_fields(window, file=None):
    """Find and analyze all edit fields."""
    log("\n" + "-"*60, file)
    log("EDIT FIELDS / TEXT INPUTS", file)
    log("-"*60, file)
    
    edits = []
    try:
        for edit in window.descendants(control_type="Edit"):
            try:
                name = edit.element_info.name or ""
                auto_id = edit.element_info.automation_id or ""
                value = ""
                try:
                    value = edit.get_value() or ""
                except:
                    pass
                
                edits.append({
                    "name": name,
                    "id": auto_id,
                    "value": value[:100] if value else "",
                    "control": edit
                })
            except:
                pass
    except:
        pass
    
    for edit in edits:
        line = f"  '{edit['name']}'"
        if edit["id"]:
            line += f" (id: {edit['id']})"
        if edit["value"]:
            line += f" = '{edit['value']}'"
        
        # Highlight important fields
        name_lower = edit["name"].lower()
        if any(x in name_lower for x in ["width", "height", "frame", "start", "end", "output", "path", "file"]):
            line += " *** IMPORTANT ***"
        
        log(line, file)
    
    log(f"\nTotal edit fields: {len(edits)}", file)
    return edits

def analyze_spinners(window, file=None):
    """Find and analyze all spinner/numeric controls."""
    log("\n" + "-"*60, file)
    log("SPINNERS / NUMERIC INPUTS", file)
    log("-"*60, file)
    
    count = 0
    try:
        for ctrl in window.descendants(control_type="Spinner"):
            try:
                name = ctrl.element_info.name or ""
                auto_id = ctrl.element_info.automation_id or ""
                value = ""
                try:
                    value = ctrl.get_value() or ""
                except:
                    pass
                
                line = f"  '{name}'"
                if auto_id:
                    line += f" (id: {auto_id})"
                if value:
                    line += f" = {value}"
                
                log(line, file)
                count += 1
            except:
                pass
    except:
        pass
    
    log(f"\nTotal spinners: {count}", file)

def analyze_comboboxes(window, file=None):
    """Find and analyze all combo boxes / dropdowns."""
    log("\n" + "-"*60, file)
    log("COMBO BOXES / DROPDOWNS", file)
    log("-"*60, file)
    
    count = 0
    try:
        for ctrl in window.descendants(control_type="ComboBox"):
            try:
                name = ctrl.element_info.name or ""
                auto_id = ctrl.element_info.automation_id or ""
                value = ""
                try:
                    value = ctrl.get_value() or ""
                except:
                    pass
                
                line = f"  '{name}'"
                if auto_id:
                    line += f" (id: {auto_id})"
                if value:
                    line += f" = '{value}'"
                
                log(line, file)
                count += 1
            except:
                pass
    except:
        pass
    
    log(f"\nTotal combo boxes: {count}", file)

def analyze_checkboxes(window, file=None):
    """Find and analyze all checkboxes."""
    log("\n" + "-"*60, file)
    log("CHECKBOXES", file)
    log("-"*60, file)
    
    count = 0
    try:
        for ctrl in window.descendants(control_type="CheckBox"):
            try:
                name = ctrl.element_info.name or ""
                auto_id = ctrl.element_info.automation_id or ""
                state = ""
                try:
                    state = "ON" if ctrl.get_toggle_state() else "OFF"
                except:
                    pass
                
                line = f"  [{state}] '{name}'"
                if auto_id:
                    line += f" (id: {auto_id})"
                
                log(line, file)
                count += 1
            except:
                pass
    except:
        pass
    
    log(f"\nTotal checkboxes: {count}", file)

def analyze_text_labels(window, file=None):
    """Find and analyze all text labels."""
    log("\n" + "-"*60, file)
    log("TEXT LABELS (first 50)", file)
    log("-"*60, file)
    
    labels = []
    try:
        for ctrl in window.descendants(control_type="Text"):
            try:
                name = ctrl.element_info.name or ""
                if name.strip():
                    labels.append(name.strip())
            except:
                pass
    except:
        pass
    
    # Show first 50 unique labels
    seen = set()
    count = 0
    for label in labels:
        if label not in seen and count < 50:
            log(f"  '{label}'", file)
            seen.add(label)
            count += 1
    
    log(f"\nTotal unique labels: {len(seen)} (showing first 50)", file)

def analyze_menus(window, file=None):
    """Analyze menu structure."""
    log("\n" + "-"*60, file)
    log("MENU STRUCTURE", file)
    log("-"*60, file)
    
    try:
        # Find menu bar
        menu_bar = None
        for child in window.children():
            try:
                if child.element_info.control_type == "MenuBar":
                    menu_bar = child
                    break
            except:
                pass
        
        if menu_bar:
            log("  Menu Bar found:", file)
            for item in menu_bar.children():
                try:
                    name = item.element_info.name or "(unnamed)"
                    log(f"    Menu: {name}", file)
                except:
                    pass
        else:
            log("  No menu bar found in window children", file)
            
            # Try to find any menu items
            log("\n  Looking for menu items anywhere:", file)
            count = 0
            for ctrl in window.descendants(control_type="MenuItem"):
                try:
                    name = ctrl.element_info.name or ""
                    if name:
                        log(f"    MenuItem: {name}", file)
                        count += 1
                        if count >= 20:
                            log("    ... (more items exist)", file)
                            break
                except:
                    pass
    except Exception as e:
        log(f"  Error analyzing menus: {e}", file)

def analyze_panes(window, file=None):
    """Analyze panel/pane structure."""
    log("\n" + "-"*60, file)
    log("PANES / PANELS (with names)", file)
    log("-"*60, file)
    
    count = 0
    try:
        for ctrl in window.descendants(control_type="Pane"):
            try:
                name = ctrl.element_info.name or ""
                auto_id = ctrl.element_info.automation_id or ""
                class_name = ctrl.element_info.class_name or ""
                
                # Only show if it has a name or ID
                if name or auto_id:
                    line = f"  Pane: '{name}'"
                    if auto_id:
                        line += f" (id: {auto_id})"
                    if class_name:
                        line += f" class='{class_name}'"
                    
                    # Check if this might be the HQ Render panel
                    if any(x in (name + auto_id).lower() for x in ["render", "quality", "hq", "output"]):
                        line += " *** POSSIBLE RENDER PANEL ***"
                    
                    log(line, file)
                    count += 1
            except:
                pass
    except:
        pass
    
    log(f"\nTotal named panes: {count}", file)

def analyze_toolbars(window, file=None):
    """Analyze toolbar structure."""
    log("\n" + "-"*60, file)
    log("TOOLBARS", file)
    log("-"*60, file)
    
    count = 0
    try:
        for ctrl in window.descendants(control_type="ToolBar"):
            try:
                name = ctrl.element_info.name or "(unnamed)"
                log(f"  ToolBar: '{name}'", file)
                
                # List toolbar items
                for item in ctrl.children():
                    try:
                        item_name = item.element_info.name or ""
                        item_type = item.element_info.control_type or ""
                        if item_name:
                            log(f"    - [{item_type}] '{item_name}'", file)
                    except:
                        pass
                
                count += 1
            except:
                pass
    except:
        pass
    
    log(f"\nTotal toolbars: {count}", file)

def test_ctrl_r(window, file=None):
    """Test what happens when we send Ctrl+R."""
    log("\n" + "-"*60, file)
    log("TESTING CTRL+R SHORTCUT", file)
    log("-"*60, file)
    
    try:
        from pywinauto import keyboard
        
        # Count buttons before
        buttons_before = len(list(window.descendants(control_type="Button")))
        log(f"  Buttons before Ctrl+R: {buttons_before}", file)
        
        # Focus and send Ctrl+R
        window.set_focus()
        time.sleep(0.3)
        keyboard.send_keys("^r")
        time.sleep(1.5)
        
        # Count buttons after
        buttons_after = len(list(window.descendants(control_type="Button")))
        log(f"  Buttons after Ctrl+R: {buttons_after}", file)
        
        if buttons_after > buttons_before:
            log(f"  New buttons appeared! (+{buttons_after - buttons_before})", file)
            log("  Ctrl+R likely opened a panel.", file)
        elif buttons_after == buttons_before:
            log("  No change in button count.", file)
            log("  Panel may already be open, or Ctrl+R does something else.", file)
        
        # Look for Start button specifically
        log("\n  Searching for 'Start' button:", file)
        for btn in window.descendants(control_type="Button"):
            try:
                name = (btn.element_info.name or "").lower()
                if "start" in name:
                    log(f"    FOUND: '{btn.element_info.name}'", file)
            except:
                pass
        
    except Exception as e:
        log(f"  Error testing Ctrl+R: {e}", file)

def main():
    print("="*60)
    print("  Vantage UI Analyzer")
    print("="*60)
    print()
    
    # Check for pywinauto
    try:
        from pywinauto import Desktop
    except ImportError:
        print("ERROR: pywinauto not installed")
        print("Run: pip install pywinauto")
        return
    
    # Open output file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # Header
        log("="*80, f)
        log("VANTAGE UI ANALYSIS REPORT", f)
        log(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", f)
        log("="*80, f)
        
        # Find Vantage windows
        desktop = Desktop(backend="uia")
        windows = find_all_vantage_windows(desktop, f)
        
        if not windows:
            return
        
        # Analyze main window (usually the first/largest one)
        main_window = windows[0]
        title = main_window.window_text()
        
        log("\n" + "="*80, f)
        log(f"ANALYZING MAIN WINDOW: {title}", f)
        log("="*80, f)
        
        # Run all analyses
        analyze_menus(main_window, f)
        analyze_toolbars(main_window, f)
        analyze_panes(main_window, f)
        analyze_buttons(main_window, f)
        analyze_edit_fields(main_window, f)
        analyze_spinners(main_window, f)
        analyze_comboboxes(main_window, f)
        analyze_checkboxes(main_window, f)
        analyze_text_labels(main_window, f)
        
        # Test Ctrl+R
        test_ctrl_r(main_window, f)
        
        # Re-analyze buttons after Ctrl+R (in case panel opened)
        log("\n" + "="*80, f)
        log("BUTTONS AFTER CTRL+R", f)
        log("="*80, f)
        analyze_buttons(main_window, f)
        analyze_edit_fields(main_window, f)
        
        # Full tree dump (limited depth)
        log("\n" + "="*80, f)
        log("CONTROL TREE (depth limited to 4 levels)", f)
        log("="*80, f)
        analyze_window_tree(main_window, max_depth=4, file=f)
        
        # Analyze any other Vantage windows (like progress dialogs)
        if len(windows) > 1:
            for win in windows[1:]:
                try:
                    title = win.window_text()
                    log("\n" + "="*80, f)
                    log(f"ADDITIONAL WINDOW: {title}", f)
                    log("="*80, f)
                    analyze_buttons(win, f)
                    analyze_text_labels(win, f)
                except:
                    pass
        
        # Summary
        log("\n" + "="*80, f)
        log("ANALYSIS COMPLETE", f)
        log("="*80, f)
        log(f"\nResults saved to: {os.path.abspath(OUTPUT_FILE)}", f)
    
    print()
    print("="*60)
    print(f"Analysis complete! Check: {OUTPUT_FILE}")
    print("="*60)

if __name__ == "__main__":
    main()
