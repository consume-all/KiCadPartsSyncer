from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse

import git  # type: ignore

from ..system.config import (
    load_settings,
    get_repository_local_path,
    get_repository_remote_name,
    DEFAULT_SETTINGS_PATH,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize_remote_url(base_url: str) -> str:
    """
    Remove any embedded credentials from the given URL when printing.

    Example:
      https://user:pass@github.com/owner/repo.git
      => https://github.com/owner/repo.git
    """
    parsed = urlparse(base_url)

    # If there's no hostname, just return as-is (unlikely but safe)
    if not parsed.hostname:
        return base_url

    # Rebuild netloc without username/password
    host = parsed.hostname
    port = f":{parsed.port}" if parsed.port else ""
    clean_netloc = f"{host}{port}"

    cleaned = parsed._replace(netloc=clean_netloc)
    return urlunparse(cleaned)


def _ahead_behind(repo: git.Repo, local_ref: str, remote_ref: str) -> Tuple[int, int]:
    """
    Return (ahead, behind):

      ahead  = commits local has that remote does not
      behind = commits remote has that local does not
    """
    out = repo.git.rev_list(
        "--left-right",
        "--count",
        "{}...{}".format(local_ref, remote_ref),
    )
    left_str, right_str = out.strip().split()
    ahead = int(left_str)
    behind = int(right_str)
    return ahead, behind


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_remote_status(explicit_repo_path: Optional[Path] = None) -> None:
    """
    Fetch remote updates for the configured repository and report sync status.

    Uses settings.json:
        repository.name
        repository.localPath
        repository.remoteName (preferred) or repository.remote (legacy)

    Auth
    ----
    This function no longer uses any explicit credentials or PATs.
    It relies entirely on the underlying Git/SSH configuration (e.g. your
    SSH key in ~/.ssh and .git/config remote URL like git@github.com:...).

    Emits:
        [Git] ...
        status: clean|ahead|behind|diverged
    """

    # ----- load config -----
    settings = load_settings(DEFAULT_SETTINGS_PATH)

    try:
        repo_cfg = settings["repository"]
        repo_name = repo_cfg["name"]
    except KeyError as exc:
        raise RuntimeError("Missing 'repository.name' in settings.json") from exc

    # ----- repo path -----
    if explicit_repo_path is not None:
        repo_path = explicit_repo_path
    else:
        repo_path = get_repository_local_path(settings)

    repo_path = Path(repo_path)
    if not repo_path.is_dir():
        raise RuntimeError(
            "Configured repository path does not exist or is not a directory: {}".format(
                repo_path
            )
        )

    # ----- open repo -----
    try:
        repo = git.Repo(str(repo_path))
    except Exception as exc:
        raise RuntimeError(
            "Failed to open git repository at '{}'".format(repo_path)
        ) from exc

    if repo.bare:
        raise RuntimeError(
            "Repository at '{}' is bare; expected a working copy.".format(repo_path)
        )

    # Remote name from settings (remoteName / remote / default 'origin')
    remote_name = get_repository_remote_name(settings)

    if remote_name not in [r.name for r in repo.remotes]:
        raise RuntimeError(
            "Remote '{}' not found in repository at '{}'.".format(
                remote_name, repo_path
            )
        )

    remote = repo.remote(remote_name)
    original_url = remote.url
    display_url = _sanitize_remote_url(original_url)

    # ----- detached HEAD handling -----
    # If HEAD is detached, we treat it as "diverged"/non-clean for HUD purposes.
    if getattr(repo, "head", None) is not None and repo.head.is_detached:
        print(
            "[Git] Repository '{}' at '{}' is in a DETACHED HEAD state; "
            "treating as diverged from '{}'.".format(
                repo_name,
                repo_path,
                remote_name,
            )
        )
        print("status: diverged")
        return

    # Determine current branch (now safe: not detached)
    try:
        branch = repo.active_branch.name
    except TypeError as exc:
        # Fallback safety net; should be covered by is_detached above.
        raise RuntimeError(
            "Repository at '{}' is in a detached HEAD state; "
            "cannot determine current branch.".format(repo_path)
        ) from exc

    # ----- fetch using existing Git/SSH credentials -----
    try:
        # Avoid interactive prompts
        with repo.git.custom_environment(GIT_TERMINAL_PROMPT="0"):
            print(
                "[Git] Fetching from {} for repository '{}'".format(
                    display_url,
                    repo_name,
                )
            )
            remote.fetch(prune=True)
    except Exception as exc:
        raise RuntimeError(
            "Failed to fetch from remote '{}': {}".format(display_url, exc)
        ) from exc

    # ----- compare local vs remote -----
    local_ref = "HEAD"
    remote_ref = "{}/{}".format(remote_name, branch)

    # Ensure the remote ref exists after fetch
    try:
        repo.commit(remote_ref)
    except Exception as exc:
        raise RuntimeError(
            "Remote branch '{}' not found after fetch. "
            "Check that the remote has this branch.".format(remote_ref)
        ) from exc

    ahead, behind = _ahead_behind(repo, local_ref, remote_ref)

    if ahead == 0 and behind == 0:
        print(
            "[Git] '{}' at '{}' is up to date with {}.".format(
                repo_name,
                repo_path,
                remote_ref,
            )
        )
        print("status: clean")
    elif ahead > 0 and behind == 0:
        print(
            "[Git] '{}' local repo is AHEAD of {} by {} commit(s). "
            "You may want to push.".format(
                repo_name,
                remote_ref,
                ahead,
            )
        )
        print("status: ahead")
    elif ahead == 0 and behind > 0:
        print(
            "[Git] '{}' local repo is BEHIND {} by {} commit(s). "
            "You may want to pull.".format(
                repo_name,
                remote_ref,
                behind,
            )
        )
        print("status: behind")
    else:
        print(
            "[Git] '{}' local and {} have DIVERGED "
            "(ahead by {}, behind by {}). Manual reconciliation required.".format(
                repo_name,
                remote_ref,
                ahead,
                behind,
            )
        )
        print("status: diverged")


# ---------------------------------------------------------------------------
# Manual probe
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    explicit: Optional[Path] = None
    if len(sys.argv) > 1:
        explicit = Path(sys.argv[1])

    try:
        check_remote_status(explicit)
    except Exception as exc:  # pragma: no cover
        print("[GitRemoteChecker] ERROR:", exc)
        # Non-zero so RepoStatusPoller returns 'unknown' (yellow) on errors.
        sys.exit(1)
