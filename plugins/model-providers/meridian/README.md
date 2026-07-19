# meridian — model provider profile

Registers `meridian` as a first-class Hermes inference provider. See the
[repo README](../../../README.md) for installation and full configuration.

Quick reference:

```yaml
# config.yaml
model:
  provider: meridian
  default: claude-sonnet-4-6
  api_mode: anthropic_messages      # required — see profile docstring
  # base_url: http://10.0.1.10:3456 # optional; MERIDIAN_BASE_URL env also works
```

```bash
# .env
MERIDIAN_API_KEY=...        # proxy's key, or any placeholder if the proxy runs open
MERIDIAN_BASE_URL=http://127.0.0.1:3456
```

What auto-wires once this directory is under `$HERMES_HOME/plugins/model-providers/`:

- `--provider meridian` CLI flag, `hermes model` picker entry
- Credential resolution from `MERIDIAN_API_KEY` / `MERIDIAN_BASE_URL`
- Live model catalog from Meridian's `/v1/models`
- `hermes doctor` connectivity probe
- Auxiliary tasks (compression, vision, summarization) default to `claude-haiku-4-5`
