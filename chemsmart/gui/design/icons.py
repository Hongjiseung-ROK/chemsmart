"""Hash-pinned Lucide-derived icon loader (ADR 0002).

The allowlist below is the complete icon vocabulary of the modern workbench.
Assets are vendored offline under ``chemsmart/gui/assets/icons/lucide`` with
their ISC/MIT notices; nothing is fetched at runtime. Loading is fail-closed:
an unknown name, a missing file, or a content-hash mismatch raises
:class:`IconError` instead of silently rendering a wrong or tampered glyph.

Icons are recolored through ``currentColor`` substitution with a semantic
token, so one asset serves light, dark, and increased-contrast modes. Icons
never replace labels, tooltips, or accessible names — callers still set those.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

_ASSET_DIR = (
    Path(__file__).resolve().parent.parent / "assets" / "icons" / "lucide"
)

# name -> SHA-256 of the exact vendored SVG bytes.
MANIFEST: dict[str, str] = {
    "atom": "92b7b3439d8f7b1fb684bdf6fbafc6ec49820e63a5f4fb5b137117311fa7d315",
    "ban": "9f11b7498948d34593c0a614f9ca176ded6f03a73d373b024b667b9867fc071b",
    "chart-column": "608dcb3d294d242a3364422ae60b427e5c525f81a06deca13be93b3ef4955ea4",
    "check": "34d5f35561a8f9d2952fb579d7a97db67c46c0dfb8fce025200945760ed00f77",
    "chevron-down": "7345b09168970e85352af7a397ba107fd9d8b12db292ccbc74e2dee1d536efd5",
    "chevron-right": "8c66c30b7ed586a7ee8f801d0eb4aa5a5ee69ea8357cab7eb00f90ee24ba20c5",
    "circle-check": "7cec1f275c0fad588fb89123a955f14c59c15d4b2e62d9ed24e61b0d341b3866",
    "circle-x": "3a80fd14a83b521ac167292792138dab339c0eca0b3b8b41c3c2a83cda7a6246",
    "clock": "44ad7f69f5acfb8b5e29f49583a7d9c1ad66c0c6f013053d4b03e8268d1d076b",
    "copy": "44e455c8659c6c52175c5e7e7d88847761d9a136042ab7dd12dc4b5f3c5cbddc",
    "database": "e19bd8f9d1ff640d53abac95605b88958bbd4bd4b70fb6c319c1d63332d2f520",
    "eye": "195dd35c95fb553bd66179acf531ec4357a769e1336c981e9c61bc9a7af01dd6",
    "flask-conical": "3b15d9672a91c229a8082b5a1da6a5124f069c04aedbff85a596b0ba9f3c0e04",
    "folder-open": "837c3bb20dd1b8d0856082e8bdf794b3beccccccebff0b6ec1259c4684c66763",
    "info": "3d0447616b12fa824d24287e246368f57c157ec877ab2eb44bfe3d229a817be8",
    "loader-circle": "fcc2861d495aa864f3d618a2b474e578dd3659af2905e3dfb88635a6044b3f69",
    "message-square": "5f9350e154a5569e430462c2c1ad15969e7d928b7298e71767b89cdb1d9d433c",
    "play": "c7cd6f9962b5b91db2991b3d717617201dfb62576adbc61188b24ad7cb67f65b",
    "rotate-ccw": "a2003347c21ace78a559d54e60b12391efccc75d60c71fd15feed54190cefc2b",
    "search": "9c24b8aca7afe0824d649726c4d3c8d1ed4c1255d693fcdbe2fb32a840a41d50",
    "settings": "f6a8de9eacbff916e045c012ab633a5212464f96a477b791c555cc417a372909",
    "shield-check": "cfcfa16042b1b3bba9cdd853dc189dc8c356ea8f8af25fd47f80bbc123a3122a",
    "square": "b039603faf398f9a953ac245ff7a03eae11009b81f7130bf38a4bda819b03c10",
    "terminal": "4dcda503eab52e25eb89ef10882036d8993e395d47da54bc5c450dcf4367b035",
    "triangle-alert": "7487a3f87d7f91cdcbcae5d3ae95998cf218a6a7a64f50ca9acbec1d444e70f3",
    "x": "3bfde5660f68acb8e7f4a530a9e2e67d47022d4240d1faa9aa2fc86251e046ca",
}


class IconError(RuntimeError):
    """A requested icon is unknown, missing, or fails hash verification."""


def icon_names() -> list[str]:
    """The allowlisted icon vocabulary, sorted."""
    return sorted(MANIFEST)


@lru_cache(maxsize=None)
def _verified_svg(name: str) -> bytes:
    """Return the exact SVG bytes for ``name`` after hash verification."""
    expected = MANIFEST.get(name)
    if expected is None:
        raise IconError(f"icon {name!r} is not in the pinned allowlist")
    path = _ASSET_DIR / f"{name}.svg"
    try:
        data = path.read_bytes()
    except OSError as error:
        raise IconError(f"icon asset missing: {path}") from error
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise IconError(
            f"icon asset hash mismatch for {name!r}: "
            f"expected {expected}, found {digest}"
        )
    return data


def svg_bytes(name: str, color: str) -> bytes:
    """The verified SVG recolored to a semantic token color."""
    if not color.startswith("#") or len(color) != 7:
        raise IconError(f"icon color must be #rrggbb, got {color!r}")
    return _verified_svg(name).replace(b"currentColor", color.encode("ascii"))


def pixmap(name: str, color: str, size: int = 16):
    """A device-pixel-ratio-aware ``QPixmap`` of the icon."""
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance()
    ratio = app.devicePixelRatio() if app is not None else 1.0
    edge = max(1, round(size * ratio))
    image = QImage(QSize(edge, edge), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(svg_bytes(name, color))
    if not renderer.isValid():
        raise IconError(f"icon asset is not renderable SVG: {name!r}")
    painter = QPainter(image)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    result = QPixmap.fromImage(image)
    result.setDevicePixelRatio(ratio)
    return result


def icon(name: str, color: str, size: int = 16):
    """A recolored ``QIcon`` for buttons, badges, and navigation."""
    from PySide6.QtGui import QIcon

    return QIcon(pixmap(name, color, size))
