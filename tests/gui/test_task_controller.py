"""Stress contracts for the reusable Qt background-task lifecycle."""

from __future__ import annotations

import time

import pytest


pytest.importorskip("PySide6")

from PySide6.QtTest import QTest

from chemsmart.gui.application.task_controller import (
    QtTaskController,
    TaskStatus,
)


def _wait_until(qapp, predicate, *, timeout_ms: int = 1500) -> None:
    deadline = time.monotonic() + timeout_ms / 1000
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition did not become true before timeout")
        qapp.processEvents()
        QTest.qWait(5)


def test_success_reports_honest_progress_and_cleans_thread(qapp) -> None:
    controller = QtTaskController()
    progress = []
    results = []
    calls = []
    controller.progress_changed.connect(progress.append)
    controller.succeeded.connect(results.append)

    def task(context):
        calls.append("run")
        context.report_indeterminate("Discovering inputs")
        context.report_progress(1, 2, "Preparing")
        context.report_progress(2, 2, "Complete")
        return {"status": "ok"}

    controller.start(task)
    _wait_until(qapp, lambda: controller.snapshot.status == TaskStatus.SUCCEEDED)
    _wait_until(qapp, lambda: controller.active_thread_count == 0)

    assert progress[0].indeterminate
    assert progress[-1].current == progress[-1].total == 2
    assert results == [{"status": "ok"}]
    assert calls == ["run"]


def test_cooperative_cancel_has_explicit_state_and_cleanup(qapp) -> None:
    controller = QtTaskController()

    def task(context):
        context.report_indeterminate("Waiting")
        while not context.token.cancelled:
            time.sleep(0.002)
        context.raise_if_cancelled()

    controller.start(task)
    _wait_until(qapp, lambda: controller.snapshot.progress.message == "Waiting")
    controller.cancel()
    assert controller.snapshot.status == TaskStatus.CANCELLING
    _wait_until(qapp, lambda: controller.snapshot.status == TaskStatus.CANCELLED)
    _wait_until(qapp, lambda: controller.active_thread_count == 0)


def test_new_generation_suppresses_stale_result(qapp) -> None:
    controller = QtTaskController()
    results = []
    controller.succeeded.connect(results.append)

    def old_task(context):
        context.report_indeterminate("Old task started")
        while not context.token.cancelled:
            time.sleep(0.002)
        return "stale"

    controller.start(old_task)
    _wait_until(
        qapp,
        lambda: controller.snapshot.progress.message == "Old task started",
    )
    controller.start(lambda _context: "current")
    _wait_until(qapp, lambda: controller.snapshot.status == TaskStatus.SUCCEEDED)
    _wait_until(qapp, lambda: controller.active_thread_count == 0)

    assert results == ["current"]


def test_timeout_redacts_failure_and_drains_cooperative_worker(qapp) -> None:
    controller = QtTaskController()
    failures = []
    controller.failed.connect(failures.append)

    def task(context):
        while not context.token.cancelled:
            time.sleep(0.002)
        context.raise_if_cancelled()

    controller.start(task, timeout_ms=25)
    _wait_until(qapp, lambda: controller.snapshot.status == TaskStatus.TIMED_OUT)
    _wait_until(qapp, lambda: controller.active_thread_count == 0)

    assert failures[-1].diagnostic_type == "TimeoutError"
    assert "timed out" in failures[-1].user_message


def test_repeated_start_cancel_stress_leaves_no_threads(qapp) -> None:
    controller = QtTaskController()

    def task(context):
        while not context.token.cancelled:
            time.sleep(0.001)
        context.raise_if_cancelled()

    for _ in range(40):
        controller.start(task)
        controller.cancel()

    _wait_until(qapp, lambda: controller.active_thread_count == 0, timeout_ms=3000)
    assert controller.shutdown(100)


def test_secret_bearing_task_can_disable_retry_retention(qapp) -> None:
    controller = QtTaskController()
    controller.start(
        lambda _context: "ok",
        retain_for_retry=False,
    )
    _wait_until(qapp, lambda: controller.snapshot.status == TaskStatus.SUCCEEDED)
    _wait_until(qapp, lambda: controller.active_thread_count == 0)

    with pytest.raises(RuntimeError, match="No background task"):
        controller.retry()
