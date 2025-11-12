from __future__ import annotations

import sys
import time
import threading
import subprocess
from typing import Callable, Optional
from pathlib import Path

from ..system.config import get_repo_poll_interval_seconds

# repo_status_poller.py is at: src/KiCadPartsSyncer/infrastructure/git/
# We want cwd=src so that `-m KiCadPartsSyncer....` works.
SRC_ROOT = Path(__file__).resolve().parents[3]


class RepoStatusPoller(object):
    """
    Periodically runs `KiCadPartsSyncer.infrastructure.git.remote_checker`
    and reports a normalized status string via a callback:

        'unknown'  -> not configured / cannot check / error
        'clean'    -> repo in sync with remote
        'diverged' -> local and/or remote is ahead / diverged / detached

    Responsibilities:
      - Own background thread + interval.
      - Never depend on Qt or UI.
      - Never crash the app on errors.
    """

    def __init__(self, on_status: Callable[[str], None]) -> None:
        if on_status is None:
            raise ValueError("on_status callback must not be None.")

        self._on_status = on_status
        self._interval = get_repo_poll_interval_seconds()
        self._stop = threading.Event()
        self._thread = None  # type: Optional[threading.Thread]

    # ---------- lifecycle ----------

    def start(self) -> None:
        """
        Start the background loop (idempotent).

        Safe to call multiple times; a new thread is only started if
        there isn't one already running.
        """
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="RepoStatusPoller",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """
        Signal the background loop to stop.

        A future start() call will spin up a fresh thread.
        """
        self._stop.set()

    # ---------- internals ----------

    def _run_loop(self) -> None:
        # Initial notification so consumers have a known starting point.
        self._safe_report("unknown")

        while not self._stop.is_set():
            status = self._check_once()
            self._safe_report(status)

            # Sleep in 1s chunks so stop() is responsive.
            remaining = self._interval
            while remaining > 0 and not self._stop.is_set():
                time.sleep(1.0)
                remaining -= 1

    def _safe_report(self, status: str) -> None:
        """Invoke the callback; swallow any exceptions."""
        try:
            self._on_status(status)
        except Exception:
            # Consumer issues must not kill this thread.
            pass

    def _check_once(self) -> str:
        """
        Invoke remote_checker via subprocess and interpret its output.

        Rules:
          - Non-zero exit           -> 'unknown'
          - 'status: clean'         -> 'clean'
          - 'status: ahead/behind/diverged' -> 'diverged'
          - 'detached head'         -> 'diverged'
          - Generic ahead/behind/diverg*   -> 'diverged'
          - Generic up-to-date/in sync     -> 'clean'
          - Otherwise (exit 0)      -> 'clean' (safe fallback)
        """
        try:
            cmd = [
                sys.executable,
                "-m",
                "KiCadPartsSyncer.infrastructure.git.remote_checker",
            ]

            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(SRC_ROOT),
            )

            if completed.returncode != 0:
                return "unknown"

            text = ((completed.stdout or "") + (completed.stderr or "")).lower()

            # Detached HEAD explicitly => treat as diverged / non-clean.
            if "detached" in text and "head" in text:
                return "diverged"

            # Explicit machine-style markers (preferred).
            if "status: clean" in text or "status=clean" in text:
                return "clean"

            if (
                "status: ahead" in text
                or "status=ahead" in text
                or "status: behind" in text
                or "status=behind" in text
                or "status: diverged" in text
                or "status=diverged" in text
            ):
                return "diverged"

            # Generic wording from human-readable messages.
            if "ahead" in text or "behind" in text or "diverg" in text:
                return "diverged"

            if "up-to-date" in text or "up to date" in text or "in sync" in text:
                return "clean"

            # If remote_checker exited 0 but we didn't match anything scary,
            # assume "clean" rather than leaving HUD stuck at unknown.
            return "clean"

        except Exception:
            return "unknown"
