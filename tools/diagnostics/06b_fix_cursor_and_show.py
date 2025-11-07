# -*- coding: utf-8 -*-
"""
06_fix_cursor_and_show.py
Add-only diagnostic launcher that patches Overlay methods at runtime:
- Overlay.show(): force onto the GUI (Graphical User Interface) thread, reapply flags, center, raise, log DIAG
- Overlay.show_overlay(): replace bad QGuiApplication.cursor() with PySide6-safe QCursor.pos(), clamp to screen
Then runs ProjectRoot/run.py unchanged.
"""
import sys, runpy
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QAction, QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QStyle, QMenu

HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from KiCadPartsSyncer.ui.overlay import Overlay  # import after sys.path fix

# ---------- helpers ----------
def _flags_to_str(f):
    names = []
    for name in [
        "Tool", "FramelessWindowHint", "WindowStaysOnTopHint",
        "WindowTransparentForInput", "BypassWindowManagerHint",
        "NoDropShadowWindowHint",
    ]:
        if f & getattr(Qt, name):
            names.append(name)
    return "|".join(names) if names else "<none>"

def _active_screen_and_geo(point: QPoint = None):
    app = QApplication.instance()
    scr = None
    if point is not None:
        # PySide6: QGuiApplication.screenAt(QPoint) exists on Qt 6.x; guard just in case
        screenAt = getattr(QGuiApplication, "screenAt", None)
        if callable(screenAt):
            scr = screenAt(point)
    if scr is None:
        scr = (QGuiApplication.primaryScreen() if QGuiApplication.primaryScreen() else (app.primaryScreen() if app else None))
    geo = scr.availableGeometry() if scr else None
    return scr, geo

def _center_on_geo(w, geo):
    W = max(420, w.width())
    H = max(28,  w.height())
    x = geo.x() + (geo.width()  - W) // 2
    y = geo.y() + int(geo.height() * 0.05)
    w.setGeometry(x, y, W, H)

def _clamp_to_geo(x, y, W, H, geo):
    x = max(geo.x(), min(geo.right() - W + 1, x))
    y = max(geo.y(), min(geo.bottom() - H + 1, y))
    return x, y

# ---------- patch Overlay.show ----------
_orig_show = Overlay.show

def _patched_show(self):
    print(f"DIAG: Overlay.show intercepted -> isVisible={self.isVisible()} flags={_flags_to_str(self.windowFlags())}")
    def _do():
        self.setWindowFlag(Qt.Tool, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # center on active screen
        _, geo = _active_screen_and_geo()
        if geo:
            _center_on_geo(self, geo)

        print("DIAG: Overlay.show -> applying flags & centering, then QWidget.show()")
        _orig_show(self)
        QTimer.singleShot(120, lambda: (
            self.raise_(),
            self.activateWindow(),
            print(f"DIAG: Overlay after show -> isVisible={self.isVisible()} geom={self.geometry().getRect()} flags={_flags_to_str(self.windowFlags())}")
        ))
    QTimer.singleShot(0, _do)

Overlay.show = _patched_show  # runtime patch

# ---------- patch Overlay.show_overlay (bad API fix) ----------
def _patched_show_overlay(self):
    try:
        pos = QCursor.pos()  # PySide6-correct global cursor position
    except Exception:
        pos = None

    scr, geo = _active_screen_and_geo(pos)
    if geo is None:
        # fallback: just call show(); our patched show() will center later
        print("DIAG: show_overlay -> no screen geo; delegating to show()")
        self.show()
        return

    W = max(420, self.width())
    H = max(28,  self.height())
    if pos is None:
        _center_on_geo(self, geo)
    else:
        # place near cursor, then clamp to screen
        x = pos.x() - W // 2
        y = pos.y() + 20
        x, y = _clamp_to_geo(x, y, W, H, geo)
        self.setGeometry(x, y, W, H)

    print(f"DIAG: show_overlay -> at geom={self.geometry().getRect()} (cursor-driven)")
    self.show()  # uses patched show() to raise/activate

# Replace only if method exists
if hasattr(Overlay, "show_overlay"):
    setattr(Overlay, "show_overlay", _patched_show_overlay)

# ---------- install a small diagnostic tray AFTER QApplication exists ----------
_orig_qapp_init = QApplication.__init__
_installed = {"ok": False}

def _install_diag_tray(app: QApplication):
    if _installed["ok"]:
        return
    tray = QSystemTrayIcon(app.style().standardIcon(QStyle.SP_MessageBoxInformation))
    tray.setToolTip("HUD Diagnostics")
    menu = QMenu()
    act_show = QAction("Show HUD (center)")
    act_quit = QAction("Quit App")

    def _show_any_overlay():
        for w in app.topLevelWidgets():
            if isinstance(w, Overlay):
                w.show()  # patched show() handles GUI thread + raise
        print("DIAG: tray -> requested Overlay.show()")

    act_show.triggered.connect(lambda: QTimer.singleShot(0, _show_any_overlay))
    act_quit.triggered.connect(app.quit)
    menu.addAction(act_show); menu.addSeparator(); menu.addAction(act_quit)
    tray.setContextMenu(menu)
    tray.setVisible(True); tray.show()
    print("DIAG: diag tray installed; tray.isVisible =", tray.isVisible())
    _installed["ok"] = True

def _patched_qapp_init(self, *args, **kwargs):
    _orig_qapp_init(self, *args, **kwargs)
    QTimer.singleShot(0, lambda: _install_diag_tray(self))

QApplication.__init__ = _patched_qapp_init

# ---------- launch your real app ----------
RUN = PROJECT_ROOT / "run.py"
if not RUN.exists():
    print("DIAG: ERROR -> ProjectRoot/run.py not found.")
    sys.exit(1)

print("DIAG: launching real app via run.py ...")
runpy.run_path(str(RUN), run_name="__main__")
