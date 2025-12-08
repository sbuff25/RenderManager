#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wain Launcher with Splash Screen
================================
Shows a splash screen immediately, then launches the main app.
The splash closes when the app window appears.

Uses .pyw extension so Windows runs it without a console window.
"""

import sys
import os
import subprocess
import threading
import time
import ctypes

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, 'assets')
LOGO_PATH = os.path.join(ASSETS_DIR, 'wain_logo.png')
WAIN_SCRIPT = os.path.join(SCRIPT_DIR, 'wain.py')


def find_wain_window():
    """Check if Wain window exists using Windows API."""
    if sys.platform != 'win32':
        return False
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, 'Wain')
        return hwnd != 0
    except:
        return False


def run_splash():
    """Run the splash screen."""
    import tkinter as tk
    
    # Create borderless splash window
    splash = tk.Tk()
    splash.title("Wain Loading")
    splash.overrideredirect(True)  # No window decorations
    splash.attributes('-topmost', True)
    splash.configure(bg='#0a0a0a')
    
    # Size and center the splash
    width, height = 380, 280
    screen_w = splash.winfo_screenwidth()
    screen_h = splash.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    splash.geometry(f'{width}x{height}+{x}+{y}')
    
    # Main container
    frame = tk.Frame(splash, bg='#0a0a0a')
    frame.pack(expand=True, fill='both')
    
    # Try to load logo
    logo_label = None
    try:
        if os.path.exists(LOGO_PATH):
            from PIL import Image, ImageTk, ImageOps
            img = Image.open(LOGO_PATH).convert('RGBA')
            img = img.resize((80, 80), Image.Resampling.LANCZOS)
            # Invert for dark background
            r, g, b, a = img.split()
            rgb = Image.merge('RGB', (r, g, b))
            rgb = ImageOps.invert(rgb)
            img = Image.merge('RGBA', (*rgb.split(), a))
            photo = ImageTk.PhotoImage(img)
            logo_label = tk.Label(frame, image=photo, bg='#0a0a0a')
            logo_label.image = photo  # Keep reference
            logo_label.pack(pady=(50, 15))
    except ImportError:
        # PIL not available - show text
        logo_label = tk.Label(frame, text="W", font=('Segoe UI', 48, 'bold'),
                              fg='#fafafa', bg='#0a0a0a')
        logo_label.pack(pady=(40, 10))
    except Exception:
        pass
    
    # Title
    title = tk.Label(frame, text="WAIN", font=('Segoe UI', 22, 'bold'),
                     fg='#fafafa', bg='#0a0a0a')
    title.pack(pady=(10 if not logo_label else 0, 4))
    
    # Subtitle
    subtitle = tk.Label(frame, text="Render Queue Manager", 
                        font=('Segoe UI', 9), fg='#71717a', bg='#0a0a0a')
    subtitle.pack(pady=(0, 25))
    
    # Loading text
    loading_var = tk.StringVar(value="Starting...")
    loading_label = tk.Label(frame, textvariable=loading_var,
                             font=('Segoe UI', 9), fg='#52525b', bg='#0a0a0a')
    loading_label.pack(pady=(10, 0))
    
    # Progress bar
    progress_frame = tk.Frame(frame, bg='#27272a', height=3, width=180)
    progress_frame.pack(pady=(12, 0))
    progress_frame.pack_propagate(False)
    
    progress_fill = tk.Frame(progress_frame, bg='#71717a', height=3, width=0)
    progress_fill.place(x=0, y=0, height=3)
    
    # State
    state = {
        'progress': 0,
        'app_ready': False,
        'process': None,
        'closing': False
    }
    
    def update_loading_text():
        """Update loading status text based on progress."""
        if state['progress'] < 30:
            loading_var.set("Loading dependencies...")
        elif state['progress'] < 60:
            loading_var.set("Initializing UI...")
        elif state['progress'] < 120:
            loading_var.set("Starting Wain...")
        else:
            loading_var.set("Ready")
    
    def check_app_window():
        """Check if Wain window has appeared."""
        if find_wain_window():
            state['app_ready'] = True
    
    def animate():
        """Animate progress bar and check for app window."""
        if state['closing']:
            return
        
        # Check if Wain window appeared
        check_app_window()
        
        # Update progress
        if state['app_ready']:
            state['progress'] = min(state['progress'] + 20, 180)
        else:
            # Slow progress while loading (cap at 120 until app ready)
            state['progress'] = min(state['progress'] + 1, 120)
        
        progress_fill.place(x=0, y=0, height=3, width=state['progress'])
        update_loading_text()
        
        # Close when animation complete
        if state['progress'] >= 180:
            state['closing'] = True
            splash.after(100, splash.destroy)
        else:
            splash.after(25, animate)
    
    def launch_app():
        """Launch Wain in background."""
        try:
            # Find pythonw for no-console execution
            python_dir = os.path.dirname(sys.executable)
            pythonw = os.path.join(python_dir, 'pythonw.exe')
            if not os.path.exists(pythonw):
                pythonw = sys.executable
            
            # Launch wain.py
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            
            state['process'] = subprocess.Popen(
                [pythonw, WAIN_SCRIPT],
                cwd=SCRIPT_DIR,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            )
        except Exception as e:
            print(f"Failed to launch Wain: {e}")
            state['app_ready'] = True  # Force close splash
    
    # Launch app in background thread
    threading.Thread(target=launch_app, daemon=True).start()
    
    # Start animation
    splash.after(100, animate)
    
    # Add timeout to force close
    def timeout_close():
        if not state['closing']:
            state['closing'] = True
            splash.destroy()
    splash.after(15000, timeout_close)  # 15 second max
    
    # Run splash mainloop
    try:
        splash.mainloop()
    except:
        pass


def main():
    """Main entry point."""
    # Check if wain.py exists
    if not os.path.exists(WAIN_SCRIPT):
        print(f"Error: {WAIN_SCRIPT} not found")
        return
    
    # Run splash screen (this blocks until splash closes)
    run_splash()


if __name__ == '__main__':
    main()
