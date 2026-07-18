"""Entry point for ``python -m chemsmart.gui`` and the ``chemsmart-gui`` script.

Bootstraps the ``QApplication``, ensures ``~/.chemsmart`` exists, gates on the
first-run onboarding wizard when no agent config is present, then shows the
main window. Kept deliberately thin — all UI lives in :mod:`chemsmart.gui.app`
and the screens.
"""

from __future__ import annotations

import argparse
import sys


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
    parser = argparse.ArgumentParser(prog="chemsmart-gui")
    parser.add_argument(
        "--session-root",
        default=None,
        help="Override the agent session storage root.",
    )
    args = parser.parse_args(argv)

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChemSmart")

    _ensure_environment()

    from pathlib import Path

    from chemsmart.gui.app import MainWindow

    session_root = Path(args.session_root) if args.session_root else None
    window = MainWindow(session_root=session_root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
