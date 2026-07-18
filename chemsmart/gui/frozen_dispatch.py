"""Absolute-path dispatch for the CLI embedded in a frozen GUI bundle."""

from __future__ import annotations

import sys


INTERNAL_CLI_MARKER = "--chemsmart-internal-cli"


def is_frozen_runtime() -> bool:
    """Recognize both PyInstaller and Nuitka frozen/compiled runtimes."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def internal_cli_command(args: list[str]) -> list[str]:
    """Build an argv that never resolves ``chemsmart`` through ambient PATH."""
    if is_frozen_runtime():
        return [sys.executable, INTERNAL_CLI_MARKER, *args]
    return [
        sys.executable,
        "-m",
        "chemsmart.gui",
        INTERNAL_CLI_MARKER,
        *args,
    ]


def dispatch_internal_cli(args: list[str]) -> int:
    """Run the existing Click root in-process for a self-dispatched child."""
    import click

    from chemsmart.cli.main import entry_point

    try:
        result = entry_point.main(
            args=args,
            prog_name="chemsmart",
            standalone_mode=False,
            obj={},
        )
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    return int(result or 0)
