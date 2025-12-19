"""
Wain Bootstrap
==============

Automatic dependency checking and installation.
"""

import subprocess
import sys

REQUIRED_PACKAGES = [
    ('nicegui', 'nicegui', True),
    ('PyQt6', 'PyQt6', True),
    ('PyQt6.QtWebEngineWidgets', 'PyQt6-WebEngine', True),
    ('qtpy', 'qtpy', True),
    ('webview', 'pywebview', True),
    ('PIL', 'Pillow', True),
    ('pywinauto', 'pywinauto', True),
]


def check_and_install_dependencies():
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
        print("Wain - First Run Setup")
        print("=" * 60)
        print(f"\nInstalling packages: {', '.join(all_missing)}")
        
        failed_required = []
        
        for package in all_missing:
            print(f"  Installing {package}...")
            try:
                if package == 'pywebview' and sys.version_info >= (3, 13):
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package, '--no-deps'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'proxy-tools', 'bottle'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                else:
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                print(f"  [OK] {package}")
            except subprocess.CalledProcessError:
                if package in missing_required:
                    failed_required.append(package)
                    print(f"  [X] Failed: {package}")
        
        if failed_required:
            print(f"\n[X] Failed: {', '.join(failed_required)}")
            sys.exit(1)
        
        print("\nSetup complete!")


def check_native_mode_available() -> bool:
    import os
    try:
        os.environ['QT_API'] = 'pyqt6'
        os.environ['PYWEBVIEW_GUI'] = 'qt'
        import PyQt6
        from PyQt6 import QtWebEngineWidgets
        import qtpy
        import webview
        return True
    except ImportError:
        return False
