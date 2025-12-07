# Render Manager ITT04-Native Desktop

NiceGUI as a **Native Desktop Application** - no browser, no web server!

## How It Works

This version uses:
- **NiceGUI** for the modern UI
- **pywebview** with Qt backend for the native window
- **PyQt6** as the rendering engine
- **tkinter** for native file dialogs (more reliable than Qt dialogs in this context)

The trick is setting `PYWEBVIEW_GUI=qt` before importing anything, which tells pywebview to use PyQt6 instead of EdgeChromium (which requires pythonnet and doesn't work on Python 3.14).

## Installation

```bash
pip install nicegui pywebview PyQt6
```

Note: tkinter comes built-in with Python on Windows.

## Running

Double-click `RenderManager_Native.bat` or:

```bash
python render_manager_ITT04_native.py
```

A native desktop window opens - no browser!

## Features

- **Resizable dialogs**: Drag the corner of Add Job/Settings dialogs to resize
- **Native file pickers**: Browse buttons open native Windows file dialogs
- **No notifications**: Desktop app mode - no connection lost messages
- **Consistent dark theme**: Custom scrollbars and styling throughout

## What Makes This Different

| Feature | ITT04 (Browser) | ITT04-Native Desktop |
|---------|-----------------|----------------------|
| Window type | Browser tab | **Native window** |
| Web server | localhost:8080 | **None visible** |
| File dialogs | Paste paths | **Native tkinter dialogs** |
| Feels like | Web app | **Desktop app** |

## The Magic Lines

At the top of the script:

```python
import os
os.environ['QT_API'] = 'pyqt6'        # Tell qtpy to use PyQt6
os.environ['PYWEBVIEW_GUI'] = 'qt'    # Use PyQt6 instead of EdgeChromium
```

This must be set BEFORE importing nicegui or pywebview.

Then NiceGUI runs with:

```python
ui.run(
    native=True,              # Desktop window mode
    window_size=(1200, 850),
    title='Render Manager',
    reconnect_timeout=0,      # Disable reconnection (desktop app)
)
```

## Comparison of All Versions

| Version | Framework | Window | File Dialogs | Dependencies |
|---------|-----------|--------|--------------|--------------|
| ITT03 | tkinter | Desktop | Native | None |
| ITT04 | NiceGUI | Browser | Paste paths | nicegui |
| **ITT04-Native** | NiceGUI+pywebview | **Desktop** | Native (tkinter) | nicegui, pywebview, PyQt6 |
| ITT05 | PyQt6 | Desktop | Native | PyQt6 |

## Why Not Just Use ITT05?

ITT05 (pure PyQt6) is also a great choice! The difference:

- **ITT04-Native**: Uses NiceGUI's component system (easier to modify UI)
- **ITT05**: Pure Qt widgets (more control, faster rendering)

Both are valid desktop applications. ITT04-Native is good if you prefer NiceGUI's web-like component model.

## Troubleshooting

**"No module named pywebview"**
```bash
pip install pywebview
```

**"No module named PyQt6"**
```bash
pip install PyQt6
```

**Window doesn't open / crashes**
Make sure the environment variable lines are at the very top of the script, before any other imports.

**Browse button doesn't work**
Make sure tkinter is available (it comes with Python on Windows).

## Config

Uses the same `render_manager_config.json` - your jobs carry over between versions!
