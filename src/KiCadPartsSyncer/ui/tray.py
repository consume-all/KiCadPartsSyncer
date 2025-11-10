from __future__ import annotations
import os
from pathlib import Path
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QAction, QIcon


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

        # Resolve icon path relative to this file
        base_dir = Path(__file__).resolve().parent
        icon_path = base_dir / "resources" / "KiCadPartsSyncer.ico"

        icon = QIcon(str(icon_path))
        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip("KiCad Parts Syncer")

        self.menu = QMenu()

        a_center = QAction("Show HUD", self.menu)  # shows in center of screen
        # WAS: a_center.triggered.connect(self.overlay.show_centered)
        a_center.triggered.connect(self._show_centered)
        self.menu.addAction(a_center)

        a_hide = QAction("Hide HUD", self.menu)
        a_hide.triggered.connect(self.overlay.hide_overlay)
        self.menu.addAction(a_hide)

        self.menu.addSeparator()

        a_quit = QAction("Quit", self.menu)
        a_quit.triggered.connect(self.app.quit)
        self.menu.addAction(a_quit)

        self.tray.setContextMenu(self.menu)

        self.tray.setVisible(True)
        self.tray.show()

        # left-click toggles HUD quickly
        self.tray.activated.connect(self._on_click)

    def _show_centered(self) -> None:
        """
        Prefer overlay.show_centered(); fall back to show_overlay(); then show().
        Keeps existing behavior if show_centered exists, avoids AttributeError if not.
        """
        if hasattr(self.overlay, "show_centered"):
            self.overlay.show_centered()
        elif hasattr(self.overlay, "show_overlay"):
            self.overlay.show_overlay()
        else:
            self.overlay.show()

    def _on_click(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.Trigger:
            if self.overlay.isVisible():
                self.overlay.hide_overlay()
            else:
                self.overlay.show_overlay()
