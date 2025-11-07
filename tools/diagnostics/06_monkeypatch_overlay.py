# -*- coding: utf-8 -*-
"""
06_monkeypatch_overlay.py (fixed: no pre-App creation)
- Patches companion.ui.overlay.Overlay.show() to always run on the Qt GUI (Graphical User Interface) thread,
  reapply flags, center, raise/activate, and emit DIAG logs.
- Patches QApplication.__init__ to install a small diagnostics tray AFTER your app creates QApplication.
- Then launches your real app by executing run.py as __main__.
Run:
    python tools/diagnostics/06_monkeypatch_overlay.py
"""
import sys, runpy
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QStyle, QMenu

HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Import target class to patch
from KiCadPartsSyncer.ui.overlay import Overlay  # noqa: E402

# -------- Overlay.show patch --------
_orig_show = Overlay.show

def _flags_to_str(f):
    names = []
    for name in [
        "Tool", "FramelessWindowHint", "WindowStaysOnTopHint",
        "WindowTransparentForInput", "BypassWindowManagerHint",
        "WindowTransparentForInput", "NoDropShadowWindowHint",
    ]:
        if f & getattr(Qt, name):
            names.append(name)
    return "|".join(names) if names else "<none>"

def _center_on_active_screen(w):
    app = QApplication.instance()
    scr = (w.screen() or (app.primaryScreen() if app else None))
    if scr:
        geo = scr.availableGeometry()
        W = max(420, w.width())
        H = max(28,  w.height())
        x = geo.x() + (geo.width()  - W) // 2
        y = geo.y() + int(geo.height() * 0.05)
        w.setGeometry(x, y, W, H)

def _patched_show(self):
    print(f"DIAG: Overlay.show intercepted -> isVisible={self.isVisible()} "
          f"flags={_flags_to_str(self.windowFlags())}")
    def _do():
        self.setWindowFlag(Qt.Tool, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        _center_on_active_screen(self)

        print("DIAG: Overlay.show -> applying flags & centering, then QWidget.show()")
        _orig_show(self)
        QTimer.singleShot(120, lambda: (
            self.raise_(),
            self.activateWindow(),
            print(f"DIAG: Overlay after show -> isVisible={self.isVisible()} "
                  f"geom={self.geometry().getRect()} flags={_flags_to_str(self.windowFlags())}")
        ))
    QTimer.singleShot(0, _do)  # force onto GUI thread

Overlay.show = _patched_show  # runtime patch

# -------- Install diagnostics tray AFTER QApplication exists --------
_orig_qapp_init = QApplication.__init__
_tray_installed = {"done": False}

def _install_diag_tray(app: QApplication):
    if _tray_installed["done"]:
        return
    tray = QSystemTrayIcon()
    tray.setIcon(app.style().standardIcon(QStyle.SP_MessageBoxInformation))
    tray.setToolTip("HUD Diagnostics")
    tray.setVisible(True); tray.show()

    menu = QMenu()
    act_show = QAction("Show HUD (center)")
    act_quit = QAction("Quit App")

    def _show_any_overlay():
        # Call show() on any Overlay top-level widgets (uses our patched show)
        for w in app.topLevelWidgets():
            if isinstance(w, Overlay):
                w.show()
        print("DIAG: tray -> requested Overlay.show()")

    act_show.triggered.connect(lambda: QTimer.singleShot(0, _show_any_overlay))
    act_quit.triggered.connect(app.quit)
    menu.addAction(act_show); menu.addSeparator(); menu.addAction(act_quit)
    tray.setContextMenu(menu)
    print("DIAG: diag tray installed; tray.isVisible =", tray.isVisible())
    _tray_installed["done"] = True

def _patched_qapp_init(self, *args, **kwargs):
    _orig_qapp_init(self, *args, **kwargs)
    # Install tray on the next event-loop turn so widgets can register
    QTimer.singleShot(0, lambda: _install_diag_tray(self))

QApplication.__init__ = _patched_qapp_init  # runtime patch

# -------- Launch your real app --------
RUN = PROJECT_ROOT / "run.py"
if not RUN.exists():
    print("DIAG: ERROR -> ProjectRoot/run.py not found.")
    sys.exit(1)

print("DIAG: launching real app via run.py ...")
runpy.run_path(str(RUN), run_name="__main__")
