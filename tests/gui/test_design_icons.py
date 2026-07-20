"""Fail-closed contracts for the hash-pinned icon allowlist (ADR 0002)."""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.gui.design import icons

ASSET_DIR = (
    Path(__file__).resolve().parents[2]
    / "chemsmart"
    / "gui"
    / "assets"
    / "icons"
    / "lucide"
)


def test_every_manifest_entry_verifies() -> None:
    for name in icons.icon_names():
        data = icons._verified_svg(name)
        assert data.startswith(b"<svg "), name
        assert b"currentColor" in data, name


def test_no_unlisted_assets_ship() -> None:
    """Every vendored SVG must be in the pinned allowlist (and vice versa)."""
    on_disk = {p.stem for p in ASSET_DIR.glob("*.svg")}
    assert on_disk == set(icons.MANIFEST)


def test_license_notices_ship_with_the_assets() -> None:
    notice = (ASSET_DIR / "LICENSE.txt").read_text(encoding="utf-8")
    assert "ISC License" in notice
    assert "Lucide" in notice
    assert "MIT License" in notice  # Feather-derived portions


def test_unknown_icon_fails_closed() -> None:
    with pytest.raises(icons.IconError):
        icons.svg_bytes("definitely-not-an-icon", "#000000")


def test_tampered_asset_fails_closed(monkeypatch) -> None:
    monkeypatch.setitem(icons.MANIFEST, "x", "0" * 64)
    icons._verified_svg.cache_clear()
    try:
        with pytest.raises(icons.IconError, match="hash mismatch"):
            icons.svg_bytes("x", "#000000")
    finally:
        icons._verified_svg.cache_clear()


def test_invalid_color_is_rejected() -> None:
    with pytest.raises(icons.IconError):
        icons.svg_bytes("x", "red")


def test_recolor_substitutes_the_token() -> None:
    data = icons.svg_bytes("check", "#123456")
    assert b"#123456" in data
    assert b"currentColor" not in data


def test_pixmap_renders_nonblank(qapp) -> None:
    pixmap = icons.pixmap("flask-conical", "#000000", 24)
    assert not pixmap.isNull()
    image = pixmap.toImage()
    nonblank = any(
        image.pixelColor(x, y).alpha() > 0
        for x in range(0, image.width(), 3)
        for y in range(0, image.height(), 3)
    )
    assert nonblank, "rendered icon has no visible pixels"
