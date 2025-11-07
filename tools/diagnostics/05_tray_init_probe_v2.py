# -*- coding: utf-8 -*-
"""
05_tray_init_probe_v2.py
Builds your real Tray with the correct constructor args (by name), guarantees a visible QSystemTrayIcon,
and adds a "Show Overlay (center)" action that runs on the GUI (Graphical User Interface) thread.
"""
import sys, inspect
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QStyle, QMenu
from PySide6.QtGui import QAction  # PySide6 puts QAction in QtGui

# --- ensure ProjectRoot/src on sys.path ---
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from KiCadPartsSyncer.ui.overlay import Overlay
from KiCadPartsSyncer.ui.tray import Tray
from KiCadPartsSyncer.infrastructure.system.event_hub import EventHub

def build_overlay_and_env(app: QApplication):
    hub = EventHub()
    # Try Overlay(hub, settings) then Overlay(settings)
    try:
        overlay = Overlay(hub)
    except TypeError:
        overlay = Overlay()
    # Defensive flags for HUD behavior
    overlay.setWindowFlag(Qt.Tool, True)
    overlay.setWindowFlag(Qt.FramelessWindowHint, True)
    overlay.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    overlay.setAttribute(Qt.WA_TranslucentBackground, True)
    return overlay, hub

def make_tray(app: QApplication, overlay, settings, hub):
    # Map ctor args by parameter name to avoid ordering issues
    sig = inspect.signature(Tray.__init__)
    names = list(sig.parameters.keys())  # includes 'self'
    kwargs = {}
    if "app" in names:      kwargs["app"] = app
    if "overlay" in names:  kwargs["overlay"] = overlay
    if "settings" in names: kwargs["settings"] = settings
    if "hub" in names:      kwargs["hub"] = hub
    return Tray(**kwargs)

def center_show_overlay(app, overlay):
    scr = overlay.screen() or app.primaryScreen()
    geo = scr.availableGeometry()
    w, h = max(420, overlay.width()), max(28, overlay.height())
    x = geo.x() + (geo.width() - w)//2
    y = geo.y() + int(geo.height()*0.05)
    overlay.setGeometry(x, y, w, h)
    overlay.show()
    QTimer.singleShot(120, lambda: (overlay.raise_(), overlay.activateWindow()))
    print("DIAG: overlay show requested from tray")

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Base sanity tray to ensure an icon is visible regardless of your Tray internals
    base_tray = QSystemTrayIcon()
    icon = app.style().standardIcon(QStyle.SP_MessageBoxInformation)
    base_tray.setIcon(icon)
    base_tray.setToolTip("Base Tray Sanity")
    base_tray.setVisible(True)
    base_tray.show()
    print("DIAG: base_tray.isVisible =", base_tray.isVisible())

    overlay, settings, hub = build_overlay_and_env(app)

    # Build your Tray with correct args (by name)
    t = make_tray(app, overlay, settings, hub)

    # Get underlying QSystemTrayIcon or make one
    tray = getattr(t, "tray", None)
    if not isinstance(tray, QSystemTrayIcon):
        tray = QSystemTrayIcon()
        tray.setIcon(icon)
        tray.setToolTip("Tray Init Probe v2")
        tray.setVisible(True)
        tray.show()

    # Use your tray's menu if exposed; else our own
    menu = getattr(t, "menu", None)
    if not isinstance(menu, QMenu):
        menu = QMenu()

    act_show = QAction("Show Overlay (center)")
    act_quit = QAction("Quit")

    act_show.triggered.connect(lambda: QTimer.singleShot(0, lambda: center_show_overlay(app, overlay)))
    act_quit.triggered.connect(app.quit)

    menu.addAction(act_show)
    menu.addSeparator()
    menu.addAction(act_quit)
    tray.setContextMenu(menu)

    def on_activated(reason: QSystemTrayIcon.ActivationReason):
        print(f"DIAG: tray.activated reason={int(reason)} (1=Context,2=Double,3=Trigger/Single,4=Middle)")
    tray.activated.connect(on_activated)

    print("DIAG: tray.isSystemTrayAvailable =", QSystemTrayIcon.isSystemTrayAvailable())
    print("DIAG: tray.supportsMessages =", QSystemTrayIcon.supportsMessages())
    print("DIAG: tray.isVisible =", tray.isVisible())

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
