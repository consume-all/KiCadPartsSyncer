# -*- coding: utf-8 -*-
"""
10_overlay_event_timeline.py

Measure the first-show event ordering and geometry behavior of Overlay:
- Logs sizes during showEvent, resizeEvent, paintEvent
- Optional: force child geometry in showEvent to test if it sticks

Usage:
  python tools/diagnostics/10_overlay_event_timeline.py
  python tools/diagnostics/10_overlay_event_timeline.py --force-geom
"""

from __future__ import annotations
import sys, time
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

# ---- ensure src on sys.path ----
HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from KiCadPartsSyncer.ui.overlay import Overlay  # type: ignore

# ---- helpers -----------------------------------------------------------------

@dataclass
class Flags:
    force_geom: bool = False

def parse_flags() -> Flags:
    return Flags(force_geom=("--force-geom" in sys.argv))

class DummySettings:
    def __init__(self): self._data = {}
    def get(self, k, d=None): return self._data.get(k, d)
    def set(self, k, v): self._data[k] = v
    def save(self): pass

def pick_body_attr(obj) -> str | None:
    for name in ("_body", "_root", "_frame", "_container", "_widget", "_content"):
        if hasattr(obj, name):
            return name
    return None

# ---- instrumented overlay ----------------------------------------------------

class InstrumentedOverlay(Overlay):
    def __init__(self, *a, **kw):
        # Pop our private flags BEFORE super() so Overlay.__init__ never sees them
        flags = kw.pop("_flags", None)
        super().__init__(*a, **kw)

        self._flags: Flags = flags if isinstance(flags, Flags) else Flags()
        self._t0 = time.perf_counter()
        self._body_name = pick_body_attr(self)
        self._body_ref = getattr(self, self._body_name) if self._body_name else None
        self._forced = False

        print(f"\n[10] InstrumentedOverlay ready | body_attr={self._body_name!r} | force_geom={self._flags.force_geom}")
        self._log_sizes("init")

        # Post-show checkpoints
        QTimer.singleShot(0,  lambda: self._log_sizes("checkpoint+0ms"))
        QTimer.singleShot(16, lambda: self._log_sizes("checkpoint+16ms"))
        QTimer.singleShot(100,lambda: self._log_sizes("checkpoint+100ms"))

    # Logging utilities
    def _dt(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0
    def _sizes(self):
        win_sz = self.size()
        body_sz = self._body_ref.size() if self._body_ref is not None else None
        return win_sz, body_sz
    def _log_sizes(self, where: str):
        win_sz, body_sz = self._sizes()
        forced = " forced" if self._forced else ""
        print(f"[10] t={self._dt():7.2f}ms {where:>18}: window={win_sz} body={body_sz}{forced}")

    # Qt events
    def showEvent(self, e):
        self._log_sizes("showEvent (pre)")
        if self._flags.force_geom and self._body_ref is not None:
            self._body_ref.setGeometry(self.rect())
            self._forced = True
            self._log_sizes("showEvent (post-setGeom)")
        super().showEvent(e)
        self._log_sizes("showEvent (post)")

    def resizeEvent(self, e):
        self._log_sizes("resizeEvent (pre)")
        super().resizeEvent(e)
        self._log_sizes("resizeEvent (post)")

    def paintEvent(self, e):
        self._log_sizes("paintEvent (pre)")
        super().paintEvent(e)
        self._log_sizes("paintEvent (post)")

# ---- main --------------------------------------------------------------------

def main():
    flags = parse_flags()
    app = QApplication(sys.argv)

    ov = InstrumentedOverlay(hub=None, settings=DummySettings(), _flags=flags)

    print("\n[10] Before show_overlay():")
    ov._log_sizes("pre-show")

    ov.show_overlay()
    app.processEvents()

    print("\n[10] After show_overlay() + processEvents():")
    ov._log_sizes("post-show")

    print("\n[10] Notes:")
    print(" - Re-run with --force-geom to test setting body := rect() inside showEvent.")
    print(" - Check whether paintEvent logs still show body << window on the first frame.")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
