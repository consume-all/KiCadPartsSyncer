# Windows-only helpers to make a Qt window truly click-through (mouse passes to apps under it)
import ctypes
from ctypes import wintypes

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

_user32 = ctypes.windll.user32

# Use Ptr variants when available (64-bit)
try:
    _GetWindowLongPtrW = _user32.GetWindowLongPtrW
    _SetWindowLongPtrW = _user32.SetWindowLongPtrW
    _LONG_T = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
except AttributeError:
    _GetWindowLongPtrW = _user32.GetWindowLongW
    _SetWindowLongPtrW = _user32.SetWindowLongW
    _LONG_T = ctypes.c_long

_GetWindowLongPtrW.restype = _LONG_T
_GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_SetWindowLongPtrW.restype = _LONG_T
_SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, _LONG_T]

def _hwnd_from_qt(widget) -> int:
    # Ensure a native window exists
    widget.winId()
    return int(widget.winId())

def enable_click_through(widget) -> None:
    """Make the window ignore mouse (and stay layered for translucency)."""
    try:
        hwnd = _hwnd_from_qt(widget)
        ex = _GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        ex |= (WS_EX_LAYERED | WS_EX_TRANSPARENT)
        _SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
    except Exception:
        pass

def disable_click_through(widget) -> None:
    """Restore normal hit-testing (keep LAYERED so opacity/translucency still works)."""
    try:
        hwnd = _hwnd_from_qt(widget)
        ex = _GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        ex = (ex | WS_EX_LAYERED) & (~WS_EX_TRANSPARENT)
        _SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
    except Exception:
        pass
