#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wain - Multi-Engine Render Queue Manager
Entry point for running as a package: python -m wain

Built with NiceGUI + pywebview (Qt backend) for native desktop window
Works on Python 3.10+ (including 3.13 and 3.14)
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

# Check if native mode is available (pywebview + PyQt6 + WebEngine + qtpy)
HAS_NATIVE_MODE = False
try:
    # Set environment variables FIRST
    os.environ['QT_API'] = 'pyqt6'
    os.environ['PYWEBVIEW_GUI'] = 'qt'
    
    import PyQt6
    from PyQt6 import QtWebEngineWidgets  # This is what pywebview Qt backend needs
    import qtpy  # Qt compatibility layer - required by pywebview
    import webview
    
    HAS_NATIVE_MODE = True
    print("Native mode: PyQt6 + WebEngine + qtpy available")
except ImportError as e:
    print(f"Native mode unavailable ({e}) - will use browser mode")

from nicegui import ui, app

# Import the main page (this registers the @ui.page('/') route)
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
    # Look for assets relative to the package, or in current working directory
    package_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(package_dir)
    cwd = os.getcwd()
    
    # Try multiple locations for assets folder
    possible_asset_dirs = [
        os.path.join(parent_dir, 'assets'),     # ../assets (next to wain package)
        os.path.join(cwd, 'assets'),            # ./assets (current directory)
        os.path.join(package_dir, 'assets'),    # wain/assets (inside package)
    ]
    
    assets_dir = None
    for d in possible_asset_dirs:
        if os.path.exists(d):
            assets_dir = d
            break
    
    if assets_dir is None:
        # Create assets folder next to package
        assets_dir = os.path.join(parent_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        print(f"Created assets folder: {assets_dir}")
    else:
        print(f"Using assets folder: {assets_dir}")
    
    # Clear Qt WebEngine cache to ensure fresh assets load (native mode only)
    if HAS_NATIVE_MODE:
        def clear_webview_cache():
            """Clear Qt WebEngine cache directories."""
            import shutil
            cache_dirs = []
            
            # Windows cache locations
            if os.name == 'nt':
                local_appdata = os.environ.get('LOCALAPPDATA', '')
                appdata = os.environ.get('APPDATA', '')
                if local_appdata:
                    cache_dirs.append(os.path.join(local_appdata, 'nicegui'))
                    cache_dirs.append(os.path.join(local_appdata, 'pywebview'))
                if appdata:
                    cache_dirs.append(os.path.join(appdata, 'nicegui'))
                    cache_dirs.append(os.path.join(appdata, 'pywebview'))
            else:
                # Linux/Mac
                home = os.path.expanduser('~')
                cache_dirs.append(os.path.join(home, '.local', 'share', 'nicegui'))
                cache_dirs.append(os.path.join(home, '.cache', 'nicegui'))
            
            for cache_dir in cache_dirs:
                if os.path.exists(cache_dir):
                    try:
                        shutil.rmtree(cache_dir)
                        print(f"Cleared cache: {cache_dir}")
                    except Exception as e:
                        print(f"Could not clear cache {cache_dir}: {e}")
        
        # Clear cache on startup to ensure fresh assets
        clear_webview_cache()
    
    app.add_static_files('/logos', assets_dir)
    
    # Set window icon path - prefer .ico for Windows compatibility
    icon_ico = os.path.join(assets_dir, 'wain_icon.ico')
    icon_png = os.path.join(assets_dir, 'wain_logo.png')
    
    # On Windows, try to create .ico from .png if it doesn't exist
    if sys.platform == 'win32' and not os.path.exists(icon_ico) and os.path.exists(icon_png):
        try:
            from PIL import Image
            print(f"Creating ICO from PNG: {icon_png}")
            img = Image.open(icon_png)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img.save(icon_ico, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            print(f"Created ICO file: {icon_ico}")
        except ImportError:
            print("PIL not available - cannot create ICO from PNG")
        except Exception as e:
            print(f"Could not create ICO file: {e}")
    
    # Use ICO for native window icon (Windows), PNG as fallback
    if os.path.exists(icon_ico):
        favicon_path = icon_ico
    elif os.path.exists(icon_png):
        favicon_path = icon_png
    else:
        favicon_path = None
    
    if HAS_NATIVE_MODE:
        # Configure native window settings for pywebview
        print("Configuring native window...")
        app.native.window_args['title'] = 'Wain'
        app.native.window_args['frameless'] = True
        app.native.window_args['easy_drag'] = False
        
        # Create JS API for window controls (minimize, maximize, close)
        class WindowAPI:
            """JavaScript API for window controls in frameless mode."""
            
            def _get_hwnd(self):
                """Get the window handle."""
                try:
                    import ctypes
                    return ctypes.windll.user32.FindWindowW(None, 'Wain')
                except:
                    return None
            
            def start_drag(self):
                """Start window drag operation."""
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            ctypes.windll.user32.ReleaseCapture()
                            ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, 2, 0)
                            return True
                except Exception as e:
                    print(f"Start drag error: {e}")
                return False
            
            def minimize(self):
                """Minimize the window with animation."""
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            ctypes.windll.user32.ShowWindow(hwnd, 6)
                            return True
                    else:
                        import webview
                        if webview.windows:
                            webview.windows[0].minimize()
                            return True
                except Exception as e:
                    print(f"Minimize error: {e}")
                return False
            
            def maximize(self):
                """Maximize the window with animation."""
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            ctypes.windll.user32.ShowWindow(hwnd, 3)
                            return True
                    else:
                        import webview
                        if webview.windows:
                            webview.windows[0].maximize()
                            return True
                except Exception as e:
                    print(f"Maximize error: {e}")
                return False
            
            def restore(self):
                """Restore the window with animation."""
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            ctypes.windll.user32.ShowWindow(hwnd, 9)
                            return True
                    else:
                        import webview
                        if webview.windows:
                            webview.windows[0].restore()
                            return True
                except Exception as e:
                    print(f"Restore error: {e}")
                return False
            
            def is_maximized(self):
                """Check if window is maximized."""
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            return bool(ctypes.windll.user32.IsZoomed(hwnd))
                except Exception as e:
                    print(f"IsMaximized error: {e}")
                return False
            
            def toggle_maximize(self):
                """Toggle between maximized and restored state."""
                if self.is_maximized():
                    return self.restore()
                else:
                    return self.maximize()
            
            def close(self):
                """Close the window."""
                try:
                    import webview
                    if webview.windows:
                        webview.windows[0].destroy()
                        return True
                except Exception as e:
                    print(f"Close error: {e}")
                return False
        
        # Expose the API to JavaScript
        app.native.window_args['js_api'] = WindowAPI()
        
        # Set taskbar icon on Windows using native API
        if sys.platform == 'win32':
            import ctypes
            
            # Set AppUserModelID for proper taskbar grouping
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Wain.RenderManager.1')
                print("Set AppUserModelID for taskbar")
            except Exception as e:
                print(f"Could not set AppUserModelID: {e}")
            
            def set_taskbar_icon_windows():
                """Set the taskbar icon using Windows API after window is created."""
                import time
                time.sleep(2.0)
                
                try:
                    user32 = ctypes.windll.user32
                    hwnd = user32.FindWindowW(None, 'Wain')
                    if hwnd == 0:
                        print("Could not find Wain window for icon")
                        return
                    
                    ICON_SMALL = 0
                    ICON_BIG = 1
                    WM_SETICON = 0x0080
                    IMAGE_ICON = 1
                    LR_LOADFROMFILE = 0x0010
                    
                    icon_to_load = icon_ico if os.path.exists(icon_ico) else icon_png
                    
                    if not icon_to_load or not os.path.exists(icon_to_load):
                        print("No icon file found")
                        return
                    
                    print(f"Loading icon from: {icon_to_load}")
                    
                    hIconBig = user32.LoadImageW(None, icon_to_load, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
                    hIconSmall = user32.LoadImageW(None, icon_to_load, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                    
                    if hIconBig:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hIconBig)
                        print("Set large taskbar icon")
                    if hIconSmall:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hIconSmall)
                        print("Set small title bar icon")
                        
                except Exception as e:
                    print(f"Failed to set taskbar icon: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Run icon setter in background thread
            if (icon_ico and os.path.exists(icon_ico)) or (icon_png and os.path.exists(icon_png)):
                threading.Thread(target=set_taskbar_icon_windows, daemon=True).start()
        
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
        # Browser mode
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
