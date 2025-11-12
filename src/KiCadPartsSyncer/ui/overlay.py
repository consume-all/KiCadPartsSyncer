# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Dict

from PySide6.QtCore import Qt, QTimer, QPoint, QSize, Signal, Slot, QThread, QObject, QEvent
from PySide6.QtGui import QGuiApplication, QCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QApplication

try:
    from ..infrastructure.system import win_clickthrough
except Exception:
    win_clickthrough = None

from KiCadPartsSyncer.infrastructure.system.settings_opener import open_settings_in_editor

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
    _sig_set_status = Signal(str)
    _sig_pull_requested = Signal()
    _sig_push_requested = Signal()

    def __init__(self, hub):
        super().__init__(None)
        self._hub = hub
        self._click_through = False
        self._frozen = False #ToDo: This should probably be removed now
        self._is_expanded = False
        self._status = "unknown"  # 'unknown' | 'clean' | 'diverged'
        # self._collapsed_size = QSize(120, 60) #ToDo: Probably should remove these
        # self._expanded_size = QSize(120, 220)

        # Drag state
        self._drag_active = False
        self._drag_offset = QPoint(0, 0)

        # Window flags: topmost, not in taskbar, frameless (we add manual dragging)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Minimal UI card
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame(self)
        self._card.setObjectName("hud")
        self._card.setStyleSheet("""
            #hud {
                background: rgba(10, 10, 10, 100);
                color:#FFFFFF;
                border:1px solid #555;
                border-radius:8px;
            }
            QLabel#t {
                font-size:12pt;
                font-weight:600;
                padding:8px 10px 2px 10px;
                color: #FFFFFF
            }
            QLabel#b {
                padding:0 10px 8px 10px;
                color: #FFFFFF
            }
            QPushButton {
                margin:0 10px 10px 10px;
            }
            QPushButton#toggle {
                margin: 0;
                padding: 0;
                color: #FFFFFF;
                background: transparent;
                border: none;
            }
            QPushButton#toggle:hover {
                color: #CCCCCC;
            }
            QPushButton#panel_button {
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
                padding: 0;
                margin: 2px 0;
                border-radius: 10px;
                background: transparent;
                color: #FFFFFF;
                border: 1px solid #555;
            }
            QPushButton#panel_button:hover {
                background: rgba(255, 255, 255, 25);
            }
        """)

        inner = QVBoxLayout(self._card)
        inner.setContentsMargins(4, 8, 4, 8)

        self._panel = QWidget(self._card)
        self._panel_layout = QVBoxLayout(self._panel)
        self._panel_layout.setContentsMargins(0, 0, 0, 0)
        # start with the panel collapsed
        self._panel.setVisible(False)

        # Panel Buttons
        # 🡅 Push, 🡇 Pull, ⚙ Settings, 👁 Hide
        self._btn_push = QPushButton("🡅", self._panel)
        self._btn_push.setObjectName("panel_button")
        self._btn_push.setToolTip("Push")
        self._btn_push.clicked.connect(self._on_push_clicked)

        self._btn_pull = QPushButton("🡇", self._panel)
        self._btn_pull.setObjectName("panel_button")
        self._btn_pull.setToolTip("Pull")
        self._btn_pull.clicked.connect(self._on_pull_clicked)

        self._btn_settings = QPushButton("⚙", self._panel)
        self._btn_settings.setObjectName("panel_button")
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.clicked.connect(self._on_settings_clicked)

        self._btn_hide = QPushButton("👁", self._panel)
        self._btn_hide.setObjectName("panel_button")
        self._btn_hide.setToolTip("Hide")
        self._btn_hide.clicked.connect(self.hide_overlay)

        self._panel_layout.addWidget(self._btn_push,     0, Qt.AlignHCenter)
        self._panel_layout.addWidget(self._btn_pull,     0, Qt.AlignHCenter)
        self._panel_layout.addWidget(self._btn_settings, 0, Qt.AlignHCenter)
        self._panel_layout.addWidget(self._btn_hide,     0, Qt.AlignHCenter)

        self._title = QLabel("KiCad Parts Syncer", self) #ToDo: Remove
        self._title.setObjectName("t") #ToDo: Remove
        self._title.hide() #ToDo: Remove
        

        self._body  = QLabel("Idle", self) #ToDo: Remove
        self._body.setObjectName("b") #ToDo: Remove
        self._body.hide() #ToDo: Remove

        self._toggle = QPushButton("▼", self._card)
        self._toggle.setObjectName("toggle")
        self._toggle.setFlat(True)
        self._toggle.setFixedSize(22, 18)
        self._toggle.setToolTip("Expand")
        self._toggle.clicked.connect(self._toggle_expanded)

        # ToDo: Remove the following & any other associated code

        # self._btnHide = QPushButton("Hide", self._card)
        # self._btnHide.clicked.connect(self.hide_overlay)
        # inner.addWidget(self._title)
        # inner.addWidget(self._body)
        # inner.addWidget(self._btnHide)
        inner.addWidget(self._panel)
        inner.addStretch()
        inner.addWidget(self._toggle, 0, Qt.AlignHCenter)

        outer.addWidget(self._card)
        self._set_expanded(False)

        # Thread-safe wiring: ensure UI ops run on GUI thread
        self._sig_show.connect(self._show_impl, Qt.QueuedConnection)
        self._sig_hide.connect(self._hide_impl, Qt.QueuedConnection)
        self._sig_set_status.connect(self._set_status_impl, Qt.QueuedConnection)

        # Accept mouse events on both the frame and the top-level for dragging
        self._card.installEventFilter(self)
        self.installEventFilter(self)

    # ---------- public API (thread-safe entry points) ----------

    # def apply_prefs(self, prefs: Dict) -> None:
    #     # Reserved for future opacity / theming.
    #     pass

    def set_repo_status(self, status: str) -> None:
        """
        Thread-safe: set HUD status:
          - 'unknown'  -> yellow (not configured / cannot check)
          - 'clean'    -> green  (in sync)
          - 'diverged' -> red    (remote or local ahead)
        """
        if self._on_gui_thread():
            self._set_status_impl(status)
        else:
            self._sig_set_status.emit(status)

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

    # def show_centered(self) -> None:
    #     self._show_impl(None, None)

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
        if win_clickthrough is None:
            # Fallback: Qt-only behavior
            self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
            return

        if enabled:
            win_clickthrough.enable_click_through(self)
        else:
            win_clickthrough.disable_click_through(self)

        if was_visible:
            # Flags changes require a show() to take effect; restore original position.
            self.show()
            self.raise_()
            self.setGeometry(old_geom)

    # def show_frozen(self, frozen: bool) -> None:
    #     self._frozen = bool(frozen)
    #     if self.isVisible():
    #         self._title.setText("Companion (Frozen)" if frozen else "Companion (Active)")

    # ---------- Qt overrides / helpers ----------
    @Slot()
    def _on_push_clicked(self) -> None:
        self._sig_push_requested.emit()

    @Slot()
    def _on_settings_clicked(self) -> None:
        open_settings_in_editor()

    @Slot()
    def _on_pull_clicked(self) -> None:
        self._sig_pull_requested.emit()

    @Slot(str)
    def _set_status_impl(self, status: str) -> None:
        s = (status or "").strip().lower()
        if s not in ("unknown", "clean", "diverged"):
            s = "unknown"
        if s != self._status:
            self._status = s
            self.update()  # trigger repaint with new color

    def _set_expanded(self, expanded: bool) -> None:
        self._is_expanded = bool(expanded)
        self._panel.setVisible(self._is_expanded)
        self._toggle.setText("▲" if self._is_expanded else "▼")
        self._toggle.setToolTip("Collapse" if self._is_expanded else "Expand")
        # target = self._expanded_size if self._is_expanded else self._collapsed_size
        # self.resize(target)
        self._update_size_for_state()

    def _toggle_expanded(self) -> None:
        self._set_expanded(not self._is_expanded)

    def _update_size_for_state(self) -> None:
        card_layout = self._card.layout()
        if card_layout is None:
            return

        # Recompute based on current visibility (_panel visible/hidden).
        card_layout.invalidate()
        hint = card_layout.sizeHint()

        width = 120
        height = hint.height()

        self.setFixedSize(width, height)

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter, QColor, QBrush

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Map _status -> background/border
        if getattr(self, "_status", "unknown") == "clean":
            # In sync
            bg = QColor(0, 170, 0, 220)        # green
            border = QColor(0, 90, 0, 230)
        elif self._status == "diverged":
            # Remote or local ahead
            bg = QColor(200, 40, 40, 220)      # red
            border = QColor(255, 100, 100, 230)
        else:
            # Default / unknown / not configured / cannot check
            bg = QColor(230, 200, 40, 220)     # yellow
            border = QColor(180, 140, 0, 230)

        # If click-through is enabled, make border fully opaque so it stands out
        if getattr(self, "_click_through", False):
            border = QColor(border.red(), border.green(), border.blue(), 255)

        p.setBrush(QBrush(bg))
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
        card_layout = self._card.layout()
        if card_layout is not None:
            hint = card_layout.sizeHint()
            return QSize(120, hint.height())
        return QSize(120, 40)

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

    # def _restore_border(self) -> None:
    #     self._card.setStyleSheet(self._card.styleSheet())

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
        self._set_expanded(False)
        self.hide()

    def _nudge_front(self) -> None:
        # re-raise shortly after show to combat z-order weirdness on Windows
        try:
            self.raise_()
        except Exception:
            pass
