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
  /meridian [status|quota|models|profiles|refresh|switch <id>]
"""

from __future__ import annotations

import json
import logging

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
    return (
        "Usage: /meridian [status|quota [all]|models|profiles|refresh [profile]|switch <id>]"
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
        description="Meridian Claude proxy: status, quota, profiles, auth refresh.",
    )
