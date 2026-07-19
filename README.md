# hermes-provider-meridian

[Meridian](https://github.com/rynfar/meridian) as a first-class provider for
[Hermes Agent](https://hermes-agent.nousresearch.com/). Meridian is a local
proxy that bridges the Claude Agent SDK to the standard Anthropic Messages
API, so a Claude subscription can serve any Anthropic-compatible client —
including Hermes.

This repo *is* the tools plugin (its `plugin.yaml` and `__init__.py` sit
right here at the root) — install this repo directly and you get the
`/meridian` slash command + agent tools. The
[model-provider profile](provider/README.md) lives in `provider/` and is
installed separately; see below.

## Disclaimer

Educational/research project, **not affiliated with, endorsed by, or
supported by Anthropic** or the Meridian project. Meridian routes requests
through a Claude subscription rather than metered API billing — whether
that's appropriate depends on the terms you agreed to when you subscribed.
**You are solely responsible for complying with [Anthropic's Usage
Policy](https://www.anthropic.com/legal/aup), your Anthropic terms of
service, and Meridian's own license and docs.** Provided "as is", no
warranty — see [LICENSE](LICENSE).

## Install

**Tools plugin (this repo)** — a plain whole-repo install, no subdirectory
needed:

```bash
hermes plugins install jdotcole/hermes-provider-meridian
hermes plugins enable meridian
```

(or the dashboard's "install from URL", pointed at the bare repo URL.)

**Provider profile** (`provider/`) — needs a fixed install path
(`$HERMES_HOME/plugins/model-providers/meridian/`) that Hermes' generic
installer can't produce, regardless of subfolder. Once the tools plugin
above is installed and enabled, finish the job from inside Hermes — no
shell/SSH needed:

```
/meridian install-provider
```

Or bootstrap everything from a shell in one step:

```bash
git clone https://github.com/jdotcole/hermes-provider-meridian.git
cd hermes-provider-meridian && ./install.sh
```

**Restart Hermes (or start a fresh session) afterward** — provider
discovery only runs once per process.

## Configuration

```bash
# $HERMES_HOME/.env
MERIDIAN_API_KEY=...                      # the proxy's key, or any placeholder if it runs open
MERIDIAN_BASE_URL=http://127.0.0.1:3456
```

```yaml
# config.yaml
model:
  provider: meridian
  default: claude-sonnet-4-6

plugins:
  enabled:
    - meridian
```

Hermes refuses to run an api-key provider with an empty secret, so
`MERIDIAN_API_KEY` must always be set — to the proxy's real key, or any
placeholder if it runs without auth. See the
[provider profile README](provider/README.md) for `api_mode`
auto-detection details, model naming, and migrating from a
`custom_providers` entry.

## Tools (toolset `meridian`)

| Tool | Proxy endpoint | Use |
|---|---|---|
| `meridian_status` | `GET /health` | reachability, version, logged-in account + subscription tier, `api_mode` patch diagnostics |
| `meridian_quota` | `GET /v1/usage/quota[/all]` | rate-limit windows with utilization % and reset times; `all_profiles` covers every account |
| `meridian_models` | `GET /v1/models` | served models + context windows |
| `meridian_profiles` | `GET /profiles/list` | multi-account profiles, active one, routing mode |
| `meridian_switch_profile` | `POST /profiles/active` | activate another account (clears proxy session + rate-limit caches) |
| `meridian_refresh_auth` | `POST /auth/refresh` | force an OAuth token refresh when requests 401 |

Patterns these enable: quota-aware scheduling (defer heavy jobs when a
window is nearly exhausted), auth self-healing (call `meridian_refresh_auth`
on 401s instead of paging a human), and multi-account rotation via
`meridian_switch_profile`.

```
/meridian                 # status
/meridian quota [all]
/meridian models
/meridian profiles
/meridian refresh [profile]
/meridian switch <profile-id>
/meridian install-provider [force]
```

## `install-provider`

The `provider/` profile can't be installed through Hermes' normal plugin
flow at all — that flow always drops a plugin flat under
`$HERMES_HOME/plugins/<name>/`, but a model-provider profile is only ever
discovered from the fixed path
`$HERMES_HOME/plugins/model-providers/<name>/`. `/meridian install-provider`
(or `hermes meridian install-provider [--force]`) clones this repo and
copies `provider/` into that exact path — from inside a running Hermes
process, so no shell or SSH access to the host is required once this tools
plugin is installed and enabled.

Requires `git` on the Hermes host. Set `MERIDIAN_PLUGIN_REPO_URL` to install
from a fork or self-hosted mirror instead of the canonical repo.
Deliberately not agent-callable — reinstalling a provider plugin is an
operator action, not something the agent should trigger on its own.

## Repo layout

```
__init__.py, cli.py, install_provider.py, schemas.py, tools.py, plugin.yaml
                                # tools plugin — this repo's root
provider/                      # ProviderProfile plugin (own install path)
install.sh                     # shell-based bootstrap for both plugins
```

## Compatibility

Built against hermes-agent's plugin contracts and Meridian's HTTP API as of
2026-07. Both projects move independently of this repo — if something stops
working after upgrading either one, check the linked
[provider README](provider/README.md) first (especially the `api_mode`
patch, which depends on undocumented Hermes internals) before filing an
issue.

Issues and PRs welcome — this is a community integration, not an official
product of either upstream project.
