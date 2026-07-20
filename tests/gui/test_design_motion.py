"""Reduced-motion policy contracts (review finding L3)."""

from __future__ import annotations

import pytest

from chemsmart.gui.design import motion


@pytest.fixture(autouse=True)
def _reset_motion_state():
    motion.set_reduced_motion_override(None)
    motion._platform_reduce_motion_cache = None
    yield
    motion.set_reduced_motion_override(None)
    motion._platform_reduce_motion_cache = None


def test_override_wins_over_platform_detection() -> None:
    motion.set_reduced_motion_override(True)
    assert motion.reduce_motion() is True
    assert motion.effective_duration_ms(160) == 0
    motion.set_reduced_motion_override(False)
    assert motion.reduce_motion() is False
    assert motion.effective_duration_ms(160) == 160


def test_platform_detection_reads_macos_defaults(monkeypatch) -> None:
    class _Result:
        stdout = "1\n"

    monkeypatch.setattr(motion.sys, "platform", "darwin")
    monkeypatch.setattr(motion.subprocess, "run", lambda *a, **k: _Result())
    assert motion.reduce_motion() is True


def test_platform_detection_fails_toward_motion(monkeypatch) -> None:
    def _boom(*args, **kwargs):
        raise OSError("no defaults tool")

    monkeypatch.setattr(motion.sys, "platform", "darwin")
    monkeypatch.setattr(motion.subprocess, "run", _boom)
    assert motion.reduce_motion() is False


def test_detection_result_is_cached(monkeypatch) -> None:
    calls: list[int] = []

    class _Result:
        stdout = "1"

    def _run(*args, **kwargs):
        calls.append(1)
        return _Result()

    monkeypatch.setattr(motion.sys, "platform", "darwin")
    monkeypatch.setattr(motion.subprocess, "run", _run)
    assert motion.reduce_motion() is True
    assert motion.reduce_motion() is True
    assert len(calls) == 1
