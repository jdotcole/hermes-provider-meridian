# meridian — model provider profile

Registers `meridian` as a first-class Hermes inference provider. See the
[repo README](../../README.md) for the big picture and disclaimers.

## Install

Hermes' normal plugin flow (dashboard "install from URL", `hermes plugins
install`) can't place this plugin — model-provider profiles are only
discovered from the fixed path `$HERMES_HOME/plugins/model-providers/<name>/`,
and that flow always drops a plugin flat under `$HERMES_HOME/plugins/<name>/`
instead. Use one of:

```bash
# from inside a running Hermes with the plugins/meridian-tools/ tools plugin
# installed and enabled — no shell/SSH needed:
/meridian install-provider
# or: hermes meridian install-provider

# or, bootstrapping everything from a shell in one step:
git clone https://github.com/jdotcole/hermes-provider-meridian.git
cd hermes-provider-meridian && ./install.sh
```

**Restart Hermes (or start a fresh session) afterward** — provider
discovery runs once per process, at first use.

## Configuration

```yaml
# config.yaml
model:
  provider: meridian
  default: claude-sonnet-4-6
  # base_url: http://meridian-host:3456   # optional; MERIDIAN_BASE_URL env also works
  # api_mode: anthropic_messages          # optional — see below
```

```bash
# .env
MERIDIAN_API_KEY=...        # the proxy's key, or any placeholder if it runs open
MERIDIAN_BASE_URL=http://127.0.0.1:3456
```

What auto-wires once this plugin is in place:

- `--provider meridian` CLI flag, `hermes model` picker entry
- Credential resolution from `MERIDIAN_API_KEY` / `MERIDIAN_BASE_URL`
- Live model catalog from Meridian's `/v1/models`
- `hermes doctor` connectivity probe
- Auxiliary tasks (compression, vision, summarization) default to `claude-haiku-4-5`
- Best-effort `api_mode` auto-detection (see below) so the config line above
  can usually stay commented out

## `api_mode` auto-detection

Hermes needs to know Meridian speaks the native Anthropic Messages protocol
(`api_mode: anthropic_messages`), not the default OpenAI-compatible
`chat_completions`. Hermes only infers this from URL shape
(`api.anthropic.com`, or a path ending in `/anthropic`), which a bare
`host:port` endpoint never matches — so normally you'd have to set
`api_mode: anthropic_messages` explicitly.

This plugin instead patches Hermes' internal URL-detection so it also
recognizes Meridian's configured endpoint, meaning `api_mode` usually
doesn't need to be set at all. Worth understanding what that means:

- **What it targets**: two private, underscore-prefixed functions inside
  Hermes (`hermes_cli.runtime_provider._detect_api_mode_for_url` and
  `hermes_cli.providers.determine_api_mode`) — there's no supported plugin
  hook for this, so the plugin wraps them directly at runtime. Nothing in
  Hermes' source tree is modified.
- **Scoped to Meridian's own endpoint**: it only ever overrides the result
  for requests whose host/port match your configured `MERIDIAN_BASE_URL`
  (or the default `127.0.0.1:3456`). It cannot affect any other provider.
- **Applied lazily, not at plugin load**: attempting this at plugin-import
  time reliably fails with a circular-import error, because Hermes' own
  provider discovery is triggered from the middle of a module
  (`hermes_cli.auth`) that hasn't finished defining its own names yet. The
  patch is deferred to the first time Hermes calls one of this provider's
  request-time hooks — which, by construction, only happens after the whole
  process has finished starting up. Practical effect: the very first
  request in a freshly started process may go out over the
  OpenAI-compatible wire (Meridian handles that fine too) while the patch
  applies; every request after that uses the native Anthropic Messages API.
- **Fails safe, with logging, if Hermes changes underneath it**: this
  reaches into undocumented internals with no compatibility guarantee. The
  patch retries a handful of times, then gives up permanently and logs one
  clear warning — it never spams the log, and a failed patch never breaks a
  request; it only means falling back to the OpenAI-compatible wire (or
  needing the explicit config line for the native one).
- **An explicit `model.api_mode` in config.yaml always wins** over this
  patch — set one yourself if you'd rather not depend on it.
- **Opt out entirely**: set `MERIDIAN_SKIP_API_MODE_PATCH=1`.
- **Check whether it's active**: `meridian_status` / `/meridian` includes
  an `api_mode_patch` field (`applied` / `gave_up` / `attempts` / `last_error`).

## Choosing models

Meridian accepts versioned ids (`claude-sonnet-4-6`, `claude-opus-4-8`, …),
bare aliases (`sonnet`, `opus`, `haiku`, `fable`), and 1M-context variants
(`opus[1m]`, `fable[1m]`) where your subscription and Meridian's own config
allow it. Reasoning effort flows through to the Claude Agent SDK's
extended-thinking controls.

## Migrating from a `custom_providers` entry

A legacy `custom_providers` entry named `meridian` keeps working —
`provider: custom:meridian` still resolves to it. Once this plugin is
installed, plain `provider: meridian` resolves here instead (built-in
providers win over same-named custom entries). Migrate at your leisure.
