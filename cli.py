"""CLI commands for the meridian plugin.

Wires `hermes meridian install-provider [--force]` — see install_provider.py
for what it does and why it exists.
"""

from __future__ import annotations

import argparse

from . import install_provider as ip


def register_cli(subparser: argparse.ArgumentParser) -> None:
    """Build the ``hermes meridian`` argparse tree."""
    subs = subparser.add_subparsers(dest="meridian_command")

    install_p = subs.add_parser(
        "install-provider",
        help=(
            "Install the meridian model-provider profile into "
            "$HERMES_HOME/plugins/model-providers/meridian/"
        ),
    )
    install_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing install",
    )


def meridian_command(args: argparse.Namespace) -> int:
    sub = getattr(args, "meridian_command", None)
    if sub == "install-provider":
        print(ip.install_provider(force=bool(getattr(args, "force", False))))
        return 0
    print("usage: hermes meridian install-provider [--force]")
    return 2
