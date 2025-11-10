# src/companion/app/hotkeys.py
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from ..infrastructure.system.win_hotkey import (
    WinHotkeyManager,
    MOD_CONTROL,
    VK_OEM_3,
)
from ..infrastructure.system.logger import Logger
from ..ui.overlay import Overlay


def install_global_hotkeys(app: QApplication, overlay: Overlay, log: Logger) -> None:
    """
    Register process-wide hotkeys.

    Currently:
      - Ctrl+` toggles HUD click-through ONLY when the HUD is visible.
      - Does nothing if HUD is hidden (we respect explicit hides).
    """

    def _toggle_click_through() -> None:
        try:
            # Don't resurrect a hidden HUD.
            if not overlay.isVisible():
                log.info("hotkey", "ignored_while_hidden", {})
                return

            # Toggle click-through.
            overlay.set_click_through(not overlay.is_click_through())

            # If something during toggle caused it to vanish/minimize, restore it.
            if not overlay.isVisible():
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
        ok = hk.register(
            id=1,
            modifiers=MOD_CONTROL,
            vk=VK_OEM_3,
            callback=_toggle_click_through,
        )
        if not ok:
            log.error("hotkey", "registration_failed", {"combo": "Ctrl+`"})
    except Exception as ex:
        # Non-Windows or unexpected failure; app still runs without the global hotkey.
        log.error("hotkey", "manager_init_failed", {"err": repr(ex)})
