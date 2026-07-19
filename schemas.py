"""Tool schemas for the meridian plugin — what the LLM sees."""

MERIDIAN_STATUS = {
    "name": "meridian_status",
    "description": (
        "Check the Meridian Claude proxy: whether it is reachable and healthy, "
        "which account is logged in (email, subscription tier), the proxy "
        "version, and its mode. Use this first when Claude requests through "
        "Meridian are failing, or when asked about the proxy's state."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

MERIDIAN_QUOTA = {
    "name": "meridian_quota",
    "description": (
        "Report Claude Max subscription usage through the Meridian proxy: "
        "utilization per rate-limit window (5-hour, 7-day, per-model buckets) "
        "with reset times, plus any extra-usage/overage info. Use this to "
        "check how much subscription quota remains before heavy work, or when "
        "requests start hitting rate limits."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "all_profiles": {
                "type": "boolean",
                "description": (
                    "Set true to report quota for every configured Meridian "
                    "account profile instead of only the active one."
                ),
            },
        },
        "required": [],
    },
}

MERIDIAN_MODELS = {
    "name": "meridian_models",
    "description": (
        "List the Claude models the Meridian proxy currently serves, with "
        "context window sizes. Reflects the logged-in subscription (Max "
        "accounts get 1M-context variants on eligible models)."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

MERIDIAN_PROFILES = {
    "name": "meridian_profiles",
    "description": (
        "List Meridian account profiles (multi-account setups): each "
        "profile's id, login state, email, subscription tier, and which one "
        "is active, plus the routing mode."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

MERIDIAN_SWITCH_PROFILE = {
    "name": "meridian_switch_profile",
    "description": (
        "Switch the Meridian proxy's active account profile (multi-account "
        "setups). Clears the proxy's session and rate-limit caches, so "
        "in-flight conversations restart on the new account. Use "
        "meridian_profiles first to see valid ids."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Profile id to activate (from meridian_profiles).",
            },
        },
        "required": ["profile"],
    },
}

MERIDIAN_REFRESH_AUTH = {
    "name": "meridian_refresh_auth",
    "description": (
        "Force the Meridian proxy to refresh its Claude OAuth token now. "
        "Meridian normally refreshes automatically (~8h expiry); use this "
        "when requests fail with authentication errors. If the refresh "
        "itself fails, someone must run 'claude login' on the proxy host."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": (
                    "Optional profile id to refresh (defaults to the proxy's "
                    "active profile)."
                ),
            },
        },
        "required": [],
    },
}
