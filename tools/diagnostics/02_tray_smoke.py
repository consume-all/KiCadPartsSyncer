# -*- coding: utf-8 -*-
import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QStyle, QMenu, QWidget, QLabel

def _apply_dpi_policy_if_available():
    policy_enum = getattr(Qt, "HighDpiScaleFactorRoundingPolicy", None)
    setter = getattr(QGuiApplication, "setHighDpiScaleFactorRoundingPolicy", None)
    if policy_enum is not None and setter is not None:
        try:
            setter(policy_enum.PassThrough)
        except Exception:
            pass

class Hud(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.Tool, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("TrayHud")
        lab = QLabel("TRAY HUD — Right-click tray to exit", self)
        lab.setStyleSheet("QLabel { color: white; background: rgba(0,0,0,180); padding: 8px 14px; }")
        self.resize(520, 32)

    def center_top(self):
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + int(geo.height() * 0.05)
        self.move(x, y)

def main():
    app = QApplication(sys.argv)
    _apply_dpi_policy_if_available()

    tray = QSystemTrayIcon()
    icon = app.style().standardIcon(QStyle.SP_MessageBoxInformation)  # guaranteed non-null
    tray.setIcon(icon)
    tray.setToolTip("Tray Smoke Test")

    menu = QMenu()
    show_action = QAction("Show HUD (center)")
    quit_action = QAction("Exit")

    hud = Hud()

    def do_show():
        hud.center_top()
        hud.show()
        QTimer.singleShot(120, lambda: (hud.raise_(), hud.activateWindow()))
        print("DIAG: HUD show requested from tray.")

    show_action.triggered.connect(do_show)
    quit_action.triggered.connect(app.quit)
    menu.addAction(show_action)
    menu.addSeparator()
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.setVisible(True)
    tray.show()

    print("DIAG: tray.isSystemTrayAvailable =", QSystemTrayIcon.isSystemTrayAvailable())
    print("DIAG: tray.supportsMessages =", QSystemTrayIcon.supportsMessages())
    print("DIAG: tray.isVisible =", tray.isVisible())

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
