# hermes-provider-meridian

[Meridian](https://github.com/rynfar/meridian) as a first-class provider for
[Hermes Agent](https://hermes-agent.nousresearch.com/). Meridian is a proxy
that bridges the Claude Agent SDK to the standard Anthropic Messages API, so
a Claude Max/Pro **subscription** (not API billing) can serve any
Anthropic-compatible client — including Hermes.

Two plugins, no Hermes core changes:

| Plugin | Path | What it does |
|---|---|---|
| `meridian` model-provider profile | `plugins/model-providers/meridian/` | Registers `provider: meridian` — credentials, endpoint, live model catalog, `hermes doctor` probe, model picker, aux-model default |
| `meridian` tools plugin | `plugins/meridian/` | Agent tools + `/meridian` slash command for the proxy's management API: health, Claude Max quota, model list, multi-account profiles, OAuth refresh |

## Why not just a `custom_providers` entry?

A generic custom entry works for basic inference (that's how this setup ran
before this repo existed), but it leaves Hermes blind to everything else
Meridian offers. As a first-class provider you get:

- `--provider meridian`, the `hermes model` picker, and setup-wizard support
- live model catalog from Meridian's `/v1/models` (subscription-aware: Max
  accounts list 1M-context variants) with a curated fallback list
- `hermes doctor` connectivity checks
- auxiliary tasks (vision, compression, summarization, title generation)
  defaulting to `claude-haiku-4-5` without per-block configuration
- the management toolset: the agent can check its own subscription quota
  before burning it, self-heal auth, and switch accounts

## Install

```bash
git clone https://github.com/jdotcole/hermes-provider-meridian.git
cd hermes-provider-meridian
./install.sh            # copies into $HERMES_HOME (default ~/.hermes)
# or: ./install.sh --link   # symlink, so git pull updates the live plugins
```

On the live Hermes server (where `HERMES_HOME=/opt/data`):

```bash
HERMES_HOME=/opt/data ./install.sh --link
```

Then:

```bash
hermes plugins enable meridian    # the tools plugin is opt-in
hermes doctor                     # verify the provider probe passes
```

The model-provider profile needs no enabling — anything under
`$HERMES_HOME/plugins/model-providers/` is auto-discovered.

### Deploying via hermes-agent-config

This repo is listed in `repositories/manifest.txt` of `hermes-agent-config`,
so the `hermes-config-sync` cron job clones it to
`/opt/data/home/repositories/hermes-provider-meridian` on the live server.
The clone alone doesn't activate anything — run the install step once from
there:

```bash
HERMES_HOME=/opt/data /opt/data/home/repositories/hermes-provider-meridian/install.sh --link
```

With `--link`, subsequent `git pull`s in that clone update the live plugins
in place.

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
  api_mode: anthropic_messages   # required — see below
  # base_url: http://10.0.1.10:3456   # alternative to MERIDIAN_BASE_URL

plugins:
  enabled:
    - meridian
```

**`MERIDIAN_API_KEY`**: Meridian only enforces auth when the *proxy* has
`MERIDIAN_API_KEY` set on its side (it then accepts the key via `x-api-key`
or `Authorization: Bearer`). Hermes, however, refuses to run an api-key
provider with an empty secret — so always set the variable: to the proxy's
real key, or to any placeholder when the proxy runs open.

**`api_mode: anthropic_messages` is required** in the model block. Hermes
auto-detects the Anthropic wire protocol only from URL shape
(`api.anthropic.com` or a `/anthropic` path suffix); a bare `host:3456`
endpoint would otherwise default to `chat_completions`. Meridian *does*
expose an OpenAI-compatible `/v1/chat/completions`, but the native Messages
route is the first-class path (prompt caching stats, thinking blocks,
fine-grained tool streaming).

### Choosing models

Meridian accepts:

- **Versioned ids** — `claude-sonnet-4-6`, `claude-opus-4-8`,
  `claude-haiku-4-5`, `claude-fable-5`, … (pinned exactly as requested)
- **Bare aliases** — `sonnet`, `opus`, `haiku`, `fable` (proxy-canonical pin)
- **1M-context variants** — `opus[1m]`, `fable[1m]` (included with Max;
  auto-downgraded where unavailable). `sonnet[1m]` additionally requires
  Extra Usage and `MERIDIAN_SONNET_MODEL=sonnet[1m]` on the proxy.

Reasoning effort flows through: Hermes' `agent.reasoning_effort` /
Anthropic `thinking` parameters are honored by Meridian and mapped onto the
Claude Agent SDK's extended-thinking controls.

### Existing `custom:meridian` setups

A legacy `custom_providers` entry named `meridian` keeps working — explicit
`provider: custom:meridian` references still resolve to it. Once this plugin
is installed, plain `provider: meridian` resolves to the first-class profile
(built-in providers win over same-named custom entries). Migrate the model
block and any `auxiliary.*.provider` entries at your leisure; per-block
`model:` values can then be dropped wherever `claude-haiku-4-5` is the
desired aux model.

## The management toolset

Once the `meridian` plugin is enabled the agent gains toolset `meridian`:

| Tool | Proxy endpoint | Use |
|---|---|---|
| `meridian_status` | `GET /health` | reachability, version, logged-in account + subscription tier, passthrough/internal mode |
| `meridian_quota` | `GET /v1/usage/quota[/all]` | Claude Max rate-limit windows (5-hour, 7-day, per-model) with utilization % and reset times; `all_profiles` covers every account |
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

- **Quota-aware scheduling** — cron jobs can call `meridian_quota` and defer
  heavy batch work when the 5-hour window is nearly exhausted.
- **Auth self-healing** — on 401s, the agent calls `meridian_refresh_auth`
  instead of paging a human (Meridian refreshes ~8-hourly on its own; this
  covers the edge cases).
- **Multi-account rotation** — with several Max accounts configured as
  Meridian profiles, `meridian_switch_profile` moves the whole agent to a
  fresh quota pool. (Meridian's own `MERIDIAN_ROUTING=sticky` mode can also
  spread concurrent sessions across accounts transparently.)

## Meridian features exposed elsewhere

Not everything needs plugin code — these work out of the box once inference
routes through the proxy:

- **Streaming** — full SSE on `/v1/messages`; Hermes streaming works as with
  native Anthropic.
- **Prompt caching** — cache read/write token counts flow back in `usage`
  and show up in Hermes' cache stats.
- **Vision / multimodal** — image blocks in user and tool-result messages.
- **Beta headers** — Hermes' standard `anthropic-beta` headers pass through;
  Meridian's default `allow-safe` policy strips only betas that would
  trigger Extra-Usage billing on subscriptions.
- **Telemetry dashboard** — browse `http://<proxy>/telemetry` (token usage,
  cache metrics, cost estimates) and `/metrics` for Prometheus scraping.

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

Built against hermes-agent's plugin contracts as of 2026-07 (`ProviderProfile`
in `providers/base.py`, `PluginContext.register_tool`/`register_command`) and
Meridian's HTTP API as of v1.x (routes verified against source: `/health`,
`/v1/models`, `/v1/usage/quota`, `/v1/usage/quota/all`, `/profiles/list`,
`/profiles/active`, `/auth/refresh`). Both surfaces are additive-friendly;
pin versions if you need stability.
