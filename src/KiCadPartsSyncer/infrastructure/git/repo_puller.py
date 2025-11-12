from __future__ import annotations

import os
import subprocess
from typing import Tuple

from ..system import config

GIT_PULL_TIMEOUT_SECONDS = 30  # so HUD can't get stuck forever


def pull_once() -> Tuple[bool, str]:
    """
    Perform a single `git pull --ff-only` on the configured repository.

    Returns:
        (success, message)

    Semantics:
      - success = True:
          * either updates were fetched/applied, OR repo was already up to date.
          * message text tells which.
      - success = False:
          * git or config error; message is user-facing.
    """
    # 1) Load settings
    try:
        settings = config.load_settings()
    except RuntimeError as exc:
        return False, str(exc)

    # 2) Resolve repo path
    try:
        repo_path = config.get_repository_local_path(settings)
    except RuntimeError as exc:
        return False, str(exc)

    # 3) Remote name
    remote_name = config.get_repository_remote_name(settings)

    cmd = [
        "git",
        "-C",
        str(repo_path),
        "pull",
        "--ff-only",
        remote_name,
    ]

    # Disable terminal-style prompts; GUI helpers (GCM) can still do their thing
    # if needed, and once creds are cached pulls are silent + fast.
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
        # Distinguish "no changes" vs "updated" using git's own message.
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

    # Non-zero exit: compose a helpful error.
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
    # Direct module test harness: run this to see exactly what happens.
    ok, msg = pull_once()
    print("success:", ok)
    print("message:")
    print(msg)



# from __future__ import annotations

# import os
# import subprocess
# from typing import Tuple

# from ..system import config


# GIT_PULL_TIMEOUT_SECONDS = 30  # so HUD can't get stuck forever


# def pull_once() -> Tuple[bool, str]:
#     """
#     Perform a single `git pull --ff-only` on the configured repository.

#     Returns:
#         (success, message)
#     """
#     # 1) Load settings
#     try:
#         settings = config.load_settings()
#     except RuntimeError as exc:
#         return False, str(exc)

#     # 2) Resolve repo path
#     try:
#         repo_path = config.get_repository_local_path(settings)
#     except RuntimeError as exc:
#         return False, str(exc)

#     # 3) Remote name
#     remote_name = config.get_repository_remote_name(settings)

#     cmd = [
#         "git",
#         "-C",
#         str(repo_path),
#         "pull",
#         "--ff-only",
#         remote_name,
#     ]

#     # Disable interactive prompts so we never hang waiting for credentials.
#     env = os.environ.copy()
#     env.setdefault("GIT_TERMINAL_PROMPT", "0")

#     try:
#         proc = subprocess.run(
#             cmd,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True,
#             encoding="utf-8",
#             env=env,
#             timeout=GIT_PULL_TIMEOUT_SECONDS,
#         )
#     except subprocess.TimeoutExpired:
#         return (
#             False,
#             (
#                 "Timed out while running 'git pull'.\n\n"
#                 "This usually means the remote is unreachable or Git is "
#                 "waiting for credentials.\n"
#                 "Please verify your network and stored credentials, then try again."
#             ),
#         )
#     except FileNotFoundError:
#         return False, "Git executable not found. Please install Git and try again."
#     except Exception as exc:
#         return False, "Unexpected error while running git pull: {0}".format(exc)

#     if proc.returncode == 0:
#         return True, (
#             "Library successfully updated from remote.\n\n"
#             "Changes will take effect after restarting KiCad."
#         )

#     stdout = (proc.stdout or "").strip()
#     stderr = (proc.stderr or "").strip()

#     if stderr and stdout:
#         detail = stderr + "\n\n" + stdout
#     else:
#         detail = stderr or stdout or "Unknown git error."

#     msg = (
#         "Failed to pull from remote.\n\n"
#         "Command: {cmd}\n\n"
#         "{detail}"
#     ).format(cmd=" ".join(cmd), detail=detail)

#     return False, msg


# if __name__ == "__main__":
#     # Direct module test harness: run this to see exactly what happens.
#     ok, msg = pull_once()
#     print("success:", ok)
#     print("message:")
#     print(msg)


# # src/KiCadPartsSyncer/infrastructure/git/repo_puller.py

# from __future__ import annotations

# import os
# import subprocess
# from typing import Tuple

# from ..system import config


# GIT_PULL_TIMEOUT_SECONDS = 30  # keep this reasonable so HUD never hangs


# def pull_once() -> Tuple[bool, str]:
#     """
#     Perform a single `git pull --ff-only` on the configured repository.

#     Returns:
#         (success, message)

#     Design:
#       - Uses config.load_settings / get_repository_local_path / get_repository_remote_name.
#       - Disables interactive credential prompts.
#       - Applies a timeout so the HUD cannot get stuck in 'in progress'.
#     """
#     try:
#         settings = config.load_settings()
#     except RuntimeError as exc:
#         return False, str(exc)

#     try:
#         repo_path = config.get_repository_local_path(settings)
#     except RuntimeError as exc:
#         return False, str(exc)

#     remote_name = config.get_repository_remote_name(settings)

#     cmd = [
#         "git",
#         "-C",
#         str(repo_path),
#         "pull",
#         "--ff-only",
#         remote_name,
#     ]

#     # Environment: disable interactive prompts so we fail fast on missing creds.
#     env = os.environ.copy()
#     # If unset, ensure Git does NOT try to open a prompt that will hang.
#     env.setdefault("GIT_TERMINAL_PROMPT", "0")

#     try:
#         proc = subprocess.run(
#             cmd,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True,
#             encoding="utf-8",
#             env=env,
#             timeout=GIT_PULL_TIMEOUT_SECONDS,
#         )
#     except subprocess.TimeoutExpired:
#         return (
#             False,
#             (
#                 "Timed out while running 'git pull'.\n\n"
#                 "This usually means the remote is unreachable or Git is "
#                 "waiting for credentials.\n"
#                 "Please verify your network and stored credentials, then try again."
#             ),
#         )
#     except FileNotFoundError:
#         return False, "Git executable not found. Please install Git and try again."
#     except Exception as exc:
#         return False, "Unexpected error while running git pull: {0}".format(exc)

#     if proc.returncode == 0:
#         return True, (
#             "Library successfully updated from remote.\n\n"
#             "Changes will take effect after restarting KiCad."
#         )

#     stdout = (proc.stdout or "").strip()
#     stderr = (proc.stderr or "").strip()

#     if stderr and stdout:
#         detail = stderr + "\n\n" + stdout
#     else:
#         detail = stderr or stdout or "Unknown git error."

#     msg = (
#         "Failed to pull from remote.\n\n"
#         "Command: {cmd}\n\n"
#         "{detail}"
#     ).format(cmd=" ".join(cmd), detail=detail)

#     return False, msg


# # src/KiCadPartsSyncer/infrastructure/git/repo_puller.py

# from __future__ import annotations

# import subprocess
# from pathlib import Path
# from typing import Tuple

# from ..system import config


# def pull_once() -> Tuple[bool, str]:
#     """
#     Perform a single `git pull --ff-only` on the configured repository.

#     Returns:
#         (success, message)
#     """
#     try:
#         settings = config.load_settings()
#     except RuntimeError as exc:
#         # Config/shape issue: surface directly to the user via dialog.
#         return False, str(exc)

#     try:
#         repo_path = config.get_repository_local_path(settings)
#     except RuntimeError as exc:
#         return False, str(exc)

#     remote_name = config.get_repository_remote_name(settings)

#     # Run git pull with fast-forward only for safety.
#     cmd = [
#         "git",
#         "-C",
#         str(repo_path),
#         "pull",
#         "--ff-only",
#         remote_name,
#     ]

#     try:
#         proc = subprocess.run(
#             cmd,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True,
#             encoding="utf-8",
#         )
#     except FileNotFoundError:
#         return False, "Git executable not found. Please install Git and try again."
#     except Exception as exc:
#         return False, "Unexpected error while running git pull: {0}".format(exc)

#     if proc.returncode == 0:
#         return True, (
#             "Library successfully updated from remote.\n\n"
#             "Changes will take effect after restarting KiCad."
#         )

#     stdout = (proc.stdout or "").strip()
#     stderr = (proc.stderr or "").strip()

#     if stderr and stdout:
#         detail = stderr + "\n\n" + stdout
#     else:
#         detail = stderr or stdout or "Unknown git error."

#     msg = (
#         "Failed to pull from remote.\n\n"
#         "Command: {cmd}\n\n"
#         "{detail}"
#     ).format(cmd=" ".join(cmd), detail=detail)

#     return False, msg
