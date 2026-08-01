# P2 scientific payload firewall addendum v1

## Status

Closed remediated at 2026-07-31T20:27:31Z. This is an additive P2 evidence
and regression-boundary record. It corrects a defect found in the optional
`scientific_v1` value firewall without revising the historical P2 receipt,
Runtime V1 event schema, CLI semantics, provider behavior, or execution
authority.

## Objective

Ensure that the `scientific_v1` event payload firewall rejects a small,
predeclared set of synthetic secret-shaped strings both before event creation
and when validating a hash-correct JSONL replay. The objective is prevention
of an identified regression surface, not a claim that the runtime can detect
all credentials or that any real secret was present.

## Inputs

| Input | Required use |
| --- | --- |
| Frozen [P2 receipt](receipts/p2-runtime-contracts.json) | Preserve the original Runtime V2 contract observation as a historical artifact. |
| Historical [P2 phase document](02-runtime-scientific-contracts.md) | Preserve the original no-CLI/no-execution boundary. |
| `events.py` firewall and `test_scientific_contracts.py` fixtures | Reproduce, repair, and bound only the opt-in `scientific_v1` validation path. |
| Synthetic in-memory probe | Record the failure without using a credential, provider, file, engine, or network request. |

## Tools and authority

- Allowed: source inspection, a synthetic in-memory payload, fixture-only
  JSONL replay, a targeted source/test patch, SHA-256 checks, and one focused
  Runtime V2 test invocation.
- Not allowed: credential access, provider/API calls, prompt/transcript
  capture, CLI changes, engine/scheduler execution, dependency installation,
  commit, or push.

## Budget

| Resource | Ceiling | Observed |
| --- | ---: | ---: |
| Synthetic probes | 1 | 1 |
| Focused Runtime V2 test invocation | 1 | 1 |
| Provider/API/engine/scheduler calls | 0 | 0 |
| CLI semantic changes | 0 | 0 |
| Real credential values retained | 0 | 0 |

## Artifacts

- [Machine-readable receipt](receipts/p2-scientific-firewall-addendum-v1.json)
  hashes the historical P2 inputs and the repaired source/test/documents.
- [Dedicated validator](../../../scripts/review/validate_frontier_p2_scientific_firewall_addendum.py)
  verifies all pinned artifacts, failure-record completeness, zero authority
  use, and the limited gate/claim contract.
- The existing focused Runtime V2 test file gains three synthetic patterns at
  both creation and replay boundaries. It contains no usable credential.

## Failure, hypothesis, and minimal change

| Field | Record |
| --- | --- |
| Failure | A harmless in-memory `scientific_v1` claim statement containing a synthetic `api_key=` shape was accepted. |
| Hypothesis | Raw-string regexes used doubled backslashes, so their intended word-boundary and whitespace tokens were interpreted as literal backslash sequences. |
| Minimal change | Correct only the three value-pattern escapes in `events.py`; add create/replay regression cases for synthetic key-assignment, bearer, and `sk-` shapes. |
| Evidence | One synthetic in-memory probe was accepted before the patch; source inspection showed the doubled escapes. |
| Result | After the correction, all three shapes are rejected at event creation and during replay of a hash-correct JSONL row. |
| Limitation | The firewall is a heuristic, opt-in `scientific_v1` guard. It cannot prove a payload has no secret, scan arbitrary legacy fields, or substitute for a secret-management boundary. |
| Rollback boundary | Revert only this additive correction and regression test if it creates a demonstrated false-positive compatibility regression; retain this evidence record and do not weaken the guard without a reviewed replacement. |

## Gates

| Gate | Current status | Evidence boundary |
| --- | --- | --- |
| P2A-G1 creation firewall | Passed | All three predeclared synthetic shapes raise the protected-value rejection before event creation. |
| P2A-G2 replay firewall | Passed | A hash-correct JSONL row containing each synthetic shape is rejected on load. |
| P2A-G3 Runtime V1 preservation | Passed narrowly | The existing frozen V1 fixture replay remains in the focused test; no V1 event kind or schema changes were made. |
| P2A-G4 scope preservation | Passed | No provider, CLI, engine, scheduler, or approval/executor path was invoked or changed. |
| P2A-G5 complete secret prevention | Unresolved | Pattern matching cannot establish universal secret detection. |

## Blockers

- This repair does not implement executor-side consumption of an approval,
  create a normal provider tool loop, or authorize dispatch.
- It does not establish a chemistry result, a held-out outcome, replication,
  training eligibility, publication readiness, or SOTA.
- Any future expansion beyond `scientific_v1` needs a separately reviewed
  compatibility and secret-handling design.

## Phase-close validation

The one focused close check was:

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/runtime/test_scientific_contracts.py -q
```

It passed `18` tests in `0.90 s`. This is a fixture-only runtime validation;
it is not product, provider, CLI, chemistry-engine, or release validation.

## Claim-evidence ledger

| ID | Claim type | Statement | Status |
| --- | --- | --- | --- |
| P2A-C1 | source observation | The pre-patch `scientific_v1` value patterns accepted one synthetic secret-shaped statement. | Supported by the recorded in-memory probe. |
| P2A-C2 | code observation | The repaired value patterns reject the three fixed synthetic shapes at creation and replay boundaries. | Supported by focused fixtures only. |
| P2A-C3 | inference | Runtime V2 prevents all credential retention or secret exposure. | Rejected; the guard is heuristic and opt-in. |
| P2A-C4 | unresolved uncertainty | Executor-side approval consumption, normal provider behavior, and chemistry-result integrity are now established. | Unresolved; outside this repair. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P2A-D1 | Patch the escape defect rather than broaden schemas or event kinds. | The defect is localized to three regexes and needs no routing change. | Remove only the localized patch if a reviewed compatibility regression is demonstrated. |
| P2A-D2 | Test both creation and replay. | Persisted rows can bypass ordinary creation and still require value-boundary validation. | Preserve both checks in future refactors. |
| P2A-D3 | Leave all P3–P6 red/no-go decisions unchanged. | This is a security regression repair, not evidence of model, science, or evaluation capability. | A future phase requires its own evidence and authority. |
