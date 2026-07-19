#!/bin/sh
# Install the meridian Hermes plugins into $HERMES_HOME.
#
# Usage: ./install.sh [--link] [--force]
#   --link   symlink files/dirs into HERMES_HOME instead of copying,
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

# Shared "does dest already exist" guard — returns 1 (skip) if so and not forcing.
_check_dest() {
    dest="$1"
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        if ! $FORCE; then
            echo "  skip (exists): $dest   (use --force to replace)"
            return 1
        fi
        rm -rf "$dest"
    fi
    return 0
}

install_dir() {
    # Copy/link a whole directory as-is. Used for provider/, which is
    # self-contained.
    src="$1" dest="$2"
    _check_dest "$dest" || return 0
    mkdir -p "$(dirname "$dest")"
    if $LINK; then
        ln -s "$src" "$dest"
        echo "  linked: $dest -> $src"
    else
        cp -R "$src" "$dest"
        echo "  installed: $dest"
    fi
}

install_tools_plugin() {
    # The tools plugin's files sit at this repo's root, alongside meta
    # files (LICENSE, this script, provider/) that shouldn't be copied
    # into the installed plugin directory too — so this copies the
    # specific files that make up the plugin, not the whole repo root.
    dest="$HERMES_HOME/plugins/meridian"
    _check_dest "$dest" || return 0
    mkdir -p "$dest"
    for f in __init__.py cli.py install_provider.py schemas.py tools.py plugin.yaml; do
        if $LINK; then
            ln -s "$SRC_DIR/$f" "$dest/$f"
        else
            cp "$SRC_DIR/$f" "$dest/$f"
        fi
    done
    echo "  installed: $dest"
}

echo "Installing meridian plugins into $HERMES_HOME"
install_dir "$SRC_DIR/provider" "$HERMES_HOME/plugins/model-providers/meridian"
install_tools_plugin

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
     (api_mode is usually auto-detected — see provider/README.md)
  4. Verify:  hermes doctor   (Meridian appears under Provider Connectivity)
EOF
