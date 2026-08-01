# Frontier evidence index v1

## Status

This is an append-only, offline P6 no-go evidence index. It consolidates the
frozen P6 decision with the later bounded P3 v2 chain and P1/P5/P6
reconciliation. It is not an evaluation, replication, training, paper,
release, or SOTA result.

## Objective

Make the current evidence state independently inspectable without modifying
the frozen P6 no-go manifest or treating a single provider-surface observation
as a research outcome.

## Inputs and artifacts

The [machine-readable index](frontier-evidence-index-v1.json) pins the frozen
P6 no-go manifest and close receipt, P3 v2 pre-call readiness receipt, P3 v2
provider receipt, and P1/P5/P6 reconciliation. It separately pins the three
offline verifier/test pairs and the index's own harness/test source.

## Tools and budget

Only local file hashing, JSON parsing, deterministic validation, and focused
offline tests are permitted. All external API calls, provider completions,
tool dispatches, engines, schedulers, training, publication, commits, and
pushes have a zero budget for the index itself.

## Gates and blockers

The index must retain the exact P6 blocker register; false flags for paper
release, replication, training eligibility, and SOTA permission; all-zero
index authority counters; the one-request/zero-dispatch P3 v2 boundary; and
the reconciliation's exact no-go gate map. Any source or manifest drift is a
red index, not a reason to update a conclusion.

## Claim discipline

The index supports an infrastructure observation: the stated artifacts are
hash-linked and locally validated. It preserves as unresolved P6-C1 through
P6-C4 and rejects P5 eligibility, results, SOTA, replication, training,
publication, causal ceiling attribution, current quota claims, and active-path
provider/CLI/tool-loop claims.

## Phase-close validation

Run the index's focused validator once after its final source and manifest
hashes are frozen. This validates provenance/no-go state only; it does not run
the provider, a chemistry engine, scheduler, or held-out study.

## Failure and decision ledger

| ID | Failure or decision | Minimal response | Limitation and rollback |
| --- | --- | --- | --- |
| IDX-F1 | The frozen P6 manifest predates P3 v2. | Preserve it and add a separately hash-pinned index. | The index cannot make P6-C1 through P6-C4 green; delete only the index if invalid. |
| IDX-F2 | A later valid function schema could be mistaken for a study result. | Require explicit P3 isolation and P5/P6 no-go gates. | The index cannot establish causality, active-path behavior, or chemistry; any promotion invalidates it. |
| IDX-D1 | Keep all index authority counters at zero. | Check them mechanically with source hashes. | A future experiment needs separate protocol, evidence, and authority. |
