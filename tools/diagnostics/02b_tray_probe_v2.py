# -*- coding: utf-8 -*-
import sys, itertools
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QAction, QIcon, QPainter, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QStyle, QMenu, QWidget, QLabel

def _apply_dpi_policy_if_available():
    policy_enum = getattr(Qt, "HighDpiScaleFactorRoundingPolicy", None)
    setter = getattr(QGuiApplication, "setHighDpiScaleFactorRoundingPolicy", None)
    if policy_enum is not None and setter is not None:
        try: setter(policy_enum.PassThrough)
        except Exception: pass

def _make_pix(color: QColor) -> QIcon:
    # Make a crisp 20x20 icon so Windows won't drop it as "empty"
    pm = QPixmap(20, 20)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setPen(Qt.black)
    p.setBrush(color)
    p.drawEllipse(2, 2, 16, 16)
    p.end()
    return QIcon(pm)

class Hud(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.Tool, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        lab = QLabel("TRAY PROBE v2 — Right-click tray icon", self)
        lab.setStyleSheet("QLabel { color: white; background: rgba(0,0,0,180); padding: 8px 14px; }")
        self.resize(420, 28)

    def center_top(self):
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.move(geo.x() + (geo.width() - self.width()) // 2,
                  geo.y() + int(geo.height() * 0.05))

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # ensures process stays even if HUD closed
    _apply_dpi_policy_if_available()

    hud = Hud()

    tray = QSystemTrayIcon()
    # Build two distinct icons and blink between them every 1s so you can *see* it
    ico_a = _make_pix(QColor(0, 180, 255))
    ico_b = _make_pix(QColor(255, 120, 0))
    fallback = app.style().standardIcon(QStyle.SP_ComputerIcon)
    tray.setIcon(ico_a if not fallback.isNull() else fallback)
    tray.setToolTip("Tray Probe v2 — right-click me")

    menu = QMenu()
    act_show = QAction("Show HUD (center)")
    act_bubble = QAction("Show Balloon (3s)")
    act_quit = QAction("Exit")
    menu.addAction(act_show)
    menu.addAction(act_bubble)
    menu.addSeparator()
    menu.addAction(act_quit)

    def do_show():
        hud.center_top()
        hud.show()
        QTimer.singleShot(120, lambda: (hud.raise_(), hud.activateWindow()))
        print("DIAG: HUD show requested from tray.")

    def do_bubble():
        ok = tray.showMessage("Tray Probe v2",
                              "If you see this near the system tray, the icon exists.",
                              QSystemTrayIcon.Information, 3000)
        print(f"DIAG: tray.showMessage() returned {ok}")

    act_show.triggered.connect(do_show)
    act_bubble.triggered.connect(do_bubble)
    act_quit.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    tray.setVisible(True)   # IMPORTANT on Win10/11
    tray.show()             # belt + suspenders

    # Blink the icon so it’s obvious even if overflowed
    cycler = itertools.cycle([ico_a, ico_b])
    def blink():
        tray.setIcon(next(cycler))
    timer = QTimer()
    timer.timeout.connect(blink)
    timer.start(1000)

    def on_activated(reason: QSystemTrayIcon.ActivationReason):
        print(f"DIAG: tray.activated reason={int(reason)} "
              "(1=Context,2=Double,3=Trigger/Single,4=Middle)")
    tray.activated.connect(on_activated)

    print("DIAG: isSystemTrayAvailable =", QSystemTrayIcon.isSystemTrayAvailable())
    print("DIAG: supportsMessages =", QSystemTrayIcon.supportsMessages())
    print("DIAG: tray.isVisible =", tray.isVisible())
    print("DIAG: NOTE — On Windows 11, the icon may be in the overflow (^). "
          "Right-click there if you don't see it on the taskbar.")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
