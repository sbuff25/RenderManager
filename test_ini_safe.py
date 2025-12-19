"""
Vantage INI Test Script (SAFE - Read Only)
==========================================

Tests the INI manager WITHOUT writing to your vantage.ini.
Run this to verify the read functionality works before enabling writes.

Usage:
    python test_ini_safe.py

https://github.com/Spencer-Sliffe/Wain
"""

import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("=" * 60)
    print("  Vantage INI Manager Test (SAFE - Read Only)")
    print("=" * 60)
    print()
    
    try:
        from wain.engines.vantage_settings import VantageINIManager, VantageHQSettings
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you're running from the Wain directory")
        return
    
    # Create manager in READ-ONLY mode
    manager = VantageINIManager(read_only=True)
    
    print(f"INI Path: {manager.ini_path}")
    print(f"Exists: {manager.exists()}")
    print()
    
    if not manager.exists():
        print("ERROR: vantage.ini not found!")
        print("Make sure Vantage has been run at least once.")
        return
    
    # Validate INI
    print("-" * 60)
    print("VALIDATION:")
    print("-" * 60)
    is_valid, msg = manager.validate_ini()
    print(f"  Valid: {is_valid}")
    print(f"  Message: {msg}")
    print()
    
    # Read current settings
    print("-" * 60)
    print("CURRENT HQ SETTINGS (from INI):")
    print("-" * 60)
    
    try:
        settings = manager.read_hq_settings()
        print(f"  Resolution: {settings.width} x {settings.height}")
        print(f"  Samples: {settings.samples}")
        print(f"  Quality Preset: {settings.quality_preset} ({manager.QUALITY_PRESETS.get(settings.quality_preset, 'Unknown')})")
        print(f"  Denoise Enabled: {settings.denoise_enabled}")
        print(f"  Denoiser Type: {settings.denoiser_type} ({manager.DENOISER_TYPES.get(settings.denoiser_type, 'Unknown')})")
        print(f"  Motion Blur: {settings.motion_blur}")
        print(f"  Light Cache: {settings.light_cache}")
        print(f"  Output Path: {settings.output_path or '(not set)'}")
        print()
    except Exception as e:
        print(f"  ERROR reading settings: {e}")
        return
    
    # Show raw INI structure
    print("-" * 60)
    print("RAW INI SECTIONS:")
    print("-" * 60)
    
    sections = manager.read_ini()
    for section_name in ['Preferences', 'DialogLocations']:
        if section_name in sections:
            print(f"\n[{section_name}]")
            section = sections[section_name]
            # Show only snapshot-related keys
            for key, value in sorted(section.items()):
                if 'snapshot' in key.lower() or 'SaveImage' in key:
                    # Truncate long values
                    display_value = value[:60] + "..." if len(value) > 60 else value
                    print(f"  {key} = {display_value}")
    
    print()
    print("-" * 60)
    print("TEST COMPLETE")
    print("-" * 60)
    print()
    print("If everything above looks correct, the INI read functionality works!")
    print()
    print("To test WRITE functionality (creates backup first):")
    print("  1. Edit wain/engines/vantage.py")
    print("  2. Set ENABLE_INI_WRITE = True")
    print("  3. Run a Vantage job from Wain")
    print()


if __name__ == "__main__":
    main()
    input("Press Enter to exit...")
