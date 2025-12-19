"""
Vantage File Inspector
======================

Inspect the JSON structure of a .vantage file to understand
what keys are used for render settings.

Usage:
    python inspect_vantage_file.py "C:/path/to/file.vantage"
    
Or drag & drop a .vantage file onto this script.
"""

import sys
import json
import os

def inspect_file(file_path):
    print("=" * 70)
    print("  Vantage File Inspector")
    print("=" * 70)
    print()
    print(f"File: {file_path}")
    print()
    
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        return
    
    # Check file size
    size = os.path.getsize(file_path)
    print(f"Size: {size:,} bytes")
    
    # Try to read as JSON
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("Format: JSON ✓")
        print()
        
        # Show top-level keys
        print("-" * 70)
        print("TOP-LEVEL KEYS:")
        print("-" * 70)
        for key in sorted(data.keys()):
            value = data[key]
            if isinstance(value, dict):
                print(f"  {key}: {{...}} ({len(value)} keys)")
            elif isinstance(value, list):
                print(f"  {key}: [...] ({len(value)} items)")
            elif isinstance(value, str) and len(value) > 50:
                print(f"  {key}: \"{value[:50]}...\"")
            else:
                print(f"  {key}: {value}")
        print()
        
        # Look for render-related sections
        render_keys = ['render', 'renderSettings', 'hqRenderSettings', 'hqSettings', 
                       'highQualityRender', 'output', 'outputSettings', 'export',
                       'animation', 'camera', 'resolution', 'image']
        
        print("-" * 70)
        print("RENDER-RELATED SECTIONS:")
        print("-" * 70)
        
        found_any = False
        for key in data.keys():
            key_lower = key.lower()
            # Check if this key contains any render-related words
            if any(rk.lower() in key_lower for rk in ['render', 'output', 'export', 'hq', 'quality', 'image', 'resolution', 'frame', 'animation']):
                found_any = True
                print()
                print(f">>> {key}:")
                value = data[key]
                if isinstance(value, dict):
                    # Show contents of this section
                    print(json.dumps(value, indent=4))
                else:
                    print(f"    {value}")
        
        if not found_any:
            print("  No obvious render settings found.")
            print()
            print("  Showing ALL top-level sections with their contents:")
            print()
            for key in sorted(data.keys()):
                value = data[key]
                if isinstance(value, dict) and len(value) < 20:
                    print(f">>> {key}:")
                    print(json.dumps(value, indent=4))
                    print()
        
        # Show RENDER_SETTINGS section in detail
        if 'render_settings' in data:
            print()
            print("-" * 70)
            print("RENDER_SETTINGS SECTION:")
            print("-" * 70)
            print(json.dumps(data['render_settings'], indent=2))
        
        # Show ADDITIONAL_OPTIONS section
        if 'additional_options' in data:
            print()
            print("-" * 70)
            print("ADDITIONAL_OPTIONS SECTION:")
            print("-" * 70)
            print(json.dumps(data['additional_options'], indent=2))
        
        # Show OPTIONS section in detail (this has 170 keys - likely where HQ settings are)
        if 'options' in data:
            print()
            print("-" * 70)
            print("OPTIONS SECTION (looking for HQ/render settings):")
            print("-" * 70)
            opts = data['options']
            
            # Look for keys containing these terms
            search_terms = ['hq', 'render', 'output', 'width', 'height', 'resolution', 
                           'frame', 'path', 'file', 'image', 'export', 'quality', 'sample']
            
            print("\nKeys containing render-related terms:")
            for key in sorted(opts.keys()):
                key_lower = key.lower()
                if any(term in key_lower for term in search_terms):
                    value = opts[key]
                    if isinstance(value, str) and len(value) > 80:
                        print(f"  {key}: \"{value[:80]}...\"")
                    else:
                        print(f"  {key}: {value}")
            
            print("\n\nALL OPTIONS KEYS (for reference):")
            for key in sorted(opts.keys()):
                value = opts[key]
                if isinstance(value, (int, float, bool)):
                    print(f"  {key}: {value}")
                elif isinstance(value, str):
                    if len(value) > 50:
                        print(f"  {key}: \"{value[:50]}...\"")
                    else:
                        print(f"  {key}: \"{value}\"")
                elif isinstance(value, dict):
                    print(f"  {key}: {{...}} ({len(value)} keys)")
                elif isinstance(value, list):
                    print(f"  {key}: [...] ({len(value)} items)")
                else:
                    print(f"  {key}: {type(value).__name__}")
        
    except json.JSONDecodeError as e:
        print(f"Format: NOT JSON (parse error: {e})")
        print()
        print("This may be a binary format or corrupted file.")
        print()
        print("First 500 bytes (hex):")
        with open(file_path, 'rb') as f:
            data = f.read(500)
        print(data.hex())
        
    except Exception as e:
        print(f"ERROR: {e}")
    
    print()
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_vantage_file.py <path_to_vantage_file>")
        print()
        print("Example:")
        print('  python inspect_vantage_file.py "C:\\Projects\\MyScene.vantage"')
        sys.exit(1)
    
    inspect_file(sys.argv[1])
    
    print()
    input("Press Enter to exit...")
