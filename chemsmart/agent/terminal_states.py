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

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

#: The one program-neutral validity finding: a converged search landed on
#: a stationary point of the wrong order for what the approved plan
#: declared -- a minimum with an imaginary mode, a transition state with
#: none or several. Declared by the jobtype the human approved, never by
#: prose, and counted with the same 20 cm-1 convention the
#: thermochemistry uses for numerical noise.
STATIONARY_POINT_ORDER_FINDING = "result.stationary_point_order"

#: The same rule applied to the geometry a job was *handed*, where its job
#: type promises something about it: an intrinsic reaction coordinate
#: leaves a first-order saddle of the surface it walks, so the spectrum the
#: run took there must show exactly one imaginary mode. Its own id, because
#: the order of a start and the order of the structure a result ends on
#: are different claims about different geometries.
START_POINT_ORDER_FINDING = "result.start_point_order"

#: Anomalies earlier cycles of a goal recorded, handed to a run's host
#: through its own run directory so the completion receipt it mints can
#: carry them (a dispatched job reads the same file).
PRIOR_ANOMALIES_FILE = "prior-anomalies.json"

#: Node endings a revision can answer with ordinary work. The repair
#: menu in the driver and the recovery guide both key on this set, so a
#: new repairable ending is added here once.
REPAIRABLE_NODE_STATES = frozenset(
    {
        "failed_wrong_stationary_point",
        "failed_nonconverged_scf",
        "failed_nonconverged_geometry",
        "failed_nonconverged_scan_step",
        "failed_nonconverged_excited_state",
        "failed_nonconverged_correlation",
        "timeout_terminated",
        "memory_limit_terminated",
        "failed_native",
    }
)

#: The native failure classes that are themselves statements about
#: convergence. A class that names a cause outranks the convergence flag
#: it leaves behind; these keep their own meaning. The response solver
#: and the coupled-cluster amplitudes joined the SCF and the optimiser
#: when PySCF's td and correlated stages became executable (contract v5):
#: an unconverged Davidson root or an unconverged amplitude set is a
#: convergence statement about a stage whose SCF converged, and the word
#: ``failed_nonconverged_scf`` would be false for such a run.
_CONVERGENCE_FAILURE_CLASSES = frozenset(
    {
        "scf_convergence",
        "geometry_optimization",
        "excited_state_convergence",
        "correlation_convergence",
    }
)

#: What a program's output falls back to when no rule matched: "it ended
#: badly" and "it stopped". Both are the ``next()`` default in
#: ``io/native_failure._summarize``, so neither is a diagnosis, and
#: neither may outrank one.
#:
#: Earned by getting this wrong. ORCA reports a non-converged relaxed
#: scan step by failing to store the step's geometry and then aborting
#: inside its property module with "ERROR (SHARK): Failed to read input
#: file", which matches no rule and lands on ``native_runtime``. Read as
#: a cause, that turned a convergence failure into a crash. Probed at
#: one rank with no MPI in the run at all, the same input fails at the
#: same step, and the output says why in words: "The optimization did
#: not converge but reached the maximum number of" steps.
#:
#: PySCF's ``driver_exception`` is deliberately not here: it is a
#: ``.get()`` default for an unrecognised stage rather than this
#: fallback, and no run has shown it masking a convergence failure.
_UNDIAGNOSED_FAILURE_CLASSES = frozenset(
    {"native_runtime", "incomplete_output"}
)

#: Modes above this magnitude below zero are imaginary in earnest;
#: smaller ones are the rotor and translation noise thermochemistry
#: already treats as zero.
CONSEQUENTIAL_IMAGINARY_MODE_CM1 = -20.0


#: geomeTRIC's ``convergence_gmax`` (Eh/Bohr), the optimiser's own word
#: for "the gradient is zero".  It lives here, beside the imaginary-mode
#: convention, because both are program-neutral physics the host reports
#: facts through, and two organs now read this one: the run sensor that
#: raises ``stationary_point.gradient_above_optimizer_criterion`` and the
#: characterisation that says what a structure is.
#:
#: A Hessian computed at a geometry whose gradient exceeds it is an
#: observation with standing and **never** a verdict on the run: PySCF's
#: harmonic analysis projects rotations out, so the projected spectrum at
#: a non-stationary point can be entirely real (the archived
#: stretched-water Hessian: three real modes at max|g| = 0.0185 Eh/Bohr),
#: and asking for a Hessian off a stationary point is legitimate (owner
#: ruling, 2026-09-12).  What that ruling governs is the result's
#: validity.  Calling such a point "a minimum" or "a first-order saddle"
#: is a different act -- a host-rendered claim about a structure -- and it
#: is refused, because an order is a property of a *stationary* point and
#: the numbers stay readable either way.
HESS_STATIONARITY_GRADIENT_EH_PER_BOHR = 4.5e-4


#: How many imaginary modes each job type promises: one for a
#: transition-state search, none for a minimum or a Hessian, and no
#: promise at all for a job type that is absent here -- a scan samples a
#: surface whose points are not stationary, an IRC walks a path, and
#: neither makes the claim. This mapping is the promise itself, and
#: eleven copies of its two halves used to be spread over the driver,
#: the workspace record, the sensors, the capability cells and the
#: geometry handoff.
STATIONARY_POINT_PROMISES: Mapping[str, int] = MappingProxyType(
    {"freq": 0, "hess": 0, "opt": 0, "ts": 1}
)

#: What a job type promises about the geometry it was *handed*, judged on
#: the spectrum a reader serves as ``trajectory_start_frequencies``: an
#: IRC leaves a first-order saddle of the surface it walks. A reader that
#: serves no such spectrum (ORCA's IRC log prints none) makes no claim.
START_POINT_PROMISES: Mapping[str, int] = MappingProxyType({"irc": 1})

#: Of those, the job types that search for the structure rather than
#: being handed it. A run of one that printed no vibrational modes never
#: checked its own promise; its geometry is a producer for a downstream
#: stage; and the walk from the input geometry to the one it reached is
#: what the basin sensor measures. A Hessian is not here because it
#: moves nothing.
GEOMETRY_SEARCH_JOBTYPES = frozenset({"opt", "ts"})

#: Job types that sample a surface: they converge per point and produce
#: a geometry, but no point they return is claimed to be stationary.
SURFACE_SAMPLING_JOBTYPES = frozenset({"scan"})


#: Job types that are handed a structure and measure its curvature
#: without moving it. What such a node's spectrum is *supposed* to
#: contain is not a property of the Hessian: it is a property of the
#: structure it was handed, and the node that produced that structure
#: already said what it was searching for.
FIXED_GEOMETRY_CURVATURE_JOBTYPES = frozenset({"freq", "hess"})


def expected_imaginary_mode_count(
    jobtype: str, input_jobtype: str = ""
) -> int | None:
    """How many imaginary modes this node promises, or None.

    ``input_jobtype`` is the job type of the *result* whose geometry this
    node consumed, where it consumed one. A Hessian inherits the promise
    of the search that produced its structure, because the promise was
    never about the Hessian: ORCA runs ``OptTS Freq`` as one node and the
    saddle it confirms is what ``ts`` promised, while PySCF and xTB split
    the same physics into a search and a Hessian -- and the Hessian half,
    judged as though it were a minimum's, called two live saddles
    ``failed_wrong_stationary_point`` for confirming exactly the one
    imaginary mode they were run to find (CUHK g2-h2co-foreign-saddle and
    g4-hooh-rotation, 2026-09-20). The same physics gets the same word.

    It reads both ways, which is the point. A saddle search that
    converges onto a minimum -- which a converged ``ts`` cannot itself
    detect, because its artifact carries no spectrum of what it reached
    -- produces a Hessian with no imaginary mode, and that Hessian now
    fails the promise its producer made instead of validating as a
    minimum nobody asked for.

    A node handed a bare geometry inherits nothing and keeps the promise
    its own job type carries.
    """

    own = STATIONARY_POINT_PROMISES.get(jobtype)
    if jobtype not in FIXED_GEOMETRY_CURVATURE_JOBTYPES:
        return own
    inherited = STATIONARY_POINT_PROMISES.get(
        str(input_jobtype or "").strip().lower()
    )
    return own if inherited is None else inherited


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


def start_point_order_finding(
    jobtype: str, observed_imaginary_modes: int | None
) -> str:
    """The finding for a start that is not what the job type promised it
    was handed, or "" when it is, or when nothing makes or checks the
    claim."""

    expected = START_POINT_PROMISES.get(jobtype)
    if expected is None or observed_imaginary_modes is None:
        return ""
    return (
        ""
        if observed_imaginary_modes == expected
        else START_POINT_ORDER_FINDING
    )


def stationary_point_order_finding(
    jobtype: str,
    observed_imaginary_modes: int | None,
    input_jobtype: str = "",
) -> str:
    """The finding to record, or "" when the result matches its claim or
    makes none."""

    expected = expected_imaginary_mode_count(jobtype, input_jobtype)
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
    "failed_nonconverged_excited_state",
    "failed_nonconverged_correlation",
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
    #: The host's own post-processing after the engine exited, from the
    #: receipt's evaluated_at; None for receipts minted before the stamp.
    host_seconds: float | None = None
    wrapper_exit_status: int | None = None
    child_exit_status: int | None = None
    #: Event hashes and artifact digests this derivation read -- the
    #: citation a revision carries.
    evidence_event_hashes: tuple[str, ...] = ()
    evidence_artifact_sha256s: tuple[str, ...] = ()
    #: The registered-result ids those digests carry when their bytes are
    #: bound (<program>-result-<sha16>): a digest an outcome names must
    #: either resolve or say how it would.
    evidence_artifact_ids: tuple[str, ...] = ()
    #: Host-detected surprises recorded beneath this node's verdict:
    #: signal id, status, the numbers that tripped it, the receipt
    #: digest. Empty for streams that predate the sensor.
    anomalies: tuple[Mapping[str, Any], ...] = ()
    #: What the recorded path was, for a node that walked one: the
    #: validator's own measurements of the branch plus how many of its
    #: frames are path steps. Empty for every node that walked no path
    #: and for streams whose program records no account.
    #:
    #: A ``default_factory``, not a ``MappingProxyType({})`` literal:
    #: Python 3.11's dataclass machinery refuses an unhashable default
    #: outright, and this host's controller is 3.11 while the tree it was
    #: written on is 3.12, which accepts one. Every CLI run of the first
    #: cluster batch (Slurm 2141121) died importing this module after its
    #: engine had finished.
    path_account: Mapping[str, Any] = field(default_factory=dict)

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
            "host_seconds": self.host_seconds,
            "wrapper_exit_status": self.wrapper_exit_status,
            "child_exit_status": self.child_exit_status,
            "evidence_event_hashes": self.evidence_event_hashes,
            "evidence_artifact_sha256s": self.evidence_artifact_sha256s,
            "evidence_artifact_ids": self.evidence_artifact_ids,
            "anomalies": tuple(dict(item) for item in self.anomalies),
            "path_account": dict(self.path_account),
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
    host_seconds: float = 0.0
    stream_head_hash: str = ""
    stream_tail_hash: str = ""
    #: Launches charged to the excursion grant, counted apart so the
    #: engine-call budget never pays for an investigation.
    excursion_calls_consumed: int = 0

    def public_record(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "workflow_state": self.workflow_state,
            "nodes": tuple(item.public_record() for item in self.nodes),
            "engine_calls_consumed": self.engine_calls_consumed,
            "engine_wall_seconds": self.engine_wall_seconds,
            "host_seconds": self.host_seconds,
            "excursion_calls_consumed": self.excursion_calls_consumed,
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


#: Where each program's result validation records its account of a path
#: it walked.  One entry per program, so a second program that walks a
#: path is one line rather than a second reader of the same shape.  The
#: validator is the author: it already measures the first step against
#: the transition vector, every step against the steepest descent, and
#: the energy along the way, and recomputing any of it here would be two
#: organs answering one question.
PATH_ACCOUNT_OBSERVATIONS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"pyscf": ("irc_validation", "ts_validation")}
)

#: The path facts a session is given, in the order a chemist reads them.
#: Every one is a measurement or a count the validator already made; none
#: is a verdict, because what a path means is the session's to say.
#: A stage that carries none of them contributes none; the union is
#: taken because an IRC's branch and a saddle search's climb answer
#: overlapping halves of one question.
PATH_ACCOUNT_FIELDS: tuple[str, ...] = (
    "frames",
    "iterations",
    "maxsteps",
    "path_converged",
    "search_converged",
    "seed_frequencies_cm1",
    "energy_rise_eh",
    "seed_max_abs_gradient_eh_per_bohr",
    "end_max_abs_gradient_eh_per_bohr",
    "displacement_amu_half_bohr",
    "requested_direction",
    "direction_followed",
    "first_step_projection_measured",
    "start_frequencies_cm1",
    "start_max_abs_gradient_eh_per_bohr",
    "energy_rises_along_path",
    "steepest_descent_cosine_median",
    "steepest_descent_cosine_min_after_first_step",
    "steepest_descent_steps_compared",
    "switched_to_minimisation",
)


def _path_account(
    program: str, observations: Mapping[str, Any]
) -> Mapping[str, Any]:
    """What the recorded path was, for the session that must read it.

    A branch's own account lived entirely inside the program's result
    validation: a session could read the path energies, the frame count,
    the start's spectrum and the end's connectivity through selectors and
    could not learn that the walk had run out of steps, that its tail was
    a minimisation rather than path steps, or how far any step lay from
    the surface's steepest descent.  So "the IRC reached X" and "a
    minimisation started from the IRC's tail reached X" read identically,
    and they are different scientific statements.

    Nothing is graded here and no threshold is applied -- no threshold has
    been earned, and geomeTRIC reaching the basin and then minimising is
    ordinary IRC practice rather than a fault.  What the host adds to the
    validator's numbers is the one fact none of them states: how many of
    the recorded frames are path steps, how many are the minimisation
    after it, and therefore by which of the two mechanisms the endpoint
    was reached.  ``reached_by`` names a mechanism, never a chemistry.
    """

    validation = observations.get("result_validation")
    if not isinstance(validation, Mapping):
        return {}
    keys = PATH_ACCOUNT_OBSERVATIONS.get(str(program).strip().lower()) or ()
    account = next(
        (
            validation[key]
            for key in keys
            if isinstance(validation.get(key), Mapping)
        ),
        None,
    )
    if account is None:
        return {}
    record: dict[str, Any] = {
        name: account[name]
        for name in PATH_ACCOUNT_FIELDS
        if account.get(name) is not None
    }
    if not record:
        return {}
    frames = account.get("frames")
    switch = account.get("switch_after_iteration")
    switched = account.get("switched_to_minimisation")
    if switched is True:
        # Silence here would read as "the path stepped all the way",
        # which is the reading this record exists to prevent, so the
        # word is written from the flag and the counts only from an
        # index that indexes these frames.
        record["reached_by"] = "minimisation_from_path_tail"
        if (
            isinstance(frames, int)
            and isinstance(switch, int)
            and 0 <= switch < frames
        ):
            record["path_step_frames"] = switch + 1
            record["minimisation_frames"] = frames - (switch + 1)
    elif switched is False and isinstance(frames, int) and frames >= 1:
        record["reached_by"] = "path_step"
        record["path_step_frames"] = frames
        record["minimisation_frames"] = 0
    return record


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
    from chemsmart.analysis.result_readers import reader_for

    program = str(validation_record.get("program") or "").strip().lower()
    reader = reader_for(program)
    if reader is None:
        return converged, reached, planned, ()
    for artifact in validation_record.get("output_artifacts") or ():
        if not isinstance(artifact, Mapping):
            continue
        # Read through the program's own reader rather than ORCA's alone:
        # ``converged`` was None on every non-ORCA node, so the flag the
        # outcome record publishes was permanently absent for three of
        # four programs and the nonconverged branch reached PySCF only
        # through its native failure class.
        if artifact.get("kind") != reader.artifact_kind:
            continue
        path = Path(str(artifact.get("path") or ""))
        sha256 = str(artifact.get("sha256") or "")
        if not path.is_file():
            continue
        try:
            from chemsmart.agent._contracts import file_sha256

            if sha256 and file_sha256(path) != sha256:
                continue
            output = reader.open_output(path)
            value = getattr(output, "converged", None)
            converged = None if value is None else bool(value)
            reached = getattr(output, "scan_step_count", None) or None
            coordinate = getattr(output, "scan_coordinate", None)
            planned = int(coordinate["points"]) if coordinate else None
            digests.append(sha256)
            break
        except Exception:  # noqa: BLE001 - an unreadable file yields absence
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
    # A crash is not a convergence statement. ``converged is False`` is
    # what a dead run leaves behind, not what it was, so testing it
    # before the program's own error class typed an ORCA input-syntax
    # death (``maxiter`` written on the route line, one second of
    # runtime) as ``failed_nonconverged_geometry``, and a property-module
    # abort (``ERROR (SHARK): Failed to read input file``) as
    # ``failed_nonconverged_scan_step``. The repair menu then prescribed
    # chemistry for a broken input file. Both were live in one goal
    # (NOVEL-1 ino1, 2026-09-04) and four archived scans on this host
    # carry the same SHARK signature, so the word had been calling engine
    # crashes chemistry for the whole campaign.
    #
    # This branch cannot swallow a genuine non-convergence: a run that
    # merely hit its iteration cap terminates normally, so it carries no
    # native failure class at all, and the two classes that *are*
    # convergence statements keep their meaning -- ``scf_convergence``
    # here, ``geometry_optimization`` in the derivation below. Reading
    # the flag first cost that too: an SCF failure carrying
    # ``converged is False`` was typed ``failed_nonconverged_geometry``
    # even on a single point, which has no geometry to converge. That
    # second case was found by the general test rather than by a run.
    if native_class == "scf_convergence":
        return "failed_nonconverged_scf"
    # A response solver or an amplitude set that did not converge is a
    # convergence statement about a stage whose SCF did converge; each
    # keeps its own word and its own public repair control.
    if native_class == "excited_state_convergence":
        return "failed_nonconverged_excited_state"
    if native_class == "correlation_convergence":
        return "failed_nonconverged_correlation"
    # A path that could not leave its start because the start was not a
    # first-order saddle of the walked surface: the program's own word for
    # a wrong stationary point, answered as one.
    if native_class == "stationary_point_order":
        return "failed_wrong_stationary_point"
    if (
        native_class
        and native_class not in _CONVERGENCE_FAILURE_CLASSES
        and native_class not in _UNDIAGNOSED_FAILURE_CLASSES
    ):
        return "failed_native"
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
        or item == START_POINT_ORDER_FINDING
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


def run_live_leases(events: Any) -> tuple[str, ...]:
    """Nodes whose launch reservation may still be a running engine.

    The cohort barrier is "every member terminal", and a member inside
    its lease is not terminal -- it is being run right now by another
    array element. Asking this is how a wave avoids waking the model
    over a half-finished cohort.

    A node that also holds a receipt has finished and is never live,
    whatever its reservation says. A reservation with no lease, or an
    unreadable one, is not live: every reservation written before leases
    existed carries none, and a lease the host cannot read is not a
    licence to wait forever.

    Args:
        events: The run's own events, as `derive_run_outcome` takes them.

    Returns:
        tuple[str, ...]: Node ids still inside a live lease, sorted.
    """

    from chemsmart.agent.runtime.records import reservation_lease_is_live

    leases: dict[str, tuple[str, Any]] = {}
    finished: set[str] = set()
    for event in events:
        payload = getattr(event, "payload", None) or {}
        record = payload.get("record") or {}
        node_id = str(
            payload.get("node_id") or (record or {}).get("node_id") or ""
        )
        if not node_id:
            continue
        if getattr(event, "kind", "") == "workflow_node_launch_reserved":
            if isinstance(record, Mapping):
                leases[node_id] = (
                    str(record.get("reserved_at") or ""),
                    record.get("lease_seconds"),
                )
        elif getattr(event, "kind", "") == "program_execution_observed":
            finished.add(node_id)
    return tuple(
        sorted(
            node_id
            for node_id, (reserved_at, lease_seconds) in leases.items()
            if node_id not in finished
            and reservation_lease_is_live(
                reserved_at=reserved_at, lease_seconds=lease_seconds
            )
        )
    )


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
    # Imported here: runtime.records reaches the capability layer, and a
    # module-level import closes a cycle through it.

    reservations: set[str] = set()
    #: node id -> (reserved_at, lease_seconds) from its own reservation.
    reservation_leases: dict[str, tuple[str, Any]] = {}
    excursion_nodes: set[str] = set()
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
            if payload.get("excursion"):
                excursion_nodes.add(node_id)
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
            # Which line this call came from, for a launch that never
            # wrote a receipt to say so.
            if (payload.get("record") or {}).get("excursion"):
                excursion_nodes.add(node_id)
            # The lease the reservation was taken under, so a node still
            # inside it can be told from one whose process is gone.
            record = event.payload.get("record") or {}
            if isinstance(record, Mapping):
                reservation_leases[node_id] = (
                    str(record.get("reserved_at") or ""),
                    record.get("lease_seconds"),
                )
            event_hashes_by_node.setdefault(node_id, []).append(
                event.event_hash
            )
        elif event.kind == "workflow_node_state_changed":
            event_hashes_by_node.setdefault(node_id, []).append(
                event.event_hash
            )

    nodes: list[NodeTerminalStateV1] = []
    engine_calls = 0
    excursion_calls = 0
    engine_wall = 0.0
    host_total = 0.0
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
        host = None
        # A call is spent when it is **taken**, not when it returns --
        # the launch fence has counted it that way all along
        # (`engine_calls_spent`). Counting receipts here meant the two
        # authorities disagreed exactly where it matters: a controller
        # killed between the reservation and the receipt left a node the
        # fence had charged and the outcome had not, so the grant
        # silently regained a call that the engine had already begun
        # burning, and the next cycle was handed budget that omitted it.
        if execution or node_id in reservations:
            if node_id in excursion_nodes:
                excursion_calls += 1
            else:
                engine_calls += 1
        if execution:
            wall = _wall_seconds(
                execution.get("started_at") or "",
                execution.get("finished_at") or "",
            )
            if wall:
                engine_wall += wall
            host = _wall_seconds(
                execution.get("finished_at") or "",
                execution.get("evaluated_at") or "",
            )
            if host:
                host_total += host

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
            # A reservation with no receipt used to mean exactly one
            # thing: the prior invocation died mid-engine. Under a wave
            # cohort it is also what a *healthy sibling* looks like, and
            # the two were indistinguishable from durable state. The
            # lease separates them: inside it, the node may still be
            # running and this run is simply not finished, so it is not
            # given a terminal word at all; past it, no engine can still
            # be alive and the interrupted reading stands.
            # The word stays what it was: from a *run outcome's* point of
            # view the engine's result never arrived, and "running" is not
            # a terminal state -- NodeTerminalStateV1 would refuse it.
            # Liveness is a different question and belongs to the cohort
            # barrier, which must not call a wave finished while a member
            # is still inside its lease. `run_live_leases` is what asks.
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
                host_seconds=host,
                wrapper_exit_status=execution.get("wrapper_exit_status"),
                child_exit_status=execution.get("child_exit_status"),
                evidence_event_hashes=tuple(
                    event_hashes_by_node.get(node_id, ())
                ),
                evidence_artifact_sha256s=artifact_digests,
                evidence_artifact_ids=tuple(
                    f"{program}-result-{digest[:16]}"
                    for digest in artifact_digests
                    if program and digest
                ),
                anomalies=tuple(anomalies_by_node.get(node_id, ())),
                path_account=dict(_path_account(program, observations)),
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
        excursion_calls_consumed=excursion_calls,
        engine_wall_seconds=engine_wall,
        host_seconds=host_total,
        stream_head_hash=events[0].event_hash if events else "",
        stream_tail_hash=events[-1].event_hash if events else "",
    )


#: A session the provider's transport or protocol ended, rather than
#: the science. The loop writes it and the driver reads it, so it is
#: one word in one place: a cycle lost this way produced no scientific
#: evidence and must not spend the goal's scientific opportunity.
PROVIDER_TRANSPORT_TERMINAL_REASON = "provider transport or protocol failed"


def is_provider_transport_terminal(reason: str) -> bool:
    """True when a cycle ended on the provider rather than the science."""

    return str(reason or "").strip() == PROVIDER_TRANSPORT_TERMINAL_REASON


__all__ = [
    "NODE_TERMINAL_STATES",
    "PROVIDER_TRANSPORT_TERMINAL_REASON",
    "is_provider_transport_terminal",
    "NodeTerminalStateV1",
    "RunOutcomeV1",
    "derive_run_outcome",
    "run_live_leases",
]
