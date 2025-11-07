from __future__ import annotations
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QStyle
from PySide6.QtGui import QAction

class Tray:
    """
    Windows tray with explicit debug actions:
      - Show HUD (near cursor)
      - Show HUD (center)
      - Flash HUD (white border blink)
      - Hide HUD
      - Quit
    Ensures a valid icon + setVisible(True) so it actually appears.
    """

    def __init__(self, app: QApplication, overlay, hub):
        self.app = app
        self.overlay = overlay
        self.hub = hub

        icon = app.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip("KiCad Companion")

        menu = QMenu()
        a_show = QAction("Show HUD (near cursor)"); a_show.triggered.connect(lambda: self.overlay.show_overlay()); menu.addAction(a_show)
        a_center = QAction("Show HUD (center)");    a_center.triggered.connect(self.overlay.show_centered);     menu.addAction(a_center)
        a_flash = QAction("Flash HUD");             a_flash.triggered.connect(self.overlay.flash);             menu.addAction(a_flash)
        a_hide = QAction("Hide HUD");               a_hide.triggered.connect(self.overlay.hide_overlay);       menu.addAction(a_hide)
        menu.addSeparator()
        a_quit = QAction("Quit");                   a_quit.triggered.connect(self.app.quit);                   menu.addAction(a_quit)

        self.tray.setContextMenu(menu)
        self.tray.setVisible(True)
        self.tray.show()

        # left-click toggles HUD quickly
        self.tray.activated.connect(self._on_click)

    def _on_click(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.Trigger:
            if self.overlay.isVisible():
                self.overlay.hide_overlay()
            else:
                self.overlay.show_overlay()
