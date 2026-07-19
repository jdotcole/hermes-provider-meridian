# hermes-provider-meridian

[Meridian](https://github.com/rynfar/meridian) as a first-class provider for
[Hermes Agent](https://hermes-agent.nousresearch.com/). Meridian is a local
proxy that bridges the Claude Agent SDK to the standard Anthropic Messages
API, so a Claude subscription can serve any Anthropic-compatible client —
including Hermes.

Two plugins, no Hermes core changes:

| Plugin | Path | What it does |
|---|---|---|
| `meridian` model-provider profile | `plugins/model-providers/meridian/` | Registers `provider: meridian` — credentials, endpoint, live model catalog, `hermes doctor` probe, model picker, aux-model default, best-effort `api_mode` auto-detection |
| `meridian` tools plugin | `plugins/meridian/` | Agent tools + `/meridian` slash command for the proxy's management API: health, quota, model list, multi-account profiles, OAuth refresh |

## Disclaimer

This project is provided for **educational and research purposes**. It is an
independent, unofficial integration and is **not affiliated with, endorsed
by, or supported by Anthropic** or the Meridian project. "Claude" and
"Anthropic" are trademarks of Anthropic, PBC.

Meridian routes requests through a Claude subscription rather than metered
API billing. Whether that is appropriate for your use case depends on the
terms you agreed to when you subscribed — consumer subscription terms and
API terms are not the same thing, and automated/agentic use may be treated
differently than interactive use under either. **You are solely responsible
for reading and complying with [Anthropic's Usage
Policy](https://www.anthropic.com/legal/aup), Anthropic's consumer and
commercial terms of service (whichever apply to your account), and
Meridian's own license and documentation**, and for any consequences of
using this software, including rate limiting, quota exhaustion, or account
action by Anthropic. Use at your own risk. This software is provided "as
is", without warranty of any kind — see [LICENSE](LICENSE).

## Why not just a `custom_providers` entry?

A generic custom entry works for basic inference, but it leaves Hermes blind
to everything else Meridian offers. As a first-class provider you get:

- `--provider meridian`, the `hermes model` picker, and setup-wizard support
- live model catalog from Meridian's `/v1/models` (subscription-aware: Max
  accounts list 1M-context variants) with a curated fallback list
- `hermes doctor` connectivity checks
- auxiliary tasks (vision, compression, summarization, title generation)
  defaulting to `claude-haiku-4-5` without per-block configuration
- the management toolset: the agent can check its own subscription quota
  before burning it, self-heal auth, and switch accounts
- one fewer line of config — see "api_mode auto-detection" below

## Install

```bash
git clone https://github.com/jdotcole/hermes-provider-meridian.git
cd hermes-provider-meridian
./install.sh            # copies into $HERMES_HOME (default ~/.hermes)
# or: ./install.sh --link   # symlink, so git pull updates the live plugins
```

Then:

```bash
hermes plugins enable meridian    # the tools plugin is opt-in
hermes doctor                     # verify the provider probe passes
```

The model-provider profile needs no enabling — anything under
`$HERMES_HOME/plugins/model-providers/` is auto-discovered.

## Configuration

```bash
# $HERMES_HOME/.env
MERIDIAN_API_KEY=...                      # see note below
MERIDIAN_BASE_URL=http://127.0.0.1:3456   # wherever meridian listens
```

```yaml
# config.yaml
model:
  provider: meridian
  default: claude-sonnet-4-6
  # base_url: http://meridian-host:3456   # alternative to MERIDIAN_BASE_URL

plugins:
  enabled:
    - meridian
```

**`MERIDIAN_API_KEY`**: Meridian only enforces auth when the *proxy* has
`MERIDIAN_API_KEY` set on its side (it then accepts the key via `x-api-key`
or `Authorization: Bearer`). Hermes, however, refuses to run an api-key
provider with an empty secret — so always set the variable: to the proxy's
real key, or to any placeholder when the proxy runs open.

### `api_mode` auto-detection

Hermes needs to know Meridian speaks the native Anthropic Messages protocol
(`api_mode: anthropic_messages`), not the default OpenAI-compatible
`chat_completions`. Hermes only infers this from URL shape
(`api.anthropic.com`, or a path ending in `/anthropic`), which a bare
`host:port` endpoint never matches — so normally you'd have to set
`api_mode: anthropic_messages` explicitly in the `model:` block.

This plugin instead patches Hermes' internal URL-detection so it also
recognizes Meridian's configured endpoint, meaning `api_mode` usually
doesn't need to be set at all. Worth understanding what that means in
practice:

- **What it targets**: two private, underscore-prefixed functions inside
  Hermes (`hermes_cli.runtime_provider._detect_api_mode_for_url` and
  `hermes_cli.providers.determine_api_mode`) — there is no supported plugin
  hook for this, so the plugin wraps them directly at runtime. Nothing in
  Hermes' source tree is modified.
- **Scoped to Meridian's own endpoint**: the patch only ever overrides the
  result for requests whose host/port match your configured
  `MERIDIAN_BASE_URL` (or the default `127.0.0.1:3456`). It cannot affect
  any other provider you have configured.
- **Applied lazily, not at plugin load**: attempting this at plugin-import
  time reliably fails with a circular-import error, because Hermes' own
  provider-discovery is triggered from the middle of a module (`hermes_cli
  .auth`) that hasn't finished defining its own names yet. The patch is
  deferred to the first time Hermes actually calls one of this provider's
  request-time hooks — which, by construction, only happens after the whole
  process has finished starting up. Practical effect: the very first
  request in a freshly started process may go out over the
  OpenAI-compatible wire (Meridian handles that fine too) while the patch
  applies; every request after that — same session, same process, and every
  later process — uses the native Anthropic Messages API.
- **Fails safe, with logging, if Hermes changes underneath it**: because
  this reaches into undocumented internals with no compatibility guarantee,
  a future Hermes release could rename, remove, or restructure either
  function. The patch retries a handful of times, then gives up
  permanently and logs one clear warning telling you to set
  `api_mode: anthropic_messages` explicitly — it never spams the log on
  every request, and a failed patch never breaks a request; it only means
  you fall back to the OpenAI-compatible wire (or need the explicit config
  line for the native one).
- **An explicit `model.api_mode` in config.yaml always wins** over this
  patch, so setting it yourself is a fully supported way to bypass this
  behavior entirely if you'd rather not depend on it.
- **Opt out entirely**: set `MERIDIAN_SKIP_API_MODE_PATCH=1` to disable the
  patch attempt outright (then set `api_mode: anthropic_messages` yourself).
- **Check whether it's active**: the `meridian_status` tool / `/meridian`
  slash command includes an `api_mode_patch` field (`applied` /
  `gave_up` / `attempts` / `last_error`).

### Choosing models

Meridian accepts:

- **Versioned ids** — `claude-sonnet-4-6`, `claude-opus-4-8`,
  `claude-haiku-4-5`, `claude-fable-5`, … (pinned exactly as requested)
- **Bare aliases** — `sonnet`, `opus`, `haiku`, `fable` (proxy-canonical pin)
- **1M-context variants** — `opus[1m]`, `fable[1m]` (subscription-dependent
  availability; check your plan and Meridian's own docs/config for exact
  behavior, including any additional-usage implications)

Reasoning effort flows through: Hermes' `agent.reasoning_effort` /
Anthropic `thinking` parameters are honored by Meridian and mapped onto the
Claude Agent SDK's extended-thinking controls.

### Existing `custom_providers` setups

A legacy `custom_providers` entry named `meridian` keeps working — explicit
`provider: custom:meridian` references still resolve to it. Once this
plugin is installed, plain `provider: meridian` resolves to the
first-class profile (built-in providers win over same-named custom
entries). Migrate the model block and any `auxiliary.*.provider` entries at
your leisure; per-block `model:` values can then be dropped wherever
`claude-haiku-4-5` is the desired aux model.

## The management toolset

Once the `meridian` plugin is enabled the agent gains toolset `meridian`:

| Tool | Proxy endpoint | Use |
|---|---|---|
| `meridian_status` | `GET /health` | reachability, version, logged-in account + subscription tier, passthrough/internal mode, `api_mode` patch diagnostics |
| `meridian_quota` | `GET /v1/usage/quota[/all]` | rate-limit windows (5-hour, 7-day, per-model) with utilization % and reset times; `all_profiles` covers every account |
| `meridian_models` | `GET /v1/models` | served models + context windows (subscription-aware) |
| `meridian_profiles` | `GET /profiles/list` | multi-account profiles, active one, routing mode |
| `meridian_switch_profile` | `POST /profiles/active` | activate another account (clears proxy session + rate-limit caches) |
| `meridian_refresh_auth` | `POST /auth/refresh` | force an OAuth token refresh when requests 401 |

Humans get the same via `/meridian`:

```
/meridian                 # status
/meridian quota [all]
/meridian models
/meridian profiles
/meridian refresh [profile]
/meridian switch <profile-id>
```

Practical patterns this enables:

- **Quota-aware scheduling** — a scheduled job can call `meridian_quota` and
  defer heavy batch work when a rate-limit window is nearly exhausted.
- **Auth self-healing** — on 401s, the agent can call
  `meridian_refresh_auth` instead of requiring a human to intervene
  (Meridian refreshes on its own periodically; this covers the edge cases).
- **Multi-account rotation** — with several accounts configured as Meridian
  profiles, `meridian_switch_profile` moves the whole agent to a different
  quota pool. (Meridian's own sticky-routing mode can also spread
  concurrent sessions across accounts transparently — see Meridian's docs.)

## Meridian features exposed elsewhere

Not everything needs plugin code — these work out of the box once inference
routes through the proxy:

- **Streaming** — full SSE on `/v1/messages`; Hermes streaming works as with
  native Anthropic.
- **Prompt caching** — cache read/write token counts flow back in `usage`
  and show up in Hermes' cache stats.
- **Vision / multimodal** — image blocks in user and tool-result messages.
- **Beta headers** — Hermes' standard `anthropic-beta` headers pass through;
  check Meridian's own documentation for its current beta-header policy.
- **Telemetry dashboard** — Meridian exposes its own `/telemetry` (token
  usage, cache metrics, cost estimates) and `/metrics` (Prometheus) — browse
  or scrape it directly against your proxy instance.

Not currently wired (would need Hermes-core support for per-provider extra
headers on the Anthropic transport): tagging requests with
`x-meridian-source` / per-request `x-meridian-profile` routing.

## Repo layout

```
plugins/
├── model-providers/meridian/   # ProviderProfile plugin (auto-discovered)
│   ├── __init__.py
│   ├── plugin.yaml
│   └── README.md
└── meridian/                   # general plugin: tools + /meridian command
    ├── __init__.py
    ├── plugin.yaml
    ├── schemas.py
    └── tools.py
install.sh                      # copy/symlink into $HERMES_HOME
```

## Compatibility

Built against hermes-agent's plugin contracts and Meridian's HTTP API as of
2026-07. Both projects move independently of this repo; if something stops
working after upgrading either one, check the Compatibility notes above
first (especially the `api_mode` patch, which depends on undocumented
Hermes internals) before filing an issue.

## Contributing

Issues and PRs welcome. This is a community integration, not an official
product of either upstream project.
