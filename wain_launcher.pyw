#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wain Launcher with Splash Screen
=================================

Shows a professional splash screen immediately, then loads the main app 
in the background. Uses .pyw extension so Windows runs it without a console.

The splash screen features:
- Centered Wain logo as focal point
- Smooth animated progress bar with shimmer effect
- Professional dark theme matching Wain's UI
- Status messages during loading
- Auto-closes when main app window is detected
"""

import sys
import os
import subprocess
import time
import math

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, 'assets')

# Check for logo with either spelling
LOGO_PATH = None
for logo_name in ['wain_logo.png', 'wain_logo.png']:
    path = os.path.join(ASSETS_DIR, logo_name)
    if os.path.exists(path):
        LOGO_PATH = path
        break

# ============================================================================
# SPLASH SCREEN (Tkinter - lightweight, loads instantly)
# ============================================================================

def create_splash():
    """Create and show professional splash screen using tkinter."""
    import tkinter as tk
    
    # ========== CONFIGURATION ==========
    WINDOW_WIDTH = 480
    WINDOW_HEIGHT = 360
    
    # Colors matching Wain's dark theme
    BG_COLOR = '#09090b'           # Near black (zinc-950)
    BORDER_COLOR = '#27272a'       # Zinc-800
    TEXT_PRIMARY = '#fafafa'       # Near white
    TEXT_SECONDARY = '#a1a1aa'     # Zinc-400
    TEXT_TERTIARY = '#52525b'      # Zinc-600
    PROGRESS_BG = '#18181b'        # Zinc-900
    PROGRESS_FILL = '#a1a1aa'      # Zinc-400 (neutral accent)
    PROGRESS_SHIMMER = '#d4d4d8'   # Zinc-300
    
    # ========== CREATE WINDOW ==========
    splash = tk.Tk()
    splash.title("")  # No title
    splash.overrideredirect(True)  # No window decorations
    splash.attributes('-topmost', True)
    splash.configure(bg=BG_COLOR)
    
    # Center on screen
    screen_w = splash.winfo_screenwidth()
    screen_h = splash.winfo_screenheight()
    x = (screen_w - WINDOW_WIDTH) // 2
    y = (screen_h - WINDOW_HEIGHT) // 2
    splash.geometry(f'{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}')
    
    # ========== MAIN CONTAINER ==========
    # Outer frame with subtle border
    outer_frame = tk.Frame(splash, bg=BORDER_COLOR, padx=1, pady=1)
    outer_frame.pack(expand=True, fill='both')
    
    # Inner frame
    frame = tk.Frame(outer_frame, bg=BG_COLOR)
    frame.pack(expand=True, fill='both')
    
    # ========== LOGO ==========
    logo_label = None
    try:
        if LOGO_PATH and os.path.exists(LOGO_PATH):
            from PIL import Image, ImageTk, ImageOps
            img = Image.open(LOGO_PATH)
            
            # Resize with high quality - large focal point
            img = img.resize((120, 120), Image.Resampling.LANCZOS)
            
            # Invert for dark background (logo is dark, we need light)
            if img.mode == 'RGBA':
                r, g, b, a = img.split()
                rgb = Image.merge('RGB', (r, g, b))
                rgb = ImageOps.invert(rgb)
                img = Image.merge('RGBA', (*rgb.split(), a))
            elif img.mode == 'RGB':
                img = ImageOps.invert(img)
            
            photo = ImageTk.PhotoImage(img)
            logo_label = tk.Label(frame, image=photo, bg=BG_COLOR)
            logo_label.image = photo  # Keep reference
            logo_label.pack(pady=(60, 30))
    except ImportError:
        # No PIL - show text fallback
        fallback = tk.Label(frame, text="WAIN", font=('Segoe UI', 48, 'bold'),
                           fg=TEXT_PRIMARY, bg=BG_COLOR)
        fallback.pack(pady=(60, 30))
    except Exception as e:
        print(f"Logo error: {e}")
    
    # ========== PROGRESS BAR ==========
    progress_frame = tk.Frame(frame, bg=BG_COLOR)
    progress_frame.pack(pady=(20, 15), padx=60, fill='x')
    
    # Progress track (background)
    PROGRESS_HEIGHT = 6
    PROGRESS_WIDTH = WINDOW_WIDTH - 120
    
    progress_canvas = tk.Canvas(
        progress_frame, 
        width=PROGRESS_WIDTH, 
        height=PROGRESS_HEIGHT,
        bg=PROGRESS_BG, 
        highlightthickness=0,
        bd=0
    )
    progress_canvas.pack()
    
    # Round the track corners
    progress_canvas.create_rectangle(
        0, 0, PROGRESS_WIDTH, PROGRESS_HEIGHT,
        fill=PROGRESS_BG, outline=PROGRESS_BG
    )
    
    # Progress fill bar (will be updated)
    progress_fill = progress_canvas.create_rectangle(
        0, 0, 0, PROGRESS_HEIGHT,
        fill=PROGRESS_FILL, outline=PROGRESS_FILL
    )
    
    # Shimmer overlay (animated highlight)
    shimmer_bar = progress_canvas.create_rectangle(
        -60, 0, -30, PROGRESS_HEIGHT,
        fill=PROGRESS_SHIMMER, outline=PROGRESS_SHIMMER
    )
    
    # ========== STATUS TEXT ==========
    status_var = tk.StringVar(value="Initializing...")
    status_label = tk.Label(
        frame, 
        textvariable=status_var,
        font=('Segoe UI', 10),
        fg=TEXT_SECONDARY,
        bg=BG_COLOR
    )
    status_label.pack(pady=(10, 0))
    
    # ========== VERSION ==========
    version_label = tk.Label(
        frame,
        text="v2.8.3",
        font=('Segoe UI', 9),
        fg=TEXT_TERTIARY,
        bg=BG_COLOR
    )
    version_label.pack(side='bottom', pady=(0, 20))
    
    # ========== ANIMATION STATE ==========
    splash.progress = 0
    splash.target_progress = 0
    splash.shimmer_pos = -60
    splash.start_time = time.time()
    splash.app_launched = False
    splash.app_detected = False
    
    # Status messages at different progress points
    STATUS_MESSAGES = {
        0: "Initializing...",
        12: "Loading dependencies...",
        30: "Preparing render engines...",
        50: "Building interface...",
        70: "Configuring settings...",
        85: "Almost ready...",
        95: "Launching...",
        100: "Ready"
    }
    
    def update_status():
        """Update status message based on progress."""
        current = int(splash.progress)
        msg = "Initializing..."
        for threshold, text in sorted(STATUS_MESSAGES.items()):
            if current >= threshold:
                msg = text
        status_var.set(msg)
    
    def ease_out_cubic(t):
        """Cubic ease-out for smooth deceleration."""
        return 1 - pow(1 - t, 3)
    
    def animate():
        """Main animation loop - 60fps."""
        if not splash.winfo_exists():
            return
        
        # Smoothly animate progress toward target
        diff = splash.target_progress - splash.progress
        if abs(diff) > 0.1:
            # Ease toward target
            splash.progress += diff * 0.08
        else:
            splash.progress = splash.target_progress
        
        # Update progress bar fill
        fill_width = (splash.progress / 100) * PROGRESS_WIDTH
        progress_canvas.coords(progress_fill, 0, 0, fill_width, PROGRESS_HEIGHT)
        
        # Animate shimmer (sweeps across the filled portion)
        if splash.progress > 5:
            splash.shimmer_pos += 3
            if splash.shimmer_pos > fill_width + 30:
                splash.shimmer_pos = -60
            
            # Only show shimmer within the filled area
            shimmer_start = max(0, splash.shimmer_pos)
            shimmer_end = min(fill_width, splash.shimmer_pos + 40)
            
            if shimmer_end > shimmer_start:
                progress_canvas.coords(shimmer_bar, shimmer_start, 0, shimmer_end, PROGRESS_HEIGHT)
                progress_canvas.itemconfig(shimmer_bar, state='normal')
            else:
                progress_canvas.itemconfig(shimmer_bar, state='hidden')
        
        # Update status text
        update_status()
        
        # Continue animation
        splash.after(16, animate)  # ~60fps
    
    def simulate_progress():
        """Simulate loading progress with realistic timing."""
        if not splash.winfo_exists():
            return
        
        elapsed = time.time() - splash.start_time
        
        if splash.app_detected:
            # App detected - complete quickly
            splash.target_progress = 100
            if splash.progress >= 99:
                splash.after(300, splash.destroy)
                return
        else:
            # Simulate natural loading progress
            if elapsed < 0.5:
                splash.target_progress = 10
            elif elapsed < 1.0:
                splash.target_progress = 25
            elif elapsed < 2.0:
                splash.target_progress = 40
            elif elapsed < 3.5:
                splash.target_progress = 55
            elif elapsed < 5.0:
                splash.target_progress = 70
            elif elapsed < 7.0:
                splash.target_progress = 82
            elif elapsed < 10.0:
                splash.target_progress = 90
            else:
                # Slow crawl after 10 seconds
                splash.target_progress = min(95, 90 + (elapsed - 10) * 0.5)
        
        # Safety timeout - close after 25 seconds regardless
        if elapsed > 25:
            splash.destroy()
            return
        
        splash.after(100, simulate_progress)
    
    def check_for_app():
        """Check if the main Wain window has appeared."""
        if not splash.winfo_exists():
            return
        
        if splash.app_detected:
            return
        
        # Use Windows API to find the window
        try:
            if sys.platform == 'win32':
                import ctypes
                user32 = ctypes.windll.user32
                
                # Look for Wain window
                hwnd = user32.FindWindowW(None, 'Wain')
                if hwnd and hwnd != 0:
                    # Verify it's visible
                    if user32.IsWindowVisible(hwnd):
                        splash.app_detected = True
                        splash.target_progress = 100
                        return
        except Exception:
            pass
        
        # Keep checking
        splash.after(200, check_for_app)
    
    def launch_app():
        """Launch the main Wain application."""
        if splash.app_launched:
            return
        splash.app_launched = True
        
        try:
            # Find the wain package
            wain_dir = SCRIPT_DIR
            
            # Use pythonw to avoid console window
            if sys.platform == 'win32':
                pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
                if not os.path.exists(pythonw):
                    pythonw = sys.executable
            else:
                pythonw = sys.executable
            
            # Launch as module
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            
            subprocess.Popen(
                [pythonw, '-m', 'wain'],
                cwd=wain_dir,
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"Launch error: {e}")
            status_var.set(f"Error: {e}")
    
    # ========== START ==========
    # Launch app after splash is shown
    splash.after(200, launch_app)
    
    # Start checking for app window
    splash.after(1000, check_for_app)
    
    # Start progress simulation
    splash.after(100, simulate_progress)
    
    # Start animation loop
    splash.after(16, animate)
    
    return splash


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    try:
        splash = create_splash()
        splash.mainloop()
    except Exception as e:
        print(f"Splash error: {e}")
        # If splash fails, just launch the app directly
        import subprocess
        subprocess.Popen([sys.executable, '-m', 'wain'], cwd=SCRIPT_DIR)
