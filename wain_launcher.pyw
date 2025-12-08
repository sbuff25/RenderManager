#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wain Launcher with Splash Screen
================================
Shows a professional splash screen immediately, then loads the main app in the background.
Uses .pyw extension so Windows runs it without a console window.
"""

import sys
import os
import subprocess
import time

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, 'assets')
LOGO_PATH = os.path.join(ASSETS_DIR, 'wain_logo.png')

# ============================================================================
# SPLASH SCREEN (Tkinter - lightweight, loads instantly)
# ============================================================================

def create_splash():
    """Create and show splash screen using tkinter (fast, no heavy deps)."""
    import tkinter as tk
    
    # ========== CONFIGURATION ==========
    WINDOW_WIDTH = 380
    WINDOW_HEIGHT = 260
    BG_COLOR = '#09090b'           # Near black
    ACCENT_COLOR = '#a1a1aa'       # Zinc-400 (neutral accent)
    TEXT_PRIMARY = '#fafafa'       # Near white
    TEXT_SECONDARY = '#71717a'     # Zinc-500
    TEXT_TERTIARY = '#3f3f46'      # Zinc-700
    PROGRESS_BG = '#27272a'        # Zinc-800
    PROGRESS_GLOW = '#52525b'      # Zinc-600
    
    # ========== CREATE WINDOW ==========
    splash = tk.Tk()
    splash.title("")  # No title (window is borderless anyway)
    splash.overrideredirect(True)  # No window decorations
    splash.attributes('-topmost', True)
    splash.configure(bg=BG_COLOR)
    
    # Center on screen
    screen_w = splash.winfo_screenwidth()
    screen_h = splash.winfo_screenheight()
    x = (screen_w - WINDOW_WIDTH) // 2
    y = (screen_h - WINDOW_HEIGHT) // 2
    splash.geometry(f'{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}')
    
    # Add subtle shadow/border effect (Windows 10/11 style)
    splash.attributes('-transparentcolor', '')
    
    # ========== MAIN CONTAINER ==========
    # Outer frame with subtle border
    outer_frame = tk.Frame(splash, bg='#18181b', padx=1, pady=1)
    outer_frame.pack(expand=True, fill='both')
    
    # Inner frame
    frame = tk.Frame(outer_frame, bg=BG_COLOR)
    frame.pack(expand=True, fill='both')
    
    # ========== LOGO ==========
    logo_label = None
    try:
        if os.path.exists(LOGO_PATH):
            from PIL import Image, ImageTk, ImageOps
            img = Image.open(LOGO_PATH)
            
            # Resize with high quality - larger since it's the main focus now
            img = img.resize((100, 100), Image.Resampling.LANCZOS)
            
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
            logo_label.pack(pady=(55, 35))
    except ImportError:
        pass
    except Exception as e:
        print(f"Logo error: {e}")
    
    # ========== PROGRESS SECTION ==========
    progress_section = tk.Frame(frame, bg=BG_COLOR)
    progress_section.pack(fill='x', padx=50, pady=(0, 30))
    
    # Progress bar container (rounded corners simulation)
    progress_container = tk.Frame(progress_section, bg=PROGRESS_BG, height=4)
    progress_container.pack(fill='x')
    progress_container.pack_propagate(False)
    
    # Progress bar fill (using Canvas for smoother animation)
    progress_canvas = tk.Canvas(
        progress_container, 
        height=4, 
        bg=PROGRESS_BG, 
        highlightthickness=0
    )
    progress_canvas.pack(fill='both', expand=True)
    
    # Draw initial progress bar
    bar_width = 300  # Will be updated dynamically
    progress_bar = progress_canvas.create_rectangle(
        0, 0, 0, 4, 
        fill=ACCENT_COLOR, 
        outline=''
    )
    
    # Shimmer effect rectangle (for animation)
    shimmer = progress_canvas.create_rectangle(
        -50, 0, -20, 4,
        fill='#d4d4d8',  # Lighter for shimmer
        outline=''
    )
    
    # ========== STATUS TEXT ==========
    status_var = tk.StringVar(value="Loading...")
    status_label = tk.Label(
        progress_section,
        textvariable=status_var,
        font=('Segoe UI', 9),
        fg=TEXT_TERTIARY,
        bg=BG_COLOR
    )
    status_label.pack(pady=(12, 0))
    
    # ========== ANIMATION STATE ==========
    splash.progress = 0
    splash.target_progress = 0
    splash.shimmer_pos = -50
    splash.status_var = status_var
    splash.progress_canvas = progress_canvas
    splash.progress_bar = progress_bar
    splash.shimmer = shimmer
    splash.bar_width = 300
    splash.app_detected = False
    splash.start_time = time.time()
    
    # Status messages at different progress points
    STATUS_MESSAGES = {
        0: "Loading...",
        40: "Starting...",
        80: "Almost ready...",
        100: ""
    }
    
    def update_status(progress):
        """Update status text based on progress."""
        for threshold in sorted(STATUS_MESSAGES.keys(), reverse=True):
            if progress >= threshold:
                splash.status_var.set(STATUS_MESSAGES[threshold])
                break
    
    def ease_out_cubic(t):
        """Easing function for smooth animation."""
        return 1 - pow(1 - t, 3)
    
    def animate():
        """Main animation loop."""
        if not splash.winfo_exists():
            return
        
        # Get current canvas width
        splash.update_idletasks()
        canvas_width = splash.progress_canvas.winfo_width()
        if canvas_width > 1:
            splash.bar_width = canvas_width
        
        # Smoothly animate progress toward target
        diff = splash.target_progress - splash.progress
        if abs(diff) > 0.5:
            # Ease toward target
            splash.progress += diff * 0.08
        else:
            splash.progress = splash.target_progress
        
        # Update progress bar
        bar_end = (splash.progress / 100) * splash.bar_width
        splash.progress_canvas.coords(splash.progress_bar, 0, 0, bar_end, 4)
        
        # Animate shimmer effect (only when loading, not at 100%)
        if splash.progress < 100:
            splash.shimmer_pos += 4
            if splash.shimmer_pos > splash.bar_width + 50:
                splash.shimmer_pos = -50
            
            # Only show shimmer within the progress bar
            shimmer_start = max(0, splash.shimmer_pos)
            shimmer_end = min(bar_end, splash.shimmer_pos + 30)
            
            if shimmer_end > shimmer_start and shimmer_start < bar_end:
                splash.progress_canvas.coords(splash.shimmer, shimmer_start, 0, shimmer_end, 4)
                splash.progress_canvas.itemconfig(splash.shimmer, state='normal')
            else:
                splash.progress_canvas.itemconfig(splash.shimmer, state='hidden')
        else:
            splash.progress_canvas.itemconfig(splash.shimmer, state='hidden')
        
        # Update status text
        update_status(int(splash.progress))
        
        # Check if app window is detected and progress is complete
        if splash.app_detected and splash.progress >= 99:
            splash.after(300, splash.destroy)  # Brief pause then close
            return
        
        # Timeout after 20 seconds
        if time.time() - splash.start_time > 20:
            splash.destroy()
            return
        
        # Continue animation
        splash.after(16, animate)  # ~60fps
    
    def check_for_app():
        """Check if the main Wain window has appeared."""
        if not splash.winfo_exists():
            return
        
        try:
            import ctypes
            
            # Look for Wain window
            hwnd = ctypes.windll.user32.FindWindowW(None, 'Wain')
            
            if hwnd:
                splash.app_detected = True
                splash.target_progress = 100
                return
            
            # Also check for NiceGUI window (might have different title initially)
            # Enumerate windows and look for our process
            def check_windows():
                found = False
                
                def enum_callback(hwnd, _):
                    nonlocal found
                    if ctypes.windll.user32.IsWindowVisible(hwnd):
                        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
                        if length > 1:
                            buff = ctypes.create_unicode_buffer(length)
                            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length)
                            title = buff.value.lower()
                            if 'wain' in title or 'nicegui' in title:
                                found = True
                                return False  # Stop enumeration
                    return True
                
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
                return found
            
            if check_windows():
                splash.app_detected = True
                splash.target_progress = 100
                return
                
        except Exception as e:
            pass
        
        # Simulate progress while waiting
        elapsed = time.time() - splash.start_time
        if not splash.app_detected:
            # Progress curve: fast start, slow in middle, fast at end when detected
            if elapsed < 1:
                splash.target_progress = min(30, elapsed * 30)
            elif elapsed < 3:
                splash.target_progress = 30 + (elapsed - 1) * 15
            elif elapsed < 8:
                splash.target_progress = 60 + (elapsed - 3) * 6
            else:
                splash.target_progress = min(90, 90)
        
        # Check again
        splash.after(100, check_for_app)
    
    def launch_app():
        """Launch the main Wain application."""
        try:
            wain_script = os.path.join(SCRIPT_DIR, 'wain.py')
            if os.path.exists(wain_script):
                # Use pythonw to avoid console window
                pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
                if not os.path.exists(pythonw):
                    pythonw = sys.executable
                
                # Launch detached
                subprocess.Popen(
                    [pythonw, wain_script],
                    cwd=SCRIPT_DIR,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception as e:
            print(f"Launch error: {e}")
    
    # ========== START ==========
    # Launch app after a brief delay (let splash render first)
    splash.after(100, launch_app)
    
    # Start checking for app window
    splash.after(500, check_for_app)
    
    # Start animation
    splash.after(16, animate)
    
    # Initial progress boost
    splash.target_progress = 10
    
    return splash


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    splash = create_splash()
    splash.mainloop()
