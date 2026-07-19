"""meridian plugin — Meridian Claude-proxy management tools for Hermes.

Companion to the ``meridian`` model-provider profile (which routes Hermes
inference through the proxy). This plugin exposes Meridian's management
surface to the agent and to humans:

Tools (toolset ``meridian``):
  - meridian_status          proxy health, version, logged-in account
  - meridian_quota           Claude Max rate-limit windows / utilization
  - meridian_models          served models + context windows
  - meridian_profiles        multi-account profile list
  - meridian_switch_profile  activate a different account profile
  - meridian_refresh_auth    force an OAuth token refresh

Slash command:
  /meridian [status|quota|models|profiles|refresh|switch <id>|install-provider]

CLI:
  hermes meridian install-provider [--force]

`install-provider` is deliberately human/CLI-only, not an agent-callable
tool — see install_provider.py for why it exists (Hermes' plugin installer
can't place a model-provider profile at its required fixed path) and why
letting the agent trigger it autonomously would be the wrong default.
"""

from __future__ import annotations

import json
import logging

from . import cli as _cli
from . import install_provider as _install_provider
from . import schemas, tools

logger = logging.getLogger(__name__)

_TOOLSET = "meridian"


def _fmt(raw: str) -> str:
    """Pretty-print a handler's JSON string for human slash-command output."""
    try:
        return json.dumps(json.loads(raw), indent=2)
    except Exception:
        return raw


def _handle_slash(raw_args: str) -> str:
    parts = (raw_args or "").split()
    sub = parts[0].lower() if parts else "status"

    if sub == "status":
        return _fmt(tools.meridian_status({}))
    if sub == "quota":
        return _fmt(tools.meridian_quota({"all_profiles": "all" in parts[1:]}))
    if sub == "models":
        return _fmt(tools.meridian_models({}))
    if sub == "profiles":
        return _fmt(tools.meridian_profiles({}))
    if sub == "refresh":
        return _fmt(tools.meridian_refresh_auth({"profile": " ".join(parts[1:])}))
    if sub == "switch":
        if len(parts) < 2:
            return "Usage: /meridian switch <profile-id>"
        return _fmt(tools.meridian_switch_profile({"profile": parts[1]}))
    if sub == "install-provider":
        return _install_provider.install_provider(force="force" in parts[1:])
    return (
        "Usage: /meridian [status|quota [all]|models|profiles|refresh [profile]|"
        "switch <id>|install-provider [force]]"
    )


def register(ctx) -> None:
    ctx.register_tool(
        name="meridian_status",
        toolset=_TOOLSET,
        schema=schemas.MERIDIAN_STATUS,
        handler=tools.meridian_status,
    )
    ctx.register_tool(
        name="meridian_quota",
        toolset=_TOOLSET,
        schema=schemas.MERIDIAN_QUOTA,
        handler=tools.meridian_quota,
    )
    ctx.register_tool(
        name="meridian_models",
        toolset=_TOOLSET,
        schema=schemas.MERIDIAN_MODELS,
        handler=tools.meridian_models,
    )
    ctx.register_tool(
        name="meridian_profiles",
        toolset=_TOOLSET,
        schema=schemas.MERIDIAN_PROFILES,
        handler=tools.meridian_profiles,
    )
    ctx.register_tool(
        name="meridian_switch_profile",
        toolset=_TOOLSET,
        schema=schemas.MERIDIAN_SWITCH_PROFILE,
        handler=tools.meridian_switch_profile,
    )
    ctx.register_tool(
        name="meridian_refresh_auth",
        toolset=_TOOLSET,
        schema=schemas.MERIDIAN_REFRESH_AUTH,
        handler=tools.meridian_refresh_auth,
    )
    ctx.register_command(
        "meridian",
        handler=_handle_slash,
        description="Meridian Claude proxy: status, quota, profiles, auth refresh, install-provider.",
    )
    ctx.register_cli_command(
        name="meridian",
        help="Meridian plugin utilities",
        setup_fn=_cli.register_cli,
        handler_fn=_cli.meridian_command,
        description=(
            "Install the meridian model-provider profile "
            "($HERMES_HOME/plugins/model-providers/meridian/) without shell "
            "or SSH access to the Hermes host."
        ),
    )
