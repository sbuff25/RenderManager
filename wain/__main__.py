#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wain - Multi-Engine Render Queue Manager
Entry point for running as a package: python -m wain

Built with NiceGUI + pywebview (Qt backend) for native desktop window
Works on Python 3.10+ (including 3.13 and 3.14)

v2.19.5 - GPU-accelerated UI by default (--software-ui to opt out), dark
          webview base color, visual redesign per companion Figma file

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
# QtWebEngine GPU configuration
# v2.19.3: GPU compositing is ENABLED by default. The UI's compositing load is
# negligible next to an actual render, and software rasterization made the
# styled UI sluggish. Pass --software-ui to fall back to CPU rendering if you
# ever see UI/driver conflicts with Vantage or Toolbag.
# Checked via sys.argv because this must run before Qt imports, which happen
# before argparse runs.
# ============================================================================
if '--software-ui' in sys.argv:
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-gpu --disable-gpu-compositing'
    print("Software UI mode: QtWebEngine hardware acceleration DISABLED")
os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'

# ============================================================================
# Frozen build support (v2.20.0)
# Windowed .exe builds have no console — capture stdout/stderr in a log file
# in the writable data dir so worker mode and errors stay diagnosable.
# ============================================================================
if getattr(sys, 'frozen', False):
    try:
        from wain.config import DATA_DIR
        _console_log = open(
            os.path.join(DATA_DIR, 'wain_console.log'),
            'a', buffering=1, encoding='utf-8', errors='replace',
        )
        sys.stdout = _console_log
        sys.stderr = _console_log
        print(f"--- Wain started: {__import__('datetime').datetime.now().isoformat()} ---")
    except Exception:
        pass

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

from .app import render_app

# NOTE: wain.ui.main is imported lazily inside run_standalone()/run_server().
# Importing it registers the main app's ui.page routes, which breaks worker
# mode (NiceGUI forbids mixing registered pages with worker-dashboard UI).


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
        help='Path remapping for worker mode. Comma-separated (e.g., F:=Z:,E:=E:)',
    )
    parser.add_argument(
        '--token', type=str, default=None,
        help='API token for worker authentication (shown when server starts)',
    )
    parser.add_argument(
        '--headless', action='store_true',
        help='Worker mode: terminal only, no dashboard window (v2.24.0)',
    )
    parser.add_argument(
        '--gpu', type=int, default=None,
        help='Worker mode: pin Unreal renders to a GPU adapter index '
             '(-graphicsadapter=N). Run one worker per GPU for multi-GPU '
             'boxes. Console session only - never RDP. (v2.25.0)',
    )
    parser.add_argument(
        '--min-free-ram', type=float, default=None,
        help='Worker mode: do not claim a new job while available system '
             'RAM (GB) is below this - guards multi-GPU boxes against two '
             'simultaneous scene loads. Default 16. (v2.25.5)',
    )
    parser.add_argument(
        '--software-ui', action='store_true',
        help='Disable GPU compositing for the UI window (fallback if the UI '
             'conflicts with render engines; default is GPU-accelerated)',
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

    # Frozen build: assets are bundled next to the executable (and in
    # _MEIPASS for PyInstaller's internal layout) — check those first (v2.20.0)
    if getattr(sys, 'frozen', False):
        frozen_dirs = [os.path.join(os.path.dirname(sys.executable), 'assets')]
        if hasattr(sys, '_MEIPASS'):
            frozen_dirs.append(os.path.join(sys._MEIPASS, 'assets'))
        possible_asset_dirs = frozen_dirs + possible_asset_dirs

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


def _configure_native_window(icon_path=None):
    """Configure the native PyQt6/pywebview window."""
    print("Configuring native window...")
    # Taskbar/window icon (v2.25.5): pywebview's Qt backend accepts an icon
    # via webview.start(icon=...) - NiceGUI forwards start_args to it.
    if icon_path and os.path.exists(icon_path):
        app.native.start_args['icon'] = icon_path
    app.native.window_args['title'] = 'Wain'
    app.native.window_args['frameless'] = True
    app.native.window_args['easy_drag'] = False
    # Dark base color for the webview surface — prevents white flashes when
    # GPU compositor surfaces are created (e.g. opening menus/dialogs). v2.19.4
    app.native.window_args['background_color'] = '#121212'

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
    from .ui.main import main_page  # noqa: F401 - registers the app's ui.page routes
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
        _configure_native_window(favicon_path)
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
    from .ui.main import main_page  # noqa: F401 - registers the app's ui.page routes
    from wain.config import DATABASE_FILE, NETWORK_DEFAULT_PORT, AUTH_TOKEN_FILE
    from wain.network.auth import load_or_create_token
    from wain.network.database import JobDatabase
    from wain.network.server import register_api_routes

    port = args.port or NETWORK_DEFAULT_PORT

    print(f"Starting Wain Server (Network Mode)...")
    print(f"Python: {sys.version}")
    print(f"API will be available at http://0.0.0.0:{port}/api/")

    # Initialize database
    db = JobDatabase(DATABASE_FILE)
    print(f"[Wain] Database: {os.path.abspath(DATABASE_FILE)}")

    # Load or generate API authentication token
    api_token = load_or_create_token(AUTH_TOKEN_FILE)
    print(f"[Wain] API Token: {api_token}")
    print(f"[Wain] Workers must use: --token {api_token}")

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

    # Register REST API routes (with auth token)
    register_api_routes(app, db, render_app, api_token=api_token)
    render_app._api_routes_registered = True

    _assets_dir, favicon_path = _setup_assets()

    if HAS_NATIVE_MODE:
        _configure_native_window(favicon_path)
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
    # Resolve server/token from CLI args, saved worker config, or an
    # interactive first-run dialog (installed builds launch with no args).
    from wain.network.worker_setup import get_worker_connection
    server, token = get_worker_connection(args)
    if not server:
        print("Error: no server configured for worker mode")
        print("Usage: python -m wain --worker --server <ip:port> [--token <token>]")
        sys.exit(1)
    args.server = server
    if token and not args.token:
        args.token = token

    print(f"Starting Wain Worker...")
    print(f"Python: {sys.version}")

    from wain.network.worker import WorkerClient

    # Parse path mappings (e.g., "F:=Z:,E:=E:")
    path_maps = []
    if args.path_map:
        for mapping in args.path_map.split(","):
            parts = mapping.strip().split("=")
            if len(parts) == 2:
                path_maps.append((parts[0].strip(), parts[1].strip()))
                print(f"[Worker] Path mapping: {parts[0].strip()} -> {parts[1].strip()}")

    client = WorkerClient(
        server_url=args.server,
        worker_id=args.worker_id,
        path_maps=path_maps or None,
        api_token=args.token,
        gpu_index=args.gpu,
        min_free_ram_gb=args.min_free_ram,
    )

    # Headless (terminal-only) worker: --headless flag, or no Qt available
    if args.headless or not HAS_NATIVE_MODE:
        client.run()
        return

    # Dashboard mode (v2.24.0): worker loop in a background thread, compact
    # NiceGUI status window in the main thread.
    #
    # NiceGUI's native window is a multiprocessing child that re-imports this
    # module and re-executes run_worker() up to its ui.run() call (which
    # no-ops in the child). Guard the worker thread so only the real main
    # process polls for jobs - otherwise every job would be claimed twice.
    import multiprocessing
    is_window_child = multiprocessing.parent_process() is not None

    if not is_window_child:
        threading.Thread(target=client.run, daemon=True).start()
        app.on_shutdown(client.stop)

    from wain.ui.worker_ui import build_worker_ui

    @ui.page('/')
    def _worker_page():
        build_worker_ui(client)

    _assets_dir, favicon_path = _setup_assets()

    # Pick a free port for the dashboard's local server - multiple workers
    # per machine (one per GPU) must not collide, and 8080 belongs to a
    # possible Wain server on the same box.
    import socket as _socket
    _s = _socket.socket()
    _s.bind(('127.0.0.1', 0))
    ui_port = _s.getsockname()[1]
    _s.close()

    if favicon_path and os.path.exists(favicon_path):
        app.native.start_args['icon'] = favicon_path

    print(f"Starting worker dashboard (port {ui_port})...")
    ui.run(
        title='Wain Worker',
        favicon=favicon_path,
        dark=True,
        reload=False,
        native=True,
        window_size=(470, 720),
        fullscreen=False,
        reconnect_timeout=0,
        show=True,
        port=ui_port,
    )


# ============================================================================
# ENTRY POINT
# ============================================================================
def _set_windows_app_identity():
    """Give the process its own taskbar identity (v2.25.5): without an
    explicit AppUserModelID, Windows groups the window under python.exe
    and shows the Python icon regardless of the window's own icon."""
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Wain.RenderManager')
        except Exception:
            pass


def run():
    """Main entry point — dispatches to the appropriate mode.

    If the user previously enabled network mode via the settings toggle,
    the preference is persisted in wain_config.json.  On next launch we
    honour that preference and start in server mode automatically — no
    need for the ``--network`` flag.
    """
    _set_windows_app_identity()
    args = parse_args()

    if args.worker:
        run_worker(args)
    elif args.network or getattr(render_app, '_config_network_mode', False):
        run_server(args)
    else:
        run_standalone()


if __name__ in {"__main__", "__mp_main__"}:
    # freeze_support is required for frozen builds: NiceGUI's native window
    # uses multiprocessing, which would otherwise respawn the whole app
    import multiprocessing
    multiprocessing.freeze_support()
    run()
