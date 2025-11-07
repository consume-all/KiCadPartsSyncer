# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Dict

from PySide6.QtCore import Qt, QTimer, QPoint, QSize, Signal, Slot, QThread, QObject, QEvent
from PySide6.QtGui import QGuiApplication, QCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QApplication

try:
    # Optional Windows click-through helpers
    from ..infrastructure.system.win_clickthrough import enable_click_through as _win_enable_click, disable_click_through as _win_disable_click
except Exception:
    _win_enable_click = None
    _win_disable_click = None


class Overlay(QWidget):
    """
    Always-on-top HUD overlay that stays off the taskbar (Qt.Tool).

    Public API (thread-safe):
      - show_overlay(info: Optional[Dict] = None, pos: Optional[QPoint] = None)
      - hide_overlay()
      - show_centered()
      - flash()
      - set_click_through(enabled: bool)
      - show_frozen(frozen: bool)
      - appear_idle()
      - is_click_through() -> bool
    """

    # Internal signals to marshal calls to the GUI thread
    _sig_show = Signal(object, object)   # (info: Optional[Dict], pos: Optional[QPoint])
    _sig_hide = Signal()

    def __init__(self, hub):
        super().__init__(None)
        self._hub = hub
        self._click_through = False
        self._frozen = False

        # Drag state
        self._drag_active = False
        self._drag_offset = QPoint(0, 0)

        # Window flags: topmost, not in taskbar, frameless (we add manual dragging)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # Minimal UI card
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame(self)
        self._card.setObjectName("hud")
        self._card.setStyleSheet("""
            #hud { background:#111; color:#eaeaea; border:1px solid #555; border-radius:8px; }
            QLabel#t { font-size:12pt; font-weight:600; padding:8px 10px 2px 10px; }
            QLabel#b { padding:0 10px 8px 10px; }
            QPushButton { margin:0 10px 10px 10px; }
        """)

        inner = QVBoxLayout(self._card)
        inner.setContentsMargins(8, 8, 8, 8)

        self._title = QLabel("KiCad Companion HUD", self._card); self._title.setObjectName("t")
        self._body  = QLabel("Idle", self._card);                self._body.setObjectName("b")

        self._btnHide = QPushButton("Hide", self._card)
        self._btnHide.clicked.connect(self.hide_overlay)

        inner.addWidget(self._title)
        inner.addWidget(self._body)
        inner.addWidget(self._btnHide)

        outer.addWidget(self._card)
        self.resize(360, 140)

        # Thread-safe wiring: ensure UI ops run on GUI thread
        self._sig_show.connect(self._show_impl, Qt.QueuedConnection)
        self._sig_hide.connect(self._hide_impl, Qt.QueuedConnection)

        # Accept mouse events on both the frame and the top-level for dragging
        self._card.installEventFilter(self)
        self.installEventFilter(self)

    # ---------- public API (thread-safe entry points) ----------

    def apply_prefs(self, prefs: Dict) -> None:
        # Reserved for future opacity / theming.
        pass

    def appear_idle(self) -> None:
        self.hide_overlay()

    def is_click_through(self) -> bool:
        return bool(self._click_through)

    def show_overlay(self, info: Optional[Dict] = None, pos: Optional[QPoint] = None) -> None:
        """Thread-safe: may be called from any thread."""
        if self._on_gui_thread():
            self._show_impl(info, pos)
        else:
            self._sig_show.emit(info, pos)

    def hide_overlay(self) -> None:
        """Thread-safe: may be called from any thread."""
        if self._on_gui_thread():
            self._hide_impl()
        else:
            self._sig_hide.emit()

    def show_centered(self) -> None:
        self._show_impl(None, None)

    def flash(self) -> None:
        self.show_overlay()
        QTimer.singleShot(600, self.hide_overlay)

    def set_click_through(self, enabled: bool) -> None:
        """Enable/disable click-through (mouse input passes to windows underneath)."""
        self._click_through = bool(enabled)

        # Remember visibility + geometry so flag changes don't nudge the HUD.
        was_visible = self.isVisible()
        if was_visible:
            old_geom = self.geometry()

        # Qt flag-based click-through (cross-platform where supported)
        f = self.windowFlags()
        if enabled:
            f |= Qt.WindowTransparentForInput
        else:
            f &= ~Qt.WindowTransparentForInput
        self.setWindowFlags(f)

        # Apply Win32 extended style as well for robustness, if available
        try:
            if enabled and _win_enable_click:
                _win_enable_click(self)
            elif (not enabled) and _win_disable_click:
                _win_disable_click(self)
        except Exception:
            # Non-fatal; Qt flag path still active
            pass

        if was_visible:
            # Flags changes require a show() to take effect; restore original position.
            self.show()
            self.raise_()
            self.setGeometry(old_geom)

    def show_frozen(self, frozen: bool) -> None:
        self._frozen = bool(frozen)
        if self.isVisible():
            self._title.setText("Companion (Frozen)" if frozen else "Companion (Active)")

    # ---------- Qt overrides / helpers ----------

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter, QColor, QBrush
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QBrush(QColor(20, 20, 22, 200)))
        if getattr(self, "_click_through", False):
            border = QColor(0, 200, 255, 220)
        else:
            border = QColor(255, 255, 255, 64)
        p.setPen(border)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.drawRoundedRect(r, 10, 10)

    def showEvent(self, e):
        # self._body.setGeometry(self.rect())   # child fills window before first paint
        super().showEvent(e)


    def resizeEvent(self, e):
        # self._body.setGeometry(self.rect())
        super().resizeEvent(e)

    def sizeHint(self) -> QSize:
        return QSize(360, 140)

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:
        # Only allow dragging when not in click-through mode
        if self._click_through:
            return super().eventFilter(obj, ev)

        if ev.type() == QEvent.MouseButtonPress and ev.buttons() & Qt.LeftButton:
            # Begin drag: capture offset between cursor and window top-left
            global_pos = ev.globalPosition().toPoint() if hasattr(ev, 'globalPosition') else QCursor.pos()
            self._drag_active = True
            self._drag_offset = global_pos - self.frameGeometry().topLeft()
            return True

        if ev.type() == QEvent.MouseMove and self._drag_active:
            global_pos = ev.globalPosition().toPoint() if hasattr(ev, 'globalPosition') else QCursor.pos()
            new_top_left = global_pos - self._drag_offset
            self.move(new_top_left)
            return True

        if ev.type() == QEvent.MouseButtonRelease and self._drag_active:
            self._drag_active = False
            return True

        return super().eventFilter(obj, ev)

    def _restore_border(self) -> None:
        self._card.setStyleSheet(self._card.styleSheet())

    def _on_gui_thread(self) -> bool:
        app = QGuiApplication.instance() or QApplication.instance()
        return QThread.currentThread() == app.thread() if app else True

    @Slot(object, object)
    def _show_impl(self, info: Optional[Dict], pos: Optional[QPoint]) -> None:
        # update content
        if info:
            title = info.get("title") or "KiCad Parts Syncer HUD"
            body  = info.get("body")  or "Connected to KiCad"
        else:
            title, body = "KiCad Parts Syncer HUD", "Active"
        self._title.setText(title); self._body.setText(body)

        # Find starting position
        if pos is not None:
            target = pos
        else:
            c = QCursor.pos()
            target = QPoint(c.x() + 16, c.y() + 16)

        # Clamp to active screen
        screen = QGuiApplication.screenAt(target) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        w, h = self.width(), self.height()
        x = max(g.left(), min(target.x(), g.right() - w))
        y = max(g.top(),  min(target.y(), g.bottom() - h))
        self.move(QPoint(x, y))

        # Re-apply flags every show path (z-order & click-through)
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if self._click_through:
            flags |= Qt.WindowTransparentForInput
        self.setWindowFlags(flags)

        # Show & nudge front
        # self._body.setGeometry(self.rect())
        self.show()
        self._body.style().polish(self._body)
        self._body.update()
        self.raise_()
        QTimer.singleShot(0, self._nudge_front)

    @Slot()
    def _hide_impl(self) -> None:
        self.hide()

    def _nudge_front(self) -> None:
        # re-raise shortly after show to combat z-order weirdness on Windows
        try:
            self.raise_()
        except Exception:
            pass
