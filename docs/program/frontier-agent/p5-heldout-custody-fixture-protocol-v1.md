# P5 held-out custody fixture protocol v1

## Status

Closed as a fixture-only custody-admission control. It is append-only with
respect to the frozen P5 preregistration and does not provision an external
catalog, access a held-out case, attest an independent holder, run a model, or
make the P5 study eligible.

## Objective

Make P4-RT-02 and P5-F2 operationally harder to bypass: define a no-content
prospective custody shape that refuses a checkout-visible development case,
requires an opaque independent-custodian declaration, preserves the frozen P5
factor/repetition surface, and returns P5 ineligible even when every fixture
shape check passes.

## Inputs

| Input | Required use |
| --- | --- |
| Frozen [P5 preregistration](../../../tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json) | Retain the eight configurations, three repetitions, zero authority budget, public-development catalog, and all P5 red gates. |
| Frozen [P5 close receipt](receipts/p5-component-ablation.json) and [failure ledger](receipts/p5-failure-ledger.json) | Preserve the blocked result and its F2 custody limitation. |
| Frozen [P4 red-team finding](reviews/p4-red-team-findings-v1.json) | Preserve the rule that checkout-visible seeded fixtures are never held out. |
| Post-P3-v2 [P1/P5/P6 reconciliation](receipts/p1-p5-p6-post-p3-v2-reconciliation-v1.json) | Preserve P5's `red_false_no_trials` status after the narrow direct provider specimen. |

## Tools and authority

- Allowed: deterministic digest-only dataclasses, P5 preregistration loading,
  in-memory synthetic fixture commitments, structural checks, static import
  checks, source hashes, and focused tests.
- Not allowed: creating or retrieving a held-out catalog; retaining a held-out
  task, seed, geometry, prompt, output, score, or raw case identifier;
  external API/provider use; tool dispatch; command execution; chemistry engine
  or scheduler use; dependency installation; commit, push, publication, or
  P5/P6 gate promotion.

## Budget

| Resource | Ceiling | Observed |
| --- | ---: | ---: |
| Frozen P5 preregistration loads | 1 fixture scope | 1 fixture scope |
| Synthetic sealed matrix shape | 1 in-memory case × 8 configs × 3 repetitions | 1 only |
| Actual held-out catalog/case/seed accesses | 0 | 0 |
| Provider, engine, scheduler, command, or external-evaluator calls | 0 | 0 |
| P5 trial receipts or aggregates | 0 | 0 |

## Artifacts

- An unwired `frontier_heldout_custody` module. Its proposed sealed trial key
  contains only domain-separated case commitments and control digests, never a
  case identifier or task content.
- Focused fixtures for a complete synthetic shape, development-case reuse,
  invalid/claimed-real custody, input digest drift, duplicate and incomplete
  matrices, pair/surface/custody drift, and static unwired behavior.
- This protocol, a zero-authority receipt, and a dedicated integrity validator.
  The frozen P5 artifacts remain hash-pinned inputs and are not edited.

## Fixture contract

`FixtureHeldOutCustodyEnvelope` is always `fixture_only` and always records
`real_custody_verified=false`. It binds the frozen P5 manifest digest, visible
public-development catalog digest, grader-seed-manifest digest, an opaque
external-catalog commitment, and an opaque custodian-identity commitment. The
module cannot verify an external person, organization, signature, or catalog;
those are deliberately outside this checkout.

`FixtureSealedTrialKey` has only a domain-separated case commitment,
configuration, repetition, pair commitment, surface-control digest, and custody
commitment. The deterministic evaluator rejects a known public-development case
commitment; duplicate tuples; unknown configurations; incomplete eight-way
pairs; anything other than the preregistered three repetitions; pair/surface
drift; or custody-commitment drift. A structurally valid fixture result remains
`p5_evaluation_eligible=false` with the unchanged P5 red-gate list.

## Gates

| Gate | Current status | Evidence boundary |
| --- | --- | --- |
| P5H-G1 development-only reuse refusal | Passed in fixture | A domain-separated commitment derived from a visible P3 case is refused. |
| P5H-G2 sealed factorial/repetition shape | Passed in fixture | The synthetic digest-only matrix requires all 8 configurations for exactly 3 repetitions. |
| P5H-G3 fail-closed study eligibility | Passed in fixture | Even a complete synthetic shape reports every frozen P5 red gate and `false` eligibility. |
| P5H-G4 actual independent custody | Unresolved | No external holder, catalog, attestation, or hidden case exists or is accessed. |
| P5-G4/P5-G5 benefit/replication readiness | Blocked unchanged | No trial receipt, score, interval, environment capture, or independent rerun exists. |

## Failure, hypothesis, and minimal-change ledger

| ID | Failure | Hypothesis | Minimal change | Evidence | Result | Limitation | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P5H-F1 | P5 has no independent held-out catalog or commitment, so source-controlled P3 material could be mislabeled. | A digest-only fixture control can at least forbid reuse of known development cases and make actual external custody an explicit unresolved input. | Add an unwired custody shape; do not create a catalog or revise P5. | P5-F2, P4-RT-02, and focused visible-case commitment refusal. | Fixture reuse and claimed-real-custody paths fail closed; no actual custody claim is made. | Digest checks cannot prove secrecy, independence, or non-leakage outside the checkout. | Replace only with an external custody interface and a new authorized P5 preregistration revision. |
| P5H-F2 | Future paired aggregates can be distorted by an incomplete or drifting sealed matrix before scores exist. | A no-content key shape should require the frozen 2 × 2 × 2 × 3 pairing and common pair/surface/custody controls. | Add deterministic prospective shape checks only. | Focused duplicate, incomplete, pair, surface, and custody drift fixtures. | Structural defects are rejected before any possible score/aggregate. | No trial outcome, interval, or statistical analysis is produced. | Retire only if a future scorer proves equivalent or stronger validation over retained raw receipts. |
| P5H-F3 | A fixture-positive custody shape could be overread as an external-held-out evaluation. | The result object must be incapable of reporting P5 eligibility and must carry the original red-gate list. | Hard-code `p5_evaluation_eligible=false` and use the frozen eligibility result. | Complete synthetic shape test. | The valid fixture shape remains explicitly ineligible. | This does not solve provider, executor, chemical-result, trial, or replication gates. | Do not relax without a separately authorized live study design and evidence. |

## Blockers

- P5H-G4 remains red. An actual external custodian must be independently named
  and authorized outside the checkout, provide a non-checkout-visible catalog
  commitment and custody/attestation method, and support an approved access and
  audit protocol. This fixture cannot create or validate those facts.
- P5-RG-01 through P5-RG-08 remain red. In particular there is still no active
  provider/tool-loop evidence, live authority, executor consumption, chemical
  result trace, trial receipt, or aggregate.
- Any real P5 trial requires a materially new user decision covering the
  provider/model/tool/prompt/budget envelope, external custody/access, active
  executor boundary, and separate chemistry-engine authority if needed.

## Phase-close validation

The close runs one focused custody test and one receipt-integrity wrapper. A
passing result validates only a prospective local refusal boundary. It is not
evidence of external custody, a held-out result, a controlled comparison, a
paper result, replication, training, release, or SOTA status.

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_heldout_custody.py -q
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_p5_heldout_custody_fixture.py -q
```

## Claim-evidence ledger

| ID | Claim type | Statement | Status |
| --- | --- | --- | --- |
| P5H-C1 | code observation | The fixture rejects the defined development-case and sealed-matrix violations while retaining no case content. | Supported by focused deterministic fixtures only. |
| P5H-C2 | code observation | A complete synthetic custody shape cannot report P5 evaluation eligibility. | Supported by focused deterministic fixture only. |
| P5H-C3 | inference | Independent external custody, hidden held-out performance, or a component effect is established. | Rejected. |
| P5H-C4 | unresolved uncertainty | An independent custodian and a safe access/audit interface are available. | Unresolved. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P5H-D1 | Retain no raw held-out identifier or content in the new source/receipt. | P4-RT-02 and P5-F2 require a boundary that source-controlled fixtures cannot satisfy. | Introduce an external sealed interface only with separate authority. |
| P5H-D2 | Do not edit P5's frozen manifest or `HeldOutBoundary`. | Its hash-pinned `held_out_commitment_sha256=null` records the correct current no-custody state. | Create a new P5 preregistration revision only after material inputs exist. |
| P5H-D3 | Make a complete fixture shape ineligible by type and value. | Structural checks are not custody verification or study evidence. | Any eligibility path needs a separately approved active study boundary. |
