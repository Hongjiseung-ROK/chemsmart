"""Absolute-path dispatch for the CLI embedded in a frozen GUI bundle."""

from __future__ import annotations

from pathlib import Path
import sys


INTERNAL_CLI_MARKER = "--chemsmart-internal-cli"
_SOURCE_DISPATCH = (
    "import runpy,sys;"
    "sys.path.insert(0,sys.argv.pop(1));"
    "runpy.run_module('chemsmart.gui',run_name='__main__')"
)


def is_frozen_runtime() -> bool:
    """Recognize both PyInstaller and Nuitka frozen/compiled runtimes."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def internal_cli_command(args: list[str]) -> list[str]:
    """Build an argv that never resolves ``chemsmart`` through ambient PATH."""
    if is_frozen_runtime():
        return [sys.executable, INTERNAL_CLI_MARKER, *args]
    package_root = str(Path(__file__).resolve().parents[2])
    return [
        sys.executable,
        "-I",
        "-c",
        _SOURCE_DISPATCH,
        package_root,
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
