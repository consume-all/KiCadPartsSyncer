# -*- coding: utf-8 -*-
import sys, socket
from contextlib import closing
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QTextEdit, QToolBar, QMessageBox, QWidget, QLabel
from PySide6.QtGui import QGuiApplication

HOST = "127.0.0.1"
PORT = 52731
NUDGE = b"SHOW_OVERLAY_CENTER\n"

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
        "WindowDoesNotAcceptFocus",
        "BypassWindowManagerHint",
        "WindowTransparentForInput",
    ]:
        if f & getattr(Qt, name):
            names.append(name)
    return "|".join(names) if names else "<none>"

class LocalHud(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.Tool, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("InstrumentHud")
        lab = QLabel("INSTRUMENT HUD — Compare with your overlay logs", self)
        lab.setStyleSheet("QLabel { color: white; background: rgba(0,0,0,180); padding: 8px 14px; }")
        self.resize(640, 34)

    def center_top(self):
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + int(geo.height() * 0.05)
        self.move(x, y)

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Overlay Instrument")
        self.resize(700, 420)

        self.log = QTextEdit(self)
        self.log.setReadOnly(True)
        self.setCentralWidget(self.log)

        bar = QToolBar("Controls")
        self.addToolBar(bar)

        act_show_local = QAction("Show Local HUD (center+raise)", self)
        act_nudge_remote = QAction("Nudge Remote Overlay (SHOW_OVERLAY_CENTER)", self)
        act_help = QAction("What to copy back", self)

        act_show_local.triggered.connect(self.show_local_hud)
        act_nudge_remote.triggered.connect(self.nudge_remote)
        act_help.triggered.connect(self.help_text)

        bar.addAction(act_show_local)
        bar.addAction(act_nudge_remote)
        bar.addAction(act_help)

        self.local = LocalHud()

    def append(self, s: str):
        self.log.append(s)
        print(s)

    def show_local_hud(self):
        self.append("DIAG: LocalHUD before show "
                    f"isVisible={self.local.isVisible()} flags={flags_to_str(self.local.windowFlags())}")
        self.local.center_top()
        self.local.show()
        self.append("DIAG: LocalHUD after show "
                    f"isVisible={self.local.isVisible()} geom={self.local.geometry().getRect()}")
        QTimer.singleShot(150, lambda: (self.local.raise_(), self.local.activateWindow(),
                                        self.append("DIAG: LocalHUD nudge -> raised+activated")))

    def nudge_remote(self):
        try:
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.settimeout(0.8)
                s.connect((HOST, PORT))
                s.sendall(NUDGE)
                data = s.recv(4096)
                self.append(f"DIAG: Remote reply: {data!r}")
        except Exception as e:
            self.append(f"DIAG: Remote nudge failed: {e!r}")
            QMessageBox.warning(self, "Nudge failed",
                                "Could not contact your app's overlay endpoint.\n"
                                "If you do have a socket, point HOST/PORT to it.\n"
                                "Otherwise, use Local HUD and compare vs 01/02.")

    def help_text(self):
        self.append("Copy these back:\n"
                    "1) DIAG lines from 01/02/03\n"
                    "2) Whether HUD appears and tray shows\n"
                    "3) App logs at enter_active_monitoring\n")

def main():
    app = QApplication(sys.argv)
    _apply_dpi_policy_if_available()
    w = Main()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
