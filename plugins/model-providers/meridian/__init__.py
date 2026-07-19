"""Meridian provider profile — Claude (Max subscription) via the Meridian proxy.

Meridian (https://github.com/rynfar/meridian) bridges the Claude Agent SDK to
the standard Anthropic Messages API, so a Claude Max/Pro subscription can be
used by any Anthropic-compatible client. This profile registers it as a
first-class Hermes provider:

    model:
      provider: meridian
      default: claude-sonnet-4-6
      api_mode: anthropic_messages   # see note below

Endpoint resolution: MERIDIAN_BASE_URL env var, else model.base_url from
config.yaml (when model.provider is meridian), else http://127.0.0.1:3456.

Auth: Meridian only enforces a key when its own MERIDIAN_API_KEY is set on
the proxy side; Hermes' api-key plumbing however requires a non-empty secret,
so always set MERIDIAN_API_KEY in the Hermes environment — to the proxy's
real key, or any placeholder when the proxy runs open.

api_mode note: Hermes' URL auto-detection can't infer the Anthropic Messages
protocol from a bare host:port endpoint (detection keys off api.anthropic.com
or a /anthropic path suffix). This profile declares
api_mode="anthropic_messages", which seeds the setup wizard and model picker,
but runtime resolution for api-key providers only honours the mode written in
config — so keep `api_mode: anthropic_messages` in the model block.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:3456"

# Shown when the live /v1/models fetch fails. Meridian resolves bare aliases
# (sonnet/opus/haiku/fable) itself; [1m] suffix opts into the 1M context
# window where the subscription allows it (opus/fable on Max; sonnet[1m]
# needs Extra Usage and MERIDIAN_SONNET_MODEL=sonnet[1m] on the proxy).
_FALLBACK_MODELS = (
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
    "sonnet",
    "opus",
    "haiku",
    "fable",
    "opus[1m]",
    "fable[1m]",
)


def resolve_meridian_base_url(explicit: str | None = None) -> str:
    """MERIDIAN_BASE_URL env wins, then the caller's URL, then the default."""
    url = (
        os.getenv("MERIDIAN_BASE_URL", "").strip()
        or (explicit or "").strip()
        or DEFAULT_BASE_URL
    )
    return url.rstrip("/")


class MeridianProfile(ProviderProfile):
    """Meridian — Anthropic Messages proxy in front of a Claude subscription."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Meridian's catalog lives at /v1/models (OpenAI list shape).

        The generic implementation would probe {base_url}/models, which
        Meridian 404s, so build the /v1/models URL explicitly. Auth goes in
        x-api-key AND Authorization: Bearer — Meridian accepts either, and
        sending both keeps this working whichever header a future version
        prefers.
        """
        url = resolve_meridian_base_url(base_url or self.base_url) + "/v1/models"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        if api_key:
            req.add_header("x-api-key", api_key)
            req.add_header("Authorization", f"Bearer {api_key}")
        try:
            try:
                from hermes_cli.urllib_security import open_credentialed_url as _open
            except Exception:  # running outside a full Hermes install
                _open = urllib.request.urlopen
            with _open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            items = data if isinstance(data, list) else data.get("data", [])
            models = [m["id"] for m in items if isinstance(m, dict) and "id" in m]
            return models or None
        except Exception as exc:
            logger.debug("fetch_models(meridian): %s", exc)
            return None


meridian = MeridianProfile(
    name="meridian",
    aliases=("claude-max", "meridian-proxy"),
    api_mode="anthropic_messages",
    display_name="Meridian",
    description="Claude Max/Pro subscription via the Meridian proxy (Anthropic Messages API)",
    signup_url="https://github.com/rynfar/meridian",
    env_vars=("MERIDIAN_API_KEY", "MERIDIAN_BASE_URL"),
    base_url=DEFAULT_BASE_URL,
    auth_type="api_key",
    # Anthropic Messages API accepts images in user and tool-result content.
    supports_vision=True,
    default_aux_model="claude-haiku-4-5",
    fallback_models=_FALLBACK_MODELS,
)

register_provider(meridian)
