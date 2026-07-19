"""Tool handlers for the meridian plugin.

All handlers talk plain HTTP to the Meridian proxy resolved from
MERIDIAN_BASE_URL (default http://127.0.0.1:3456), authenticating with
MERIDIAN_API_KEY when set. Every handler returns a JSON string and never
raises — errors come back as {"error": ...} so the tool loop stays healthy
even when the proxy is down.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:3456"
_TIMEOUT = 15.0


def base_url() -> str:
    return (os.getenv("MERIDIAN_BASE_URL", "").strip() or DEFAULT_BASE_URL).rstrip("/")


def _request(
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    """Return (status, parsed-json-or-text). Raises only urllib/network errors."""
    url = base_url() + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    api_key = os.getenv("MERIDIAN_API_KEY", "").strip()
    if api_key:
        req.add_header("x-api-key", api_key)
    for k, v in (headers or {}).items():
        req.add_header(k, v)

    try:
        from hermes_cli.urllib_security import open_credentialed_url as _open
    except Exception:  # standalone / test context
        _open = urllib.request.urlopen

    try:
        with _open(req, timeout=_TIMEOUT) as resp:
            raw = resp.read().decode()
            status = resp.status
    except urllib.error.HTTPError as exc:  # non-2xx still carries a JSON body
        raw = exc.read().decode(errors="replace")
        status = exc.code
    try:
        return status, json.loads(raw)
    except Exception:
        return status, raw


def _error_result(exc: Exception) -> str:
    return json.dumps(
        {
            "error": f"Meridian proxy unreachable at {base_url()}: {exc}",
            "hint": (
                "Check that meridian is running (npx @rynfar/meridian or the "
                "service unit) and that MERIDIAN_BASE_URL points at it."
            ),
        }
    )


def _iso(epoch_ms: Any) -> Any:
    """Epoch-milliseconds → ISO-8601 UTC string (passthrough on bad input)."""
    try:
        return (
            datetime.fromtimestamp(float(epoch_ms) / 1000.0, tz=timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )
    except Exception:
        return epoch_ms


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def meridian_status(args: dict, **kwargs) -> str:
    try:
        status, health = _request("/health")
    except Exception as exc:
        return _error_result(exc)
    if not isinstance(health, dict):
        return json.dumps({"error": f"Unexpected /health response ({status}): {health!r}"})
    result = {
        "base_url": base_url(),
        "status": health.get("status"),
        "version": health.get("version"),
        "mode": health.get("mode"),
        "auth": health.get("auth"),
    }
    if health.get("error"):
        result["error"] = health["error"]
        if health.get("status") == "unhealthy":
            result["hint"] = (
                "The proxy has no valid Claude login. Try meridian_refresh_auth; "
                "if that fails, run 'claude login' on the proxy host."
            )

    # Surface whether the sibling model-provider plugin's api_mode
    # auto-detection patch is active — see plugins/model-providers/meridian/
    # for what this does and why it can be off (opted out, still deferred,
    # or gave up after Hermes internals changed underneath it). Looked up via
    # the provider registry rather than a direct module import: as a user
    # plugin, that module loads under a generated name
    # (_hermes_user_provider_meridian), not a fixed one.
    try:
        from providers import get_provider_profile

        profile = get_provider_profile("meridian")
        if profile is not None and hasattr(profile, "patch_status"):
            result["api_mode_patch"] = profile.patch_status()
    except Exception:
        pass

    return json.dumps(result)


def _format_quota_windows(windows: list) -> list:
    out = []
    for w in windows or []:
        if not isinstance(w, dict):
            continue
        entry = dict(w)
        util = entry.get("utilization")
        if isinstance(util, (int, float)) and util <= 1.0:
            entry["utilization_pct"] = round(util * 100, 1)
        if entry.get("resetsAt"):
            entry["resetsAt"] = _iso(entry["resetsAt"])
        out.append(entry)
    return out


def meridian_quota(args: dict, **kwargs) -> str:
    all_profiles = bool(args.get("all_profiles"))
    path = "/v1/usage/quota/all" if all_profiles else "/v1/usage/quota"
    try:
        status, data = _request(path)
    except Exception as exc:
        return _error_result(exc)
    if status != 200 or not isinstance(data, dict):
        return json.dumps({"error": f"Quota fetch failed ({status}): {data!r}"})

    if all_profiles:
        for p in data.get("profiles", []):
            if isinstance(p, dict):
                p["windows"] = _format_quota_windows(p.get("windows", []))
        if data.get("asOf"):
            data["asOf"] = _iso(data["asOf"])
        return json.dumps(data)

    # Single-profile shape: buckets keyed by rate-limit window
    for key in ("buckets", "windows"):
        if isinstance(data.get(key), list):
            data[key] = _format_quota_windows(data[key])
    if not any(data.get(k) for k in ("buckets", "windows")):
        data.setdefault(
            "note",
            "No quota data observed yet — the proxy reports usage after its "
            "first SDK call since startup.",
        )
    return json.dumps(data)


def meridian_models(args: dict, **kwargs) -> str:
    try:
        status, data = _request("/v1/models")
    except Exception as exc:
        return _error_result(exc)
    if status != 200 or not isinstance(data, dict):
        return json.dumps({"error": f"Model list failed ({status}): {data!r}"})
    models = [
        {
            "id": m.get("id"),
            "display_name": m.get("display_name"),
            "context_window": m.get("context_window"),
        }
        for m in data.get("data", [])
        if isinstance(m, dict)
    ]
    return json.dumps(
        {
            "models": models,
            "note": (
                "Bare aliases (sonnet, opus, haiku, fable) and [1m] context "
                "variants (e.g. opus[1m]) are also accepted as model ids."
            ),
        }
    )


def meridian_profiles(args: dict, **kwargs) -> str:
    try:
        status, data = _request("/profiles/list")
    except Exception as exc:
        return _error_result(exc)
    if status != 200 or not isinstance(data, dict):
        return json.dumps({"error": f"Profile list failed ({status}): {data!r}"})
    for p in data.get("profiles", []):
        if isinstance(p, dict):
            for key in ("lastCheckedAt", "lastSuccessAt"):
                if p.get(key):
                    p[key] = _iso(p[key])
    return json.dumps(data)


def meridian_switch_profile(args: dict, **kwargs) -> str:
    profile = str(args.get("profile") or "").strip()
    if not profile:
        return json.dumps({"error": "Missing required 'profile' argument."})
    try:
        status, data = _request(
            "/profiles/active", method="POST", body={"profile": profile}
        )
    except Exception as exc:
        return _error_result(exc)
    if status != 200:
        return json.dumps({"error": f"Profile switch failed ({status}): {data!r}"})
    if isinstance(data, dict):
        data.setdefault(
            "note",
            "Proxy session and rate-limit caches were cleared; the next "
            "request starts fresh on the new account.",
        )
    return json.dumps(data)


def meridian_refresh_auth(args: dict, **kwargs) -> str:
    profile = str(args.get("profile") or "").strip()
    headers = {"x-meridian-profile": profile} if profile else None
    try:
        status, data = _request("/auth/refresh", method="POST", headers=headers)
    except Exception as exc:
        return _error_result(exc)
    if isinstance(data, dict):
        if status != 200 or not data.get("success"):
            data.setdefault(
                "hint",
                "If refresh keeps failing, run 'claude login' on the proxy host.",
            )
        return json.dumps(data)
    return json.dumps({"error": f"Auth refresh failed ({status}): {data!r}"})
