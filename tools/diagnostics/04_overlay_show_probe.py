# -*- coding: utf-8 -*-
"""
04_overlay_show_probe.py
Runs your real Overlay (companion.ui.overlay.Overlay) in isolation.
Acronyms: GUI = Graphical User Interface, HUD = Heads-Up Display.
"""
import sys, inspect
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QTextEdit, QToolBar
from PySide6.QtGui import QAction

# --- ensure ProjectRoot/src is on sys.path ---
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]  # ProjectRoot/tools/diagnostics/...
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# --- import your real classes from src package ---
from KiCadPartsSyncer.ui.overlay import Overlay
from KiCadPartsSyncer.infrastructure.system.event_hub import EventHub

def flags_to_str(f):
    names = []
    for name in [
        "Tool", "FramelessWindowHint", "WindowStaysOnTopHint",
        "WindowTransparentForInput", "BypassWindowManagerHint",
        "NoDropShadowWindowHint",
    ]:
        if f & getattr(Qt, name):
            names.append(name)
    return "|".join(names) if names else "<none>"

def make_overlay():
    hub = EventHub()
    sig = inspect.signature(Overlay.__init__)
    params = list(sig.parameters.keys())  # ['self', ...]
    try:
        if len(params) >= 3:
            return Overlay(hub)   # Overlay(self, hub, settings)
        else:
            return Overlay()        # Overlay(self, settings)
    except TypeError:
        # Last-resort try both orders
        try:
            return Overlay()
        except TypeError:
            return Overlay(hub)

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Overlay Show Probe")
        self.resize(820, 480)

        self.log = QTextEdit(self); self.log.setReadOnly(True)
        self.setCentralWidget(self.log)
        bar = QToolBar("Controls"); self.addToolBar(bar)

        act_show = QAction("Show Overlay (center+raise)", self)
        act_flags = QAction("Log Flags/Geometry", self)
        bar.addAction(act_show); bar.addAction(act_flags)

        self.overlay = make_overlay()
        # Defensive flags
        self.overlay.setWindowFlag(Qt.Tool, True)
        self.overlay.setWindowFlag(Qt.FramelessWindowHint, True)
        self.overlay.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.overlay.setAttribute(Qt.WA_TranslucentBackground, True)

        act_show.triggered.connect(self.show_overlay_center)
        act_flags.triggered.connect(self.dump_state)
        QTimer.singleShot(50, self.show_overlay_center)

    def append(self, s: str):
        self.log.append(s); print(s)

    def dump_state(self):
        self.append(f"DIAG: overlay state -> isVisible={self.overlay.isVisible()} "
                    f"isActive={self.overlay.isActiveWindow()} "
                    f"geom={self.overlay.geometry().getRect()} "
                    f"flags={flags_to_str(self.overlay.windowFlags())}")

    def show_overlay_center(self):
        scr = self.overlay.screen() or self.screen()
        geo = scr.availableGeometry() if scr else self.geometry()
        w, h = max(420, self.overlay.width()), max(28, self.overlay.height())
        x = geo.x() + (geo.width() - w) // 2
        y = geo.y() + int(geo.height() * 0.05)
        self.overlay.setGeometry(x, y, w, h)

        self.append("DIAG: before show -> "
                    f"isVisible={self.overlay.isVisible()} flags={flags_to_str(self.overlay.windowFlags())}")
        self.overlay.show()
        QTimer.singleShot(120, lambda: (
            self.overlay.raise_(),
            self.overlay.activateWindow(),
            self.append("DIAG: nudge -> raised+activated"),
            self.dump_state()
        ))

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = Main(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
