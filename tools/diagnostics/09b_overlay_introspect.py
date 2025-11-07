# -*- coding: utf-8 -*-
"""
09_overlay_introspect.py
Quick helper to list private attributes of Overlay
so we can see what the internal HUD container is named.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# ---- ensure src on sys.path ----
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from KiCadPartsSyncer.ui.overlay import Overlay


class DummySettings:
    def get(self, *a, **k): return None
    def set(self, *a, **k): pass
    def save(self): pass


app = QApplication([])
o = Overlay(None, DummySettings())

print("\nOverlay attributes (private ones only):")
for name in dir(o):
    if not name.startswith("_"):
        continue
    if any(key in name for key in ("frame", "root", "widget", "body", "container")):
        print("   ", name)
