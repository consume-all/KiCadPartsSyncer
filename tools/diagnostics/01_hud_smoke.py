# -*- coding: utf-8 -*-
import sys
from PySide6.QtCore import Qt, QTimer, QRect, QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget, QLabel

def _apply_dpi_policy_if_available():
    policy_enum = getattr(Qt, "HighDpiScaleFactorRoundingPolicy", None)
    setter = getattr(QGuiApplication, "setHighDpiScaleFactorRoundingPolicy", None)
    if policy_enum is not None and setter is not None:
        try:
            setter(policy_enum.PassThrough)
        except Exception:
            pass

def flags_to_str(f: Qt.WindowType) -> str:
    names = []
    for name in [
        "Tool",
        "FramelessWindowHint",
        "WindowStaysOnTopHint",
        "BypassWindowManagerHint",
        "WindowTransparentForInput",
        "NoDropShadowWindowHint",
        "X11BypassWindowManagerHint",
    ]:
        if f & getattr(Qt, name):
            names.append(name)
    return "|".join(names) if names else "<none>"

class HudProbe(QWidget):
    def __init__(self):
        super().__init__()
        # Set flags in a version-safe way
        self.setWindowFlag(Qt.Tool, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.setObjectName("HudProbe")
        lab = QLabel("HUD PROBE — ESC to close", self)
        lab.setStyleSheet("QLabel { color: white; background: rgba(0,0,0,180); padding: 8px 14px; font-size: 14px; }")
        self.resize(600, 34)

    def center_top(self):
        screen = QGuiApplication.primaryScreen()
        geo: QRect = screen.availableGeometry()
        size: QSize = self.size()
        x = geo.x() + (geo.width() - size.width()) // 2
        y = geo.y() + int(geo.height() * 0.05)
        self.move(x, y)

    def showEvent(self, ev):
        super().showEvent(ev)
        print(f"DIAG: showEvent -> isVisible={self.isVisible()} geom={self.geometry().getRect()} flags={flags_to_str(self.windowFlags())}")

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            QApplication.quit()
        else:
            super().keyPressEvent(ev)

def main():
    app = QApplication(sys.argv)
    _apply_dpi_policy_if_available()

    w = HudProbe()
    print("DIAG: before show -> isVisible=", w.isVisible())
    w.center_top()
    w.show()
    QTimer.singleShot(120, lambda: (w.raise_(), w.activateWindow(), print("DIAG: nudge -> raised + activated")))
    print(f"DIAG: after show -> isVisible={w.isVisible()} geom={w.geometry().getRect()} flags={flags_to_str(w.windowFlags())}")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
