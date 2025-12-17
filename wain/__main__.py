#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wain - Multi-Engine Render Queue Manager
Entry point for running as a package: python -m wain

Built with NiceGUI + pywebview (Qt backend) for native desktop window
Works on Python 3.10+ (including 3.13 and 3.14)

v2.10.0 - Bidirectional engine communication architecture
"""

# ============================================================================
# AUTOMATIC DEPENDENCY INSTALLATION (must run first!)
# ============================================================================
from .utils.bootstrap import check_and_install_dependencies
check_and_install_dependencies()

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================
import os
import sys
import threading

# Check if native mode is available
HAS_NATIVE_MODE = False
try:
    os.environ['QT_API'] = 'pyqt6'
    os.environ['PYWEBVIEW_GUI'] = 'qt'
    
    import PyQt6
    from PyQt6 import QtWebEngineWidgets
    import qtpy
    import webview
    
    HAS_NATIVE_MODE = True
    print("Native mode: PyQt6 + WebEngine + qtpy available")
except ImportError as e:
    print(f"Native mode unavailable ({e}) - will use browser mode")

from nicegui import ui, app

from .ui.main import main_page
from .app import render_app


# ============================================================================
# RUN APPLICATION
# ============================================================================
def run():
    """Run the Wain application."""
    mode = "Desktop (Native)" if HAS_NATIVE_MODE else "Browser"
    print(f"Starting Wain ({mode} Mode)...")
    print(f"Python: {sys.version}")
    
    if HAS_NATIVE_MODE:
        print("Using NiceGUI with PyQt6/pywebview backend")
    else:
        print("Running in browser mode")
        print("Open http://localhost:8080 if browser doesn't open automatically")
    
    # Serve logo/asset files from assets subfolder
    package_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(package_dir)
    cwd = os.getcwd()
    
    possible_asset_dirs = [
        os.path.join(parent_dir, 'assets'),
        os.path.join(cwd, 'assets'),
        os.path.join(package_dir, 'assets'),
    ]
    
    assets_dir = None
    for d in possible_asset_dirs:
        if os.path.exists(d):
            assets_dir = d
            break
    
    if assets_dir is None:
        assets_dir = os.path.join(parent_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        print(f"Created assets folder: {assets_dir}")
    else:
        print(f"Using assets folder: {assets_dir}")
    
    from wain.config import check_assets, AVAILABLE_LOGOS
    print("Checking for asset files...")
    check_assets(assets_dir)
    print(f"Available logos: {list(AVAILABLE_LOGOS.keys()) if AVAILABLE_LOGOS else 'None (using icon fallbacks)'}")
    
    app.add_static_files('/logos', assets_dir)
    
    # Set window icon
    icon_ico = os.path.join(assets_dir, 'wain_icon.ico')
    icon_png = os.path.join(assets_dir, 'wain_logo.png')
    
    if sys.platform == 'win32' and not os.path.exists(icon_ico) and os.path.exists(icon_png):
        try:
            from PIL import Image
            img = Image.open(icon_png)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img.save(icon_ico, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            print(f"Created ICO file: {icon_ico}")
        except Exception as e:
            print(f"Could not create ICO file: {e}")
    
    if os.path.exists(icon_ico):
        favicon_path = icon_ico
    elif os.path.exists(icon_png):
        favicon_path = icon_png
    else:
        favicon_path = None
    
    if HAS_NATIVE_MODE:
        print("Configuring native window...")
        app.native.window_args['title'] = 'Wain'
        app.native.window_args['frameless'] = True
        app.native.window_args['easy_drag'] = False
        
        class WindowAPI:
            def _get_hwnd(self):
                try:
                    import ctypes
                    return ctypes.windll.user32.FindWindowW(None, 'Wain')
                except:
                    return None
            
            def start_drag(self):
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            ctypes.windll.user32.ReleaseCapture()
                            ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, 2, 0)
                            return True
                except:
                    pass
                return False
            
            def minimize(self):
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            ctypes.windll.user32.ShowWindow(hwnd, 6)
                            return True
                except:
                    pass
                return False
            
            def maximize(self):
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            ctypes.windll.user32.ShowWindow(hwnd, 3)
                            return True
                except:
                    pass
                return False
            
            def restore(self):
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            ctypes.windll.user32.ShowWindow(hwnd, 9)
                            return True
                except:
                    pass
                return False
            
            def is_maximized(self):
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            return bool(ctypes.windll.user32.IsZoomed(hwnd))
                except:
                    pass
                return False
            
            def toggle_maximize(self):
                if self.is_maximized():
                    return self.restore()
                else:
                    return self.maximize()
            
            def close(self):
                try:
                    import webview
                    if webview.windows:
                        webview.windows[0].destroy()
                        return True
                except:
                    pass
                return False
        
        app.native.window_args['js_api'] = WindowAPI()
        
        print("Starting UI (native mode)...")
        ui.run(
            title='Wain',
            favicon=favicon_path,
            dark=True,
            reload=False,
            native=True,
            window_size=(1200, 850),
            fullscreen=False,
            reconnect_timeout=0,
            show=True,
        )
    else:
        print("Starting UI (browser mode)...")
        ui.run(
            title='Wain',
            favicon=favicon_path,
            dark=True,
            reload=False,
            native=False,
            port=8080,
            show=True,
        )


if __name__ in {"__main__", "__mp_main__"}:
    run()
