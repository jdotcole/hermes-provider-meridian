# meridian — tools plugin

General Hermes plugin: agent tools + a `/meridian` slash command for
Meridian's management API (health, quota, model catalog, account profiles,
OAuth refresh), plus a helper that installs the companion model-provider
profile. See the [repo README](../../README.md) for the big picture.

## Install

Works through Hermes' normal plugin flow — dashboard "install from URL"
pointed at this subfolder, or:

```bash
hermes plugins install jdotcole/hermes-provider-meridian/plugins/meridian-tools
hermes plugins enable meridian
```

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

## Slash command

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

The companion `plugins/meridian-provider/` profile can't be installed
through Hermes' normal plugin flow at all — that flow always drops a plugin
flat under `$HERMES_HOME/plugins/<name>/`, but a model-provider profile is
only ever discovered from the fixed path
`$HERMES_HOME/plugins/model-providers/<name>/`. This command does what
[`install.sh`](../../install.sh) does — clone the repo and copy the profile
into that exact path — from inside a running Hermes process, so no shell or
SSH access to the host is required once this tools plugin is installed and
enabled.

```
/meridian install-provider        # slash command
/meridian install-provider force  # overwrite an existing install

hermes meridian install-provider [--force]   # CLI equivalent
```

Requires `git` on the Hermes host. Set `MERIDIAN_PLUGIN_REPO_URL` to install
from a fork or self-hosted mirror instead of the canonical repo.

Provider discovery runs once per process, at first use — **restart Hermes
(or start a fresh session)** after running this for `provider: meridian` to
become selectable.

Deliberately not exposed as an agent-callable tool: reinstalling a provider
plugin is an operator action, not something the agent should be able to
trigger on its own mid-conversation.
