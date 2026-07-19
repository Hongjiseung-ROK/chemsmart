"""Reusable Qt lifecycle controller for blocking desktop work."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Generic, TypeVar

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

T = TypeVar("T")
U = TypeVar("U")


class TaskStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class TaskProgress:
    """Progress with an honest indeterminate representation."""

    current: int | None = None
    total: int | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if (self.current is None) != (self.total is None):
            raise ValueError(
                "Progress current and total must be set together."
            )
        if self.current is not None:
            if self.total is None or self.total <= 0:
                raise ValueError(
                    "Determinate progress needs a positive total."
                )
            if self.current < 0 or self.current > self.total:
                raise ValueError("Progress current must be within total.")

    @property
    def indeterminate(self) -> bool:
        return self.total is None


@dataclass(frozen=True)
class TaskFailure:
    """Redacted user/diagnostic error boundary."""

    user_message: str
    diagnostic_type: str


@dataclass(frozen=True)
class TaskSnapshot:
    generation: int
    status: TaskStatus
    progress: TaskProgress
    message: str = ""


class TaskCancelled(RuntimeError):
    """Raised by cooperative task code after cancellation is requested."""


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._state_lock = threading.Lock()
        self._commit_sealed = False
        self._committed = False

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> bool:
        """Request cancellation unless an irreversible commit has started."""

        with self._state_lock:
            if self._commit_sealed or self._committed:
                return False
            self._event.set()
            return True

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise TaskCancelled("Task cancelled.")

    def commit(self, action: Callable[[], U]) -> U:
        """Run an irreversible action after atomically sealing cancellation.

        Cancellation wins if it was requested before this method acquires the
        state lock. Once sealed, later cancellation is rejected so a published
        side effect cannot be reported as cancelled by the worker.
        """

        with self._state_lock:
            if self._event.is_set():
                raise TaskCancelled("Task cancelled before commit.")
            self._commit_sealed = True
        try:
            result = action()
        except Exception:
            with self._state_lock:
                self._commit_sealed = False
            raise
        with self._state_lock:
            self._committed = True
        return result


class TaskContext:
    """Capabilities intentionally exposed to a blocking task."""

    def __init__(
        self,
        token: CancellationToken,
        report: Callable[[TaskProgress], None],
    ) -> None:
        self.token = token
        self._report = report

    def report_indeterminate(self, message: str = "") -> None:
        self._report(TaskProgress(message=message))

    def report_progress(
        self, current: int, total: int, message: str = ""
    ) -> None:
        self._report(
            TaskProgress(current=current, total=total, message=message)
        )

    def raise_if_cancelled(self) -> None:
        self.token.raise_if_cancelled()

    def commit(self, action: Callable[[], U]) -> U:
        return self.token.commit(action)


TaskCallable = Callable[[TaskContext], T]


class _TaskWorker(QObject, Generic[T]):
    progress = Signal(int, object)
    succeeded = Signal(int, object)
    failed = Signal(int, object)
    cancelled = Signal(int)
    done = Signal()

    def __init__(
        self,
        generation: int,
        task: TaskCallable[T],
        token: CancellationToken,
    ) -> None:
        super().__init__()
        self._generation = generation
        self._task = task
        self._token = token

    @Slot()
    def run(self) -> None:
        context = TaskContext(
            self._token,
            lambda value: self.progress.emit(self._generation, value),
        )
        try:
            self._token.raise_if_cancelled()
            result = self._task(context)
            if self._token.cancelled:
                self.cancelled.emit(self._generation)
            else:
                self.succeeded.emit(self._generation, result)
        except TaskCancelled:
            self.cancelled.emit(self._generation)
        except Exception as exc:
            self.failed.emit(
                self._generation,
                TaskFailure(
                    user_message="The background task failed.",
                    diagnostic_type=type(exc).__name__,
                ),
            )
        finally:
            self.done.emit()


@dataclass
class _TaskRuntime:
    thread: QThread
    worker: _TaskWorker
    token: CancellationToken
    timer: QTimer | None


@dataclass
class _PendingTask(Generic[T]):
    generation: int
    task: TaskCallable[T]
    token: CancellationToken
    timeout_ms: int


class QtTaskController(QObject, Generic[T]):
    """Own one logical task while safely draining superseded workers."""

    state_changed = Signal(object)
    progress_changed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)
    cancelled = Signal()
    drained = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._generation = 0
        self._status = TaskStatus.IDLE
        self._progress = TaskProgress()
        self._runtimes: dict[int, _TaskRuntime] = {}
        self._pending: _PendingTask[T] | None = None
        self._last_task: TaskCallable[T] | None = None
        self._last_timeout_ms = 0

    @property
    def snapshot(self) -> TaskSnapshot:
        return TaskSnapshot(
            generation=self._generation,
            status=self._status,
            progress=self._progress,
        )

    @property
    def active_thread_count(self) -> int:
        return len(self._runtimes)

    def start(
        self,
        task: TaskCallable[T],
        *,
        timeout_ms: int = 0,
        retain_for_retry: bool = True,
    ) -> int:
        if timeout_ms < 0:
            raise ValueError("timeout_ms must be zero or positive.")
        if not self._cancel_generation(self._generation):
            raise RuntimeError(
                "The current task is committing an irreversible result."
            )
        self._generation += 1
        generation = self._generation
        token = CancellationToken()
        self._pending = _PendingTask(generation, task, token, timeout_ms)
        self._last_task = task if retain_for_retry else None
        self._last_timeout_ms = timeout_ms if retain_for_retry else 0

        self._status = TaskStatus.RUNNING
        self._progress = TaskProgress()
        self._emit_state()
        if not self._runtimes:
            self._launch_pending()
        return generation

    def _launch_pending(self) -> None:
        pending = self._pending
        if pending is None or self._runtimes:
            return
        self._pending = None
        thread = QThread()
        worker: _TaskWorker[T] = _TaskWorker(
            pending.generation, pending.task, pending.token
        )
        worker.moveToThread(thread)

        timer = None
        if pending.timeout_ms:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(
                lambda current=pending.generation: self._on_timeout(current)
            )

        runtime = _TaskRuntime(thread, worker, pending.token, timer)
        self._runtimes[pending.generation] = runtime
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.done.connect(thread.quit)
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(
            lambda current=pending.generation: self._release_runtime(current)
        )
        thread.finished.connect(thread.deleteLater)
        thread.start()
        if timer is not None:
            timer.start(pending.timeout_ms)

    def retry(self) -> int:
        if self._last_task is None:
            raise RuntimeError("No background task is available to retry.")
        if self._runtimes or self._pending is not None:
            raise RuntimeError(
                "The previous background task is still draining."
            )
        return self.start(self._last_task, timeout_ms=self._last_timeout_ms)

    def cancel(self) -> None:
        runtime = self._runtimes.get(self._generation)
        pending = (
            self._pending
            if self._pending is not None
            and self._pending.generation == self._generation
            else None
        )
        token = (
            runtime.token
            if runtime is not None
            else pending.token if pending else None
        )
        if token is None or self._status != TaskStatus.RUNNING:
            return
        if not token.cancel():
            return
        self._status = TaskStatus.CANCELLING
        self._emit_state()

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        """Request cancellation and wait a bounded time for worker cleanup."""
        if timeout_ms < 0:
            raise ValueError("timeout_ms must be zero or positive.")
        if self._pending is not None:
            self._pending.token.cancel()
            self._pending = None
        for runtime in self._runtimes.values():
            runtime.token.cancel()
        deadline_per_thread = (
            timeout_ms // max(1, len(self._runtimes))
            if self._runtimes
            else timeout_ms
        )
        return all(
            runtime.thread.wait(deadline_per_thread)
            for runtime in list(self._runtimes.values())
        )

    def _cancel_generation(self, generation: int) -> bool:
        if (
            self._pending is not None
            and self._pending.generation == generation
        ):
            return self._pending.token.cancel()
        runtime = self._runtimes.get(generation)
        if runtime is not None:
            return runtime.token.cancel()
        return True

    @Slot(int, object)
    def _on_progress(self, generation: int, progress: TaskProgress) -> None:
        if generation != self._generation or self._status not in {
            TaskStatus.RUNNING,
            TaskStatus.CANCELLING,
        }:
            return
        self._progress = progress
        self.progress_changed.emit(progress)
        self._emit_state()

    @Slot(int, object)
    def _on_succeeded(self, generation: int, result: T) -> None:
        if (
            generation != self._generation
            or self._status != TaskStatus.RUNNING
        ):
            return
        self._finish_timer(generation)
        self._status = TaskStatus.SUCCEEDED
        self._emit_state()
        self.succeeded.emit(result)

    @Slot(int, object)
    def _on_failed(self, generation: int, failure: TaskFailure) -> None:
        if generation != self._generation or self._status not in {
            TaskStatus.RUNNING,
            TaskStatus.CANCELLING,
        }:
            return
        self._finish_timer(generation)
        self._status = TaskStatus.FAILED
        self._emit_state(failure.user_message)
        self.failed.emit(failure)

    @Slot(int)
    def _on_cancelled(self, generation: int) -> None:
        if generation != self._generation or self._status not in {
            TaskStatus.RUNNING,
            TaskStatus.CANCELLING,
        }:
            return
        self._finish_timer(generation)
        self._status = TaskStatus.CANCELLED
        self._emit_state("Cancelled.")
        self.cancelled.emit()

    def _on_timeout(self, generation: int) -> None:
        if (
            generation != self._generation
            or self._status != TaskStatus.RUNNING
        ):
            return
        runtime = self._runtimes.get(generation)
        if runtime is None or not runtime.token.cancel():
            return
        self._status = TaskStatus.TIMED_OUT
        failure = TaskFailure("The background task timed out.", "TimeoutError")
        self._emit_state(failure.user_message)
        self.failed.emit(failure)

    def _finish_timer(self, generation: int) -> None:
        runtime = self._runtimes.get(generation)
        if runtime is not None and runtime.timer is not None:
            runtime.timer.stop()
            runtime.timer.deleteLater()
            runtime.timer = None

    def _release_runtime(self, generation: int) -> None:
        runtime = self._runtimes.pop(generation, None)
        if runtime is not None and runtime.timer is not None:
            runtime.timer.stop()
            runtime.timer.deleteLater()
        if not self._runtimes:
            if self._pending is not None:
                self._launch_pending()
                return
            self.drained.emit()
            # Failure and cancellation can be reported just before QThread
            # emits ``finished``.  Re-emit the stable state so clients can
            # enable retry only after every worker has actually drained.
            self._emit_state()

    def _emit_state(self, message: str = "") -> None:
        self.state_changed.emit(
            TaskSnapshot(
                generation=self._generation,
                status=self._status,
                progress=self._progress,
                message=message,
            )
        )


__all__ = [
    "CancellationToken",
    "QtTaskController",
    "TaskCallable",
    "TaskCancelled",
    "TaskContext",
    "TaskFailure",
    "TaskProgress",
    "TaskSnapshot",
    "TaskStatus",
]
