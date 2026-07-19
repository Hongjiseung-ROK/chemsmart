"""Entry point for ``python -m chemsmart.gui`` and the ``chemsmart-gui`` script.

Bootstraps the ``QApplication``, ensures ``~/.chemsmart`` exists, gates on the
first-run onboarding wizard when no agent config is present, then shows the
main window. Kept deliberately thin — all UI lives in :mod:`chemsmart.gui.app`
and the screens.
"""

from __future__ import annotations

import argparse
import logging
import sys


def _configure_desktop_diagnostics() -> None:
    from chemsmart import __version__
    from chemsmart.gui.application.desktop_logging import (
        configure_desktop_logging,
        install_exception_logging,
    )

    try:
        configure_desktop_logging()
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Desktop file logging unavailable (%s); continuing.",
            type(exc).__name__,
        )
    try:
        install_exception_logging()
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Desktop exception logging unavailable (%s); continuing.",
            type(exc).__name__,
        )
    logging.getLogger(__name__).info(
        "ChemSmart desktop %s starting; frozen=%s",
        __version__,
        bool(getattr(sys, "frozen", False)),
    )


def _needs_onboarding() -> bool:
    """True when no agent provider config exists yet at ``~/.chemsmart``."""
    from chemsmart.cli.config import Config

    return not Config().chemsmart_agent_yaml.exists()


def _ensure_environment() -> None:
    """Create ``~/.chemsmart`` from bundled templates if it does not exist.

    Reuses :meth:`Config.setup_environment` (the same code the CLI runs), which
    also lays down ``~/.chemsmart/server/*.yaml`` — a prerequisite for the
    Job builder dry-run to construct a ``JobRunner``.
    """
    from chemsmart.cli.config import Config

    Config().ensure_user_config_tree()


def main(argv: list[str] | None = None) -> int:
    from chemsmart.gui.frozen_dispatch import (
        INTERNAL_CLI_MARKER,
        dispatch_internal_cli,
    )

    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == INTERNAL_CLI_MARKER:
        return dispatch_internal_cli(raw_args[1:])

    parser = argparse.ArgumentParser(prog="chemsmart-gui")
    parser.add_argument(
        "--session-root",
        default=None,
        help="Override the agent session storage root.",
    )
    parser.add_argument(
        "--packaging-probe-receipt",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--packaging-probe-workspace",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--packaging-shell-smoke-receipt",
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(raw_args)

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChemSmart")
    app.setOrganizationName("ZhangLab")
    from chemsmart import __version__

    app.setApplicationVersion(__version__)

    _configure_desktop_diagnostics()

    _ensure_environment()

    from pathlib import Path

    if args.packaging_probe_receipt:
        if not args.packaging_probe_workspace:
            parser.error(
                "--packaging-probe-workspace is required with the probe receipt"
            )
        from chemsmart.gui.packaging_probe import run_packaging_probe

        return run_packaging_probe(
            app,
            receipt_path=Path(args.packaging_probe_receipt).resolve(),
            workspace=Path(args.packaging_probe_workspace).resolve(),
        )

    from chemsmart.gui.app import MainWindow

    session_root = Path(args.session_root) if args.session_root else None
    preferences = QSettings("ZhangLab", "ChemSmart")
    window = MainWindow(
        session_root=session_root,
        preference_store=preferences,
    )
    if args.packaging_shell_smoke_receipt:
        from chemsmart.gui.packaging_probe import run_shell_smoke

        return run_shell_smoke(
            app,
            window,
            receipt_path=Path(args.packaging_shell_smoke_receipt).resolve(),
        )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
