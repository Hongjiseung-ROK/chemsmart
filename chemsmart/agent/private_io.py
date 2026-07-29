"""Private-by-default filesystem helpers for agent session evidence."""

from __future__ import annotations

import os
from pathlib import Path

PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def ensure_private_directory(path: str | Path) -> Path:
    """Create a directory and remove group/other permissions."""

    directory = Path(path)
    if directory.is_symlink():
        raise RuntimeError(
            f"Private directory cannot be a symlink: {directory}"
        )
    directory.mkdir(
        mode=PRIVATE_DIRECTORY_MODE,
        parents=True,
        exist_ok=True,
    )
    directory.chmod(PRIVATE_DIRECTORY_MODE)
    return directory


def ensure_private_file(path: str | Path) -> Path:
    """Remove group/other permissions from an existing regular file."""

    target = Path(path)
    if target.is_symlink():
        raise RuntimeError(f"Private file cannot be a symlink: {target}")
    if target.is_file():
        target.chmod(PRIVATE_FILE_MODE)
    return target


def secure_private_tree(path: str | Path) -> Path:
    """Apply private modes to an existing session tree without following links."""

    root = ensure_private_directory(path)
    for child in root.rglob("*"):
        if child.is_symlink():
            continue
        if child.is_dir():
            child.chmod(PRIVATE_DIRECTORY_MODE)
        elif child.is_file():
            child.chmod(PRIVATE_FILE_MODE)
    return root


def write_private_text(
    path: str | Path,
    content: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Write a private text file without a world-readable creation window."""

    target = Path(path)
    ensure_private_directory(target.parent)
    descriptor = os.open(
        target,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
        PRIVATE_FILE_MODE,
    )
    try:
        with os.fdopen(descriptor, "w", encoding=encoding) as handle:
            descriptor = -1
            handle.write(content)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    ensure_private_file(target)
    return target


def append_private_text(
    path: str | Path,
    content: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Append to a private text file without relaxing existing permissions."""

    target = Path(path)
    ensure_private_directory(target.parent)
    descriptor = os.open(
        target,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
        PRIVATE_FILE_MODE,
    )
    try:
        with os.fdopen(descriptor, "a", encoding=encoding) as handle:
            descriptor = -1
            handle.write(content)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    ensure_private_file(target)
    return target


__all__ = [
    "PRIVATE_DIRECTORY_MODE",
    "PRIVATE_FILE_MODE",
    "append_private_text",
    "ensure_private_directory",
    "ensure_private_file",
    "secure_private_tree",
    "write_private_text",
]
