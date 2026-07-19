# hermes-provider-meridian

[Meridian](https://github.com/rynfar/meridian) as a first-class provider for
[Hermes Agent](https://hermes-agent.nousresearch.com/). Meridian is a local
proxy that bridges the Claude Agent SDK to the standard Anthropic Messages
API, so a Claude subscription can serve any Anthropic-compatible client —
including Hermes.

Two plugins, no Hermes core changes:

| Plugin | Path | What it does |
|---|---|---|
| [model-provider profile](plugins/model-providers/meridian/README.md) | `plugins/model-providers/meridian/` | Registers `provider: meridian` — credentials, live model catalog, `hermes doctor` probe, aux-model default, best-effort `api_mode` auto-detection |
| [tools plugin](plugins/meridian/README.md) | `plugins/meridian/` | Agent tools + `/meridian` slash command: health, quota, model list, account profiles, OAuth refresh, self-install helper |

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

The two plugins need different install paths — Hermes' generic
"install from URL" flow can only handle one of them.

**Tools plugin** — works normally:

```bash
hermes plugins install jdotcole/hermes-provider-meridian/plugins/meridian
hermes plugins enable meridian
```

(or the dashboard's "install from URL", pointed at that same subfolder path.)

**Provider profile** — needs a fixed install path
(`$HERMES_HOME/plugins/model-providers/meridian/`) that Hermes' generic
installer can't produce. Once the tools plugin above is installed and
enabled, finish the job from inside Hermes — no shell/SSH needed:

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
placeholder if it runs without auth.

See the [provider profile README](plugins/model-providers/meridian/README.md)
for `api_mode` auto-detection details, model naming, and migrating from a
`custom_providers` entry. See the
[tools plugin README](plugins/meridian/README.md) for the full tool/slash
command reference.

## Repo layout

```
plugins/
├── model-providers/meridian/   # ProviderProfile plugin (auto-discovered)
└── meridian/                   # general plugin: tools + /meridian command
install.sh                      # shell-based bootstrap for both plugins
```

## Compatibility

Built against hermes-agent's plugin contracts and Meridian's HTTP API as of
2026-07. Both projects move independently of this repo — if something stops
working after upgrading either one, check the linked READMEs above first
(especially the `api_mode` patch, which depends on undocumented Hermes
internals) before filing an issue.

Issues and PRs welcome — this is a community integration, not an official
product of either upstream project.
