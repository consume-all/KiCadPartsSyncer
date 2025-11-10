# src/companion/app/main.py
from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

# ---- infrastructure ----
from ..infrastructure.system.logger import Logger
from ..infrastructure.system.event_hub import EventHub
from ..infrastructure.ipc.endpoint_detector import EndpointDetector

# ---- UI ----
from ..ui.overlay import Overlay
from ..ui.tray import Tray

# ---- domain ----
from ..domain.events import (
    EndpointAppeared,
    EndpointVanished,
    ConnectedToKiCad,
    DisconnectedFromKiCad,
    RemoteUpdatesFound,
    LocalChangesFound,
    NewLibraryDiscovered,
    FreezeToggled,
)
from .orchestrator import Orchestrator

# ---- app-level helpers ----
from .hotkeys import install_global_hotkeys


def _qt_bootstrap(app: QApplication) -> None:
    app.setQuitOnLastWindowClosed(False)

    # High-DPI awareness (best-effort on Windows)
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


def main() -> int:
    # ---- Qt bootstrap ----
    app = QApplication(sys.argv)
    _qt_bootstrap(app)

    # ---- infrastructure ----
    log = Logger()
    hub = EventHub()
    endpoint = EndpointDetector(hub, log)

    # ---- overlay ----
    overlay = Overlay(hub)

    # Defensive: if appear_idle blows up, ensure no zombie window.
    try:
        overlay.appear_idle()
    except Exception:
        try:
            overlay.hide()
        except Exception:
            pass

    # ---- tray ----
    # IMPORTANT: ensure this matches your actual Tray.__init__ signature.
    # If Tray(app, overlay, hub) is your current definition, this is correct.
    # If it still expects (app, overlay, settings, hub), wire settings here explicitly.
    tray = Tray(app, overlay, hub)

    # ---- tiny service bag for Orchestrator ----
    class _Sv(object):
        pass

    sv = _Sv()
    sv.app = app
    sv.log = log
    sv.hub = hub
    sv.endpoint = endpoint
    sv.overlay = overlay
    sv.tray = tray

    # ---- orchestrator wiring ----
    orch = Orchestrator(sv)

    hub.subscribe(EndpointAppeared, orch.on_endpoint_appeared)
    hub.subscribe(EndpointVanished, orch.on_endpoint_vanished)
    hub.subscribe(ConnectedToKiCad, orch.on_connected)
    hub.subscribe(DisconnectedFromKiCad, orch.on_disconnected)
    hub.subscribe(RemoteUpdatesFound, getattr(orch, "on_remote_updates", lambda e: None))
    hub.subscribe(LocalChangesFound, getattr(orch, "on_local_changes", lambda e: None))
    hub.subscribe(NewLibraryDiscovered, getattr(orch, "on_new_library", lambda e: None))
    hub.subscribe(FreezeToggled, orch.on_freeze_toggled)

    # Ensure dormant at boot; EndpointDetector will drive transitions.
    try:
        orch.enter_dormant()
    except Exception:
        pass

    # ---- global hotkeys ----
    install_global_hotkeys(app, overlay, log)

    # ---- run ----
    endpoint.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
