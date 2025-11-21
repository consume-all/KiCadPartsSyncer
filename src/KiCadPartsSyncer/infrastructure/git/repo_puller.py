from __future__ import annotations

import os
import subprocess
from typing import Tuple

from ..system import config

GIT_PULL_TIMEOUT_SECONDS = 30  # so HUD can't get stuck forever


def pull_once() -> Tuple[bool, str]:
    """
    Perform a single `git pull --ff-only` on the configured repository.

    Uses:
      - config.load_settings()
      - config.get_repository_local_path()
      - config.get_repository_remote_name()  # remoteName/remote/'origin'

    Auth:
      - Relies entirely on your Git/SSH configuration (SSH keys, etc.).
      - No PAT or credential manager integration here.

    Returns:
        (success, message)
    """
    try:
        settings = config.load_settings()
    except RuntimeError as exc:
        return False, str(exc)

    try:
        repo_path = config.get_repository_local_path(settings)
    except RuntimeError as exc:
        return False, str(exc)

    remote_name = config.get_repository_remote_name(settings)

    cmd = [
        "git",
        "-C",
        str(repo_path),
        "pull",
        "--ff-only",
        remote_name,
    ]

    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=GIT_PULL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return (
            False,
            (
                "Timed out while running 'git pull'.\n\n"
                "This usually means the remote is unreachable or Git is "
                "waiting for credentials.\n"
                "Please verify your network and stored credentials, then try again."
            ),
        )
    except FileNotFoundError:
        return False, "Git executable not found. Please install Git and try again."
    except Exception as exc:
        return False, "Unexpected error while running git pull: {0}".format(exc)

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    if proc.returncode == 0:
        combined = (stdout + "\n" + stderr).lower()

        if "already up to date" in combined or "already up-to-date" in combined:
            return True, (
                "No changes were pulled.\n\n"
                "The KiCad libraries are already up to date."
            )

        return True, (
            "Library successfully updated from remote.\n\n"
            "Changes will take effect after restarting KiCad."
        )

    if stderr and stdout:
        detail = stderr + "\n\n" + stdout
    else:
        detail = stderr or stdout or "Unknown git error."

    msg = (
        "Failed to pull from remote.\n\n"
        "Command: {cmd}\n\n"
        "{detail}"
    ).format(cmd=" ".join(cmd), detail=detail)

    return False, msg


if __name__ == "__main__":
    ok, msg = pull_once()
    print("success:", ok)
    print("message:")
    print(msg)
