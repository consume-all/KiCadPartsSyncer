# -*- coding: utf-8 -*-
"""
09_overlay_size_check.py

Diagnostic: Verify Overlay's internal frame (_root) resizes
to match the window during its first show().

Consistent with previous diagnostic patterns (07_event_tap_and_autoshow.py).

Usage:
    python tools/diagnostics/09_overlay_size_check.py
Expected:
    - Console prints window vs _root sizes before and after show_overlay()
    - If first pair differs, initial white HUD background confirmed.
"""

from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# ---- ensure src on sys.path (consistent with 07_event_tap_and_autoshow.py) ----
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# ---- import Overlay after path fix ----
from KiCadPartsSyncer.ui.overlay import Overlay


# ---- Minimal dummy settings + hub for isolation ----
class DummySettings:
    def __init__(self):
        self._data = {}

    def get(self, k, d=None):
        return self._data.get(k, d)

    def set(self, k, v):
        self._data[k] = v

    def save(self):
        pass


class DummyHub:
    pass


# ---- main diagnostic entrypoint ----
def main():
    app = QApplication(sys.argv)
    overlay = Overlay(hub=DummyHub(), settings=DummySettings())

    print("\n[09] Initial sizes before show():")
    print("  window:", overlay.size(), "root:", overlay._body.size())

    overlay.show_overlay()
    app.processEvents()

    print("\n[09] After show_overlay() + processEvents():")
    print("  window:", overlay.size(), "root:", overlay._body.size())

    print("\n→ Try hiding/re-showing manually to confirm visual repaint behavior.\n")
    overlay.flash()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
