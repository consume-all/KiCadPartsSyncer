# -*- coding: utf-8 -*-
"""
07_event_tap_and_autoshow.py
Add-only diagnostic launcher:
- Patches EventHub.publish(...) to log every event and AUTO-SHOW the Overlay when
  'enter_active_monitoring' is published.
- Uses GUI-thread safe QTimer.singleShot(0, ...) and your (already patched) Overlay.show().
- Launches your real app (run.py) unchanged.

Acronyms: GUI = Graphical User Interface, HUD = Heads-Up Display.
"""
import sys, runpy, json, time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

# ---- ensure src on sys.path ----
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# ---- import your classes AFTER path fix ----
from KiCadPartsSyncer.infrastructure.system.event_hub import EventHub  # noqa: E402
from KiCadPartsSyncer.ui.overlay import Overlay  # noqa: E402

# ---- helper: show all Overlay instances on the GUI thread ----
def _show_any_overlay():
    app = QApplication.instance()
    if not app:
        return
    # Find any live Overlay window(s) and call show() (your patched show() will center/raise)
    shown = 0
    for w in app.topLevelWidgets():
        if isinstance(w, Overlay):
            try:
                w.show()
                shown += 1
            except Exception as e:
                print(f"DIAG: auto-show -> exception calling show(): {e!r}")
    print(f"DIAG: auto-show -> requested show() on {shown} Overlay instance(s)")

def _schedule_show():
    # Always hop to GUI thread
    QTimer.singleShot(0, _show_any_overlay)

# ---- patch EventHub.publish to tap events and trigger auto-show on ActiveMonitoring ----
_original_publish = EventHub.publish

def _publish_tap(self, event_name: str, payload=None):
    try:
        # Log everything the hub emits (helps prove whether orchestrator fires)
        stamp = time.time()
        print(f'DIAG: EventHub.publish -> {event_name} payload={json.dumps(payload) if payload is not None else "null"} ts={stamp:.3f}')
    except Exception:
        print(f'DIAG: EventHub.publish -> {event_name} (payload not JSON-serializable)')

    # On enter_active_monitoring, force the HUD to show on GUI thread
    if event_name in ("enter_active_monitoring", "ActiveMonitoring", "state_active_monitoring"):
        print("DIAG: EventHub tap -> enter_active_monitoring detected; scheduling Overlay.show()")
        _schedule_show()

    # Always pass through to original behavior
    return _original_publish(self, event_name, payload)

EventHub.publish = _publish_tap  # runtime patch

# ---- also patch Overlay.show_overlay cursor path if your code still uses it anywhere ----
# (Safe to no-op if earlier diagnostic already patched it.)
try:
    from PySide6.QtGui import QCursor, QGuiApplication
    _orig_show_overlay = getattr(Overlay, "show_overlay", None)

    def _patched_show_overlay(self):
        # Place near cursor if available; fall back to standard show()
        try:
            pos = QCursor.pos()
        except Exception:
            pos = None

        scr = None
        if pos is not None and hasattr(QGuiApplication, "screenAt") and callable(QGuiApplication.screenAt):
            scr = QGuiApplication.screenAt(pos)
        if scr is not None:
            geo = scr.availableGeometry()
            W = max(420, self.width()); H = max(28, self.height())
            x = max(geo.x(), min(geo.right() - W + 1, pos.x() - W // 2))
            y = max(geo.y(), min(geo.bottom() - H + 1, pos.y() + 20))
            self.setGeometry(x, y, W, H)

        # Defer to (possibly patched) .show(), which centers/raises/activates
        self.show()

    if callable(_orig_show_overlay):
        setattr(Overlay, "show_overlay", _patched_show_overlay)
except Exception:
    pass

# ---- launch your real app ----
RUN = PROJECT_ROOT / "run.py"
if not RUN.exists():
    print("DIAG: ERROR -> ProjectRoot/run.py not found.")
    sys.exit(1)

print("DIAG: launching real app via run.py ...")
runpy.run_path(str(RUN), run_name="__main__")
