"""One typed vocabulary for how an executed node ended.

The durable stream has always carried the facts -- execution receipts
with exit statuses, validation receipts with findings and observations,
node-state transitions -- and the artifacts carry the rest, but every
scientifically meaningful distinction between endings lived in free
text: a non-converged scan step and a SHARK abort arrived as one blob,
an interrupted engine was an empty rule-id tuple beside an English
sentence, and a session could grep none of it. This module derives the
typed terminal state **on read**, deterministically, from the sealed
events plus the artifact's own parser facts. Nothing new is written:
the provenance of a terminal state is the event hashes and artifact
digests the derivation read, which are sealed already. A frozen
settlement-time record was considered and rejected -- a producer must
anticipate every fact a future reader wants, which is exactly how the
scan's reached-versus-planned pair stayed parsed-and-thrown-away.

Both consumers -- the ``inspect_run_outcome`` tool a planning session
calls, and the goal loop's wake context -- call the same derivation, so
what a session reads and what the loop acts on cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

#: The one program-neutral validity finding: a converged search landed on
#: a stationary point of the wrong order for what the approved plan
#: declared -- a minimum with an imaginary mode, a transition state with
#: none or several. Declared by the jobtype the human approved, never by
#: prose, and counted with the same 20 cm-1 convention the
#: thermochemistry uses for numerical noise.
STATIONARY_POINT_ORDER_FINDING = "result.stationary_point_order"

#: Modes above this magnitude below zero are imaginary in earnest;
#: smaller ones are the rotor and translation noise thermochemistry
#: already treats as zero.
CONSEQUENTIAL_IMAGINARY_MODE_CM1 = -20.0


def expected_imaginary_mode_count(jobtype: str) -> int | None:
    """How many imaginary modes the declared jobtype promises: one for a
    transition-state search, none for a minimum, and no promise at all
    for a jobtype that computes no Hessian or makes no claim."""

    if jobtype == "ts":
        return 1
    if jobtype in {"opt", "hess", "freq"}:
        return 0
    return None


def consequential_imaginary_mode_count(
    frequencies: tuple[float, ...] | list[float] | None,
) -> int | None:
    """The imaginary modes that count, or None when nothing was printed."""

    if not frequencies:
        return None
    values = []
    for value in frequencies:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number != number:  # NaN
            return None
        values.append(number)
    return sum(
        1 for value in values if value < CONSEQUENTIAL_IMAGINARY_MODE_CM1
    )


def stationary_point_order_finding(
    jobtype: str, observed_imaginary_modes: int | None
) -> str:
    """The finding to record, or "" when the result matches its claim or
    makes none."""

    expected = expected_imaginary_mode_count(jobtype)
    if expected is None or observed_imaginary_modes is None:
        return ""
    return (
        ""
        if observed_imaginary_modes == expected
        else STATIONARY_POINT_ORDER_FINDING
    )


#: The shared, program-neutral endings. Layer 2 -- the program-native
#: dotted finding codes and native-failure classes -- rides beneath
#: every one of them, verbatim.
NODE_TERMINAL_STATES = (
    "validated",
    "engine_complete_unvalidated",
    "failed_native",
    "failed_nonconverged_scf",
    "failed_nonconverged_geometry",
    "failed_nonconverged_scan_step",
    "failed_wrong_stationary_point",
    "timeout_terminated",
    "timeout_ambiguous",
    "memory_limit_terminated",
    "memory_limit_ambiguous",
    "external_signal_terminated",
    "external_signal_ambiguous",
    "interrupted_mid_engine",
    "launch_failed",
    "launch_ambiguous",
    "blocked_dependency",
    "refused_admission",
    "not_launched",
    "cancelled",
)


@dataclass(frozen=True)
class NodeTerminalStateV1:
    """How one node ended, with the facts a revision needs."""

    node_id: str
    program: str
    jobtype: str
    state: str
    #: Layer 2: the program-native dotted codes, verbatim.
    native_findings: tuple[str, ...] = ()
    #: Structured finding bodies where the program produced them
    #: (xTB receipt audits, PySCF result validation): mappings of
    #: rule_id/field/expected/observed/evidence_ref.
    structured_findings: tuple[Mapping[str, Any], ...] = ()
    #: The engine's own words, bounded and redacted upstream.
    engine_lines: tuple[str, ...] = ()
    native_failure_class: str = ""
    converged: bool | None = None
    scan_steps_reached: int | None = None
    scan_steps_planned: int | None = None
    wall_seconds: float | None = None
    wrapper_exit_status: int | None = None
    child_exit_status: int | None = None
    #: Event hashes and artifact digests this derivation read -- the
    #: citation a revision carries.
    evidence_event_hashes: tuple[str, ...] = ()
    evidence_artifact_sha256s: tuple[str, ...] = ()
    #: Host-detected surprises recorded beneath this node's verdict:
    #: signal id, status, the numbers that tripped it, the receipt
    #: digest. Empty for streams that predate the sensor.
    anomalies: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.state not in NODE_TERMINAL_STATES:
            raise ValueError(
                f"unsupported node terminal state: {self.state!r}"
            )

    def public_record(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "program": self.program,
            "jobtype": self.jobtype,
            "state": self.state,
            "native_findings": self.native_findings,
            "structured_findings": tuple(
                dict(item) for item in self.structured_findings
            ),
            "engine_lines": self.engine_lines,
            "native_failure_class": self.native_failure_class,
            "converged": self.converged,
            "scan_steps_reached": self.scan_steps_reached,
            "scan_steps_planned": self.scan_steps_planned,
            "wall_seconds": self.wall_seconds,
            "wrapper_exit_status": self.wrapper_exit_status,
            "child_exit_status": self.child_exit_status,
            "evidence_event_hashes": self.evidence_event_hashes,
            "evidence_artifact_sha256s": self.evidence_artifact_sha256s,
            "anomalies": tuple(dict(item) for item in self.anomalies),
        }


@dataclass(frozen=True)
class RunOutcomeV1:
    """One run's endings plus the budget facts the goal loop reads."""

    run_id: str
    workflow_id: str
    plan_sha256: str
    approval_sha256: str
    workflow_state: str
    nodes: tuple[NodeTerminalStateV1, ...] = ()
    engine_calls_consumed: int = 0
    engine_wall_seconds: float = 0.0
    stream_head_hash: str = ""
    stream_tail_hash: str = ""

    def public_record(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "workflow_state": self.workflow_state,
            "nodes": tuple(item.public_record() for item in self.nodes),
            "engine_calls_consumed": self.engine_calls_consumed,
            "engine_wall_seconds": self.engine_wall_seconds,
        }


def _wall_seconds(started_at: str, finished_at: str) -> float | None:
    from datetime import datetime

    try:
        start = datetime.fromisoformat(str(started_at))
        end = datetime.fromisoformat(str(finished_at))
    except (TypeError, ValueError):
        return None
    seconds = (end - start).total_seconds()
    return seconds if seconds >= 0 else None


def _structured_findings(
    observations: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Collect the finding bodies xTB and PySCF already persist.

    They were reduced to bare rule ids at the evaluation boundary; the
    bodies survive in the observations bag and, for xTB, in the receipt
    artifact itself. This reads what is durable rather than asking any
    producer to change.
    """

    bodies: list[Mapping[str, Any]] = []
    validation = observations.get("result_validation")
    if isinstance(validation, Mapping):
        for item in validation.get("findings") or ():
            if isinstance(item, Mapping) and "rule_id" in item:
                bodies.append(dict(item))
    xtb = observations.get("xtb")
    if isinstance(xtb, Mapping):
        for item in xtb.get("findings") or ():
            if isinstance(item, Mapping) and "rule_id" in item:
                bodies.append(dict(item))
    return tuple(bodies)


def _native_failure(
    observations: Mapping[str, Any],
) -> tuple[str, tuple[str, ...]]:
    for key in ("orca", "xtb", "gaussian", "pyscf"):
        section = observations.get(key)
        if not isinstance(section, Mapping):
            continue
        summary = section.get("native_failure")
        if isinstance(summary, Mapping):
            return (
                str(summary.get("error_class") or ""),
                tuple(str(line) for line in summary.get("engine_lines") or ()),
            )
        for row in section.get("outputs") or ():
            if isinstance(row, Mapping) and isinstance(
                row.get("native_failure"), Mapping
            ):
                summary = row["native_failure"]
                return (
                    str(summary.get("error_class") or ""),
                    tuple(
                        str(line) for line in summary.get("engine_lines") or ()
                    ),
                )
    return ("", ())


def _artifact_scan_facts(
    validation_record: Mapping[str, Any],
) -> tuple[bool | None, int | None, int | None, tuple[str, ...]]:
    """Read convergence and scan facts from the node's own artifact.

    Derive-on-read means a fact the producer never anticipated is still
    reachable: the artifact is re-parsed under its recorded digest, and
    a moved or altered file simply yields absent facts, never wrong
    ones.
    """

    converged: bool | None = None
    reached: int | None = None
    planned: int | None = None
    digests: list[str] = []
    for artifact in validation_record.get("output_artifacts") or ():
        if not isinstance(artifact, Mapping):
            continue
        if artifact.get("kind") != "orca_output":
            continue
        path = Path(str(artifact.get("path") or ""))
        sha256 = str(artifact.get("sha256") or "")
        if not path.is_file():
            continue
        try:
            from chemsmart.agent._contracts import file_sha256

            if sha256 and file_sha256(path) != sha256:
                continue
            from chemsmart.io.orca.output import ORCAOutput

            output = ORCAOutput(filename=path)
            converged = output.converged
            reached = output.scan_step_count or None
            coordinate = output.scan_coordinate
            planned = int(coordinate["points"]) if coordinate else None
            digests.append(sha256)
            break
        except (AttributeError, OSError, TypeError, ValueError):
            continue
    return converged, reached, planned, tuple(digests)


def _classify_failure(
    *,
    jobtype: str,
    findings: tuple[str, ...],
    native_class: str,
    converged: bool | None,
    reached: int | None,
    planned: int | None,
) -> str:
    if "execution.process.timeout" in findings:
        return (
            "timeout_ambiguous"
            if "execution.process.termination_ambiguous" in findings
            else "timeout_terminated"
        )
    if "execution.process.external_signal" in findings:
        return (
            "external_signal_ambiguous"
            if "execution.process.termination_ambiguous" in findings
            else "external_signal_terminated"
        )
    if "execution.process.memory_limit_exceeded" in findings:
        return (
            "memory_limit_ambiguous"
            if "execution.process.termination_ambiguous" in findings
            else "memory_limit_terminated"
        )
    if "execution.process.launch_failed" in findings:
        return "launch_failed"
    nonconverged = (
        converged is False
        or any(
            item.endswith(".optimization_not_converged")
            or item.endswith(".scan_step_not_converged")
            for item in findings
        )
        or native_class == "geometry_optimization"
    )
    if nonconverged:
        if jobtype == "scan" or (reached is not None and planned is not None):
            return "failed_nonconverged_scan_step"
        return "failed_nonconverged_geometry"
    if native_class == "scf_convergence":
        return "failed_nonconverged_scf"
    # A search that converged cleanly onto the wrong kind of stationary
    # point is not a generic native failure, and calling it one loses the
    # only thing a reader can act on. A transition-state search that
    # returns no imaginary mode has found a minimum; one that returns
    # several has found a higher-order saddle. Both are answered by
    # stepping along a mode and searching again, and neither is
    # distinguishable from a crashed job under "failed_native".
    if any(
        item.endswith(".ts_imaginary_mode_count")
        or item == STATIONARY_POINT_ORDER_FINDING
        for item in findings
    ):
        return "failed_wrong_stationary_point"
    return "failed_native"


def read_run_events(path: str | Path) -> tuple[Any, ...]:
    """Read a run's sealed events for derivation, from any session.

    The event store binds reads to its own session id; a terminal-state
    derivation is a read over someone else's finished run, so it parses
    the sealed lines directly. Each line still constructs the typed
    event record, so a malformed stream refuses rather than half-parses.
    """

    import json

    from chemsmart.agent.runtime.events import RuntimeEvent

    events: list[Any] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        events.append(RuntimeEvent(**json.loads(text)))
    return tuple(events)


def derive_run_outcome(events: tuple[Any, ...]) -> RunOutcomeV1:
    """Derive one run's typed endings from its sealed event stream."""

    from chemsmart.agent.runtime.reducer import replay_events

    state = replay_events(events)
    run_records = getattr(state, "workflow_run_records", {}) or {}
    if len(run_records) != 1:
        raise ValueError(
            "a run directory records exactly one workflow run; found "
            f"{len(run_records)}"
        )
    ((run_id, run_record),) = run_records.items()
    node_rows = tuple(run_record.get("nodes") or ())

    execution_by_node: dict[str, Mapping[str, Any]] = {}
    validation_by_node: dict[str, Mapping[str, Any]] = {}
    anomalies_by_node: dict[str, list[dict[str, Any]]] = {}
    event_hashes_by_node: dict[str, list[str]] = {}
    reservations: set[str] = set()
    for event in events:
        payload = event.payload or {}
        node_id = str(
            payload.get("node_id")
            or (payload.get("record") or {}).get("node_id")
            or ""
        )
        if not node_id:
            continue
        if event.kind == "program_execution_observed":
            execution_by_node[node_id] = payload.get("record") or {}
            event_hashes_by_node.setdefault(node_id, []).append(
                event.event_hash
            )
        elif event.kind == "program_result_verified":
            validation_by_node[node_id] = payload.get("record") or {}
            event_hashes_by_node.setdefault(node_id, []).append(
                event.event_hash
            )
        elif event.kind == "anomaly_observed":
            record = payload.get("record") or {}
            anomalies_by_node.setdefault(node_id, []).append(
                {
                    "signal_id": str(
                        payload.get("signal_id")
                        or record.get("signal_id")
                        or ""
                    ),
                    "status": str(
                        payload.get("status") or record.get("status") or ""
                    ),
                    "values": dict(record.get("values") or {}),
                    "receipt_sha256": str(payload.get("receipt_sha256") or ""),
                }
            )
            event_hashes_by_node.setdefault(node_id, []).append(
                event.event_hash
            )
        elif event.kind == "workflow_node_launch_reserved":
            reservations.add(node_id)
            event_hashes_by_node.setdefault(node_id, []).append(
                event.event_hash
            )
        elif event.kind == "workflow_node_state_changed":
            event_hashes_by_node.setdefault(node_id, []).append(
                event.event_hash
            )

    nodes: list[NodeTerminalStateV1] = []
    engine_calls = 0
    engine_wall = 0.0
    for row in node_rows:
        node_id = str(row.get("node_id") or "")
        node_state = str(row.get("state") or "")
        rule_ids = tuple(
            str(item) for item in row.get("failure_rule_ids") or ()
        )
        execution = execution_by_node.get(node_id, {})
        validation = validation_by_node.get(node_id, {})
        findings = tuple(
            str(item)
            for item in (
                *(execution.get("findings") or ()),
                *(validation.get("findings") or ()),
                *rule_ids,
            )
        )
        observations = validation.get("observations") or {}
        native_class, engine_lines = _native_failure(observations)
        converged, reached, planned, artifact_digests = (
            _artifact_scan_facts(validation)
            if validation
            else (None, None, None, ())
        )
        program = str(
            validation.get("program") or execution.get("program") or ""
        )
        jobtype = str(validation.get("jobtype") or "")
        wall = None
        if execution:
            engine_calls += 1
            wall = _wall_seconds(
                execution.get("started_at") or "",
                execution.get("finished_at") or "",
            )
            if wall:
                engine_wall += wall

        # A receipt is the stronger fact than the state row: a stream
        # can hold a terminal receipt before (or without) the row's own
        # transition, and the receipt's execution_state is what the
        # engine actually reached.
        effective_state = node_state
        if execution:
            receipt_state = str(execution.get("execution_state") or "")
            if receipt_state in {
                "validated",
                "engine_complete",
                "failed",
                "ambiguous",
            }:
                effective_state = receipt_state
        if effective_state == "validated":
            terminal = "validated"
        elif effective_state == "engine_complete" and not (
            findings or node_state == "failed"
        ):
            terminal = "engine_complete_unvalidated"
        elif effective_state in {"engine_complete", "failed"}:
            # The engine finished and the validator then refused the
            # result: the receipt says engine_complete, the node row
            # says failed, and the findings say why. Preferring the
            # receipt's word here labelled a live saddle -- one
            # imaginary mode on an opt+freq, the rule firing exactly as
            # designed -- "unvalidated", which no revision can answer,
            # and the goal returned to the human instead of recovering.
            terminal = _classify_failure(
                jobtype=jobtype,
                findings=findings,
                native_class=native_class,
                converged=converged,
                reached=reached,
                planned=planned,
            )
        elif effective_state == "ambiguous":
            if "execution.process.timeout" in findings:
                terminal = "timeout_ambiguous"
            elif "execution.process.external_signal" in findings:
                terminal = "external_signal_ambiguous"
            else:
                terminal = "launch_ambiguous"
        elif effective_state == "running":
            # A reservation with no receipt: the prior invocation died
            # mid-engine. The durable stream is the proof; no prose or
            # in-memory field is consulted.
            terminal = (
                "interrupted_mid_engine"
                if node_id in reservations
                else "launch_ambiguous"
            )
        elif effective_state == "blocked":
            terminal = (
                "blocked_dependency"
                if any(
                    item.startswith("workflow.dependency.")
                    for item in rule_ids
                )
                else "refused_admission"
            )
        elif effective_state == "cancelled":
            # The durable row carries the human's withdrawal; before it
            # did, a cancelled node derived as not_launched and the
            # withdrawn grant left no typed trace.
            terminal = "cancelled"
        else:
            terminal = "not_launched"

        nodes.append(
            NodeTerminalStateV1(
                node_id=node_id,
                program=program,
                jobtype=jobtype,
                state=terminal,
                native_findings=findings,
                structured_findings=_structured_findings(observations),
                engine_lines=engine_lines,
                native_failure_class=native_class,
                converged=converged,
                scan_steps_reached=reached,
                scan_steps_planned=planned,
                wall_seconds=wall,
                wrapper_exit_status=execution.get("wrapper_exit_status"),
                child_exit_status=execution.get("child_exit_status"),
                evidence_event_hashes=tuple(
                    event_hashes_by_node.get(node_id, ())
                ),
                evidence_artifact_sha256s=artifact_digests,
                anomalies=tuple(anomalies_by_node.get(node_id, ())),
            )
        )

    return RunOutcomeV1(
        run_id=run_id,
        workflow_id=str(run_record.get("workflow_id") or ""),
        plan_sha256=str(run_record.get("plan_sha256") or ""),
        approval_sha256=str(run_record.get("approval_sha256") or ""),
        workflow_state=str(run_record.get("state") or ""),
        nodes=tuple(nodes),
        engine_calls_consumed=engine_calls,
        engine_wall_seconds=engine_wall,
        stream_head_hash=events[0].event_hash if events else "",
        stream_tail_hash=events[-1].event_hash if events else "",
    )


__all__ = [
    "NODE_TERMINAL_STATES",
    "NodeTerminalStateV1",
    "RunOutcomeV1",
    "derive_run_outcome",
]
