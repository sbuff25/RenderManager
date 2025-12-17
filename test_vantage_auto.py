"""
Vantage Full Render Automation
===============================

Does everything from scratch:
1. Opens Tools > High Quality Render...
2. Clicks output path button
3. Types filename in dialog
4. Clicks Save
5. Clicks Start

Usage:
    python test_vantage_auto.py "H:\\Renders\\myrender.png"
    python test_vantage_auto.py   # Uses default path
"""

import sys
import time
import os
import subprocess

try:
    from pywinauto import Application, Desktop, keyboard
except ImportError:
    print("ERROR: pip install pywinauto")
    sys.exit(1)


def connect_to_vantage():
    """Find and connect to Vantage window."""
    desktop = Desktop(backend="uia")
    
    for win in desktop.windows():
        try:
            title = win.window_text()
            class_name = win.element_info.class_name or ""
            
            if "vantage" in title.lower() and "LavinaMainWindow" in class_name:
                print(f"  Found: {title[:50]}...")
                return win
        except:
            pass
    
    return None


def find_button(window, name_contains):
    """Find a button by partial name match."""
    name_lower = name_contains.lower()
    
    for child in window.descendants(control_type="Button"):
        try:
            name = child.element_info.name or ""
            if name_lower in name.lower():
                return child, name
        except:
            pass
    
    return None, None


def find_checkbox(window, name_contains):
    """Find a checkbox by partial name match."""
    name_lower = name_contains.lower()
    
    for child in window.descendants(control_type="CheckBox"):
        try:
            name = child.element_info.name or ""
            if name_lower in name.lower():
                return child, name
        except:
            pass
    
    return None, None


def main():
    # Get output path
    if len(sys.argv) > 1:
        output_path = sys.argv[1]
    else:
        render_dir = os.path.join(os.path.expanduser("~"), "Documents", "VantageRenders")
        os.makedirs(render_dir, exist_ok=True)
        output_path = os.path.join(render_dir, f"render_{int(time.time())}.png")
    
    # Ensure directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    print("="*60)
    print("  Vantage Full Render Automation")
    print("="*60)
    print(f"  Output: {output_path}")
    print("="*60)
    print()
    
    # ==========================================
    # STEP 1: Connect to Vantage
    # ==========================================
    print("STEP 1: Connecting to Vantage...")
    
    vantage = connect_to_vantage()
    if not vantage:
        print("  ERROR: Could not find Vantage window!")
        print("  Make sure Chaos Vantage is running.")
        return False
    
    vantage.set_focus()
    time.sleep(0.3)
    
    # ==========================================
    # STEP 2: Open High Quality Render panel
    # ==========================================
    print()
    print("STEP 2: Opening render panel (Tools > High Quality Render)...")
    
    # Use keyboard: Alt+T for Tools menu, then first item
    keyboard.send_keys("%t")  # Alt+T
    time.sleep(0.4)
    keyboard.send_keys("{ENTER}")  # First item = High Quality Render...
    time.sleep(0.8)
    
    print("  Render panel should be open")
    
    # ==========================================
    # STEP 3: Find and click output path button
    # ==========================================
    print()
    print("STEP 3: Looking for output path button...")
    
    # Re-get window reference after dialog might have changed things
    vantage = connect_to_vantage()
    if not vantage:
        print("  ERROR: Lost connection to Vantage!")
        return False
    
    # Look for buttons that might open the file path dialog
    # Common names: "...", "Browse", "Output", contains "path"
    
    output_btn = None
    output_btn_name = None
    
    # List all buttons to find the right one
    print("  Scanning buttons...")
    all_buttons = []
    
    for child in vantage.descendants(control_type="Button"):
        try:
            name = child.element_info.name or ""
            auto_id = child.element_info.automation_id or ""
            all_buttons.append((name, auto_id, child))
        except:
            pass
    
    # Try to find output-related button
    for search_term in ["output", "path", "...", "browse", "folder", "file"]:
        for name, auto_id, btn in all_buttons:
            if search_term in name.lower() or search_term in auto_id.lower():
                output_btn = btn
                output_btn_name = name
                break
        if output_btn:
            break
    
    if output_btn:
        print(f"  Found: '{output_btn_name}'")
        print("  Clicking...")
        output_btn.click_input()
        time.sleep(0.8)
    else:
        print("  Could not find output path button automatically!")
        print()
        print("  Available buttons:")
        for name, auto_id, btn in all_buttons[:30]:
            if name:
                print(f"    '{name}'")
        print()
        print("  Please manually click the output path button, then press Enter...")
        input()
    
    # ==========================================
    # STEP 4: Type path in file dialog
    # ==========================================
    print()
    print("STEP 4: Typing filename in dialog...")
    print("  (Using clipboard paste method)")
    
    # Small delay to let dialog fully open
    time.sleep(0.5)
    
    # Copy path to clipboard
    ps_cmd = f'Set-Clipboard -Value "{output_path}"'
    subprocess.run(['powershell', '-Command', ps_cmd],
                   creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(0.2)
    
    # Select all and paste
    keyboard.send_keys("^a", pause=0.05)
    time.sleep(0.1)
    keyboard.send_keys("^v", pause=0.05)
    time.sleep(0.3)
    
    print(f"  Pasted: {output_path}")
    
    # ==========================================
    # STEP 5: Save (press Enter or click Save)
    # ==========================================
    print()
    print("STEP 5: Saving (pressing Enter)...")
    
    keyboard.send_keys("{ENTER}")
    time.sleep(1.0)
    
    print("  File dialog should have closed")
    
    # ==========================================
    # STEP 6: Click Start button
    # ==========================================
    print()
    print("STEP 6: Looking for Start/Render button...")
    
    # Re-connect to get fresh control list
    vantage = connect_to_vantage()
    if not vantage:
        print("  ERROR: Lost connection to Vantage!")
        return False
    
    vantage.set_focus()
    time.sleep(0.3)
    
    # Look for Start button
    start_btn, start_name = find_button(vantage, "start")
    
    if not start_btn:
        # Try other possible names
        for alt_name in ["render", "begin", "go"]:
            start_btn, start_name = find_button(vantage, alt_name)
            if start_btn:
                break
    
    if start_btn:
        print(f"  Found: '{start_name}'")
        print("  Clicking...")
        start_btn.click_input()
        time.sleep(0.5)
        
        print()
        print("="*60)
        print("  RENDER STARTED!")
        print("="*60)
        print(f"  Output: {output_path}")
        return True
    else:
        print("  Could not find Start/Render button!")
        print()
        print("  Listing all current buttons:")
        for child in vantage.descendants(control_type="Button"):
            try:
                name = child.element_info.name
                if name:
                    print(f"    '{name}'")
            except:
                pass
        print()
        print("  What is the button called to start the render?")
        return False


if __name__ == "__main__":
    success = main()
    print()
    if not success:
        print("Some steps may have failed. Check Vantage to see the current state.")
