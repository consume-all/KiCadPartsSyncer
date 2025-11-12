from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import keyring
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency: 'keyring'. Install it with:\n"
        "    pip install keyring"
    ) from exc

from .config import load_settings, get_repository_auth, DEFAULT_SETTINGS_PATH


def get_secret(target: str, username: str) -> Optional[str]:
    """
    Read a secret from the OS keyring / Windows Credential Manager.

    Parameters
    ----------
    target:
        The 'Internet or network address' / service name in Credential Manager.
    username:
        The 'User name' stored with that credential.

    Returns
    -------
    str | None
        The password/token if found, otherwise None.
    """
    if not target or not username:
        raise ValueError("Both 'target' and 'username' must be non-empty strings.")

    return keyring.get_password(target, username)


def get_auth_secret_from_config(
    config_path: Path = DEFAULT_SETTINGS_PATH,
) -> Optional[str]:
    """
    Look up the repository auth secret using settings.json.

    Uses:
        settings.json -> repository.auth.{credential_target, username}

    Returns
    -------
    str | None
        The resolved secret if present in the keyring; otherwise None.
    """
    settings = load_settings(config_path)
    target, username = get_repository_auth(settings)
    return get_secret(target, username)


if __name__ == "__main__":
    """
    Manual probe:

    1. Ensure src/KiCadPartsSyncer/settings.json contains:

       {
         "repository": {
           "name": "KiCadPartsLibrary",
           "auth": {
             "credential_target": "KiCadPartsSyncer:Git",
             "username": "mnolz"
           }
         }
       }

    2. In Windows Credential Manager → Windows Credentials → Generic Credentials, create:

       - Internet or network address: KiCadPartsSyncer:Git
       - User name: mnolz
       - Password:  <your token>

    3. From project root:

         cd src
         python -m KiCadPartsSyncer.infrastructure.system.credentials

    It will print what it finds.
    """

    try:
        secret = get_auth_secret_from_config()
    except Exception as exc:  # pragma: no cover
        print("[CredentialProbe] ERROR:", exc)
    else:
        if secret is None:
            print(
                "[CredentialProbe] No credential found for configured "
                "'repository.auth.credential_target' and 'username'."
            )
        else:
            print("[CredentialProbe] Retrieved credential:")
            print(secret)
