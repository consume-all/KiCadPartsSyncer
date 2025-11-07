# -*- coding: utf-8 -*-
"""
07_event_tap_and_autoshow_v3.py
Binds auto-show to EndpointAppeared (confirmed published) and also to any
ActiveMonitoring-style names if they ever flow through publish later.
Adds a short delay to let the Overlay be constructed before show().

Run:
    python tools/diagnostics/07_event_tap_and_autoshow_v3.py
"""
import sys, runpy, time, json, dataclasses
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QCursor, QGuiApplication

HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from KiCadPartsSyncer.infrastructure.system.event_hub import EventHub
from KiCadPartsSyncer.ui.overlay import Overlay

# ---- helper: robust show of any Overlay on GUI thread ----
def _show_any_overlay():
    app = QApplication.instance()
    if not app:
        return
    n = 0
    for w in app.topLevelWidgets():
        if isinstance(w, Overlay):
            try:
                w.show()   # if you've patched Overlay.show earlier, it will center/raise
                n += 1
            except Exception as e:
                print(f"DIAG: auto-show -> exception: {e!r}")
    print(f"DIAG: auto-show -> requested show() on {n} Overlay instance(s)")

def _schedule_show(delay_ms=150):
    QTimer.singleShot(delay_ms, _show_any_overlay)

# ---- optional fix for show_overlay cursor path (safe if unused) ----
if hasattr(Overlay, "show_overlay"):
    def _patched_show_overlay(self):
        try:
            pos = QCursor.pos()
        except Exception:
            pos = None
        # place near cursor if possible, then rely on show() to raise/activate
        if pos is not None and hasattr(QGuiApplication, "screenAt") and callable(QGuiApplication.screenAt):
            scr = QGuiApplication.screenAt(pos)
            if scr is not None:
                geo = scr.availableGeometry()
                w = max(420, self.width()); h = max(28, self.height())
                x = max(geo.x(), min(geo.right() - w + 1, pos.x() - w // 2))
                y = max(geo.y(), min(geo.bottom() - h + 1, pos.y() + 20))
                self.setGeometry(x, y, w, h)
        self.show()
    setattr(Overlay, "show_overlay", _patched_show_overlay)

# ---- event tap (signature-preserving) ----
_original_publish = EventHub.publish

ACTIVE_MATCH = {
    "enter_active_monitoring",
    "ActiveMonitoring", "EnterActiveMonitoring",
    "state_active_monitoring", "entered_active_monitoring",
}
ENDPOINT_MATCH = {"EndpointAppeared", "endpoint_appeared"}  # include the one we saw

def _safe_json(obj):
    try:
        if dataclasses.is_dataclass(obj):
            return json.dumps(dataclasses.asdict(obj))
        return json.dumps(obj)
    except Exception:
        return "<non-serializable>"

def _event_name_from_args(args, kwargs):
    ev = args[0] if args else kwargs.get("event")
    if isinstance(ev, str):
        return ev
    for key in ("name", "event", "type", "state"):
        if hasattr(ev, key):
            val = getattr(ev, key)
            if isinstance(val, str) and val:
                return val
    try:
        return ev.__class__.__name__
    except Exception:
        return "<unknown>"

def _publish_tap(self, *args, **kwargs):
    name = _event_name_from_args(args, kwargs)
    ts = time.time()
    pay = _safe_json(args[1]) if len(args) >= 2 else (_safe_json(kwargs.get("payload")) if "payload" in kwargs else None)
    print(f"DIAG: EventHub.publish -> {name} payload={pay} ts={ts:.3f}")

    # Trigger on confirmed endpoint event OR any ActiveMonitoring-style event
    if isinstance(name, str) and (name in ENDPOINT_MATCH or name in ACTIVE_MATCH or name.lower() == "enter_active_monitoring"):
        print(f"DIAG: EventHub tap -> trigger on '{name}'; scheduling Overlay.show() (150ms)")
        _schedule_show(150)

    return _original_publish(self, *args, **kwargs)

EventHub.publish = _publish_tap

# ---- launch app ----
RUN = PROJECT_ROOT / "run.py"
print("DIAG: launching real app via run.py ...")
runpy.run_path(str(RUN), run_name="__main__")
