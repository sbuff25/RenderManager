"""
Vantage Progress Window Explorer
================================

Run this WHILE Vantage is actively rendering to explore the progress
dialog window and discover:
1. Window title and class
2. All text elements (labels, percentages)
3. Progress bars and their values
4. Buttons (Abort, Pause, etc.)
5. Any other controls

This will help us accurately read progress and control the render.

Usage:
1. Start a render in Vantage (so the progress window appears)
2. Run: python explore_vantage_progress.py
3. Review the output to understand the UI structure

For Vantage 3.1.0
"""

import sys
import time

def main():
    print("=" * 70)
    print("  Vantage Progress Window Explorer")
    print("  For Vantage 3.1.0")
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
    # FIND ALL WINDOWS
    # ================================================================
    print("STEP 1: Scanning all windows...")
    print("-" * 70)
    
    all_windows = []
    vantage_windows = []
    
    for win in desktop.windows():
        try:
            title = win.window_text()
            class_name = win.element_info.class_name or ""
            ctrl_type = win.element_info.control_type or ""
            
            all_windows.append({
                'window': win,
                'title': title,
                'class': class_name,
                'type': ctrl_type
            })
            
            # Check if it's Vantage-related
            title_lower = title.lower()
            if any(x in title_lower for x in ['vantage', 'rendering', 'progress', 'hq', 'chaos']):
                vantage_windows.append({
                    'window': win,
                    'title': title,
                    'class': class_name,
                    'type': ctrl_type
                })
                print(f"  [VANTAGE] '{title}'")
                print(f"            class='{class_name}' type='{ctrl_type}'")
        except Exception as e:
            pass
    
    print()
    print(f"Found {len(vantage_windows)} Vantage-related windows")
    print()
    
    if not vantage_windows:
        print("No Vantage windows found!")
        print("Make sure Vantage is running and a render is in progress.")
        print()
        print("All visible windows:")
        for w in all_windows[:20]:
            if w['title']:
                print(f"  '{w['title'][:50]}'")
        return
    
    # ================================================================
    # EXPLORE EACH VANTAGE WINDOW
    # ================================================================
    for i, vwin in enumerate(vantage_windows):
        print()
        print("=" * 70)
        print(f"  WINDOW {i+1}: {vwin['title'][:60]}")
        print("=" * 70)
        print(f"  Class: {vwin['class']}")
        print(f"  Type: {vwin['type']}")
        print()
        
        window = vwin['window']
        
        # Count control types
        print("CONTROL TYPE COUNTS:")
        print("-" * 40)
        control_counts = {}
        try:
            for elem in window.descendants():
                try:
                    ct = elem.element_info.control_type
                    control_counts[ct] = control_counts.get(ct, 0) + 1
                except:
                    pass
        except:
            pass
        
        for ct, count in sorted(control_counts.items()):
            print(f"  {ct}: {count}")
        print()
        
        # ============================================================
        # TEXT ELEMENTS
        # ============================================================
        print("TEXT ELEMENTS:")
        print("-" * 40)
        texts_found = []
        try:
            for elem in window.descendants(control_type="Text"):
                try:
                    name = elem.element_info.name or ""
                    auto_id = elem.element_info.automation_id or ""
                    if name.strip():
                        texts_found.append({
                            'name': name,
                            'auto_id': auto_id
                        })
                except:
                    pass
        except:
            pass
        
        for t in texts_found:
            marker = ""
            name_lower = t['name'].lower()
            if '%' in t['name']:
                marker = " <-- PERCENTAGE"
            elif '/' in t['name'] and any(c.isdigit() for c in t['name']):
                marker = " <-- FRAME COUNT?"
            elif 'frame' in name_lower:
                marker = " <-- FRAME LABEL"
            elif 'total' in name_lower:
                marker = " <-- TOTAL LABEL"
            elif 'progress' in name_lower:
                marker = " <-- PROGRESS LABEL"
            elif 'render' in name_lower:
                marker = " <-- RENDER LABEL"
            elif 'time' in name_lower or 'elapsed' in name_lower:
                marker = " <-- TIME"
            elif 'remaining' in name_lower or 'eta' in name_lower:
                marker = " <-- ETA"
            
            print(f"  '{t['name']}'{marker}")
            if t['auto_id']:
                print(f"      (id: {t['auto_id']})")
        print()
        
        # ============================================================
        # PROGRESS BARS
        # ============================================================
        print("PROGRESS BARS:")
        print("-" * 40)
        try:
            progress_bars = list(window.descendants(control_type="ProgressBar"))
            if not progress_bars:
                print("  (none found)")
            for j, pb in enumerate(progress_bars):
                try:
                    name = pb.element_info.name or "(no name)"
                    auto_id = pb.element_info.automation_id or ""
                    value = None
                    try:
                        # Try different methods to get value
                        if hasattr(pb, 'get_value'):
                            value = pb.get_value()
                        elif hasattr(pb, 'legacy_properties'):
                            props = pb.legacy_properties()
                            value = props.get('Value', None)
                    except:
                        pass
                    
                    # Try to get range
                    range_info = ""
                    try:
                        if hasattr(pb, 'iface_range_value'):
                            rv = pb.iface_range_value
                            range_info = f" range=[{rv.Minimum}-{rv.Maximum}]"
                    except:
                        pass
                    
                    print(f"  [{j}] name='{name}' value={value}{range_info}")
                    if auto_id:
                        print(f"      id='{auto_id}'")
                except Exception as e:
                    print(f"  [{j}] (error reading: {e})")
        except:
            print("  (error enumerating)")
        print()
        
        # ============================================================
        # BUTTONS
        # ============================================================
        print("BUTTONS:")
        print("-" * 40)
        try:
            buttons = list(window.descendants(control_type="Button"))
            if not buttons:
                print("  (none found)")
            for btn in buttons:
                try:
                    name = btn.element_info.name or ""
                    auto_id = btn.element_info.automation_id or ""
                    enabled = "enabled" if btn.is_enabled() else "disabled"
                    
                    if not name and not auto_id:
                        continue
                    
                    marker = ""
                    name_lower = name.lower()
                    if 'abort' in name_lower or 'cancel' in name_lower or 'stop' in name_lower:
                        marker = " <-- ABORT/CANCEL"
                    elif 'pause' in name_lower:
                        marker = " <-- PAUSE"
                    elif 'resume' in name_lower or 'continue' in name_lower:
                        marker = " <-- RESUME"
                    elif 'start' in name_lower:
                        marker = " <-- START"
                    
                    print(f"  '{name}' [{enabled}]{marker}")
                    if auto_id:
                        print(f"      id='{auto_id}'")
                except:
                    pass
        except:
            print("  (error enumerating)")
        print()
        
        # ============================================================
        # STATIC TEXT / LABELS
        # ============================================================
        print("STATIC/LABEL CONTROLS:")
        print("-" * 40)
        try:
            for ctrl_type in ["Static", "Label"]:
                for elem in window.descendants(control_type=ctrl_type):
                    try:
                        name = elem.element_info.name or ""
                        if name.strip():
                            print(f"  [{ctrl_type}] '{name}'")
                    except:
                        pass
        except:
            pass
        print()
        
        # ============================================================
        # EDIT/INPUT FIELDS
        # ============================================================
        print("EDIT FIELDS:")
        print("-" * 40)
        try:
            edits = list(window.descendants(control_type="Edit"))
            if not edits:
                print("  (none found)")
            for edit in edits:
                try:
                    name = edit.element_info.name or "(no name)"
                    auto_id = edit.element_info.automation_id or ""
                    value = ""
                    try:
                        value = edit.get_value() or ""
                        if len(value) > 50:
                            value = value[:50] + "..."
                    except:
                        pass
                    print(f"  '{name}' = '{value}'")
                    if auto_id:
                        print(f"      id='{auto_id}'")
                except:
                    pass
        except:
            print("  (error enumerating)")
        print()
        
        # ============================================================
        # HIERARCHY VIEW (first 3 levels)
        # ============================================================
        print("HIERARCHY (3 levels):")
        print("-" * 40)
        try:
            def print_children(parent, depth=0, max_depth=3):
                if depth >= max_depth:
                    return
                indent = "  " * depth
                for child in parent.children():
                    try:
                        ct = child.element_info.control_type or "?"
                        name = child.element_info.name or ""
                        auto_id = child.element_info.automation_id or ""
                        
                        display = f"{indent}[{ct}]"
                        if name:
                            display += f" '{name[:30]}'"
                        if auto_id:
                            display += f" (id:{auto_id[:20]})"
                        
                        print(display)
                        print_children(child, depth + 1, max_depth)
                    except:
                        pass
            
            print_children(window)
        except Exception as e:
            print(f"  (error: {e})")
        print()
    
    # ================================================================
    # SUMMARY
    # ================================================================
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print()
    print("To parse progress, look for:")
    print("  1. Text elements with '%' (percentages)")
    print("  2. Text elements with '/' (frame counts like '1/10')")
    print("  3. Progress bar values")
    print("  4. Labels like 'Frame', 'Total', 'Progress'")
    print()
    print("To control render, look for:")
    print("  1. Abort/Cancel/Stop buttons")
    print("  2. Pause/Resume buttons")
    print()
    print("Run this script again while render is at different stages")
    print("to see how values change.")
    print("=" * 70)


if __name__ == "__main__":
    main()
