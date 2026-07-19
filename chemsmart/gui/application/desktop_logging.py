"""Bounded private logging for the native desktop application."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import stat
import sys
from types import TracebackType


LOG_FILENAME = "desktop.log"
MAX_LOG_BYTES = 1024 * 1024
BACKUP_COUNT = 3


class _PrivateRotatingFileHandler(RotatingFileHandler):
    """Open every active log with no-follow and owner-only permissions."""

    def _open(self):
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.baseFilename, flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("Desktop log path must be a regular file.")
            os.fchmod(descriptor, 0o600)
            return open(
                descriptor,
                mode=self.mode,
                encoding=self.encoding,
                errors=self.errors,
            )
        except BaseException:
            os.close(descriptor)
            raise


def desktop_log_root() -> Path:
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Logs" / "ChemSmart"
    return Path.home() / ".chemsmart" / "logs"


def configure_desktop_logging(root: Path | None = None) -> Path:
    """Add one rotating 0600 desktop log without replacing CLI handlers."""
    log_root = (root or desktop_log_root()).expanduser().absolute()
    if log_root.is_symlink():
        raise ValueError("Desktop log directory must not be a symlink.")
    log_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(log_root, 0o700)
    log_path = log_root / LOG_FILENAME
    if log_path.is_symlink():
        raise ValueError("Desktop log file must not be a symlink.")
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        from chemsmart.utils.logger import create_logger

        create_logger(debug=False, stream=True)
        root_logger = logging.getLogger()
    elif root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers:
        if getattr(handler, "_chemsmart_desktop_path", None) == log_path:
            return log_path

    handler = _PrivateRotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    os.chmod(log_path, 0o600)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "{asctime} - {levelname:6s} - [{name}] {message}",
            style="{",
        )
    )
    handler._chemsmart_desktop_path = log_path  # type: ignore[attr-defined]
    root_logger.addHandler(handler)
    return log_path


def install_exception_logging() -> None:
    """Record an unhandled Python exception before preserving normal behavior."""
    if getattr(sys.excepthook, "_chemsmart_desktop_hook", False):
        return
    previous = sys.excepthook

    def log_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        logging.getLogger("chemsmart.gui.crash").critical(
            "Unhandled desktop exception",
            exc_info=(exception_type, exception, traceback),
        )
        previous(exception_type, exception, traceback)

    log_exception._chemsmart_desktop_hook = True  # type: ignore[attr-defined]
    sys.excepthook = log_exception
