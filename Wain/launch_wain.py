#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wain Launcher
=============
Installs all required dependencies and launches Wain.

Usage:
    python launch_wain.py          - Install dependencies and launch
    python launch_wain.py --check  - Check dependencies only
    python launch_wain.py --help   - Show help
"""

import subprocess
import sys
import os
import shutil
import platform

# ============================================================================
# CONFIGURATION
# ============================================================================

APP_NAME = "Wain"
APP_VERSION = "1.0.0"
MAIN_SCRIPT = "wain.py"

# Required Python version
MIN_PYTHON_VERSION = (3, 10)

# Required packages: (import_name, pip_name, description)
REQUIRED_PACKAGES = [
    ('nicegui', 'nicegui', 'NiceGUI web framework'),
    ('webview', 'pywebview', 'Native window support'),
    ('PyQt6', 'PyQt6', 'Qt6 backend for native windows'),
]

# Required asset files (in assets/ subfolder)
ASSETS_FOLDER = "assets"
REQUIRED_ASSETS = [
    'wain_logo.png',
    'blender_logo.png',
    'marmoset_logo.png',
]

# ============================================================================
# COLORS FOR TERMINAL OUTPUT
# ============================================================================

class Colors:
    """ANSI color codes for terminal output"""
    if platform.system() == 'Windows':
        # Enable ANSI on Windows
        os.system('')
    
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def print_header():
    """Print the Wain ASCII header"""
    print(f"""
{Colors.CYAN}{Colors.BOLD}
 ██╗    ██╗ █████╗ ██╗███╗   ██╗
 ██║    ██║██╔══██╗██║████╗  ██║
 ██║ █╗ ██║███████║██║██╔██╗ ██║
 ██║███╗██║██╔══██║██║██║╚██╗██║
 ╚███╔███╔╝██║  ██║██║██║ ╚████║
  ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝
{Colors.RESET}
{Colors.DIM}  Render Queue Manager v{APP_VERSION}{Colors.RESET}
""")


def print_step(step_num, total, message):
    """Print a step indicator"""
    print(f"\n{Colors.BLUE}[{step_num}/{total}]{Colors.RESET} {message}")


def print_success(message):
    """Print a success message"""
    print(f"    {Colors.GREEN}✓{Colors.RESET} {message}")


def print_warning(message):
    """Print a warning message"""
    print(f"    {Colors.YELLOW}⚠{Colors.RESET} {message}")


def print_error(message):
    """Print an error message"""
    print(f"    {Colors.RED}✗{Colors.RESET} {message}")


def print_info(message):
    """Print an info message"""
    print(f"    {Colors.DIM}→{Colors.RESET} {message}")


# ============================================================================
# DEPENDENCY CHECKING
# ============================================================================

def check_python_version():
    """Check if Python version meets requirements"""
    current = sys.version_info[:2]
    required = MIN_PYTHON_VERSION
    
    if current >= required:
        print_success(f"Python {current[0]}.{current[1]} (required: {required[0]}.{required[1]}+)")
        return True
    else:
        print_error(f"Python {current[0]}.{current[1]} - requires {required[0]}.{required[1]}+")
        return False


def check_package(import_name, pip_name, description):
    """Check if a package is installed"""
    try:
        __import__(import_name)
        print_success(f"{description} ({pip_name})")
        return True
    except ImportError:
        print_warning(f"{description} ({pip_name}) - not installed")
        return False


def install_package(pip_name, description):
    """Install a package using pip"""
    print_info(f"Installing {description}...")
    try:
        # Use subprocess to install
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', pip_name, '--quiet'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print_success(f"Installed {pip_name}")
            return True
        else:
            print_error(f"Failed to install {pip_name}")
            if result.stderr:
                print_info(result.stderr.strip()[:200])
            return False
    except Exception as e:
        print_error(f"Error installing {pip_name}: {e}")
        return False


def check_assets(script_dir):
    """Check if required asset files exist"""
    assets_dir = os.path.join(script_dir, ASSETS_FOLDER)
    missing = []
    
    if not os.path.exists(assets_dir):
        print_warning(f"{ASSETS_FOLDER}/ folder not found")
        return REQUIRED_ASSETS  # All missing
    
    for asset in REQUIRED_ASSETS:
        asset_path = os.path.join(assets_dir, asset)
        if os.path.exists(asset_path):
            print_success(f"{ASSETS_FOLDER}/{asset}")
        else:
            print_warning(f"{ASSETS_FOLDER}/{asset} - missing")
            missing.append(asset)
    return missing


def check_main_script(script_dir):
    """Check if the main script exists"""
    main_path = os.path.join(script_dir, MAIN_SCRIPT)
    if os.path.exists(main_path):
        print_success(f"{MAIN_SCRIPT}")
        return True
    else:
        print_error(f"{MAIN_SCRIPT} - not found!")
        return False


# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def run_checks_only():
    """Run dependency checks without installing"""
    print_header()
    print(f"{Colors.BOLD}Checking dependencies...{Colors.RESET}")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    all_good = True
    
    # Check Python
    print_step(1, 4, "Python Version")
    if not check_python_version():
        all_good = False
    
    # Check packages
    print_step(2, 4, "Required Packages")
    for import_name, pip_name, description in REQUIRED_PACKAGES:
        if not check_package(import_name, pip_name, description):
            all_good = False
    
    # Check main script
    print_step(3, 4, "Main Application")
    if not check_main_script(script_dir):
        all_good = False
    
    # Check assets
    print_step(4, 4, "Asset Files")
    missing = check_assets(script_dir)
    if missing:
        all_good = False
    
    # Summary
    print()
    if all_good:
        print(f"{Colors.GREEN}{Colors.BOLD}All dependencies satisfied!{Colors.RESET}")
        print(f"{Colors.DIM}Run 'python launch_wain.py' to start Wain{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}Some dependencies are missing.{Colors.RESET}")
        print(f"{Colors.DIM}Run 'python launch_wain.py' to install and start{Colors.RESET}")
    
    return all_good


def install_and_launch():
    """Install dependencies and launch the application"""
    print_header()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Step 1: Check Python version
    print_step(1, 4, "Checking Python Version")
    if not check_python_version():
        print(f"\n{Colors.RED}Error: Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ is required.{Colors.RESET}")
        print(f"Download from: https://www.python.org/downloads/")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Step 2: Check and install packages
    print_step(2, 4, "Installing Dependencies")
    
    packages_to_install = []
    for import_name, pip_name, description in REQUIRED_PACKAGES:
        if not check_package(import_name, pip_name, description):
            packages_to_install.append((pip_name, description))
    
    if packages_to_install:
        print()
        # First upgrade pip
        print_info("Upgrading pip...")
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip', '--quiet'],
            capture_output=True
        )
        
        # Install missing packages
        failed = []
        for pip_name, description in packages_to_install:
            if not install_package(pip_name, description):
                failed.append(pip_name)
        
        if failed:
            print(f"\n{Colors.RED}Error: Failed to install: {', '.join(failed)}{Colors.RESET}")
            print("Try running manually:")
            print(f"  {sys.executable} -m pip install {' '.join(failed)}")
            input("\nPress Enter to exit...")
            sys.exit(1)
    else:
        print_info("All packages already installed")
    
    # Step 3: Check main script
    print_step(3, 4, "Checking Application Files")
    main_path = os.path.join(script_dir, MAIN_SCRIPT)
    if not os.path.exists(main_path):
        print_error(f"{MAIN_SCRIPT} not found!")
        print(f"\n{Colors.RED}Error: Main application file is missing.{Colors.RESET}")
        print(f"Make sure {MAIN_SCRIPT} is in the same folder as this launcher.")
        input("\nPress Enter to exit...")
        sys.exit(1)
    print_success(f"Found {MAIN_SCRIPT}")
    
    # Step 4: Check assets
    print_step(4, 4, "Checking Assets")
    missing_assets = check_assets(script_dir)
    if missing_assets:
        print_warning(f"Missing assets: {', '.join(missing_assets)}")
        print_info("App will use fallback icons")
    
    # Launch!
    print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Setup complete!{Colors.RESET}")
    print(f"\n{Colors.CYAN}Launching Wain...{Colors.RESET}\n")
    print("─" * 50)
    
    # Run the main application using subprocess (more reliable)
    os.chdir(script_dir)
    
    try:
        # Use pythonw on Windows to avoid console, python elsewhere
        if platform.system() == 'Windows':
            # Try pythonw first (no console), fall back to python
            pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            if os.path.exists(pythonw):
                subprocess.run([pythonw, main_path])
            else:
                subprocess.run([sys.executable, main_path])
        else:
            subprocess.run([sys.executable, main_path])
    except Exception as e:
        print(f"\n{Colors.RED}Error launching Wain: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)


def show_help():
    """Show help message"""
    print_header()
    print(f"""{Colors.BOLD}Usage:{Colors.RESET}
    python launch_wain.py          Install dependencies and launch Wain
    python launch_wain.py --check  Check dependencies without installing
    python launch_wain.py --help   Show this help message

{Colors.BOLD}Requirements:{Colors.RESET}
    • Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} or higher
    • Windows 10/11 (recommended) or Linux/macOS

{Colors.BOLD}Files:{Colors.RESET}
    Wain/
    ├── launch_wain.py        (this launcher)
    ├── wain.py               (main application)
    └── assets/
        ├── wain_logo.png     (app logo)
        ├── blender_logo.png  (Blender engine icon)
        └── marmoset_logo.png (Marmoset engine icon)

{Colors.BOLD}Installed Packages:{Colors.RESET}
    • nicegui   - Web-based UI framework
    • pywebview - Native desktop window wrapper
    • PyQt6     - Qt backend for native rendering
""")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ('--help', '-h', 'help', '/?'):
            show_help()
        elif arg in ('--check', '-c', 'check'):
            run_checks_only()
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information")
            sys.exit(1)
    else:
        # Default: install and launch
        install_and_launch()
