# -*- coding: utf-8 -*-
"""
win_hotkey.py
System-wide hotkey manager for Windows using RegisterHotKey and a Qt native event filter.

- Works even when your app window is unfocused or click-through.
- Cleanly unregisters on app exit.
- PySide6-compatible (uses QAbstractNativeEventFilter).

Usage:
    mgr = WinHotkeyManager(app)
    mgr.register(id=1, modifiers=MOD_CONTROL, vk=VK_OEM_3, callback=on_ctrl_backtick)  # Ctrl+`
    ...
    app.aboutToQuit.connect(mgr.unregister_all)
"""

from __future__ import annotations
import sys
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication

# ---- Win32 constants ----
WM_HOTKEY = 0x0312

MOD_ALT     = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT   = 0x0004
MOD_WIN     = 0x0008

# Backtick / tilde key (US layout). Adjust if you need a different layout.
VK_OEM_3 = 0xC0

# RegisterHotKey receives either a window handle or 0 (NULL) to bind to the calling thread.
user32 = ctypes.windll.user32

# Define MSG structure for event decoding
class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd",   wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam",  wintypes.WPARAM),
        ("lParam",  wintypes.LPARAM),
        ("time",    wintypes.DWORD),
        ("pt",      wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


class _NativeHotkeyFilter(QAbstractNativeEventFilter):
    """
    Installs on the QApplication to receive WM_HOTKEY from the thread message queue.
    We register with hWnd = NULL; Windows posts WM_HOTKEY to the thread that called RegisterHotKey.
    """

    def __init__(self, callback_lookup: dict[int, callable]):
        super().__init__()
        self._callbacks = callback_lookup

    def nativeEventFilter(self, eventType: bytes, message: int) -> tuple[bool, int]:  # type: ignore[override]
        # eventType is a bytes string; on Windows we expect b"windows_generic_MSG" or b"windows_dispatcher_MSG"
        if eventType not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return (False, 0)

        # message is a pointer to MSG
        # msg = ctypes.cast(message, ctypes.POINTER(MSG)).contents <---- ERROR
        try:
            ptr = int(message)  # works for sip.voidptr / c_void_p / int
            msg = MSG.from_address(ptr)
        except (TypeError, ValueError):
            # If we can't interpret it, ignore this event; don't crash.
            return False, 0
        if msg.message == WM_HOTKEY:
            hotkey_id = int(msg.wParam)
            cb = self._callbacks.get(hotkey_id)
            if cb:
                try:
                    cb()
                except Exception:
                    # Swallow exceptions to avoid breaking the dispatcher
                    pass
                # Do not consume; let other handlers see it if they care.
                # ACTUALLY, YES CONSUME! WE WANT THIS HOT KEY TO DO ONE THING ONLY
                return (True, 0)

        return (False, 0)


class WinHotkeyManager(QObject):
    """
    System-wide hotkey manager.

    Notes:
    - Only supported on Windows. On non-Windows platforms, creating this class raises RuntimeError.
    - Uses RegisterHotKey(NULL, id, modifiers, vk) so messages go to the thread queue.
      We then catch them via a Qt native event filter.
    """

    def __init__(self, app: QApplication):
        super().__init__(parent=app)
        if sys.platform != "win32":
            raise RuntimeError("WinHotkeyManager is only supported on Windows.")

        self._app = app
        self._callbacks: dict[int, callable] = {}
        self._filter = _NativeHotkeyFilter(self._callbacks)
        self._app.installNativeEventFilter(self._filter)

        # Keep track of registered ids so we can unregister on exit
        self._registered_ids: set[int] = set()

        # Ensure cleanup on app quit
        self._app.aboutToQuit.connect(self.unregister_all)

    def register(self, id: int, modifiers: int, vk: int, callback: callable) -> bool:
        """
        Register a global hotkey.
        - id must be unique per-process for your usage.
        - modifiers: MOD_ALT | MOD_CONTROL | MOD_SHIFT | MOD_WIN combination.
        - vk: a VK_* code (e.g., VK_OEM_3 for backtick/tilde).
        """
        if id in self._registered_ids:
            self.unregister(id)

        ok = bool(user32.RegisterHotKey(None, id, modifiers, vk))
        if ok:
            self._callbacks[id] = callback
            self._registered_ids.add(id)
        return ok

    def unregister(self, id: int) -> None:
        if id in self._registered_ids:
            try:
                user32.UnregisterHotKey(None, id)
            except Exception:
                pass
            self._registered_ids.discard(id)
        self._callbacks.pop(id, None)

    def unregister_all(self) -> None:
        for id in list(self._registered_ids):
            try:
                user32.UnregisterHotKey(None, id)
            except Exception:
                pass
            self._callbacks.pop(id, None)
            self._registered_ids.discard(id)
