"""The P8.1 gallery must render every primitive nonblank in all modes."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")


def test_gallery_builds_in_every_mode(qapp) -> None:
    from chemsmart.gui.design.tokens import resolve_tokens
    from chemsmart.gui.diagnostics.component_gallery import build_gallery

    for mode in ("light", "dark"):
        for increased in (False, True):
            gallery = build_gallery(
                resolve_tokens(mode, increased_contrast=increased)
            )
            assert gallery.widget() is not None
            gallery.deleteLater()


def test_gallery_capture_writes_nonblank_receipted_pngs(
    qapp, tmp_path
) -> None:
    from chemsmart.gui.diagnostics.component_gallery import main

    receipt_path = main(output_dir=tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert set(receipt["screenshots"]) == {
        "light",
        "dark",
        "light-hc",
        "dark-hc",
    }
    for mode, evidence in receipt["screenshots"].items():
        assert evidence["bytes"] > 0, mode
        assert evidence["sampled_nonblank"] > 0, mode
        assert len(evidence["sha256"]) == 64, mode
        assert (tmp_path / f"component_gallery_{mode}.png").exists()
