from __future__ import annotations
from ..domain.events import (
    EndpointAppeared, EndpointVanished,
    ConnectedToKiCad, DisconnectedFromKiCad,
    FreezeToggled,
)

class Orchestrator:
    """
    Orchestrates UI state for the HUD.
    NOTE: Overlay methods are thread-safe and self-marshal to the GUI thread,
    so we call them directly (no QTimer here).
    """

    def __init__(self, sv):
        self.sv = sv
        self._connected = False
        self._frozen = False

    # events
    def on_endpoint_appeared(self, evt: EndpointAppeared):
        self.sv.log.info("state", "endpoint_appeared", {"path": getattr(evt, "path", None)})
        if not self._frozen:
            self.enter_active_monitoring()
        else:
            self.sv.log.info("state", "endpoint_appeared_ignored_frozen", {})

    def on_endpoint_vanished(self, evt: EndpointVanished):
        self.sv.log.info("state", "endpoint_vanished", {})
        self.enter_dormant()

    def on_connected(self, evt: ConnectedToKiCad):
        self._connected = True
        project_info = getattr(evt, "project_info", None)
        self.sv.log.info("state", "connected", {"project_info": project_info})
        if not self._frozen:
            # Thread-safe: Overlay will queue to GUI thread if needed
            self.sv.overlay.show_overlay(project_info)
        else:
            self.sv.log.info("state", "connected_ignored_frozen", {})

    def on_disconnected(self, evt: DisconnectedFromKiCad):
        self._connected = False
        self.sv.log.info("state", "disconnected", {})
        self.enter_dormant()

    def on_freeze_toggled(self, evt: FreezeToggled):
        self._frozen = bool(evt.is_frozen)
        self.sv.log.info("state", "freeze_toggled", {"is_frozen": self._frozen})
        # Thread-safe call; Overlay handles GUI marshalling
        self.sv.overlay.show_frozen(self._frozen)
        if self._frozen:
            return
        if self._connected:
            self.enter_active_monitoring()
        else:
            self.enter_dormant()

    # states
    def enter_active_monitoring(self):
        self.sv.log.info("state", "enter_active_monitoring", {})
        # Thread-safe: Overlay method handles UI thread handoff
        self.sv.overlay.show_overlay()

    def enter_dormant(self):
        self.sv.log.info("state", "enter_dormant", {})
        # Thread-safe: Overlay method handles UI thread handoff
        self.sv.overlay.hide_overlay()
