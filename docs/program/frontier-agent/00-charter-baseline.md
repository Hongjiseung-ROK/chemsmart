# P0 — Charter and baseline

## Status

Complete at 2026-07-31T18:06:03Z. P0 was the only executed phase until its
focused offline validation passed. P1–P6 remain bounded plans, not completed
work or implied approvals.

## Objective

Freeze a source-backed single-agent reference and the authority boundary for a
CLI-first computational-chemistry agent. Establish a traceable program ledger
without changing Runtime V2, Click semantics, provider behavior, chemistry
engine behavior, the original dirty checkout, or GUI/Studio work.

SOTA is a hypothesis to test by controlled comparison and replication. It is
not a target label that this phase, a valid command, a model answer, or a
passing test can establish.

## Inputs

| Input | Frozen use in P0 |
| --- | --- |
| [`AGENTS.md`](../../../AGENTS.md) | Authority, scientific, approval, and reporting contract. |
| Harness, scientific-workflow, and evidence-audit skills | Local operating guidance and their six references. |
| [`chemsmart-agent-ultimate-goal.md`](../../design/chemsmart-agent-ultimate-goal.md) | Additive Runtime V2 and scientific-evidence design target. |
| [`chemsmart-agent-gap-analysis.md`](../../research/chemsmart-agent-gap-analysis.md) | Source-backed implementation-gap baseline. |
| [`frontier-agent-landscape.md`](../../research/frontier-agent-landscape.md) and its ledger/audit | Historical literature and architecture snapshot; not current publisher-passage evidence. |
| [`frontier-agent-ablation-protocol.md`](../../evaluation/frontier-agent-ablation-protocol.md) | Preregistered 2 × 2 × 2 component-study constraints. |
| Runtime, provider, schema, test, and fixture source files listed in [`p0-baseline-receipt.json`](p0-baseline-receipt.json) | Content-addressed source observations. |

The observed Frontier worktree baseline is branch
`codex/frontier-agent-foundation` at
`6da43bab030b90ea5b9777105f78fd5848dd4aed`, with merge base
`cf986251077b7ee65f8afa951ee76052146c7613`. The original checkout is a
separate read-only preservation target; its current dirty-entry counts are
recorded without listing user artifact names in the P0 receipt.

## Tools and authority

- Allowed: read-only repository inspection, content hashing, documentation in
  this worktree, and an offline deterministic validator plus its focused test.
- Allowed: bounded read-only advisers with immutable commit input, narrow
  source scope, no writes, no network, and source-cited typed findings.
- Not allowed in P0: provider/API calls, credential-value inspection, real or
  simulated chemistry-engine execution, scheduler activity, dependency
  installation, commit, push, publication, broad test suites, or changes to
  Runtime V2, CLI/schema, providers, permissions, GUI, Studio, or the original
  checkout.

## Budget

| Resource | Ceiling |
| --- | --- |
| Live provider/API calls | 0 |
| Real Gaussian, ORCA, xTB, scheduler, or HPC invocations | 0 |
| Dependency installs, commits, pushes, and publication actions | 0 |
| Mutable artifacts | Program documents, P0 receipt, offline validator, and one focused test only |
| Phase-close validation | One focused test invocation; any failure is logged before a bounded repair decision |

## Artifacts

- This seven-document program charter.
- [`p0-baseline-receipt.json`](p0-baseline-receipt.json), containing hashes,
  read-only observations, historical-receipt labeling, and zero-use quota
  counters.
- [`validate_frontier_program.py`](../../../scripts/review/validate_frontier_program.py)
  and its focused test, which verify required phase sections, local links,
  redaction guardrails, and P0 source hashes.

## Gates

| Gate | Pass condition | Red condition |
| --- | --- | --- |
| P0-G1: isolation | Frontier baseline and original-checkout status are recorded without modifying the original checkout. | Any original-checkout or GUI/Studio modification. |
| P0-G2: source identity | Governing source artifacts match the recorded SHA-256 values. | Any unrecorded source drift. |
| P0-G3: single-agent reference | The no-decomposition, no-extra-documentation, no-critic configuration remains the declared reference. | Any optional component is enabled or called superior. |
| P0-G4: no overclaim | SOTA, scientific readiness, and API availability remain unproven. | A conclusion treats a fixture, parser, or model response as proof. |
| P0-G5: deterministic close | The focused offline program validator passes once and its result is recorded. | Validator failure or an unrecorded invocation. |

## Blockers

- The historical CLI schema records two different digests from different
  baselines; P1/P2 must reconcile a fresh in-memory schema observation before
  treating either as a current immutable schema pin.
- No current quota, entitlement, publisher-passage, clean-environment
  replication, or held-out outcome evidence has been collected.
- Runtime V2 has no typed scientific task, approval-binding, validation,
  claim, report-manifest, task-graph, or old-log corpus contract yet.

## Phase-close validation

Run exactly once after the P0 files are complete:

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/test_frontier_agent_program.py -q
```

This is a document/source-integrity check. It is neither a product suite nor
scientific, provider, engine, or release validation.

## Claim-evidence ledger

| ID | Claim type | Statement | Evidence | Status and limitation |
| --- | --- | --- | --- | --- |
| P0-C1 | observation | The Frontier worktree began clean at the recorded branch, commit, and merge base. | P0 receipt plus source hashes. | Supported for the recorded observation only. |
| P0-C2 | observation | Runtime V2 has modes, typed public contracts, versioned hash-chained events, and replay tests. | Hashed Runtime V2 source and focused test source. | Supported as a code observation; not a scientific pass. |
| P0-C3 | observation | The Click tree is the executable CLI source of truth and currently generated schema metadata is hashable. | Hashed schema source and tests. | Supported; no fresh schema dump is claimed in P0. |
| P0-C4 | unresolved uncertainty | Current API quota/entitlement and external-source correction status are usable. | None in P0. | Unresolved; P1 only. |
| P0-C5 | inference | ChemSmart is SOTA-worthy. | None. | Rejected as a present-tense claim; it remains a testable hypothesis. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P0-D1 | Execute P0 only; leave P1–P6 unstarted. | Ordered phase gate and no current external evidence. | Do not start P1 until P0-G5 passes. |
| P0-D2 | Preserve Runtime V2 and CLI semantics; plan additive contracts only. | `AGENTS.md`, current contracts, and gap analysis. | Any proposed behavior change moves to P2 with replay fixtures. |
| P0-D3 | Freeze a single-agent reference before optional components. | Preregistered 2 × 2 × 2 protocol. | Enable a component only after P5 gates pass. |
| P0-D4 | Treat historical foundation receipts as historical. | Retrieval and validation dates precede P0 observation. | Refresh only through bounded P1 evidence collection. |

## P0 close handoff

When P0-G5 passes, the next safe action is P1 credential-presence and
account/usage evidence collection under the no-secret, no-top-up, existing
quota boundary. It does not authorize an engine invocation or a model call.
