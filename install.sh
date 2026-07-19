#!/bin/sh
# Install the meridian Hermes plugins into $HERMES_HOME.
#
# Usage: ./install.sh [--link] [--force]
#   --link   symlink the plugin dirs into HERMES_HOME instead of copying,
#            so a `git pull` in this clone updates the live plugins
#   --force  replace an existing install (copy mode removes the old dir first)
#
# HERMES_HOME defaults to ~/.hermes (the live Hermes server uses /opt/data).
set -eu

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LINK=false
FORCE=false

for arg in "$@"; do
    case "$arg" in
        --link)  LINK=true ;;
        --force) FORCE=true ;;
        *) echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
done

install_one() {
    src="$1" dest="$2"
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        if ! $FORCE; then
            echo "  skip (exists): $dest   (use --force to replace)"
            return
        fi
        rm -rf "$dest"
    fi
    mkdir -p "$(dirname "$dest")"
    if $LINK; then
        ln -s "$src" "$dest"
        echo "  linked: $dest -> $src"
    else
        cp -R "$src" "$dest"
        echo "  installed: $dest"
    fi
}

echo "Installing meridian plugins into $HERMES_HOME"
install_one "$SRC_DIR/plugins/model-providers/meridian" "$HERMES_HOME/plugins/model-providers/meridian"
install_one "$SRC_DIR/plugins/meridian" "$HERMES_HOME/plugins/meridian"

cat <<EOF

Done. Next steps:
  1. Set env vars (e.g. in $HERMES_HOME/.env):
       MERIDIAN_API_KEY=<proxy key, or any placeholder if the proxy runs open>
       MERIDIAN_BASE_URL=http://127.0.0.1:3456
  2. Enable the tools plugin:  hermes plugins enable meridian
     (the model-provider profile is auto-discovered; no enable needed)
  3. Point the model at meridian in config.yaml:
       model:
         provider: meridian
         default: claude-sonnet-4-6
         api_mode: anthropic_messages
  4. Verify:  hermes doctor   (Meridian appears under Provider Connectivity)
EOF
