import threading
from typing import Optional

import psutil

from ...domain.events import EndpointAppeared, EndpointVanished


class EndpointDetector:
    """
    Ultra-light KiCad presence detector for Windows.
    - Polls process list every 1.0s (near-zero CPU)
    - Publishes EndpointAppeared / EndpointVanished on transitions
    - Debounces flaps (two consecutive identical readings before emitting)
    """

    def __init__(self, hub, log, interval: float = 1.0):
        self._hub = hub
        self._log = log
        self._interval = float(interval)

        self._t: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._is_up = False
        self._want_state = None
        self._confirm_count = 0

        # Process names we treat as "KiCad is running"
        self._name_candidates = ("kicad.exe", "kicad")

    # ---------- lifecycle ----------
    def start(self):
        if self._t and self._t.is_alive():
            return
        self._stop.clear()
        self._t = threading.Thread(target=self._run, name="EndpointDetector", daemon=True)
        self._t.start()
        self._log.info("endpoint", "detector_started", {})

    def stop(self):
        self._stop.set()
        if self._t:
            self._t.join(timeout=2.0)
        self._t = None
        self._log.info("endpoint", "detector_stopped", {})

    # ---------- internals ----------
    def _run(self):
        while not self._stop.is_set():
            try:
                up_now = self._is_kicad_running()
                if self._want_state is None or self._want_state != up_now:
                    # new desire, reset confirmation window
                    self._want_state = up_now
                    self._confirm_count = 1
                else:
                    self._confirm_count += 1

                # require 2 consecutive identical readings to emit a transition
                if self._confirm_count >= 2 and self._is_up != self._want_state:
                    self._is_up = self._want_state
                    if self._is_up:
                        self._log.info("endpoint", "appeared", {"path": ""})
                        self._hub.publish(EndpointAppeared(path=""))
                    else:
                        self._log.info("endpoint", "vanished", {})
                        self._hub.publish(EndpointVanished())

            except Exception as e:
                self._log.error("endpoint", f"detector_error: {e}", {})

            self._stop.wait(self._interval)

    def _is_kicad_running(self) -> bool:
        # Cheap scan over process names; ignore access denied.
        for p in psutil.process_iter(attrs=["name"]):
            try:
                name = (p.info.get("name") or "").lower()
            except Exception:
                continue
            if name in self._name_candidates:
                return True
        return False
