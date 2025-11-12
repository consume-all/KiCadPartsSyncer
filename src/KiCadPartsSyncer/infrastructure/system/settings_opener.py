from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from . import config


def _get_settings_path() -> Path:
    """
    Single source of truth for where settings.json lives.

    Uses config.DEFAULT_SETTINGS_PATH, which is:
        ProjectRoot/src/KiCadPartsSyncer/settings.json
    """
    return config.DEFAULT_SETTINGS_PATH


def open_settings_in_editor() -> None:
    """
    Open the KiCadPartsSyncer settings file in VS Code if available,
    otherwise Notepad.

    - Ensures the directory exists
    - Creates an empty file if missing
    - Prefers `code` (VS Code CLI) if on PATH (via shell)
    - Falls back to `notepad` on Windows

    This function is best-effort and will silently do nothing if both
    attempts fail, to avoid crashing the HUD.
    """
    settings_path = _get_settings_path()

    # Make sure the directory exists
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Create the file if it doesn't exist yet
    if not settings_path.exists():
        settings_path.touch()

    # --- Try VS Code first ---
    # We just need to know if 'code' is on PATH; then we invoke it via the shell.
    if shutil.which("code"):
        try:
            # Use shell=True so the VS Code shim (code.cmd) runs correctly on Windows.
            subprocess.Popen(["code", str(settings_path)], shell=True)
            return
        except OSError:
            # If VS Code launch fails for any reason, fall back to Notepad.
            pass

    # --- Fallback: Notepad ---
    try:
        notepad_exe = shutil.which("notepad") or "notepad"
        subprocess.Popen([notepad_exe, str(settings_path)])
    except OSError:
        # Final failure – nothing more we can do here without a logger/UI.
        # We deliberately swallow the error to avoid crashing the app.
        return
