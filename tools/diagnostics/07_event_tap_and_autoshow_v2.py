# -*- coding: utf-8 -*-
"""
07_event_tap_and_autoshow_v2.py
Safe event tap:
- DOES NOT change EventHub.publish signature (uses *args, **kwargs and forwards verbatim)
- Logs every event (string or object). Extracts a readable name without assuming shape.
- Auto-shows the Overlay on GUI (Graphical User Interface) thread when we see an
  "enter_active_monitoring" style event (several name variants supported).
- Also patches Overlay.show_overlay to use PySide6-safe QCursor.pos() if present.

Run:
    python tools/diagnostics/07_event_tap_and_autoshow_v2.py
"""
import sys, runpy, time, json, dataclasses
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QCursor, QGuiApplication

# --- path fix ---
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# --- imports AFTER path fix ---
from KiCadPartsSyncer.infrastructure.system.event_hub import EventHub  # noqa: E402
from KiCadPartsSyncer.ui.overlay import Overlay  # noqa: E402

# ---------- Overlay convenience (cursor-safe show_overlay) ----------
def _safe_patch_show_overlay():
    orig = getattr(Overlay, "show_overlay", None)
    if not callable(orig):
        return

    def _patched_show_overlay(self):
        # Use global cursor position if available; otherwise just show().
        try:
            pos = QCursor.pos()
        except Exception:
            pos = None

        # Place near cursor if possible; let .show() (below) do center/raise.
        if pos is not None and hasattr(QGuiApplication, "screenAt") and callable(QGuiApplication.screenAt):
            scr = QGuiApplication.screenAt(pos)
            if scr is not None:
                geo = scr.availableGeometry()
                w = max(420, self.width())
                h = max(28, self.height())
                x = max(geo.x(), min(geo.right() - w + 1, pos.x() - w // 2))
                y = max(geo.y(), min(geo.bottom() - h + 1, pos.y() + 20))
                self.setGeometry(x, y, w, h)
        self.show()  # if you've patched Overlay.show earlier, it will center/raise.

    setattr(Overlay, "show_overlay", _patched_show_overlay)

_safe_patch_show_overlay()

# ---------- Helper: show any Overlay on GUI thread ----------
def _show_any_overlay():
    app = QApplication.instance()
    if not app:
        return
    count = 0
    for w in app.topLevelWidgets():
        if isinstance(w, Overlay):
            try:
                w.show()
                count += 1
            except Exception as e:
                print(f"DIAG: auto-show -> exception calling show(): {e!r}")
    print(f"DIAG: auto-show -> requested show() on {count} Overlay instance(s)")

def _schedule_show():
    QTimer.singleShot(0, _show_any_overlay)

# ---------- Name extraction for arbitrary event objects ----------
def _event_name_from_args(args, kwargs):
    # Common patterns: publish(event_obj), publish("name"), publish(event=...)
    ev = None
    if args:
        ev = args[0]
    elif "event" in kwargs:
        ev = kwargs["event"]

    if isinstance(ev, str):
        return ev

    # Try common attributes or class name
    for key in ("name", "event", "type", "state"):
        if hasattr(ev, key):
            try:
                val = getattr(ev, key)
                if isinstance(val, str) and val:
                    return val
            except Exception:
                pass

    # Dataclass? get class name
    try:
        return ev.__class__.__name__
    except Exception:
        return "<unknown>"

def _safe_json(obj):
    try:
        if dataclasses.is_dataclass(obj):
            return json.dumps(dataclasses.asdict(obj))
        return json.dumps(obj)
    except Exception:
        return "<non-serializable>"

# ---------- Patch EventHub.publish safely ----------
_original_publish = EventHub.publish

_ACTIVE_MONITORING_MATCHES = {
    "enter_active_monitoring",
    "ActiveMonitoring",
    "EnterActiveMonitoring",
    "state_active_monitoring",
    "entered_active_monitoring",
}

def _publish_tap(self, *args, **kwargs):
    name = _event_name_from_args(args, kwargs)
    ts = time.time()
    # Best-effort payload peek (don’t assume shape)
    payload_repr = None
    if len(args) >= 2:
        payload_repr = _safe_json(args[1])
    elif "payload" in kwargs:
        payload_repr = _safe_json(kwargs["payload"])
    print(f"DIAG: EventHub.publish -> {name} payload={payload_repr} ts={ts:.3f}")

    # Trigger HUD on ActiveMonitoring-style events
    if (isinstance(name, str) and name in _ACTIVE_MONITORING_MATCHES) or \
       (isinstance(name, str) and name.lower() == "enter_active_monitoring"):
        print("DIAG: EventHub tap -> enter_active_monitoring detected; scheduling Overlay.show()")
        _schedule_show()

    return _original_publish(self, *args, **kwargs)

EventHub.publish = _publish_tap  # signature-preserving wrapper

# ---------- Launch real app ----------
RUN = PROJECT_ROOT / "run.py"
if not RUN.exists():
    print("DIAG: ERROR -> ProjectRoot/run.py not found.")
    sys.exit(1)

print("DIAG: launching real app via run.py ...")
runpy.run_path(str(RUN), run_name="__main__")
