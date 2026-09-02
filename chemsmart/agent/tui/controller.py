"""Provider-neutral controller shared by the Textual presentation layer.

The terminal interface is a view of the goal driver: planning is the
driver's plan phase, the human's /approve is the one decision the driver
consumes, and everything after it -- execution, reading the outcome,
recovery cycles within the approved budgets, settlement -- is the same
step machine ``chemsmart agent goal`` runs. What the controller adds is
only what a screen needs: UI-thread guards that refuse before any banner
appears, worker-thread bodies for the heavy host calls, and durable
per-review decision scopes so a restart can never replay an approval.
"""

from __future__ import annotations

import getpass
import threading
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from chemsmart.agent._contracts import ContractError

if TYPE_CHECKING:
    from chemsmart.agent.driver import GoalDriver, GoalLoopResultV1
    from chemsmart.agent.execution import WorkflowExecutionReviewV1
    from chemsmart.agent.executor import WorkflowExecutionResultV1
    from chemsmart.agent.live_session import LiveAgentSessionResultV1


class AgentTuiPhase(str, Enum):
    READY = "ready"
    PLANNING = "planning"
    PREVIEW_READY = "preview-ready"
    REQUEST_REVIEWED = "request-reviewed"
    EXECUTING = "executing"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass(frozen=True)
class AgentSessionConfigV1:
    workspace: Path
    secret_file: Path | None = None
    provider: str | None = None
    provider_config_file: Path | None = None
    execution_envelope_file: Path | None = None
    review_file: Path | None = None
    identity_manifest: Path | None = None
    analysis_completion_file: Path | None = None
    #: How many host-admitted recovery cycles one /approve covers. The
    #: budgets in the envelope bound them; this is the revision count.
    max_revisions: int = 5

    def __post_init__(self) -> None:
        workspace = self.workspace.expanduser().resolve()
        if not workspace.is_dir() or workspace.is_symlink():
            raise ContractError("TUI workspace must be a current directory")
        secret = self.secret_file
        if secret is not None:
            secret = secret.expanduser().resolve()
            if not secret.is_file() or secret.is_symlink():
                raise ContractError(
                    "TUI secret file must be a current regular file"
                )
        review = self.review_file
        envelope = self.execution_envelope_file
        if envelope is None and review is not None:
            raise ContractError(
                "a review export path requires an execution envelope"
            )
        if envelope is not None:
            envelope = envelope.expanduser().resolve()
            if not envelope.is_file() or envelope.is_symlink():
                raise ContractError(
                    "TUI execution envelope must be a current regular file"
                )
            if review is not None:
                review = review.expanduser()
                if not review.is_absolute():
                    raise ContractError(
                        "TUI review export file must be absolute"
                    )
        object.__setattr__(self, "workspace", workspace)
        object.__setattr__(self, "secret_file", secret)
        object.__setattr__(self, "execution_envelope_file", envelope)
        object.__setattr__(self, "review_file", review)


class AgentTuiController:
    """Human-driven view of the goal driver; provider turns cannot approve.

    The guards run on the UI thread (`begin_planning`, `begin_execution`) so
    a refused action refuses *before* any banner or worker starts; the heavy
    host calls run on a worker thread (`run_planning`, `execute_begun`).
    """

    def __init__(self, config: AgentSessionConfigV1) -> None:
        self.config = config
        self.phase = AgentTuiPhase.READY
        self.task = ""
        self.review_copy_note = ""
        self.plan_result: LiveAgentSessionResultV1 | None = None
        self.prepared_execution: WorkflowExecutionReviewV1 | None = None
        self.execution_result: WorkflowExecutionResultV1 | None = None
        self.settlement: GoalLoopResultV1 | None = None
        self.execution_id = ""
        self.execution_run_directory: Path | None = None
        #: Set by the view when the human double-escapes a planning session.
        self.cancel_planning = threading.Event()
        #: Set by the view to observe the planning run directory (event tail).
        self.on_run_directory: Callable[[Path], None] | None = None
        self.driver: GoalDriver | None = None
        self._begun_execution: WorkflowExecutionReviewV1 | None = None

    # -- the driver --------------------------------------------------------

    def _session_kwargs(self) -> dict[str, Any]:
        from chemsmart.agent.identity import (
            load_approved_molecular_input_manifest,
        )

        approved_inputs = (
            load_approved_molecular_input_manifest(
                self.config.identity_manifest,
                workspace=self.config.workspace,
            )
            if self.config.identity_manifest is not None
            else ()
        )
        return {
            "secret_file": self.config.secret_file,
            "approved_molecular_inputs": approved_inputs,
            "on_run_directory": self.on_run_directory,
            "should_stop": self.cancel_planning.is_set,
        }

    def _driver_kwargs(self, *, goal_id: str) -> dict[str, Any]:
        return {
            "workspace": self.config.workspace,
            "execution_envelope_file": self.config.execution_envelope_file,
            "goal_id": goal_id,
            "granted_by": getpass.getuser() or "local-user",
            "max_revisions": self.config.max_revisions,
            "provider": (
                self.config.provider.lower() if self.config.provider else None
            ),
            "provider_config_file": self.config.provider_config_file,
            "analysis_completion_file": self.config.analysis_completion_file,
            "resolve_review": self._resolve_review,
            "session_kwargs": self._session_kwargs(),
        }

    # -- planning ----------------------------------------------------------

    def begin_planning(self, task: str) -> str:
        """UI-thread guard: validate and take the planning phase now."""

        normalized = str(task).strip()
        if not normalized:
            raise ContractError("agent task must not be empty")
        self.cancel_planning.clear()
        self.phase = AgentTuiPhase.PLANNING
        self.task = normalized
        return normalized

    def run_planning(self, task: str) -> LiveAgentSessionResultV1:
        """Worker-thread body: the driver's plan phase."""

        from chemsmart.agent.driver import GoalDriver

        self.execution_id = "tui-" + uuid.uuid4().hex
        try:
            driver = GoalDriver(
                task=task, **self._driver_kwargs(goal_id=self.execution_id)
            )
            driver.step()
        except Exception:
            self.phase = AgentTuiPhase.ERROR
            raise
        self.driver = driver
        result = driver.session
        self.plan_result = result
        self.prepared_execution = getattr(result, "prepared_execution", None)
        self.execution_result = None
        self.settlement = driver.result
        self.review_copy_note = ""
        if self.prepared_execution is not None:
            try:
                self._ensure_review_copy(self.prepared_execution)
            except Exception as exc:  # noqa: BLE001 - a copy failure is a
                # note, never a lost planning session.
                self.review_copy_note = (
                    "The workspace review copy could not be written "
                    f"({exc}); resume will not re-present this review."
                )
        if self.prepared_execution is not None and driver.phase == "decide":
            self.phase = AgentTuiPhase.REQUEST_REVIEWED
        elif result.terminal_state in {"complete", "planned"}:
            self.phase = AgentTuiPhase.COMPLETE
        elif result.terminal_state == "cancelled":
            self.phase = AgentTuiPhase.READY
        else:
            self.phase = AgentTuiPhase.BLOCKED
        return result

    # -- decision ----------------------------------------------------------

    def decline(self) -> None:
        """Decline the displayed workflow without creating run authority."""

        driver = self.driver
        if driver is not None and driver.phase == "decide":
            # The goal's one decision is "no": the driver settles it
            # returned_to_human so the story ends in a typed state.
            driver.initial_decision = "deny"
            driver.step()
            self.settlement = driver.result
        self.prepared_execution = None
        self.phase = (
            AgentTuiPhase.PREVIEW_READY
            if self.plan_result is not None
            else AgentTuiPhase.READY
        )

    def _review_copy_path(self, review: WorkflowExecutionReviewV1) -> Path:
        return (
            self.config.workspace
            / ".chemsmart-agent"
            / "reviews"
            / f"{review.review_sha256[:16]}.json"
        )

    def _ensure_review_copy(self, review: WorkflowExecutionReviewV1) -> Path:
        from chemsmart.agent.live_session import (
            write_workflow_execution_review,
        )

        path = self._review_copy_path(review)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.exists():
            write_workflow_execution_review(review, path)
        return path

    def _decision_scope(self, review: WorkflowExecutionReviewV1) -> Path:
        # One scope per REVIEW, not per approval id: the deterministic
        # resolution identity inside a shared decision log is what refuses a
        # second approve of the same review across process restarts.
        return (
            self.config.workspace
            / ".chemsmart-agent"
            / "decisions"
            / review.review_sha256[:16]
        )

    def _resolve_review(
        self,
        *,
        review_file: Path,
        workspace: Path,
        decision: str,
        actor: str,
        approval_id: str,
    ) -> tuple[str, Path]:
        """The driver's decision seam, writing the TUI's durable scope.

        Cycle 1 is the human's /approve under the execution id; a later
        cycle is the host-admitted revision under the same grant, and
        its scope is the review it decides on, exactly as for cycle 1.
        """

        from chemsmart.agent.live_session import (
            inspect_workflow_execution_replay,
            resolve_workflow_execution_review,
        )

        report = inspect_workflow_execution_replay(
            review_file=review_file, workspace=workspace, task_spec_sha256=""
        )
        review_sha256 = str(report["review_sha256"])
        scope = (
            self.config.workspace
            / ".chemsmart-agent"
            / "decisions"
            / review_sha256[:16]
        )
        scope.mkdir(parents=True, exist_ok=True, mode=0o700)
        chosen = (
            self.execution_id
            if approval_id.endswith("-cycle-1") and self.execution_id
            else approval_id
        )
        resolve_workflow_execution_review(
            review_file=review_file,
            reviewed_sha256=review_sha256,
            decision=decision,
            actor=actor,
            output_file=(
                scope / "bundle.json" if decision == "approve" else None
            ),
            decision_log=scope / "decisions.jsonl",
            approval_id=chosen,
        )
        return review_sha256, scope / "bundle.json"

    def restore_prepared_execution(
        self, review: WorkflowExecutionReviewV1
    ) -> None:
        """Re-present a stored review for one fresh human decision."""

        if self.phase in (AgentTuiPhase.PLANNING, AgentTuiPhase.EXECUTING):
            raise ContractError(
                "finish the current host operation before restoring a review"
            )
        self.prepared_execution = review
        self.driver = None
        self.phase = AgentTuiPhase.REQUEST_REVIEWED

    def begin_execution(self) -> WorkflowExecutionReviewV1:
        """UI-thread guard: consume the pending authority before any launch.

        A failed run remains an observed run; rerunning it requires another
        explicit plan/review act.
        """

        prepared = self.prepared_execution
        if (
            prepared is None
            or self.phase is not AgentTuiPhase.REQUEST_REVIEWED
        ):
            raise ContractError(
                "finish planning and review the displayed ChemSmart "
                "workflow first"
            )
        from chemsmart.agent.live_session import spent_workflow_approval_ids

        decisions = self._decision_scope(prepared) / "decisions.jsonl"
        already_decided = False
        if decisions.exists():
            recorded = decisions.read_text(encoding="utf-8")
            already_decided = (
                '"decision":"approve"' in recorded
                or '"decision": "approve"' in recorded
            )
        if already_decided or spent_workflow_approval_ids(
            self.config.workspace, prepared.review_sha256
        ):
            raise ContractError(
                "this exact reviewed workflow was already approved in this "
                "workspace; plan it again, or record a deliberate second "
                "decision with 'chemsmart agent review'"
            )
        if self.driver is None or self.driver.phase != "decide":
            self.execution_id = "tui-" + uuid.uuid4().hex
        self.execution_run_directory = (
            self.config.workspace
            / ".chemsmart-agent"
            / "goals"
            / self.execution_id
            / "runs"
            / "cycle-1"
        )
        self.phase = AgentTuiPhase.EXECUTING
        self.prepared_execution = None
        self._begun_execution = prepared
        return prepared

    def execute_begun(self) -> WorkflowExecutionResultV1:
        """Worker-thread body: decide durably, then drive to settlement.

        Every TUI approval leaves the same evidence the file pipeline
        leaves: a decision log, a one-shot bundle, and a workspace
        consumption ledger -- so the one-shot rule survives a restart.
        After the approved run the driver reads its outcome and, within
        the approved budgets, wakes recovery cycles exactly as
        ``chemsmart agent goal`` does.
        """

        from chemsmart.agent.driver import GoalDriver

        prepared = self._begun_execution
        if prepared is None or self.execution_run_directory is None:
            raise ContractError("no begun execution to run")
        self._begun_execution = None
        try:
            review_copy = self._ensure_review_copy(prepared)
            driver = self.driver
            if driver is None or driver.phase != "decide":
                driver = GoalDriver.from_review(
                    review_file=review_copy,
                    task_spec_sha256=getattr(prepared, "task_spec_sha256", ""),
                    task=self.task,
                    **self._driver_kwargs(goal_id=self.execution_id),
                )
                self.driver = driver
            first_result: WorkflowExecutionResultV1 | None = None
            while driver.phase not in {"settled", "parked"}:
                driver.step()
                if first_result is None and driver.execute_result is not None:
                    first_result = driver.execute_result
        except Exception:
            self.phase = AgentTuiPhase.ERROR
            raise
        self.settlement = driver.result
        result = driver.execute_result or first_result
        if result is None:
            raise ContractError(
                "the goal settled without an executed run: "
                + "; ".join(driver.result.reasons if driver.result else ())
            )
        self.execution_result = result
        self.phase = (
            AgentTuiPhase.COMPLETE
            if str(getattr(result, "status", "")) == "completed"
            else AgentTuiPhase.BLOCKED
        )
        return result


__all__ = [
    "AgentSessionConfigV1",
    "AgentTuiController",
    "AgentTuiPhase",
]
