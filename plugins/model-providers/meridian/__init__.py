"""Meridian provider profile — Claude (Max subscription) via the Meridian proxy.

Meridian (https://github.com/rynfar/meridian) bridges the Claude Agent SDK to
the standard Anthropic Messages API, so a Claude Max/Pro subscription can be
used by any Anthropic-compatible client. This profile registers it as a
first-class Hermes provider:

    model:
      provider: meridian
      default: claude-sonnet-4-6

Endpoint resolution: MERIDIAN_BASE_URL env var, else model.base_url from
config.yaml (when model.provider is meridian), else http://127.0.0.1:3456.

Auth: Meridian only enforces a key when its own MERIDIAN_API_KEY is set on
the proxy side; Hermes' api-key plumbing however requires a non-empty secret,
so always set MERIDIAN_API_KEY in the Hermes environment — to the proxy's
real key, or any placeholder when the proxy runs open.

api_mode: this profile also patches Hermes' URL-based api_mode detection so
`api_mode: anthropic_messages` doesn't need to be spelled out in config.yaml.
See _try_apply_api_mode_patch() below for what it does and why it's best-
effort. An explicit `api_mode:` in config.yaml always takes priority over
this patch — set one there if you'd rather not depend on it at all.
"""

from __future__ import annotations

import json
import logging
import os
import threading
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


# ---------------------------------------------------------------------------
# api_mode auto-detection patch
#
# Hermes picks the wire protocol for an api-key provider ("api_mode") from,
# in order: an explicit `model.api_mode` in config.yaml, then a URL-shape
# guess (api.anthropic.com, or a path ending in /anthropic or /anthropic/v1),
# then "chat_completions" by default. A bare host:port like Meridian's never
# matches the URL guess, so without this patch every Meridian request would
# go out over the OpenAI-compatible wire instead of the native Anthropic
# Messages API (Meridian happens to serve both, so it still works — just
# without native prompt-cache stats, thinking blocks, etc.).
#
# This patch wraps the two private functions that make that guess —
# hermes_cli.runtime_provider._detect_api_mode_for_url (session start) and
# hermes_cli.providers.determine_api_mode (mid-session /model switching) —
# so they also recognize Meridian's own endpoint and return
# "anthropic_messages" for it, without touching Hermes' source tree.
#
# Both are undocumented, underscore-prefixed internals with no plugin hook
# and no compatibility guarantee. If a future Hermes release renames,
# removes, or reshapes either one, this patch silently stops helping — it
# is wrapped in its own error handling and can never break a request; the
# worst case is falling back to the pre-patch behavior. Set
# `api_mode: anthropic_messages` explicitly under `model:` in config.yaml at
# any time to sidestep this patch entirely (an explicit value always wins).
#
# Timing: this can't run at plugin-import time. Provider-plugin discovery is
# itself triggered from inside hermes_cli.auth's own module-level bootstrap
# (it extends PROVIDER_REGISTRY by importing every plugins/model-providers/*
# module), so importing hermes_cli.runtime_provider from here at that point
# reliably raises a partial-circular-import ImportError — hermes_cli.auth
# hasn't finished defining its own names yet. Instead, the patch attempt is
# deferred to the first time Hermes actually calls one of this profile's
# request-time hook methods below (get_hostname, prepare_messages,
# build_extra_body, build_api_kwargs_extras, fetch_models, get_max_tokens) —
# by definition these only run once the whole process has finished
# importing, so the circular-import window has already closed. Practical
# effect: the very first request in a freshly started process may go out
# over chat_completions (Meridian's OpenAI-compat endpoint handles it fine)
# while the patch applies; everything after that — same session, same
# process, and every later process — uses anthropic_messages.
# ---------------------------------------------------------------------------

_MAX_PATCH_ATTEMPTS = 5
_patch_lock = threading.Lock()
_patch_state = {"applied": False, "gave_up": False, "attempts": 0, "last_error": ""}


def patch_status() -> dict:
    """Current state of the api_mode auto-detection patch. Read-only
    snapshot for diagnostics (see the meridian_status tool in the
    companion plugins/meridian/ tools plugin)."""
    return dict(_patch_state)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def _meridian_origins() -> set[tuple]:
    """(scheme, hostname, port) tuples this profile's endpoint could mean.

    Scoped to (scheme, host, port) rather than bare hostname so the patch
    can't misfire against some *other* local provider that happens to share
    a hostname like "localhost" or "127.0.0.1" on a different port.
    """
    try:
        from hermes_cli.urllib_security import url_origin
    except Exception:
        from urllib.parse import urlparse

        def url_origin(url):
            p = urlparse(url)
            return (p.scheme or "").lower(), (p.hostname or "").lower(), p.port

    origins = set()
    for url in (os.getenv("MERIDIAN_BASE_URL", "").strip(), DEFAULT_BASE_URL):
        if url:
            try:
                origins.add(url_origin(url))
            except Exception:
                pass
    return origins


def _base_url_is_meridian(base_url) -> bool:
    if not base_url or not isinstance(base_url, str):
        return False
    try:
        from hermes_cli.urllib_security import url_origin
    except Exception:
        from urllib.parse import urlparse

        def url_origin(url):
            p = urlparse(url)
            return (p.scheme or "").lower(), (p.hostname or "").lower(), p.port

    try:
        return url_origin(base_url) in _meridian_origins()
    except Exception:
        return False


def _patch_runtime_provider_detector() -> None:
    """Wrap hermes_cli.runtime_provider._detect_api_mode_for_url."""
    from hermes_cli import runtime_provider as rp

    target = rp._detect_api_mode_for_url
    if getattr(target, "_meridian_wrapped", False):
        return

    def _wrapped(base_url, *args, **kwargs):
        detected = target(base_url, *args, **kwargs)
        if detected:
            return detected
        if _base_url_is_meridian(base_url):
            return "anthropic_messages"
        return detected

    _wrapped._meridian_wrapped = True
    rp._detect_api_mode_for_url = _wrapped


def _patch_model_switch_detector() -> None:
    """Wrap hermes_cli.providers.determine_api_mode (used by /model)."""
    from hermes_cli import providers as hp

    target = hp.determine_api_mode
    if getattr(target, "_meridian_wrapped", False):
        return

    def _wrapped(provider, base_url="", *args, **kwargs):
        detected = target(provider, base_url, *args, **kwargs)
        # determine_api_mode's own fallback for an unknown provider is also
        # "chat_completions" — gating on _base_url_is_meridian keeps this
        # from reinterpreting some other provider's genuine chat_completions
        # result.
        if detected == "chat_completions" and _base_url_is_meridian(base_url):
            return "anthropic_messages"
        return detected

    _wrapped._meridian_wrapped = True
    hp.determine_api_mode = _wrapped


def _try_apply_api_mode_patch() -> None:
    """Best-effort, idempotent, capped-retry patch application.

    Cheap to call on every hook invocation: after the first success or the
    final give-up it's a single dict-lookup and return.
    """
    if _patch_state["applied"] or _patch_state["gave_up"]:
        return
    if _env_flag("MERIDIAN_SKIP_API_MODE_PATCH"):
        _patch_state["gave_up"] = True
        logger.info(
            "meridian: api_mode auto-detection patch skipped "
            "(MERIDIAN_SKIP_API_MODE_PATCH set) — set "
            "`api_mode: anthropic_messages` explicitly under `model:` in "
            "config.yaml."
        )
        return

    with _patch_lock:
        if _patch_state["applied"] or _patch_state["gave_up"]:
            return
        _patch_state["attempts"] += 1
        try:
            _patch_runtime_provider_detector()
            _patch_model_switch_detector()
        except Exception as exc:
            _patch_state["last_error"] = f"{type(exc).__name__}: {exc}"
            if _patch_state["attempts"] >= _MAX_PATCH_ATTEMPTS:
                _patch_state["gave_up"] = True
                logger.warning(
                    "meridian: could not enable automatic api_mode detection "
                    "after %d attempt(s) (%s). Hermes' internal provider-"
                    "resolution code may have changed since this plugin was "
                    "written. Falling back to explicit configuration — set "
                    "`api_mode: anthropic_messages` under `model:` in "
                    "config.yaml to route Meridian traffic correctly.",
                    _patch_state["attempts"], _patch_state["last_error"],
                )
            else:
                logger.debug(
                    "meridian: api_mode patch attempt %d/%d failed, will "
                    "retry on next request (%s)",
                    _patch_state["attempts"], _MAX_PATCH_ATTEMPTS,
                    _patch_state["last_error"],
                )
        else:
            _patch_state["applied"] = True
            logger.info(
                "meridian: automatic api_mode detection enabled "
                "(attempt %d)", _patch_state["attempts"],
            )


class MeridianProfile(ProviderProfile):
    """Meridian — Anthropic Messages proxy in front of a Claude subscription."""

    def patch_status(self) -> dict:
        """Instance-accessible mirror of the module-level patch_status().

        Callers outside this file (the companion tools plugin's
        meridian_status handler) can't rely on this module's import path —
        as a user plugin it loads under a generated name
        (_hermes_user_provider_meridian), not a fixed one — but
        providers.get_provider_profile("meridian") always resolves to this
        same instance, so exposing the diagnostic here works regardless.
        """
        return patch_status()

    def get_hostname(self) -> str:
        _try_apply_api_mode_patch()
        return super().get_hostname()

    def prepare_messages(self, messages):
        _try_apply_api_mode_patch()
        return super().prepare_messages(messages)

    def build_extra_body(self, *, session_id=None, **context):
        _try_apply_api_mode_patch()
        return super().build_extra_body(session_id=session_id, **context)

    def build_api_kwargs_extras(self, *, reasoning_config=None, **context):
        _try_apply_api_mode_patch()
        return super().build_api_kwargs_extras(
            reasoning_config=reasoning_config, **context
        )

    def get_max_tokens(self, model):
        _try_apply_api_mode_patch()
        return super().get_max_tokens(model)

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
        _try_apply_api_mode_patch()
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

# Try once immediately, in case something other than hermes_cli.auth's own
# bootstrap triggered discovery this time (e.g. a REPL, a test harness, or a
# later lazy discovery call after auth.py has already fully imported) — no
# harm if this fails; the hook methods above retry it during real use.
try:
    _try_apply_api_mode_patch()
except Exception:
    pass
