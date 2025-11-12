from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

# Layout:
#   ProjectRoot/
#     src/
#       KiCadPartsSyncer/
#         settings.json        <-- expected here
#         infrastructure/
#           system/
#             config.py        <-- this file

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = _PACKAGE_ROOT / "settings.json"

# Repo poll interval configuration (centralized here)
DEFAULT_REPO_POLL_INTERVAL_SECONDS = 150
MIN_REPO_POLL_INTERVAL_SECONDS = 30


def load_settings(settings_path: Path | None = None) -> Dict[str, Any]:
    """
    Load the KiCadPartsSyncer settings.json.

    Expected (minimal) structure:

        {
          "repository": {
            "name": "KiCadPartsLibrary",
            "localPath": "C:\\dev\\work\\KiCadPartsLibraries",
            "auth": {
              "credential_target": "KiCadPartsSyncer:Git",
              "username": "mnolz"
            }
          }
        }
    """
    path = settings_path or DEFAULT_SETTINGS_PATH

    if not path.is_file():
        raise RuntimeError(
            "KiCadPartsSyncer settings.json not found at: {0}".format(path)
        )

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Invalid JSON in KiCadPartsSyncer settings file: {0}".format(path)
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            "Root of KiCadPartsSyncer settings.json must be an object/dict."
        )

    return data


def get_repository_auth(settings: Dict[str, Any]) -> Tuple[str, str]:
    """
    Extract (credential_target, username) from the loaded settings.

    Returns
    -------
    (credential_target, username)

    Raises RuntimeError if keys are missing or empty.
    """
    try:
        auth_cfg = settings["repository"]["auth"]
        target = auth_cfg["credential_target"]
        username = auth_cfg["username"]
    except KeyError as exc:
        raise RuntimeError(
            "Missing 'repository.auth.credential_target' or "
            "'repository.auth.username' in settings.json"
        ) from exc

    if not target or not username:
        raise RuntimeError(
            "'repository.auth.credential_target' and 'repository.auth.username' "
            "must be non-empty."
        )

    return target, username


def get_repository_local_path(settings: Dict[str, Any]) -> Path:
    """
    Extract the repository.localPath as a Path.

    Supports absolute or relative paths.
    Relative paths are resolved against the project root
    (parent of 'src' that contains KiCadPartsSyncer).
    """
    try:
        path_str = settings["repository"]["localPath"]
    except KeyError as exc:
        raise RuntimeError(
            "Missing 'repository.localPath' in settings.json"
        ) from exc

    if not path_str:
        raise RuntimeError(
            "'repository.localPath' must be a non-empty string."
        )

    path = Path(path_str)

    if path.is_absolute():
        return path

    # Resolve relative to project root:
    # DEFAULT_SETTINGS_PATH -> .../src/KiCadPartsSyncer/settings.json
    # project_root = DEFAULT_SETTINGS_PATH.parent (KiCadPartsSyncer)
    #                                   .parent (src)
    #                                   .parent (ProjectRoot)
    project_root = DEFAULT_SETTINGS_PATH.parent.parent.parent
    return project_root / path


def get_repository_remote_name(settings: Dict[str, Any]) -> str:
    """
    Extract the repository remote name.

    If missing/empty/invalid, defaults to 'origin'.
    """
    repo_cfg = settings.get("repository") or {}
    remote = repo_cfg.get("remote", "origin")

    if not isinstance(remote, str):
        return "origin"

    remote = remote.strip()
    if not remote:
        return "origin"

    return remote


def get_repo_poll_interval_seconds(
    settings: Optional[Dict[str, Any]] = None
) -> int:
    """
    Return normalized poll interval (seconds) for repo status checks.

    Source of truth:
      - Root-level 'repoPollIntervalSeconds' in settings.json.

    Behavior:
      - If settings is None, this will load settings.json.
      - If the key is missing or invalid, falls back to DEFAULT_REPO_POLL_INTERVAL_SECONDS.
      - Enforces MIN_REPO_POLL_INTERVAL_SECONDS as a safety floor.
      - If settings.json is missing/invalid (load_settings raises), falls back
        to defaults instead of propagating, so background pollers can degrade
        gracefully to 'unknown' state handling.
    """
    if settings is None:
        try:
            settings = load_settings()
        except RuntimeError:
            # For things like the repo poller, we don't want to crash the app
            # just because settings.json is missing; they'll treat this as
            # "unknown" status and yellow HUD.
            return DEFAULT_REPO_POLL_INTERVAL_SECONDS

    raw = settings.get(
        "repoPollIntervalSeconds",
        DEFAULT_REPO_POLL_INTERVAL_SECONDS
    )

    try:
        interval = int(raw)
    except (TypeError, ValueError):
        interval = DEFAULT_REPO_POLL_INTERVAL_SECONDS

    if interval < MIN_REPO_POLL_INTERVAL_SECONDS:
        interval = MIN_REPO_POLL_INTERVAL_SECONDS

    return interval
