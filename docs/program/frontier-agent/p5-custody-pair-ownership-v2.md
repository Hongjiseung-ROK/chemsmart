# P5H-v2 — Global Pair-Commitment Ownership

## Status

Closed as a qualified, append-only fixture-only successor to P5H-v1. It
preserves the v1 source and receipt byte-for-byte, adds no catalog or held-out
content, and cannot make P5 eligible. The focused successor test and its
dedicated source/receipt validator passed. A current rerun of P5H-v1's own
static non-wiring test is red because that historical test treats two
fixture-only harness imports as active wiring; P5H-v2 records that limitation
instead of rewriting the frozen predecessor.

## Objective

P5H-v1 required a common pair commitment within each opaque case × repetition
group, but did not require that commitment to have exactly one such owner
globally. A practical two-case fixture showed that a commitment reused by two
groups could pass v1's boundary. P5H-v2 rejects that reuse before scoring or
aggregation.

## Inputs

| Input | Required use |
| --- | --- |
| Frozen P5 preregistration | Retain its eight configurations, three repetitions, P3 development catalog, and red gates. |
| P5H-v1 source and receipt | Pin exact predecessor bytes; do not edit or reinterpret them. |
| P5/P4 evidence | Retain the external-custody and duplicate/aggregate limits as red or unresolved. |

## Tools, budget, and authority

Only local digest-only records, synthetic labels, deterministic checks, static
non-wiring checks, and focused tests are allowed. The budget is two synthetic
case commitments × 8 configurations × 3 repetitions; it accesses zero actual
held-out cases or catalogs and uses zero provider, engine, scheduler, command,
network, dependency, commit, or push actions.

## Contract and gates

`FixturePairOwnedTrialKeyV2` contains no case identifier. After each group has
proved complete factor coverage and a single internal pair commitment, P5H-v2
maps that commitment to its first `(case_commitment_sha256, repetition_index)`
owner. A different owner is rejected as `heldout.pair_commitment_reused`.

| Gate | Status | Boundary |
| --- | --- | --- |
| P5H2-G1 predecessor preservation | Qualified | P5H-v1 source and receipt match their fixed SHA-256 values, but its historical static guard no longer reruns green after later harness-only consumers imported its commitment helper. |
| P5H2-G2 global pair ownership | Passed in fixture | A pair commitment may own exactly one opaque case × repetition group. |
| P5H2-G3 no active wiring / no P5 promotion | Passed in fixture | The successor has no execution surface and always returns `p5_evaluation_eligible=false`. |
| P5H-G4 / P5-G4 / P5-G5 | Red unchanged | No external custody, trial, score, interval, environment capture, or independent rerun exists. |

## Failure and decision ledger

| ID | Failure | Hypothesis | Minimal change | Evidence | Result | Limitation | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P5H2-F1 | P5H-v1 accepted one pair commitment reused across two synthetic case × repetition groups. | Pair identity needs a global owner, not merely group-local agreement. | Add a `pair_commitment → (case commitment, repetition)` ownership map in a separately named fixture successor. | A no-content local diagnostic returned `fixture_boundary_valid=true` with zero issues for the malformed two-case shape. | The focused successor test refused reuse and passed. | A digest owner does not establish external secrecy, custody, or a trial. | Replace only with a reviewed external custody/scoring interface that enforces an equal-or-stronger uniqueness rule. |
| P5H2-F2 | P5H-v1's static non-wiring test failed during current compatibility checking because it scans all agent source and classifies later fixture-only harness imports as active wiring. | Frozen historical evidence must remain byte-preserved; successor validation must distinguish current predecessor bytes from an overbroad historical scan. | Preserve v1 untouched, record the red revalidation, and keep P5H-v2's own module separately unwired. | One focused v1 test invocation: 14 passed, 1 failed at the broad static scan; both matching importers are under the fixture harness namespace. | P5H2-G1 is qualified rather than promoted; P5/P6 stay red. | This does not prove that the v1 test was correct at its original close or that any active path is safe. | Replace the historical guard only through a reviewed successor; never edit the frozen v1 test or receipt to make it green. |

## Claims

- Supported: the successor refuses the declared synthetic pair-reuse shape without retaining held-out content.
- Qualified: this is a prospective local integrity control, not independent custody; predecessor byte preservation does not make its historical static scan currently green.
- Unresolved: provider, active executor, chemical result, raw trial, component effect, comparator, replication, paper, training, release, and SOTA evidence.
- Rejected: that a passing synthetic shape permits P5 evaluation, a scientific result, or a SOTA claim.

## Phase-close validation

The focused successor test passed `4` tests in `0.08 s`; its dedicated
validator also passed. A necessary P5H-v1 compatibility test then produced
`14 passed, 1 failed` at its broad historical static scan, recorded as
P5H2-F2. All checks were offline and left P5/P6 red gates unchanged. The close
receipt records predecessor hashes, both failure records, every invocation,
and zero-authority accounting.
