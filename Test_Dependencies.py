#!/usr/bin/env python3
"""
Test script to verify pywebview + PyQt6 actually works.
Run this before running Wain to diagnose issues.
"""
import sys
import os

print("=" * 50)
print("Wain Dependency Test")
print("=" * 50)
print()

# Check Python version
print(f"Python: {sys.version}")
print()

# CRITICAL: Set environment BEFORE any imports
os.environ['PYWEBVIEW_GUI'] = 'qt'
os.environ['QT_API'] = 'pyqt6'

# Test imports
print("Testing imports...")
errors = []

try:
    import PyQt6
    print("  ✓ PyQt6")
except ImportError as e:
    print(f"  ✗ PyQt6: {e}")
    errors.append("PyQt6")

try:
    from PyQt6 import QtWebEngineWidgets
    print("  ✓ PyQt6-WebEngine")
except ImportError as e:
    print(f"  ✗ PyQt6-WebEngine: {e}")
    errors.append("PyQt6-WebEngine")

try:
    import qtpy
    print(f"  ✓ qtpy {qtpy.__version__}")
except ImportError as e:
    print(f"  ✗ qtpy: {e}")
    errors.append("qtpy")

try:
    import webview
    # Try different ways to get version
    if hasattr(webview, '__version__'):
        ver = webview.__version__
    elif hasattr(webview, 'version'):
        ver = webview.version
    else:
        ver = "unknown"
    print(f"  ✓ pywebview (version: {ver})")
    
    # Check what guilib it detected
    if hasattr(webview, 'guilib'):
        print(f"    guilib: {webview.guilib}")
    
except ImportError as e:
    print(f"  ✗ pywebview: {e}")
    errors.append("pywebview")

try:
    import nicegui
    print(f"  ✓ nicegui {nicegui.__version__}")
except ImportError as e:
    print(f"  ✗ nicegui: {e}")
    errors.append("nicegui")

print()

if errors:
    print(f"MISSING PACKAGES: {', '.join(errors)}")
    print()
    print("Run Install_Fresh.bat to install dependencies.")
    input("\nPress Enter to exit...")
    sys.exit(1)

# Test if pywebview Qt backend actually works
print("Testing pywebview Qt backend...")
print()

try:
    # Force Qt backend
    print("  Attempting to load Qt platform...")
    from webview.platforms import qt as qt_platform
    print("  ✓ Qt backend module loaded")
except ImportError as e:
    print(f"  ✗ Qt backend import failed: {e}")
    print()
    print("  Checking what backends are available...")
    try:
        import webview.platforms
        print(f"    Available: {dir(webview.platforms)}")
    except:
        pass
    print()
    print("pywebview Qt backend not available.")
    input("\nPress Enter to exit...")
    sys.exit(1)
except Exception as e:
    print(f"  ✗ Qt backend error: {e}")
    input("\nPress Enter to exit...")
    sys.exit(1)

print()
print("=" * 50)
print("All imports passed!")
print("=" * 50)
print()

# Ask if user wants to test a window
response = input("Test opening a window? (y/n): ").strip().lower()
if response == 'y':
    print()
    print("Opening test window...")
    print("(A small window should appear - close it to continue)")
    print()
    try:
        # Create a simple test window
        window = webview.create_window(
            'Wain Test', 
            html='<html><body style="background:#1a1a1a;color:white;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><h1>✓ It works!</h1></body></html>',
            width=400,
            height=300
        )
        webview.start(gui='qt')
        print("  ✓ Window test passed!")
    except Exception as e:
        print(f"  ✗ Window test failed: {type(e).__name__}: {e}")
        print()
        import traceback
        traceback.print_exc()
        print()
        print("This error is preventing Wain from running.")

print()
input("Press Enter to exit...")

