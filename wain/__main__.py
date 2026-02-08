#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wain - Multi-Engine Render Queue Manager
Entry point for running as a package: python -m wain

Built with NiceGUI + pywebview (Qt backend) for native desktop window
Works on Python 3.10+ (including 3.13 and 3.14)

v2.15.65 - Comprehensive audit, bug fixes, and optimizations

https://github.com/sbuff25/RenderManager
"""

# ============================================================================
# AUTOMATIC DEPENDENCY INSTALLATION (must run first!)
# ============================================================================
from .utils.bootstrap import check_and_install_dependencies
check_and_install_dependencies()

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================
import argparse
import os
import sys
import threading

# ============================================================================
# CRITICAL: Disable GPU acceleration in QtWebEngine
# This prevents Wain from competing with Vantage/Blender for GPU memory
# Without this, launching Vantage can crash due to GPU memory exhaustion
# ============================================================================
os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-gpu --disable-gpu-compositing --disable-software-rasterizer'
os.environ['QT_QUICK_BACKEND'] = 'software'
os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'

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
    print("Native mode: PyQt6 + WebEngine + qtpy available (GPU disabled for render engine compatibility)")
except ImportError as e:
    print(f"Native mode unavailable ({e}) - will use browser mode")

from nicegui import ui, app

from .ui.main import main_page
from .app import render_app


# ============================================================================
# CLI ARGUMENT PARSING
# ============================================================================
def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Wain - Multi-Engine Render Queue Manager'
    )
    parser.add_argument(
        '--worker', action='store_true',
        help='Run as headless worker (no UI, polls server for jobs)',
    )
    parser.add_argument(
        '--server', type=str, default=None,
        help='Server address for worker mode (e.g., 192.168.1.10:8080)',
    )
    parser.add_argument(
        '--worker-id', type=str, default=None,
        help='Custom worker ID (default: hostname)',
    )
    parser.add_argument(
        '--network', action='store_true',
        help='Enable network mode (server + REST API + SQLite)',
    )
    parser.add_argument(
        '--port', type=int, default=None,
        help='Port number (default: 8080)',
    )
    parser.add_argument(
        '--path-map', type=str, default=None,
        help='Path remapping for worker mode (e.g., F:=Z: to remap F:\\ to Z:\\)',
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='Debug mode',
    )
    return parser.parse_args()


# ============================================================================
# SHARED SETUP HELPERS
# ============================================================================
def _setup_assets():
    """Find and configure the assets directory. Returns (assets_dir, favicon_path)."""
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

    return assets_dir, favicon_path


def _configure_native_window():
    """Configure the native PyQt6/pywebview window."""
    print("Configuring native window...")
    app.native.window_args['title'] = 'Wain'
    app.native.window_args['frameless'] = True
    app.native.window_args['easy_drag'] = False

    class WindowAPI:
        def _get_hwnd(self):
            try:
                import ctypes
                return ctypes.windll.user32.FindWindowW(None, 'Wain')
            except Exception:
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
            except Exception:
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
            except Exception:
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
            except Exception:
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
            except Exception:
                pass
            return False

        def is_maximized(self):
            try:
                if sys.platform == 'win32':
                    import ctypes
                    hwnd = self._get_hwnd()
                    if hwnd:
                        return bool(ctypes.windll.user32.IsZoomed(hwnd))
            except Exception:
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
            except Exception:
                pass
            return False

    app.native.window_args['js_api'] = WindowAPI()


# ============================================================================
# MODE: STANDALONE (existing behavior, no changes)
# ============================================================================
def run_standalone():
    """Run Wain in standalone mode — existing single-machine behavior."""
    mode = "Desktop (Native)" if HAS_NATIVE_MODE else "Browser"
    print(f"Starting Wain ({mode} Mode)...")
    print(f"Python: {sys.version}")

    if HAS_NATIVE_MODE:
        print("Using NiceGUI with PyQt6/pywebview backend")
    else:
        print("Running in browser mode")
        print("Open http://localhost:8080 if browser doesn't open automatically")

    _assets_dir, favicon_path = _setup_assets()

    if HAS_NATIVE_MODE:
        _configure_native_window()
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


# ============================================================================
# MODE: SERVER (UI + REST API + SQLite + local rendering)
# ============================================================================
def run_server(args):
    """Run Wain in network server mode with REST API."""
    from wain.config import DATABASE_FILE, NETWORK_DEFAULT_PORT
    from wain.network.database import JobDatabase
    from wain.network.server import register_api_routes

    port = args.port or NETWORK_DEFAULT_PORT

    print(f"Starting Wain Server (Network Mode)...")
    print(f"Python: {sys.version}")
    print(f"API will be available at http://0.0.0.0:{port}/api/")

    # Initialize database
    db = JobDatabase(DATABASE_FILE)
    print(f"[Wain] Database: {os.path.abspath(DATABASE_FILE)}")

    # Import existing jobs from JSON if database is empty
    existing = db.get_all_jobs()
    if not existing:
        from wain.config import CONFIG_FILE
        if os.path.isfile(CONFIG_FILE):
            count = db.import_from_json(CONFIG_FILE)
            if count > 0:
                print(f"[Wain] Imported {count} job(s) from {CONFIG_FILE}")

    # Enable network mode on the render app
    render_app.enable_network_mode(db)

    # Register REST API routes
    register_api_routes(app, db)

    _assets_dir, favicon_path = _setup_assets()

    if HAS_NATIVE_MODE:
        _configure_native_window()
        print(f"Starting UI (native + network mode, port {port})...")
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
            port=port,
            host='0.0.0.0',
        )
    else:
        print(f"Starting UI (browser + network mode, port {port})...")
        ui.run(
            title='Wain',
            favicon=favicon_path,
            dark=True,
            reload=False,
            native=False,
            port=port,
            host='0.0.0.0',
            show=True,
        )


# ============================================================================
# MODE: WORKER (headless, polls server, renders locally)
# ============================================================================
def run_worker(args):
    """Run Wain in headless worker mode."""
    if not args.server:
        print("Error: --server is required in worker mode")
        print("Usage: python -m wain --worker --server <ip:port>")
        sys.exit(1)

    print(f"Starting Wain Worker...")
    print(f"Python: {sys.version}")

    from wain.network.worker import WorkerClient

    # Parse path mapping (e.g., "F:=Z:" means replace F:\ with Z:\)
    path_map = None
    if args.path_map:
        parts = args.path_map.split("=")
        if len(parts) == 2:
            path_map = (parts[0].strip(), parts[1].strip())
            print(f"[Worker] Path mapping: {path_map[0]} -> {path_map[1]}")

    client = WorkerClient(
        server_url=args.server,
        worker_id=args.worker_id,
        path_map=path_map,
    )
    client.run()


# ============================================================================
# ENTRY POINT
# ============================================================================
def run():
    """Main entry point — dispatches to the appropriate mode."""
    args = parse_args()

    if args.worker:
        run_worker(args)
    elif args.network:
        run_server(args)
    else:
        run_standalone()


if __name__ in {"__main__", "__mp_main__"}:
    run()
