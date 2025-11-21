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

    Expected (minimal) structure for SSH/system-Git setups:

        {
          "repoPollIntervalSeconds": 60,          # optional
          "repository": {
            "name": "KiCadPartsLibrary",
            "localPath": "C:\\dev\\work\\KiCadPartsLibraries",
            "remoteName": "origin",               # optional, defaults to 'origin'
            "remoteUrl": "https://github.com/..." # optional, metadata only
            // "auth": { ... }                    # optional legacy HTTPS/PAT config
          }
        }

    Notes
    -----
    - 'auth' is now optional and only used by legacy HTTPS/PAT-based flows.
      For SSH-based setups (recommended), 'auth' can be omitted entirely.
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

    This is **legacy** and only meaningful for HTTPS/PAT-based auth flows.
    For SSH/system-Git setups, 'repository.auth' may be omitted entirely.

    Behavior
    --------
    - If 'repository.auth' exists and has 'credential_target' and 'username',
      those values are returned.
    - If it is missing or incomplete, we return sensible defaults:
          target  = "KiCadPartsSyncer:Git"
          username = ""
      so callers that still use this helper won't crash, but the values are
      effectively placeholders.

    Returns
    -------
    (credential_target, username)
    """
    repo_cfg = settings.get("repository") or {}
    auth_cfg = repo_cfg.get("auth") or {}

    target = auth_cfg.get("credential_target", "KiCadPartsSyncer:Git")
    username = auth_cfg.get("username", "")

    # Normalize to strings
    if not isinstance(target, str):
        target = "KiCadPartsSyncer:Git"
    if not isinstance(username, str):
        username = ""

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

    Settings
    --------
    - Preferred key:  repository.remoteName
    - Legacy key:     repository.remote
    - If both are missing/invalid, defaults to 'origin'.
    """
    repo_cfg = settings.get("repository") or {}

    # Preferred new key
    remote = repo_cfg.get("remoteName")
    if isinstance(remote, str):
        remote = remote.strip()
        if remote:
            return remote

    # Legacy fallback: 'remote'
    legacy_remote = repo_cfg.get("remote")
    if isinstance(legacy_remote, str):
        legacy_remote = legacy_remote.strip()
        if legacy_remote:
            return legacy_remote

    # Default
    return "origin"


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
