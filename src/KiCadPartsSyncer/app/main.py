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
    EndpointAppeared, EndpointVanished,
    ConnectedToKiCad, DisconnectedFromKiCad,
    RemoteUpdatesFound, LocalChangesFound,
    NewLibraryDiscovered, FreezeToggled,
)
from .orchestrator import Orchestrator

# ---- global hotkey (works when HUD is click-through/unfocused) ----
from ..infrastructure.system.win_hotkey import (
    WinHotkeyManager, MOD_CONTROL, VK_OEM_3
)


def _qt_bootstrap(app: QApplication) -> None:
    app.setQuitOnLastWindowClosed(False)
    # High-DPI awareness (best effort; Windows only)
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


def main() -> int:
    app = QApplication(sys.argv)
    _qt_bootstrap(app)

    # ---- infra instances ----
    log = Logger()
    hub = EventHub()
    endpoint = EndpointDetector(hub, log)

    overlay = Overlay(hub)

    try:
        overlay.appear_idle()
    except Exception:
        try:
            overlay.hide()
        except Exception:
            pass

    # ---- TRAY (***match your Tray signature***) ----
    # Your Tray.__init__(self, app, overlay, settings, hub)
    tray = Tray(app, overlay, hub)

    # ---- make a simple service bag for Orchestrator ----
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

    # Ensure dormant at boot; detector will flip state
    try:
        orch.enter_dormant()
    except Exception:
        pass

    # ---- GLOBAL hotkey: Ctrl+` toggles click-through regardless of focus ----
    def _toggle_click_through() -> None:
        """
        Ctrl+` behavior:

        - If HUD is visible:
            Toggle click-through ONLY.
            If some side-effect hides/minimizes it, immediately bring it back.
        - If HUD is hidden:
            Do nothing (respect explicit hide via tray/orchestrator).
        """
        try:
            was_visible = overlay.isVisible()

            if not was_visible:
                # Don't resurrect a hidden HUD via hotkey.
                log.info("hotkey", "ignored_while_hidden", {})
                return

            # Toggle click-through flag.
            overlay.set_click_through(not overlay.is_click_through())

            # If something during toggle caused it to vanish/minimize, restore it.
            if was_visible and not overlay.isVisible():
                show_overlay = getattr(overlay, "show_overlay", None)
                if callable(show_overlay):
                    show_overlay()
                else:
                    overlay.show()

            state = "on" if overlay.is_click_through() else "off"
            log.info(
                "hotkey",
                "click_through_toggled",
                {
                    "state": state,
                    "visible": overlay.isVisible(),
                },
            )
        except Exception as ex:
            log.error("hotkey", "click_through_failed", {"err": repr(ex)})

    try:
        hk = WinHotkeyManager(app)
        if not hk.register(id=1, modifiers=MOD_CONTROL, vk=VK_OEM_3, callback=_toggle_click_through):
            log.error("hotkey", "registration_failed", {"combo": "Ctrl+`"})
    except Exception as ex:
        # Non-Windows or unexpected failure; app still runs without global hotkey.
        log.error("hotkey", "manager_init_failed", {"err": repr(ex)})

    endpoint.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
