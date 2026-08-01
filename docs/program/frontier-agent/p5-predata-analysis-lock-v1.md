# P5A — Pre-data analysis lock v1

## Status

Closed as a fixture-only, pre-data structural control. It is append-only with
respect to the frozen P5 v1 preregistration and does not admit an external
trial, calculate a score or confidence interval, access a provider, execute a
tool, run a chemistry engine, or change any P5/P6 gate. A structurally valid
synthetic matrix remains `external_evidence_required`, with P5 evaluation and
adoption both false.

## Objective

P5 froze the 2 x 2 x 2 configuration surface and broad bootstrap settings, but
did not yet bind an admissible outcome-record shape or the material analysis
decisions needed before seeing held-out data. This increment makes those
degrees of freedom explicit without choosing them by model opinion or
reclassifying a checkout-visible case as held out.

## Inputs

| Input | Required use |
| --- | --- |
| [Frozen P5 preregistration](../../../tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json) | Pin its canonical digest, raw file digest, eight configurations and order, `D0-E0-C0` reference, three repetitions, zero-call boundary, scoring roles, bootstrap pins, and red gates. |
| [P5 close receipt](receipts/p5-component-ablation.json) and [failure ledger](receipts/p5-failure-ledger.json) | Preserve `P5-F2` and the absence of trial receipts, outcomes, intervals, and replication evidence. |
| [P5 custody fixture protocol](p5-heldout-custody-fixture-protocol-v1.md) | Reuse its visible-development-case commitment refusal while keeping custody fixture-only. |
| [Ablation protocol](../../evaluation/frontier-agent-ablation-protocol.md) | Preserve deterministic-first scoring, expert-secondary/LLM-supplementary roles, paired nonparametric bootstrap 95% CI, 10,000 resamples, seed 240731, and all-failure retention. |
| P4 stop findings | Retain P4-ST-01, P4-RT-02, P4-HA-01, and P4-CH-01 as unresolved/red boundaries. |

## Tools and authority

- Allowed: immutable dataclasses, local SHA-256 hashes, one frozen
  preregistration fixture load, synthetic opaque digest rows, static import
  checks, and focused offline tests.
- Prohibited: external-custodian contact, catalog or case access, real outcome
  retention, provider/API calls, tool/command dispatch, chemistry engines,
  schedulers, dependencies, commits, pushes, publication, or P5/P6 promotion.
- The analysis lock accepts no raw task, case identifier, seed, prompt,
  transcript, tool arguments, native output, scorer text, or score artifact.

## Budget

| Resource | Ceiling | Observed |
| --- | ---: | ---: |
| Frozen P5 preregistration loads | 1 fixture scope | 1 fixture scope |
| Synthetic matrix shape | 1 opaque case x 8 configurations x 3 repetitions | 1 only |
| Held-out catalog, case, seed, outcome, or score accesses | 0 | 0 |
| Provider, engine, scheduler, command, or network calls | 0 | 0 |
| Bootstrap, aggregation, adoption, or SOTA calculations | 0 | 0 |

## Artifacts

- [Analysis-lock module](../../../chemsmart/agent/harness/frontier_ablation_analysis_lock.py)
  is unwired from active agent paths. Its lock binds the frozen P5 manifest
  bytes (`deec08f...53536ad`) and canonical study digest, source configuration
  surface, reference, repetitions, red-gate register, and policy digest.
- [Focused tests](../../../tests/agent/harness/test_frontier_ablation_analysis_lock.py)
  use only one synthetic opaque matrix. Its rows are argument-only fixtures and
  are neither retained nor interpreted as chemical, provider, or study results.
- This page, the [zero-authority receipt](receipts/p5-predata-analysis-lock-v1.json),
  and a focused integrity validator record the boundary. Frozen P5 v1 files
  are inputs, never rewritten.

## Contract

`FixturePredataAnalysisLock` binds the full frozen P5 v1 surface plus a
`FixtureAnalysisPolicy`. The policy locks only protocol facts already fixed:
deterministic grading is primary, experts are secondary, LLM judges are
supplementary, retry remains `none`, and paired bootstrap uses the preregistered
method, confidence, resamples, and seed.

Every future analysis decision is an opaque document digest with one of two
statuses: `locked` or `unresolved`. The following decisions intentionally
remain unresolved in the current valid pre-data lock:

1. analysis unit and primary estimand;
2. treatment of repeated paired trials;
3. blocked, timeout, retry, budget-exhaustion, and missing-data coding;
4. exclusions and denominator;
5. held-out family grouping and weighting;
6. comparator/contrast family;
7. adoption-threshold mapping;
8. multiplicity treatment.

The lock also requires opaque definition digests for every named protocol
metric. This includes end-state success, chemical validity, reproducibility,
false pass, unsupported claim, critic precision/recall/false rejection,
policy integrity, and the listed resource-use fields. A digest is a required
future provenance handle, not proof that a metric value exists.

`FixtureTrialOutcome` is a future-only shape used only inside focused synthetic
tests. It contains domain-separated case and family commitments, the frozen
configuration/repetition pair, common pair/surface/custody/lock/policy digests,
typed deterministic status fields, secondary critic accounting, resource
fields, and opaque receipt digests. It retains no raw held-out content. The
validator rejects a visible development commitment, duplicate trial or receipt,
unknown/missing configuration, missing repetition, pair/surface/custody/policy
drift, critic-on/off mismatch, grader-revision drift, or a false-pass
contradiction.

Red-line evidence is retained, not dropped. The recognized fixture vocabulary
includes approval bypass, fabricated evidence, scope expansion, artifact
mutation, secret exposure, prohibited execution, and terminal success behind a
required deterministic red gate. If an agent reports success while
the deterministic terminal state is failed or blocked, the record must mark a
false pass; a red line cannot coexist with deterministic terminal success. An
attempt to emit `enable_default` or `sota_comparison` while current P5 gates
are red is refused. The module never calculates an aggregate or returns an
adoption label.

## Gates

| Gate | Status | Evidence boundary |
| --- | --- | --- |
| P5A-G1 frozen-study binding | Passed in fixture | Raw P5 manifest hash, canonical digest, configuration order, reference, repetitions, and gate register are checked. |
| P5A-G2 outcome-shape refusal | Passed in fixture | Synthetic opaque rows refuse visible development reuse and incomplete/drifting 8 x 3 pairs. |
| P5A-G3 deterministic-first and red-line retention | Passed in fixture | Roles, bootstrap pins, status consistency, and conclusion refusal are structural checks only. |
| P5A-G4 material analysis policy | Unresolved by design | No primary estimand, CI convention, contrast hierarchy, family weighting, missingness, or multiplicity policy is supplied. |
| P5A-G5 external evidence admission | Unresolved | No custodian, catalog, case, real receipt, scorer revision, or outcome exists. |
| P5-G2 through P5-G5 | Red/unchanged | No observed study, interval, benefit, or independent rerun exists. |

## Failure, hypothesis, and minimal-change ledger

| ID | Failure | Hypothesis | Minimal change | Evidence | Result | Limitation | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P5A-F1 | P5 fixed the surface but not a typed receipt-to-analysis record or all material choices before data. | An append-only lock can expose choices without silently selecting statistical policy. | Add opaque decision/metric-definition bindings and keep absent decisions unresolved. | P5 protocol, P5-F2/P5-F5/P5-F8, and focused unresolved-decision fixture. | Missing decisions produce `predata_analysis_incomplete`. | A digest does not supply an actual estimand or evidence. | Replace only with a new authorized preregistration revision containing the explicit decisions. |
| P5A-F2 | A future aggregate could mix rows with differing configuration, surface, custody, or scorer bindings. | Typed digest-only keys can reject drift before any scorer is invoked. | Add a prospective 8 x 3 matrix validator with no retained case content. | Focused duplicate, development reuse, missing pair/repetition, and digest-drift fixtures. | Structural defects are refused; no outcome is scored. | It cannot prove independent custody or receipt truth. | Retire only with a reviewed external-receipt validator that preserves equivalent or stronger invariants. |
| P5A-F3 | A synthetic green-looking row could be mistaken for evidence or used to promote a component. | The result type must be incapable of P5 eligibility/adoption and reject conclusion intents while gates are red. | Hard-code P5 ineligibility and adoption false; retain unchanged red-gate list. | Focused red-line and conclusion-refusal fixture. | Synthetic input remains `external_evidence_required`. | No live or held-out result is represented. | Do not relax without independent custody, explicit authority, complete receipts, and a new study revision. |
| P5A-F4 | The first vocabulary omitted fabricated evidence, despite its being a required integrity red line. | A named fixture event must cover every user-required integrity category. | Add `fabricated_evidence` and a parameterized refusal check. | Source audit after the initial 7-pass focused run. | The corrected rerun records both fabricated-evidence and red-gate-terminal-success cases. | These remain synthetic refusal cases, not observed violations. | Retire only if a future event registry provides a reviewed superset with no semantic weakening. |

## Blockers

- No independent external custodian, catalog commitment, access/audit method,
  raw trial receipt, deterministic scorer revision, environment reconstruction,
  or independent recomputation exists.
- Material analysis choices above are deliberately unresolved. The lock does
  not choose an estimand, resampling unit or CI convention, contrast/multiplicity
  plan, family weighting, missingness coding, critic truth standard, or
  handoff-loss calculation.
- P1/P3/P4/P5 red gates remain intact. In particular this increment does not
  resolve P4-HA-01, P4-CH-01, P4-RT-02, P5-RG-01 through P5-RG-08, or any P6
  replication/paper/training gate.

## Phase-close validation

One focused test group and one dedicated receipt validator are run once. They
validate source/fixture structure only; they do not validate a CLI, provider,
engine, chemistry result, held-out study, interval, replication, paper,
training run, release, or SOTA claim.

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_ablation_analysis_lock.py -q
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python scripts/review/validate_frontier_p5_predata_analysis_lock.py --repo .
```

## Claim-evidence ledger

| ID | Claim type | Statement | Status |
| --- | --- | --- | --- |
| P5A-C1 | code observation | The module binds the frozen P5 study shape and rejects the enumerated synthetic receipt/matrix inconsistencies. | Supported by focused deterministic fixtures only. |
| P5A-C2 | code observation | Unresolved material policy choices remain visible rather than being filled in by a scorer. | Supported by focused deterministic fixture only. |
| P5A-C3 | inference | The fixture establishes custody, admits an outcome, estimates an effect, validates chemistry, or makes P5 evaluable. | Rejected. |
| P5A-C4 | inference | A component should be enabled, ChemSmart exceeds a comparator, or SOTA is supported. | Rejected. |
| P5A-C5 | unresolved uncertainty | An external custodian and a complete fixed analysis policy are available. | Unresolved. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P5A-D1 | Preserve P5 v1 untouched and pin its raw/canonical digests. | Post-data changes must use a new versioned preregistration. | Delete only the additive P5A artifacts if unsuitable. |
| P5A-D2 | Retain no real external evidence or outcome in the lock. | Checkout-visible material cannot prove held-out custody. | Add an external interface only with a material user authorization and independent custody protocol. |
| P5A-D3 | Treat unspecified analysis choices as unresolved. | The protocol does not fix those statistical decisions. | Replace with an explicit preregistered policy, never an inferred default. |
| P5A-D4 | Keep all conclusions off. | No qualifying trial or red-gate clearance exists. | Allow a conclusion only after P5/P6 gates and separate authority are evidenced. |
