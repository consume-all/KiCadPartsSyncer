from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from ..domain.events import (
    EndpointAppeared,
    EndpointVanished,
    ConnectedToKiCad,
    DisconnectedFromKiCad,
    FreezeToggled,
)

from KiCadPartsSyncer.infrastructure.git.repo_status_poller import RepoStatusPoller
from KiCadPartsSyncer.infrastructure.git import repo_puller, repo_pusher


class _GitOpResultDispatcher(QObject):
    """
    Lives on the GUI thread.

    Worker thread emits sig_show(op, success, message), Qt delivers it
    to _on_show on the GUI thread (QueuedConnection by default).
    """

    sig_show = Signal(str, bool, str)  # op, success, message

    def __init__(self, orchestrator: "Orchestrator") -> None:
        QObject.__init__(self)
        self._orchestrator = orchestrator
        self.sig_show.connect(self._on_show)

    @Slot(str, bool, str)
    def _on_show(self, op: str, success: bool, message: str) -> None:
        # Delegate to Orchestrator's GUI-thread handler.
        self._orchestrator._show_git_result(op, success, message)


class Orchestrator:
    """
    Orchestrates UI state for the HUD.

    Responsibilities:
      - Listen to domain events.
      - Control overlay visibility (active vs dormant).
      - Own the repo status poller lifecycle.
      - Handle explicit HUD actions (Pull / Push).
    """

    def __init__(self, sv):
        self.sv = sv
        self._connected = False      # logical "ConnectedToKiCad" state
        self._frozen = False

        # Track in-progress git operations by name ("pull", "push")
        self._op_in_progress = {
            "pull": False,
            "push": False,
        }

        # Dispatcher is created on GUI thread (same place Orchestrator is constructed)
        # so its slot will always run on GUI thread.
        self._git_dispatcher = _GitOpResultDispatcher(self)

        # Prepare poller; do NOT start yet.
        try:
            self._repo_poller = RepoStatusPoller(self._on_repo_status)
        except Exception:
            self._repo_poller = None
            try:
                self.sv.log.info(
                    "repo_status",
                    "poller_init_failed",
                    {"reason": "exception_during_init"},
                )
            except Exception:
                pass

        # Wire "Pull" button intent from overlay -> orchestrator.
        try:
            # Overlay must define: _sig_pull_requested = Signal()
            self.sv.overlay._sig_pull_requested.connect(self._on_pull_requested)
            self.sv.log.info(
                "repo_pull",
                "pull_signal_connected",
                {},
            )
        except Exception:
            try:
                self.sv.log.info(
                    "repo_pull",
                    "pull_signal_connect_failed",
                    {},
                )
            except Exception:
                pass

        # Wire "Push" button intent from overlay -> orchestrator.
        try:
            # Overlay must define: _sig_push_requested = Signal()
            self.sv.overlay._sig_push_requested.connect(self._on_push_requested)
            self.sv.log.info(
                "repo_push",
                "push_signal_connected",
                {},
            )
        except Exception:
            try:
                self.sv.log.info(
                    "repo_push",
                    "push_signal_connect_failed",
                    {},
                )
            except Exception:
                pass

    # ---------- repo status handling (callback from background thread) ----------

    def _on_repo_status(self, status: str) -> None:
        """
        Called from RepoStatusPoller background thread.
        """
        try:
            self.sv.log.info("repo_status", "update", {"status": status})
        except Exception:
            pass

        if self._frozen:
            return

        try:
            self.sv.overlay.set_repo_status(status)
        except Exception:
            # Never let UI issues propagate back into the poller thread.
            pass

    def _start_repo_poller(self) -> None:
        if self._repo_poller is None:
            return
        try:
            self._repo_poller.start()
            self.sv.log.info("repo_status", "poller_started", {})
        except Exception:
            try:
                self.sv.log.info("repo_status", "poller_start_failed", {})
            except Exception:
                pass

    def _stop_repo_poller(self) -> None:
        if self._repo_poller is None:
            return
        try:
            self._repo_poller.stop()
            self.sv.log.info("repo_status", "poller_stopped", {})
        except Exception:
            pass

    # ---------- generic git op pipeline (pull/push) ----------

    def _start_git_op(self, op: str, func, thread_name: str) -> None:
        """
        Shared entry point for git operations.

        op: "pull" or "push"
        func: callable returning (success: bool, message: str)
        thread_name: name for the worker thread
        """
        if self._op_in_progress.get(op, False):
            try:
                self.sv.log.info(
                    "repo_{0}".format(op),
                    "ignored_already_in_progress",
                    {},
                )
            except Exception:
                pass
            return

        self._op_in_progress[op] = True

        try:
            self.sv.log.info(
                "repo_{0}".format(op),
                "requested",
                {},
            )
        except Exception:
            pass

        t = threading.Thread(
            target=self._run_git_worker,
            name=thread_name,
            daemon=True,
            args=(op, func),
        )
        t.start()

    def _run_git_worker(self, op: str, func) -> None:
        """
        Background-thread body: call func() and emit result via dispatcher
        (Qt will deliver on GUI thread).
        """
        try:
            try:
                self.sv.log.info(
                    "repo_{0}".format(op),
                    "worker_start",
                    {},
                )
            except Exception:
                pass

            success, message = func()

            try:
                self.sv.log.info(
                    "repo_{0}".format(op),
                    "worker_done",
                    {"success": bool(success)},
                )
            except Exception:
                pass

        except Exception as exc:
            success = False
            message = "Unexpected error in repo_{0}: {1}".format(op, exc)
            try:
                self.sv.log.error(
                    "repo_{0}".format(op),
                    "worker_exception",
                    {"error": str(exc)},
                )
            except Exception:
                pass

        # Emit to dispatcher; Qt queues this to GUI thread.
        try:
            self._git_dispatcher.sig_show.emit(op, bool(success), message)
        except Exception:
            # In absolute worst case, if dispatcher fails, at least unlock.
            self._op_in_progress[op] = False
            try:
                self.sv.log.error(
                    "repo_{0}".format(op),
                    "dispatcher_emit_failed",
                    {},
                )
            except Exception:
                pass

    def _show_git_result(self, op: str, success: bool, message: str) -> None:
        """
        Runs on the GUI thread. Shows dialog and clears in-progress flag.
        """
        # Titles & log prefixes per operation
        op = (op or "").strip().lower()
        if op not in ("pull", "push"):
            op = "pull"  # fallback

        if op == "pull":
            title_ok = "KiCad Libraries Updated"
            title_err = "KiCad Library Pull Failed"
        else:
            title_ok = "KiCad Libraries Pushed"
            title_err = "KiCad Library Push Failed"

        log_prefix = "repo_{0}".format(op)

        try:
            if success:
                try:
                    QMessageBox.information(
                        self.sv.overlay,
                        title_ok,
                        message,
                    )
                except Exception:
                    try:
                        self.sv.log.info(
                            log_prefix,
                            "succeeded_no_dialog",
                            {},
                        )
                    except Exception:
                        pass

                try:
                    self.sv.log.info(
                        log_prefix,
                        "succeeded",
                        {},
                    )
                except Exception:
                    pass
            else:
                try:
                    QMessageBox.critical(
                        self.sv.overlay,
                        title_err,
                        message,
                    )
                except Exception:
                    try:
                        self.sv.log.error(
                            log_prefix,
                            "failed_no_dialog",
                            {"message": message},
                        )
                    except Exception:
                        pass

                try:
                    self.sv.log.error(
                        log_prefix,
                        "failed",
                        {"message": message},
                    )
                except Exception:
                    pass
        finally:
            self._op_in_progress[op] = False

    # ---------- pull/push public hooks from overlay ----------

    def _on_pull_requested(self) -> None:
        """
        Invoked when the overlay's Pull button is clicked.
        """
        self._start_git_op(
            op="pull",
            func=repo_puller.pull_once,
            thread_name="RepoPullerThread",
        )

    def _on_push_requested(self) -> None:
        """
        Invoked when the overlay's Push button is clicked.
        """
        self._start_git_op(
            op="push",
            func=repo_pusher.push_once,
            thread_name="RepoPusherThread",
        )

    # ---------- event handlers ----------

    def on_endpoint_appeared(self, evt: EndpointAppeared):
        """
        KiCad endpoint detected => HUD active + start repo polling.
        """
        self.sv.log.info(
            "state",
            "endpoint_appeared",
            {"path": getattr(evt, "path", None)},
        )

        if not self._frozen:
            self.enter_active_monitoring()
            self._start_repo_poller()
        else:
            self.sv.log.info(
                "state",
                "endpoint_appeared_ignored_frozen",
                {},
            )

    def on_endpoint_vanished(self, evt: EndpointVanished):
        """
        KiCad endpoint gone => stop polling + HUD dormant.
        """
        self.sv.log.info("state", "endpoint_vanished", {})
        self._stop_repo_poller()
        self.enter_dormant()

    def on_connected(self, evt: ConnectedToKiCad):
        """
        Higher-level "connected" event (e.g., project info available).
        Repo polling is already tied to endpoint presence, so we *do not*
        start/stop poller here; we only adjust HUD content.
        """
        self._connected = True
        project_info = getattr(evt, "project_info", None)

        self.sv.log.info(
            "state",
            "connected",
            {"project_info": project_info},
        )

        if not self._frozen:
            self.sv.overlay.show_overlay(project_info)
        else:
            self.sv.log.info(
                "state",
                "connected_ignored_frozen",
                {},
            )

    def on_disconnected(self, evt: DisconnectedFromKiCad):
        """
        Logical disconnect; endpoint events will still govern polling.
        """
        self._connected = False
        self.sv.log.info("state", "disconnected", {})
        # Don't touch poller here; endpoint_vanished handles that.
        self.enter_dormant()

    def on_freeze_toggled(self, evt: FreezeToggled):
        """
        Freeze = stop reacting visually (including repo status color changes).
        """
        self._frozen = bool(evt.is_frozen)
        self.sv.log.info(
            "state",
            "freeze_toggled",
            {"is_frozen": self._frozen},
        )

        # Optional: if Overlay has show_frozen, call it.
        try:
            if hasattr(self.sv.overlay, "show_frozen"):
                self.sv.overlay.show_frozen(self._frozen)
        except Exception:
            pass

        if self._frozen:
            return

        if self._connected:
            self.enter_active_monitoring()
        else:
            self.enter_dormant()

    # ---------- states ----------

    def enter_active_monitoring(self):
        self.sv.log.info("state", "enter_active_monitoring", {})
        self.sv.overlay.show_overlay()

    def enter_dormant(self):
        self.sv.log.info("state", "enter_dormant", {})
        self.sv.overlay.hide_overlay()

    # ---------- optional graceful shutdown ----------

    def shutdown(self) -> None:
        """If you add explicit shutdown wiring in main(), call this."""
        self._stop_repo_poller()
