"""QThread worker wrapping the in-process agent loop (plan Phase 4).

Drives the same :class:`chemsmart.agent.core.AgentSession` the TUI uses — no
subprocess boundary for the agent loop itself. Long-running ``run``/``run_loop``
calls execute on a worker thread and stream state back via Qt signals, the way
the TUI marshals with ``call_from_thread``. The risky-tool gate
(``_RISKY_TOOLS``) is inherited from the core; the GUI adds no bypass and, in
v1, no ``submit_hpc`` approval path.

This module is a thin scaffold; the exact ``run()`` signal shapes are wired
against the real ``AgentSession`` API in Phase 4.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal


class AgentWorker(QObject):
    """Runs one agent request and emits streamed updates + a final result."""

    step = Signal(dict)  # intermediate tool-loop state
    finished = Signal(dict)  # final assistant turn
    failed = Signal(str)

    def __init__(self, session_root: Path | None = None) -> None:
        super().__init__()
        self._session_root = session_root
        self._cancelled = False

    def cancel(self) -> None:
        """Request cooperative cancellation between tool-loop steps."""
        self._cancelled = True

    def run_request(self, request: str) -> None:
        """Execute ``request`` against a dry-submit AgentSession.

        Phase 4 connects this to ``AgentSession.run(request, dry_submit=True)``
        and forwards decision-log entries through :attr:`step`.
        """
        try:
            from chemsmart.agent.core import (  # noqa: F401
                AgentSession,
                _default_session_root,
            )

            # Placeholder: real streaming wiring lands in Phase 4.
            self.finished.emit({"request": request, "status": "not_wired"})
        except Exception as exc:
            self.failed.emit(str(exc))
