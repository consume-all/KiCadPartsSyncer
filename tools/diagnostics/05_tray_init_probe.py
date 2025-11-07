# -*- coding: utf-8 -*-
"""
05_tray_init_probe.py
Constructs your real Tray and guarantees a visible QSystemTrayIcon.
Acronyms: GUI = Graphical User Interface.
"""
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QStyle
from PySide6.QtGui import QAction

# --- ensure ProjectRoot/src is on sys.path ---
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from KiCadPartsSyncer.ui.overlay import Overlay
from KiCadPartsSyncer.ui.tray import Tray
from KiCadPartsSyncer.infrastructure.system.event_hub import EventHub

def build_overlay():
    try:
        return Overlay(hub)
    except TypeError:
        return Overlay()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    overlay = build_overlay()
    overlay.setWindowFlag(Qt.Tool, True)
    overlay.setWindowFlag(Qt.FramelessWindowHint, True)
    overlay.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    overlay.setAttribute(Qt.WA_TranslucentBackground, True)

    # Always create a guaranteed visible tray first
    base_tray = QSystemTrayIcon()
    icon = app.style().standardIcon(QStyle.SP_MessageBoxInformation)
    base_tray.setIcon(icon); base_tray.setToolTip("Base Tray Sanity")
    base_tray.setVisible(True); base_tray.show()
    print("DIAG: base_tray.isVisible =", base_tray.isVisible())

    # Build your Tray; adapt to its constructor variants
    try:
        t = Tray()
    except TypeError:
        try:
            t = Tray(overlay)
        except TypeError:
            t = Tray(EventHub(), overlay)

    tray = getattr(t, "tray", None)
    if not isinstance(tray, QSystemTrayIcon):
        tray = QSystemTrayIcon()
        tray.setIcon(icon); tray.setToolTip("Tray Init Probe")
        tray.setVisible(True); tray.show()

    from PySide6.QtWidgets import QMenu
    menu = getattr(t, "menu", None) or QMenu()
    show_act = QAction("Show Overlay (center)")
    quit_act = QAction("Quit")
    def center_show_overlay():
        scr = overlay.screen() or app.primaryScreen()
        geo = scr.availableGeometry()
        w, h = max(420, overlay.width()), max(28, overlay.height())
        x = geo.x() + (geo.width() - w)//2; y = geo.y() + int(geo.height()*0.05)
        overlay.setGeometry(x, y, w, h)
        overlay.show()
        QTimer.singleShot(120, lambda: (overlay.raise_(), overlay.activateWindow()))
        print("DIAG: overlay show requested from tray")

    show_act.triggered.connect(lambda: QTimer.singleShot(0, center_show_overlay))
    quit_act.triggered.connect(app.quit)
    menu.addAction(show_act); menu.addSeparator(); menu.addAction(quit_act)
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
