# ChemSmart Frontier Computational-Chemistry Agent: Ultimate Goal

## Purpose

ChemSmart's target is a CLI-first computational-chemistry automation agent
that can plan, execute inside explicit authority, inspect outcomes, adapt to
validated evidence, and report conservative scientific conclusions. It is not
an unrestricted chat wrapper around engines or a claim that autonomous science
is already reliable.

This document reserves an additive design for later implementation. The
Foundation branch changes no runtime, provider, parser, permission, or engine
behavior.

## Target lifecycle

```text
goal
  → clarified scientific specification
  → task graph and resource budget
  → method, geometry, and execution preflight
  → approval checkpoint
  → isolated execution
  → parser and deterministic scientific validation
  → independent read-only critique
  → evidence-bound report
  → complete | waiting for approval | blocked | failed
```

Each transition consumes and emits versioned, inspectable state. A model may
propose the next action but cannot make a terminal scientific pass by assertion.

## Architecture principles

### Provider-neutral core

Keep request/response formatting, tool-call syntax, and continuation semantics
inside provider adapters. The core records normalized public actions, artifacts,
approvals, validator results, and outcomes. Preserve any provider-required
reasoning or continuation token only as an opaque `ProviderStateRef`; it is
never evidence and must not be exposed as hidden chain-of-thought.

### Extend Runtime V2, do not replace it

The current runtime already supplies `TaskEnvelope`, `AgentDecision`,
`ToolReceipt`, `ArtifactRef`, `RuntimeEvent`, event hashing, and a lifecycle
layer. Future work extends this nucleus with versioned payloads and adapters;
it does not create a second event store, planner, or policy engine.

### Deterministic policy and validators

Permission, budget enforcement, parser checks, input invariants, artifact
identity, unit checks, and terminal-state rules belong in deterministic code.
Prompts may explain policy but must not be the sole enforcement layer.

### Bounded autonomy

Autonomy is adaptive operation inside an approved envelope. A task graph
declares inputs, expected outputs, tool capabilities, wall time, token use,
cost, compute budget, retry budget, stop condition, and approval boundary.
ChemSmart must pause rather than broaden scope silently.

## Future public contract

The following types are additive design targets, not APIs implemented by this
foundation:

| Interface | Purpose |
| --- | --- |
| `ProviderCapabilities` | Declare protocol, structured-output support, opaque continuation mode, context/tool limits, and parallel capability. |
| `ScientificTaskSpec` | Bind molecule/geometry artifact, charge, multiplicity, program/job kind, method settings, constraints, requested observable, units, assumptions, and required evidence. |
| `TaskNode` and `TaskGraph` | Define immutable inputs, dependencies, role, allowed tools, expected outputs, verifier, budget, approval scope, and deterministic join policy. |
| `ResourceBudget` | Cap model calls, tokens, cost, tool calls, wall time, and local/HPC compute. |
| `ApprovalRequest` / `ApprovalResolution` | Bind a one-shot decision to exact command, input, project, executable/environment, resource, and artifact hashes. |
| `EvidenceRef` / `ValidationReceipt` | Locate artifacts and record validator identity/version, subjects, measurements, rule IDs, units, and pass/warn/fail/unknown status. |
| `ClaimRecord` / `ReviewFinding` | Separate observation, computed result, inference, literature claim, and unresolved uncertainty; bind review to evidence. |
| `ReportManifest` | Enumerate the run, task graph, artifacts, claims, receipts, citations, and rendered report outputs. |
| `ProviderStateRef` | Hold opaque provider continuation state; explicitly non-evidentiary. |

Future event kinds include scientific specification, task-graph creation,
dispatch/join, approval request/resolution/invalidation, validation, claim,
review, report, budget exhaustion, pause/resume, and terminal state. Every
event payload carries a version. Existing event logs must replay unchanged.

## Scientific and reproducibility contract

### Calculation identity

Every calculation must have stable identifiers for molecule, geometry frame,
project, task, input, execution, output, validation, and claim. Do not infer a
geometry from a filename. Record coordinate units, atom order, charge,
multiplicity, fragments, stereochemistry, constraints, and any conformer or
spin assumption.

### Required evidence

The canonical bundle contains:

- native engine input/output/log files and content digests;
- QCSchema-compatible structured calculation records where practical;
- XYZ/SDF geometry artifacts and units;
- command, working directory, start/end time, exit status, job identifier, and
  retry rationale;
- program, executable, environment, and container/version information;
- method, basis/ECP, dispersion, solvent, temperature, standard-state, and
  convergence settings;
- parsed values with units, validator receipts, approvals, citations, claims,
  and review findings;
- a RO-Crate-compatible manifest that can regenerate Markdown/HTML/notebook
  views without treating them as the evidence source.

### Scientific pass conditions

For a task-specific applicable subset, require molecular identity,
charge/multiplicity/electron-count checks, method-setting compatibility,
normal termination, SCF and geometry convergence, frequency/stationary-point
checks, spin/stability diagnostics, stoichiometry, reference-energy and
standard-state consistency, units, and uncertainty/limitation disclosure.
Missing evidence yields a qualified, blocked, or failed outcome—not a complete
result.

## Component adoption decisions

### Task-decomposed subagents

Adopt only for independently verifiable work with a typed deterministic merge.
The primary early example is a reaction-property workflow with separately
computed species and a stoichiometric aggregation check. Do not assign agents
by academic title alone or allow two workers to modify the same artifact.

### Integrated documentation

Make evidence manifests and reproducible rendering foundational. Do not claim
that documentation itself increases model capability; evaluate whether it
improves claim coverage, auditability, and reproducibility without harming
execution outcomes.

### Adversarial critique

Use a fresh, read-only critic to challenge assumptions, incomplete evidence,
method suitability, and unsupported claims. The critic cannot execute, approve,
or repair. Deterministic validators, independent recalculation, or a human
resolve findings.

## Incremental roadmap

| Phase | Deliverable | Gate |
| --- | --- | --- |
| P0: authority and baseline | Pinned branch, canonical instructions, source ledger, skills, and deterministic validation | Dirty parent preserved; baseline contracts measured; no live compute or API use. |
| P1: typed shadow instrumentation | Versioned scientific/task/approval/evidence payloads behind Runtime V2 shadow mode | Old logs replay identically; new payloads round-trip; exact approvals bind hashes; no behavior drift. |
| P2: single-agent scientific reference | One executor produces task spec, receipts, validation, claims, and report manifest | Held-out fixtures have no approval bypass, fabricated evidence, or successful state with a red required gate. |
| P3: confirmatory ablation | Evaluate decomposition, documentation, and critique against the frozen single-agent path | Preregistered metrics and safety gates in the evaluation protocol pass. |
| P4: bounded exploration | Hypothesis/candidate loop inside approved method and compute envelopes | Every iteration has a task spec, approval decision, result, validation, and stop reason. |
| P5: training | SFT/preference/RL work from verified visible traces and outcome graders | Held-out chemistry families, anti-hacking checks, and reproducible success support the training claim. |

## Training boundary

Do not start with fine-tuning. First collect verified successful and rejected
traces, deterministic outcome labels, stateful failure fixtures, and held-out
tasks. If training becomes justified, use visible actions, tool calls,
artifacts, concise public decision summaries, and outcomes—not hidden
reasoning. Randomize tool schemas, task wording, context strategy, failure
modes, and harness configuration to avoid training a model that only works in
one scaffold.

The preregistered acceptance criteria are specified in
[frontier-agent-ablation-protocol.md](../evaluation/frontier-agent-ablation-protocol.md).
