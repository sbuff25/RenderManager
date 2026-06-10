# -*- mode: python ; coding: utf-8 -*-
"""
Wain PyInstaller Spec (v2.20.0)
===============================

Build:   pyinstaller wain.spec --noconfirm
Output:  dist/Wain/Wain.exe  (onedir — QtWebEngine does not play well with onefile)

Notes:
- nicegui ships static web assets that must be collected explicitly
- pywinauto needs comtypes hidden imports (COM code generation at runtime)
- console=False: stdout/stderr are redirected to %APPDATA%/Wain/wain_console.log
  by wain/__main__.py in frozen builds
- tkinter is kept: the worker first-run setup dialog uses it

https://github.com/sbuff25/RenderManager
"""

from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets')]
binaries = []
hiddenimports = [
    'qtpy',
    'webview',
    'webview.platforms.qt',
    'pywinauto',
    'pywinauto.application',
    'comtypes',
    'comtypes.client',
    'comtypes.stream',
    'tkinter',
    'PIL.ImageTk',
]

# nicegui bundles its web frontend as package data — collect everything
for _pkg in ('nicegui',):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

a = Analysis(
    ['wain_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Wain uses PyQt6 only — other Qt bindings installed in the build env
        # must be excluded or PyInstaller aborts (multiple Qt bindings error)
        'PyQt5', 'PySide2', 'PySide6',
        'matplotlib', 'numpy.testing', 'pytest', 'IPython',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Wain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon='assets/wain_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='Wain',
)
