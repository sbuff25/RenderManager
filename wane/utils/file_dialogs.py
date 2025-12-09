"""
Wane File Dialogs
=================

Async file and folder dialog helpers that work with pywebview/Qt.

Native file dialogs conflict with Qt/pywebview in the same process,
so we spawn a separate Python process for the tkinter dialog.
We use a result container and polling to safely update the UI.
"""

import os
import sys
import json
import subprocess
import threading
from typing import List, Optional, Callable

from nicegui import ui

# Global storage for pending file dialog results
_pending_file_results = {}
_result_counter = 0
_result_lock = threading.Lock()


def _run_file_dialog_subprocess(title: str, filetypes: list, initial_dir: str) -> Optional[str]:
    """Run file dialog in subprocess - called from background thread."""
    script = '''
import tkinter as tk
from tkinter import filedialog
import sys
import json

args = json.loads(sys.argv[1])
title = args.get('title', 'Select File')
filetypes = args.get('filetypes', [])
initial_dir = args.get('initial_dir', '')

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
root.lift()
root.update()

tk_filetypes = []
for name, pattern in filetypes:
    tk_filetypes.append((name, pattern))
tk_filetypes.append(('All Files', '*.*'))

result = filedialog.askopenfilename(
    title=title,
    filetypes=tk_filetypes,
    initialdir=initial_dir if initial_dir else None
)

print(result if result else '')
root.destroy()
'''
    
    args = {
        'title': title,
        'filetypes': filetypes or [],
        'initial_dir': initial_dir or ''
    }
    
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        proc = subprocess.Popen(
            [sys.executable, '-c', script, json.dumps(args)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags
        )
        stdout, stderr = proc.communicate(timeout=300)
        path = stdout.decode('utf-8').strip()
        if path and os.path.exists(path):
            return path
    except Exception as e:
        print(f"File dialog error: {e}")
    return None


def _run_folder_dialog_subprocess(title: str, initial_dir: str) -> Optional[str]:
    """Run folder dialog in subprocess - called from background thread."""
    script = '''
import tkinter as tk
from tkinter import filedialog
import sys
import json

args = json.loads(sys.argv[1])
title = args.get('title', 'Select Folder')
initial_dir = args.get('initial_dir', '')

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
root.lift()
root.update()

result = filedialog.askdirectory(
    title=title,
    initialdir=initial_dir if initial_dir else None
)

print(result if result else '')
root.destroy()
'''
    
    args = {
        'title': title,
        'initial_dir': initial_dir or ''
    }
    
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        proc = subprocess.Popen(
            [sys.executable, '-c', script, json.dumps(args)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags
        )
        stdout, stderr = proc.communicate(timeout=300)
        path = stdout.decode('utf-8').strip()
        if path and os.path.isdir(path):
            return path
    except Exception as e:
        print(f"Folder dialog error: {e}")
    return None


def open_file_dialog_async(
    title: str,
    filetypes: List[tuple],
    initial_dir: str,
    callback: Callable[[Optional[str]], None]
):
    """
    Open file dialog in background thread, call callback with result via polling.
    
    Args:
        title: Dialog window title
        filetypes: List of (description, pattern) tuples, e.g. [("Blender Files", "*.blend")]
        initial_dir: Starting directory path
        callback: Function to call with selected path (or None if cancelled)
    """
    global _result_counter
    
    with _result_lock:
        _result_counter += 1
        result_id = _result_counter
        _pending_file_results[result_id] = {'done': False, 'result': None, 'callback': callback}
    
    def run():
        result = _run_file_dialog_subprocess(title, filetypes, initial_dir)
        with _result_lock:
            if result_id in _pending_file_results:
                _pending_file_results[result_id]['result'] = result
                _pending_file_results[result_id]['done'] = True
    
    threading.Thread(target=run, daemon=True).start()
    
    # Start polling timer (created on main thread)
    def check_result():
        with _result_lock:
            if result_id in _pending_file_results:
                entry = _pending_file_results[result_id]
                if entry['done']:
                    result = entry['result']
                    cb = entry['callback']
                    del _pending_file_results[result_id]
                    cb(result)
                    return  # Stop polling
        # Keep polling
        ui.timer(0.1, check_result, once=True)
    
    ui.timer(0.1, check_result, once=True)


def open_folder_dialog_async(
    title: str,
    initial_dir: str,
    callback: Callable[[Optional[str]], None]
):
    """
    Open folder dialog in background thread, call callback with result via polling.
    
    Args:
        title: Dialog window title
        initial_dir: Starting directory path
        callback: Function to call with selected path (or None if cancelled)
    """
    global _result_counter
    
    with _result_lock:
        _result_counter += 1
        result_id = _result_counter
        _pending_file_results[result_id] = {'done': False, 'result': None, 'callback': callback}
    
    def run():
        result = _run_folder_dialog_subprocess(title, initial_dir)
        with _result_lock:
            if result_id in _pending_file_results:
                _pending_file_results[result_id]['result'] = result
                _pending_file_results[result_id]['done'] = True
    
    threading.Thread(target=run, daemon=True).start()
    
    # Start polling timer (created on main thread)
    def check_result():
        with _result_lock:
            if result_id in _pending_file_results:
                entry = _pending_file_results[result_id]
                if entry['done']:
                    result = entry['result']
                    cb = entry['callback']
                    del _pending_file_results[result_id]
                    cb(result)
                    return  # Stop polling
        # Keep polling
        ui.timer(0.1, check_result, once=True)
    
    ui.timer(0.1, check_result, once=True)
