#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wain - PyInstaller Entry Point
==============================

Top-level entry script for frozen .exe builds (see wain.spec).
Running from source should keep using `python -m wain` or Wain.bat.

freeze_support() MUST run before anything else: NiceGUI's native window mode
uses multiprocessing, and without it every spawned child re-runs the whole
application (infinite window spawn).

v2.20.0 - Initial version (installer phase)

https://github.com/sbuff25/RenderManager
"""

from multiprocessing import freeze_support

if __name__ in {"__main__", "__mp_main__"}:
    freeze_support()
    from wain.__main__ import run
    run()
