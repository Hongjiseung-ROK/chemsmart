# P5A-v2 — Fail-Closed Pre-Data Contract

Status: closed as an offline fixture-only integrity successor. This document
does not revise P5, P5H, or P5A-v1. It preserves their source bytes and
receipts as historical evidence, then adds a separately hash-bound contract
that addresses defects found by an independent read-only audit.

No held-out task, provider request, tool dispatch, chemistry engine,
scheduler, score, interval, replication, paper conclusion, training decision,
release decision, or SOTA result is created here. P5 evaluation eligibility and
adoption are hard-coded `False`.

## Objective

P5A-v1 established a useful fixture-only shape, but it relied on several
runtime annotations without enforcing them, labelled some invalid matrices as
`external_evidence_required`, permitted study-wide control drift across
case/repetition groups, and did not surface retained red-line observations in
its result. P5A-v2 makes those boundaries explicit while retaining no raw
case, prompt, output, score, or credential.

## Inputs

| Input | Required use |
| --- | --- |
| [Frozen P5 preregistration](../../../tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json) | Bind its raw digest, canonical study digest, eight configurations, order, `D0-E0-C0` reference, three repetitions, and unchanged red-gate register. |
| [P5 phase-close receipt](receipts/p5-component-ablation.json) | Preserve P5's blocked outcome and absence of observed trial evidence. |
| [P5A-v1 source](../../../chemsmart/agent/harness/frontier_ablation_analysis_lock.py) and [receipt](receipts/p5-predata-analysis-lock-v1.json) | Preserve their exact historical bytes; treat their audit findings as reasons for a successor, never as observed science. |
| [P5 custody fixture](receipts/p5-heldout-custody-fixture-v1.json) | Preserve its fixture-only status; do not convert a digest commitment into independent custody. |
| [P5 protocol](05-component-ablation.md) | Keep the surface frozen before trial 1, deterministic-first grading, expert-secondary / LLM-supplementary roles, and no conclusion under red gates. |

## Tools, budget, and authority

Allowed tools were local source inspection, a fixture-only Python contract, and
focused tests. The budget is one synthetic case with 8 configurations × 3
repetitions solely to exercise the shape. The successor made zero provider,
network, executor, engine, scheduler, dependency-install, commit, or push
calls. It has no active-agent import or dispatch path.

## Artifacts

- [Contract module](../../../chemsmart/agent/harness/frontier_predata_contract_v2.py)
  validates the full status vocabulary at runtime, rejects boolean repetition
  indices, binds a single study-wide surface digest, and requires a pair
  commitment to identify only one case × repetition group.
- [Focused tests](../../../tests/agent/harness/test_frontier_predata_contract_v2.py)
  cover a structurally valid fixture, unresolved policy, invalid status
  classification, global-surface drift, pair reuse, malformed literals, and
  retained red-line output.
- [Receipt](receipts/p5-predata-contract-v2.json) and dedicated validator
  record exact hashes, redaction, zero authority, the predecessor boundary,
  and the focused validation result.

## Contract and gates

| Gate | Status | Boundary |
| --- | --- | --- |
| P5A2-G1 historical predecessor preservation | Passed locally | P5A-v1 source and receipt hashes must match; P5/P5H are not edited. |
| P5A2-G2 closed construction vocabulary | Passed in fixture | Policy, deterministic, critic, LLM-judge, and repetition types fail closed at runtime. |
| P5A2-G3 structural classification | Passed in fixture | Only an issue-free shape may say `external_evidence_required`; unresolved policy is incomplete and every other defect is invalid. |
| P5A2-G4 study-wide control binding | Passed in fixture | Every row must match one pinned surface digest and no pair commitment may cross case × repetition groups. |
| P5A2-G5 red-line retention | Passed in fixture | Red-line IDs appear separately in the structural outcome and cannot enable adoption. |
| P5-G2 through P5-G5 | Red, unchanged | No external custody, live authority, executor evidence, chemistry result, complete trial, aggregation, or independent rerun exists. |

## Failure and decision ledger

| ID | Failure | Hypothesis | Minimal change | Evidence | Result | Limitation | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P5A2-F1 | A malformed policy status could bypass the v1 locked/unresolved boundary. | Runtime allowlists fail closed where annotations alone do not. | Validate the two policy statuses during construction. | Independent read-only audit and focused malformed-status fixture. | Invalid status cannot reach an outcome. | Does not authenticate a future decision document. | Replace only with a reviewed schema validator that enforces the same closed vocabulary. |
| P5A2-F2 | A structurally invalid shape could be labelled as merely awaiting external evidence. | A three-way status distinguishes invalid, incomplete, and externally blocked states. | Introduce `predata_analysis_invalid` and reserve `external_evidence_required` for zero issues. | Visible-development, missing-pair, and forbidden-conclusion fixtures. | Invalid shapes have false boundary validity and an invalid status. | This is not an analysis result. | Preserve the three-way taxonomy or supersede it explicitly. |
| P5A2-F3 | Surface and pair controls were only local to a group, allowing cross-group drift or pair reuse. | One lock-level surface and one-owner pair mapping protect the prospective study surface. | Bind every row to one surface digest and reject pair ownership reuse. | Focused drift and reuse fixtures. | Both changes are refused before any score or aggregate. | A digest does not prove external custody or environment reconstruction. | Replace only with a reviewed receipt ledger that is at least as strict. |
| P5A2-F4 | Deterministic, critic, LLM, and repetition annotations could be malformed at runtime. | Explicit construction checks prevent silent typed-contract degradation. | Validate terminal/critic/LLM vocabularies and reject boolean repetition values. | Focused negative construction fixtures. | Every listed malformed value raises before evaluation. | It does not define the future terminal-to-metric mapping. | Fix that mapping only through an authorized analysis-policy revision. |
| P5A2-F5 | Red-line evidence could be retained in a row but invisible in the structural outcome. | A separate observation field preserves failure evidence without promoting it. | Return the sorted union of observed red-line IDs. | Focused fabricated-evidence fixture. | Red-line evidence remains visible while adoption stays false. | It is synthetic, not an observed live violation. | Replace only with a reviewed event provenance model that preserves all failures. |
| P5A2-F6 | The predecessor receipt digest was opaque but was not fixed to the intended historical receipt. | A successor must bind both historical source and receipt identities. | Reject any predecessor receipt digest other than the preserved P5A-v1 receipt. | Focused predecessor-drift fixture. | A substituted predecessor receipt cannot construct successor evidence. | Byte identity alone does not validate the predecessor's historical semantics. | Replace only with an explicit reviewed successor lineage. |

## Blockers

- Material analysis choices remain unresolved: estimand, successful-block
  mapping, repeat treatment, missingness/exclusions, family weights, contrasts,
  threshold mapping, and multiplicity correction. P5A-v2 deliberately does
  not select them.
- No independent holder, non-leaking held-out catalog, auditable custody
  method, allowed live provider envelope, raw native receipt, deterministic
  grading output, environment reconstruction, or independent rerun exists.
- P4-HA-01 (active executor approval-consumption) and P4-CH-01
  (chemical-result provenance) remain red. This contract neither imports nor
  changes active execution.

## Phase-close validation

Run the focused successor test and its dedicated receipt validator once after
the receipt's source hashes are fixed. This validates only local structural
controls. It cannot clear a P5 or P6 gate.

## Claim-evidence ledger

| Claim class | Status |
| --- | --- |
| Supported | P5A-v2 rejects its specified malformed fixture records and retains red-line identifiers without authorizing a conclusion. |
| Qualified | This is a local prospective integrity control, not a custody, provider, chemistry, trial, or aggregate verification. |
| Unresolved | All observed P5 outcomes, component effects, comparator evidence, replication, paper readiness, training, release, and SOTA. |
| Rejected | That any synthetic success-like row, receipt digest, or local test supports a scientific performance claim. |

## Next safe action

Keep P5/P6 blocked. The next material action requires independent custody and
an explicit live-study authorization; before then, only append-only local
evidence-package closure work is safe.
