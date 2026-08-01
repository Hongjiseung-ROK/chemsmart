# P5A-v3 — Strict Fixture Admission for Pre-Data Analysis

Status: closed as an additive, offline fixture-only successor. It preserves
P5A-v1 and P5A-v2 bytes and adds a strict admission boundary before the v2
structural evaluator. It is not independent custody, a held-out catalog,
provider activity, tool dispatch, chemistry execution, scoring, aggregation,
replication, paper result, training decision, release decision, or SOTA claim.

## Objective

P5A-v2 correctly rejects direct malformed v2 records, but its coverage and
digest checks could accept a legacy v1 decision object with the same visible
attributes. In particular, the v1 constructor accepts `status="bogus"` with a
null digest; when placed in a v2 policy it can reach
`external_evidence_required`. A local fixture also showed that integer `0`/`1`
values can impersonate six deterministic safety booleans in v2.

P5A-v3 creates a concrete-record admission boundary: policy decisions must be
exact `PolicyDecisionV3` instances, each policy is reconstructed into direct
v2 records at ingress, every admitted row uses concrete v2 nested records, and
all six safety fields must be literal booleans. The v2 structural checks are
then reused without changing their source bytes.

## Inputs

| Input | Required use |
| --- | --- |
| [P5 preregistration](../../../tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json) | Retain eight configurations, three repetitions, frozen reference, red gates, and P5 ineligibility. |
| [P5A-v2 contract](p5-predata-contract-v2.md) and [receipt](receipts/p5-predata-contract-v2.json) | Preserve its bytes as a bounded predecessor; qualify its direct-construction evidence rather than rewriting it. |
| [P5A-v1 fixture](../../../chemsmart/agent/harness/frontier_ablation_analysis_lock.py) | Supply the real legacy malformed-record regression fixture; it is not a study outcome. |
| [P5 phase close](receipts/p5-component-ablation.json) | Retain P5-G4 and P5-G5 as blocked. |

## Tools, budget, and authority

Only local source inspection, synthetic opaque fixtures, focused tests, and a
deterministic receipt validator are in scope. The budget is one synthetic case
with 8 configurations × 3 repetitions to exercise admission and structural
shape. This successor uses zero provider, network, executor, tool-dispatch,
chemistry-engine, scheduler, dependency-install, commit, or push calls. It is
unwired from active Runtime V2, providers, CLI schema, and executable paths.

## Artifacts

- [Strict admission layer](../../../chemsmart/agent/harness/frontier_predata_contract_v3.py)
  wraps P5A-v2 without editing it, validates exact policy/row types, and
  checks the six deterministic safety booleans before v2 evaluation.
- [Focused regression tests](../../../tests/agent/harness/test_frontier_predata_contract_v3.py)
  cover a safe synthetic matrix, the actual legacy `bogus` decision ingress,
  integer safety flags, raw-row admission refusal, and a poisoned v2 lock.
- [Receipt](receipts/p5-predata-contract-v3.json) and its deterministic
  validator bind predecessor and successor bytes, redaction, authority use,
  failure records, and unchanged P5 gates.

## Gates

| Gate | Status | Boundary |
| --- | --- | --- |
| P5A3-G1 predecessor preservation | Passed locally | P5A-v1/v2 sources and receipts remain byte-pinned; no frozen artifact is rewritten. |
| P5A3-G2 exact policy admission | Passed in fixture | A real v1 `bogus` decision record cannot enter a v3 policy or wrapped v2 lock. |
| P5A3-G3 boolean safety admission | Passed in fixture | Integer values cannot impersonate the six deterministic safety booleans. |
| P5A3-G4 revalidated structural bridge | Passed in fixture | Only explicit v3-admitted rows reach the unchanged v2 structural evaluator. |
| P5A2-G2/P5A2-G3 historical scope | Qualified | Direct v2 constructor checks remain supported, but cross-version ingress is superseded by v3. |
| P5-G2 through P5-G5 | Red, unchanged | No independent custody, live study, executor/chemistry provenance, analysis, or replication exists. |

## Failure and decision ledger

| ID | Failure | Hypothesis | Minimal change | Evidence | Result | Limitation | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P5A3-F1 | A legacy v1 decision with `status="bogus"` can duck-type into v2 and reach its external-evidence classification. | Exact record types plus canonical reconstruction reject incompatible semantic records. | Add v3 decision and lock wrappers; reconstruct direct v2 policy records at each ingress. | Read-only audit plus real v1 malformed-record regression fixture. | The foreign record and a poisoned v2 lock are rejected before structural evaluation. | No decision document, holder, or external policy is authenticated. | Supersede only with a reviewed strict schema that retains exact-record admission. |
| P5A3-F2 | Integers `0`/`1` can satisfy v2 equality checks intended for deterministic safety booleans. | Exact booleans prevent truthy numeric aliases from entering the admission path. | Wrap rows in `StrictTrialOutcomeV3` and check all six fields with `type(value) is bool`. | Local construction probe and focused integer-flag fixture. | The malformed row is refused before evaluation. | This does not define the material terminal-to-metric mapping. | Resolve semantics only through an authorized analysis-policy revision while retaining strict Boolean representation. |
| P5A3-F3 | The first focused regression expected a later policy-digest rejection for a poisoned v2 lock. | The invariant is fail-closed rejection, not a particular ordering of redundant guards. | Correct only the test expectation to the earlier exact-record-type rejection. | Initial focused run: 1 failed, 3 passed. | The regression now asserts the stronger boundary; no product or policy behavior changed. | This is test-level evidence only. | Retain an explicit assertion that a poisoned v2 lock cannot be wrapped. |

## Blockers

- The material study choices are still unresolved: estimand, successful-block
  mapping, exclusions/missingness, family weights, contrasts, and multiplicity.
- There is no independent held-out custodian, non-leaking catalog commitment,
  active provider/model/tool/prompt/budget authorization, native receipt,
  executor evidence, chemical provenance, resolved environment, raw paired
  trial data, aggregate, or independent rerun.
- P4 active approval-consumption and chemical-provenance findings remain red.
  This module does not import or dispatch active execution.

## Phase-close validation

Run the v3 focused test and receipt validator once after source hashes are
bound. The resulting check proves only local fixture admission behavior; it
cannot clear a P5/P6 gate or validate a scientific claim.

## Claim-evidence ledger

| Claim class | Status |
| --- | --- |
| Supported | The specified legacy malformed decision and integer safety flags are rejected on the P5A-v3 fixture admission path. |
| Qualified | This is local prospective integrity evidence; v2 itself remains preserved historical code, not an external custody or outcome verifier. |
| Unresolved | Independent custody, live trials, deterministic grading outputs, analysis, component effects, replication, paper readiness, training, release, and SOTA. |
| Rejected | That the regression fixture, an opaque hash, or local focused validation establishes a chemistry, performance, replication, training, release, paper, or SOTA result. |

## Next safe action

Keep P5 and P6 blocked. Reconcile this append-only successor into the current
P6 no-go evidence ledger without amending P6A. The next material study action
requires independent custody and an explicit bounded live-study authorization.
