from __future__ import annotations

import os
import subprocess
from typing import Tuple

from ..system import config

GIT_PUSH_TIMEOUT_SECONDS = 30  # keep it short so HUD can't hang forever


def push_once() -> Tuple[bool, str]:
    """
    Perform a single `git push` on the configured repository.

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
        "push",
        remote_name,
    ]

    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=GIT_PUSH_TIMEOUT_SECONDS,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return False, "git push timed out after {0} seconds".format(
            GIT_PUSH_TIMEOUT_SECONDS
        )

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        msg = stderr or stdout or "git push failed with unknown error."
        return False, msg

    stdout = (proc.stdout or "").strip()
    if not stdout:
        stdout = "git push completed successfully."

    return True, stdout


if __name__ == "__main__":
    ok, msg = push_once()
    print("success:", ok)
    print("message:")
    print(msg)
