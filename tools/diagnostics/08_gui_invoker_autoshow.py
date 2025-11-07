# -*- coding: utf-8 -*-
"""
08_gui_invoker_autoshow.py
Add-only launcher that:
- Creates a GUI-thread invoker (Qt Signal -> Slot with QueuedConnection).
- Taps EventHub.publish WITHOUT changing its signature.
- On 'EndpointAppeared' (and ActiveMonitoring-style names), it emits to the
  GUI invoker which then calls Overlay.show() safely on the GUI thread.

Run:
    python tools/diagnostics/08_gui_invoker_autoshow.py
Acronyms: GUI = Graphical User Interface, HUD = Heads-Up Display.
"""
import sys, runpy, time, json, dataclasses
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtWidgets import QApplication

# --- sys.path for src ---
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Import AFTER path fix
from KiCadPartsSyncer.infrastructure.system.event_hub import EventHub
from KiCadPartsSyncer.ui.overlay import Overlay

# ---------------- GUI-thread invoker ----------------
class _GuiInvoker(QObject):
    run = Signal(object)  # emits a callable

    def __init__(self):
        super().__init__()
        # Ensure queued delivery into the GUI thread
        self.run.connect(self._run, Qt.QueuedConnection)

    @Slot(object)
    def _run(self, fn):
        try:
            fn()
        except Exception as e:
            print(f"DIAG: GuiInvoker caught: {e!r}")

_gui = {"invoker": None}
_orig_qapp_init = QApplication.__init__

def _patched_qapp_init(self, *args, **kwargs):
    _orig_qapp_init(self, *args, **kwargs)
    if _gui["invoker"] is None:
        _gui["invoker"] = _GuiInvoker()
        print("DIAG: GuiInvoker installed (queued to GUI thread).")

QApplication.__init__ = _patched_qapp_init  # patch construction to install invoker

def _emit_gui(fn):
    inv = _gui.get("invoker")
    if inv is None:
        # If someone calls before QApplication exists, just skip (won't happen after app starts)
        print("DIAG: GuiInvoker not ready; skipping.")
        return
    inv.run.emit(fn)

# ---------------- helpers ----------------
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

def _show_any_overlay_gui():
    app = QApplication.instance()
    if not app:
        return
    n = 0
    for w in app.topLevelWidgets():
        if isinstance(w, Overlay):
            # Call the real .show() (your Overlay.show may be patched by earlier probes; that’s fine)
            w.show()
            n += 1
    print(f"DIAG: auto-show -> requested show() on {n} Overlay instance(s)")

# ---------------- EventHub tap (signature-preserving) ----------------
_active_names = {
    "enter_active_monitoring", "ActiveMonitoring", "EnterActiveMonitoring",
    "state_active_monitoring", "entered_active_monitoring",
}
_endpoint_names = {"EndpointAppeared", "endpoint_appeared"}

_original_publish = EventHub.publish

def _publish_tap(self, *args, **kwargs):
    name = _event_name_from_args(args, kwargs)
    ts = time.time()
    payload_repr = None
    if len(args) >= 2:
        payload_repr = _safe_json(args[1])
    elif "payload" in kwargs:
        payload_repr = _safe_json(kwargs["payload"])
    print(f"DIAG: EventHub.publish -> {name} payload={payload_repr} ts={ts:.3f}")

    # Trigger from endpoint or active-monitoring name; marshal with queued signal
    if isinstance(name, str) and (name in _endpoint_names or name in _active_names or name.lower() == "enter_active_monitoring"):
        print(f"DIAG: EventHub tap -> trigger on '{name}'; emitting to GUI invoker.")
        _emit_gui(_show_any_overlay_gui)

    return _original_publish(self, *args, **kwargs)

EventHub.publish = _publish_tap

# ---------------- Launch real app ----------------
RUN = PROJECT_ROOT / "run.py"
print("DIAG: launching real app via run.py ...")
runpy.run_path(str(RUN), run_name="__main__")
