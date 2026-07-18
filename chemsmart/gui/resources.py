"""Integrity-checked resources shared by source and frozen GUI runtimes."""

from __future__ import annotations

import hashlib

from chemsmart.package_resources import package_resource


THREEDMOL_VERSION = "2.5.5"
THREEDMOL_SHA256 = (
    "9a39af476726e687d60f63750faaa2376c5a872963598e22ccc52dc1e66f27e5"
)


def read_threedmol_javascript() -> str:
    """Return the vendored 3Dmol.js bundle after checking its pinned hash."""
    asset = package_resource(
        "chemsmart.gui",
        "assets",
        "3dmol",
        "3Dmol-min.js",
    )
    payload = asset.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != THREEDMOL_SHA256:
        raise RuntimeError(
            "The bundled 3Dmol.js asset failed its integrity check: "
            f"expected {THREEDMOL_SHA256}, got {digest}."
        )
    return payload.decode("utf-8")
