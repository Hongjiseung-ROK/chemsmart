"""Resolve package data without depending on a frozen app's working directory."""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path
from typing import Any


def package_resource(package: str, *parts: str) -> Any:
    """Return a package resource, preferring an executable-relative bundle path.

    PyInstaller macOS apps can expose a relative ``importlib.resources`` path
    when launched by LaunchServices.  Finder launches have no reliable working
    directory, so frozen resources must be anchored to the executable instead.
    """
    is_frozen = bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()
    if is_frozen:
        package_parts = package.split(".")
        executable = Path(sys.executable).resolve()
        roots: list[Path] = []
        if sys.platform == "darwin" and executable.parent.name == "MacOS":
            contents = executable.parent.parent
            roots.extend((contents / "Resources", contents / "Frameworks"))

        raw_meipass = getattr(sys, "_MEIPASS", "")
        meipass = Path(raw_meipass) if raw_meipass else None
        if meipass is not None and meipass.is_absolute():
            roots.append(meipass)

        for root in roots:
            candidate = root.joinpath(*package_parts, *parts)
            if candidate.exists():
                return candidate

    return resources.files(package).joinpath(*parts)
