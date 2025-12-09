"""
Wane Bootstrap
==============

Automatic dependency checking and installation.
Must be called BEFORE any third-party imports.
"""

import subprocess
import sys

# Required packages: (import_name, pip_name, required)
# ORDER MATTERS: PyQt6 must install before pywebview so Qt backend is available
REQUIRED_PACKAGES = [
    ('nicegui', 'nicegui', True),      # Required - the UI framework
    ('PyQt6', 'PyQt6', True),          # Required - Qt backend (install before pywebview!)
    ('PyQt6.QtWebEngineWidgets', 'PyQt6-WebEngine', True),  # Required for native window
    ('qtpy', 'qtpy', True),            # Required - Qt compatibility layer for pywebview
    ('webview', 'pywebview', True),    # Required - native window
    ('PIL', 'Pillow', True),           # Required - image processing for icons/splash
]


def check_and_install_dependencies():
    """Check for required packages and install if missing."""
    missing_required = []
    missing_optional = []
    
    for import_name, pip_name, required in REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            if required:
                missing_required.append(pip_name)
            else:
                missing_optional.append(pip_name)
    
    all_missing = missing_required + missing_optional
    
    if all_missing:
        print("=" * 60)
        print("Wane - First Run Setup")
        print("=" * 60)
        print(f"\nInstalling packages: {', '.join(all_missing)}")
        print("This only happens once...\n")
        
        failed_required = []
        failed_optional = []
        
        for package in all_missing:
            print(f"  Installing {package}...")
            try:
                # Special handling for pywebview on Python 3.13+
                # pythonnet dependency fails to compile, but we can use Qt backend
                if package == 'pywebview' and sys.version_info >= (3, 13):
                    print(f"  (Python 3.13+ - using Qt backend only)")
                    # Install without dependencies to skip pythonnet
                    subprocess.check_call(
                        [sys.executable, '-m', 'pip', 'install', package, '--no-deps'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT
                    )
                    # Install light dependencies pywebview needs
                    subprocess.check_call(
                        [sys.executable, '-m', 'pip', 'install', 'proxy-tools', 'bottle'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT
                    )
                else:
                    subprocess.check_call(
                        [sys.executable, '-m', 'pip', 'install', package],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT
                    )
                print(f"  [OK] {package} installed successfully")
            except subprocess.CalledProcessError:
                is_required = package in missing_required
                if is_required:
                    failed_required.append(package)
                    print(f"  [X] Failed to install {package} (required)")
                else:
                    failed_optional.append(package)
                    print(f"  [!] Failed to install {package} (optional)")
        
        if failed_required:
            print(f"\n[X] Failed to install required packages: {', '.join(failed_required)}")
            print(f"\nPlease try:")
            print(f"  {sys.executable} -m pip install {' '.join(failed_required)}")
            print(f"\nNote: Python 3.10-3.12 recommended for best compatibility")
            sys.exit(1)
        
        if failed_optional:
            print(f"\n[!] Optional packages not installed: {', '.join(failed_optional)}")
            print("  Wane will run in browser mode instead of native window")
        
        print("\n" + "=" * 60)
        print("Setup complete! Starting Wane...")
        print("=" * 60 + "\n")


def check_native_mode_available() -> bool:
    """
    Check if native mode is available (pywebview + PyQt6 + WebEngine + qtpy).
    
    Returns:
        bool: True if native mode can be used, False for browser fallback.
    """
    import os
    
    try:
        # Set environment variables FIRST
        os.environ['QT_API'] = 'pyqt6'
        os.environ['PYWEBVIEW_GUI'] = 'qt'
        
        import PyQt6
        from PyQt6 import QtWebEngineWidgets  # Required by pywebview Qt backend
        import qtpy  # Qt compatibility layer
        import webview
        
        print("Native mode: PyQt6 + WebEngine + qtpy available")
        return True
    except ImportError as e:
        print(f"Native mode unavailable ({e}) - will use browser mode")
        return False
