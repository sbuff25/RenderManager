"""
Wain File Dialogs
=================

Async file and folder dialog helpers.
"""

import os
import sys
import json
import subprocess
import threading
from typing import List, Optional, Callable

from nicegui import ui

_pending_file_results = {}
_result_counter = 0
_result_lock = threading.Lock()


def _run_file_dialog_subprocess(title: str, filetypes: list, initial_dir: str) -> Optional[str]:
    script = '''
import tkinter as tk
from tkinter import filedialog
import sys
import json

args = json.loads(sys.argv[1])
root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
root.lift()
root.update()

tk_filetypes = [(name, pattern) for name, pattern in args.get('filetypes', [])]
tk_filetypes.append(('All Files', '*.*'))

result = filedialog.askopenfilename(
    title=args.get('title', 'Select File'),
    filetypes=tk_filetypes,
    initialdir=args.get('initial_dir', '') or None
)

print(result if result else '')
root.destroy()
'''
    
    args = {'title': title, 'filetypes': filetypes or [], 'initial_dir': initial_dir or ''}
    
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        proc = subprocess.Popen([sys.executable, '-c', script, json.dumps(args)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
        stdout, _ = proc.communicate(timeout=300)
        path = stdout.decode('utf-8').strip()
        if path and os.path.exists(path):
            return path
    except:
        pass
    return None


def _run_folder_dialog_subprocess(title: str, initial_dir: str) -> Optional[str]:
    script = '''
import tkinter as tk
from tkinter import filedialog
import sys
import json

args = json.loads(sys.argv[1])
root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
root.lift()
root.update()

result = filedialog.askdirectory(title=args.get('title', 'Select Folder'), initialdir=args.get('initial_dir', '') or None)
print(result if result else '')
root.destroy()
'''
    
    args = {'title': title, 'initial_dir': initial_dir or ''}
    
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        proc = subprocess.Popen([sys.executable, '-c', script, json.dumps(args)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
        stdout, _ = proc.communicate(timeout=300)
        path = stdout.decode('utf-8').strip()
        if path and os.path.isdir(path):
            return path
    except:
        pass
    return None


def open_file_dialog_async(title: str, filetypes: List[tuple], initial_dir: str, callback: Callable[[Optional[str]], None]):
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
    
    def check_result():
        with _result_lock:
            if result_id in _pending_file_results:
                entry = _pending_file_results[result_id]
                if entry['done']:
                    result = entry['result']
                    cb = entry['callback']
                    del _pending_file_results[result_id]
                    cb(result)
                    return
        ui.timer(0.1, check_result, once=True)
    
    ui.timer(0.1, check_result, once=True)


def open_folder_dialog_async(title: str, initial_dir: str, callback: Callable[[Optional[str]], None]):
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
    
    def check_result():
        with _result_lock:
            if result_id in _pending_file_results:
                entry = _pending_file_results[result_id]
                if entry['done']:
                    result = entry['result']
                    cb = entry['callback']
                    del _pending_file_results[result_id]
                    cb(result)
                    return
        ui.timer(0.1, check_result, once=True)
    
    ui.timer(0.1, check_result, once=True)
