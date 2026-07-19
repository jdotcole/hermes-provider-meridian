"""Self-install helper for the meridian model-provider profile.

Hermes' dashboard "install by URL" flow (and `hermes plugins install`) always
drops a freshly-cloned plugin flat under `$HERMES_HOME/plugins/<name>/` — but
a model-provider profile is only ever discovered from the fixed path
`$HERMES_HOME/plugins/model-providers/<name>/` (see hermes-agent's
`providers/__init__.py._discover_providers()`). That mismatch means the
provider half of this repo can never be installed through the normal
dashboard flow, no matter what URL or subdirectory you point it at.

This module does the same copy `install.sh` does, but callable from inside
a running Hermes process — via `/meridian install-provider` (slash command)
or `hermes meridian install-provider` (CLI) — so no shell/SSH access to the
Hermes host is required once the tools plugin itself is installed and
enabled through the normal dashboard flow.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_REPO_URL = "https://github.com/jdotcole/hermes-provider-meridian.git"
PROVIDER_SUBDIR = "plugins/model-providers/meridian"
_CLONE_TIMEOUT_SECONDS = 60


def repo_url() -> str:
    """MERIDIAN_PLUGIN_REPO_URL env wins — set this if you're running a
    fork or a self-hosted mirror of this repo."""
    return os.getenv("MERIDIAN_PLUGIN_REPO_URL", "").strip() or DEFAULT_REPO_URL


def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return get_hermes_home()
    except Exception:
        return Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes")))


def target_dir() -> Path:
    return _hermes_home() / "plugins" / "model-providers" / "meridian"


def install_provider(force: bool = False) -> str:
    """Clone the meridian plugin repo and copy the provider profile into
    place. Returns a human-readable status report; never raises."""
    target = target_dir()

    if target.exists() and not force:
        return (
            f"Already installed at {target}.\n"
            "Run `/meridian install-provider force` (or "
            "`hermes meridian install-provider --force`) to reinstall."
        )

    git_exe = shutil.which("git")
    if not git_exe:
        return "Error: git is not installed or not in PATH on this host."

    url = repo_url()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            clone_dir = Path(tmp) / "repo"
            try:
                result = subprocess.run(
                    [git_exe, "clone", "--depth", "1", url, str(clone_dir)],
                    capture_output=True,
                    text=True,
                    timeout=_CLONE_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return (
                    f"Error: git clone of {url} timed out after "
                    f"{_CLONE_TIMEOUT_SECONDS}s."
                )

            if result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                return f"Error: git clone of {url} failed:\n{err}"

            source = clone_dir / PROVIDER_SUBDIR
            if not source.is_dir():
                return (
                    f"Error: '{PROVIDER_SUBDIR}' not found in {url} — the "
                    "repo layout may have changed since this plugin was "
                    "written. Check the repo directly and file an issue."
                )

            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
    except OSError as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    return (
        f"Installed the provider profile to {target}.\n"
        "Restart Hermes (or start a fresh session) for `provider: meridian` "
        "to become available — provider discovery runs once per process, "
        "the first time anything asks for a provider profile."
    )
