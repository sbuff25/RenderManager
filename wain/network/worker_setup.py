"""
Wain Worker Setup
=================

Connection settings for worker (render node) mode.

Installed builds launch the worker from a Start-menu shortcut with no
command-line arguments, so the server address and API token are persisted in
the writable data dir (wain_worker.json). On first run a small tkinter dialog
prompts for them.

v2.20.0 - Initial version (installer phase)

https://github.com/sbuff25/RenderManager
"""

import json
import os

from wain.config import DATA_DIR

WORKER_CONFIG_FILE = os.path.join(DATA_DIR, "wain_worker.json")


def _load_saved():
    try:
        with open(WORKER_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('server') or None, data.get('token') or None
    except Exception:
        return None, None


def _save(server: str, token: str):
    try:
        with open(WORKER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'server': server, 'token': token or ''}, f, indent=2)
    except Exception as e:
        print(f"[Worker] Could not save worker config: {e}")


def _prompt_dialog(default_server: str = "", default_token: str = ""):
    """Small tkinter dialog asking for server address and API token.

    Returns (server, token) or (None, None) if cancelled/unavailable.
    """
    try:
        import tkinter as tk
    except ImportError:
        return None, None

    result = {'server': None, 'token': None}

    root = tk.Tk()
    root.title("Wain Worker Setup")
    root.configure(bg='#09090b')
    root.resizable(False, False)
    root.attributes('-topmost', True)

    w, h = 420, 230
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f'{w}x{h}+{x}+{y}')

    tk.Label(root, text="Connect to Wain Server", font=('Segoe UI', 13, 'bold'),
             fg='#fafafa', bg='#09090b').pack(pady=(18, 2))
    tk.Label(root, text="Find these on the server: Wain log shows the API token at startup.",
             font=('Segoe UI', 8), fg='#71717a', bg='#09090b').pack()

    frm = tk.Frame(root, bg='#09090b')
    frm.pack(pady=10, padx=24, fill='x')

    tk.Label(frm, text="Server (ip:port)", font=('Segoe UI', 9),
             fg='#a1a1aa', bg='#09090b', anchor='w').grid(row=0, column=0, sticky='w')
    server_var = tk.StringVar(value=default_server or "192.168.1.10:8080")
    tk.Entry(frm, textvariable=server_var, font=('Segoe UI', 10), width=34,
             bg='#18181b', fg='#fafafa', insertbackground='#fafafa',
             relief='flat').grid(row=1, column=0, sticky='we', pady=(2, 8))

    tk.Label(frm, text="API token", font=('Segoe UI', 9),
             fg='#a1a1aa', bg='#09090b', anchor='w').grid(row=2, column=0, sticky='w')
    token_var = tk.StringVar(value=default_token or "")
    tk.Entry(frm, textvariable=token_var, font=('Segoe UI', 10), width=34,
             bg='#18181b', fg='#fafafa', insertbackground='#fafafa',
             relief='flat').grid(row=3, column=0, sticky='we', pady=(2, 0))
    frm.columnconfigure(0, weight=1)

    def on_connect():
        result['server'] = server_var.get().strip()
        result['token'] = token_var.get().strip()
        root.destroy()

    def on_cancel():
        root.destroy()

    btns = tk.Frame(root, bg='#09090b')
    btns.pack(pady=12)
    tk.Button(btns, text="Cancel", command=on_cancel, font=('Segoe UI', 9),
              bg='#18181b', fg='#a1a1aa', relief='flat', padx=14, pady=4).pack(side='left', padx=6)
    tk.Button(btns, text="Connect", command=on_connect, font=('Segoe UI', 9, 'bold'),
              bg='#3f3f46', fg='#ffffff', relief='flat', padx=14, pady=4).pack(side='left', padx=6)

    root.bind('<Return>', lambda e: on_connect())
    root.bind('<Escape>', lambda e: on_cancel())
    root.mainloop()

    return result['server'] or None, result['token'] or None


def get_worker_connection(args):
    """Resolve (server, token) for worker mode.

    Priority: CLI args > saved wain_worker.json > interactive prompt.
    Whatever is resolved gets saved for next launch. Returns (None, None)
    if nothing could be resolved (caller should exit).
    """
    saved_server, saved_token = _load_saved()

    server = args.server or saved_server
    token = args.token or saved_token

    if not server:
        server, token = _prompt_dialog(saved_server or "", saved_token or "")

    if server:
        _save(server, token or '')

    return server, token
