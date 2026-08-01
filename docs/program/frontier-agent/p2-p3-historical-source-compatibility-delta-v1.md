# P2/P3 historical source-compatibility delta v1

## Status

Closed reconciled compatibility delta at 2026-07-31T20:39:05Z. The frozen P3
fault suite records exact source hashes, including the two P2 firewall files.
After the later P2 regression repair, the historical P3 validator correctly
reports those files as drifted. This delta preserves the old receipt and
validator unchanged, records that expected red result, and supplies a separate
current integrity check rather than reclassifying historical P3 evidence as
current.

## Objective

Distinguish a frozen P3 source snapshot from a later, hash-pinned P2 firewall
repair. Establish only that the two changed files exactly match the P2
addendum, that the original P3 receipt and validator remain byte-identical,
and that no P3 claim, budget, fixture, or gate is promoted.

## Inputs

| Input | Required use |
| --- | --- |
| Frozen [P3 fault-suite receipt](receipts/p3-single-agent-fault-suite.json) | Recover its exact historical source hashes and retain zero-authority/fixture-only P3 boundaries. |
| [P2 firewall addendum receipt](receipts/p2-scientific-firewall-addendum-v1.json) | Authorize only the current hashes for `events.py` and the Runtime V2 contract test. |
| Frozen [`validate_frontier_program.py`](../../../scripts/review/validate_frontier_program.py) | Verify the historical validator itself remains at the P3-recorded source hash. |
| Current P2 source/test hashes | Confirm the two source drifts match the P2 repair, not an unrecorded change. |

## Tools and authority

- Allowed: local SHA-256 comparisons, receipt parsing, one recorded historical
  validator invocation, one focused compatibility-validator test, and local
  text/JSON validation.
- Not allowed: modification of the original P3 receipt or validator, provider
  calls, credentials, engines, schedulers, CLI changes, dependency installs,
  commits, or pushes.

## Budget

| Resource | Ceiling | Observed |
| --- | ---: | ---: |
| Historical P3 validator invocation | 1 | 1 |
| Focused compatibility test | 1 | 1 |
| Changes to frozen P3 receipt/validator | 0 | 0 |
| Provider/API/engine/scheduler calls | 0 | 0 |

## Observed historical result

The unchanged historical program validator was invoked once after the P2
repair. It exited nonzero with exactly two source-hash drift findings:

- `chemsmart/agent/runtime/events.py`
- `tests/agent/runtime/test_scientific_contracts.py`

That is expected evidence, not a passing current-program result: P3's source
receipt predates the P2 patch. The validator source itself still matches its
P3-recorded SHA-256. No source, fixture, P3 receipt, budget, provider call, or
fault-suite outcome was modified to make it pass.

## Artifacts

- [Machine-readable compatibility receipt](receipts/p2-p3-historical-source-compatibility-delta-v1.json)
  pins the original P3 receipt, the P2 repair receipt, both before/after
  hashes, and the original-validator result class.
- [Dedicated validator](../../../scripts/review/validate_frontier_p2_p3_historical_source_compatibility.py)
  accepts only the two declared source deltas; any other P3 drift, an altered
  original validator, or a promoted P3/P5/P6 gate fails.

## Gates

| Gate | Current status | Reason |
| --- | --- | --- |
| Historical P3 source-hash check | Expected red | It correctly detects the two later P2 source changes. |
| P2 firewall source integrity | Passed | Both current hashes match the separate P2 addendum. |
| Original P3 validator integrity | Passed | Its current SHA-256 still equals the P3-recorded SHA-256. |
| P3 frozen evidence interpretation | Passed narrowly | P3 remains a fixture-only, zero-authority historical record. |
| P5/P6 eligibility and no-go | Red/no-go unchanged | A provenance reconciliation provides no provider/trial/chemistry/replication evidence. |

## Blockers

- This delta does not make the old P3 validator a current-source validator.
- It does not repair P3's strict live-provider failure, implement executor-side
  approval consumption, or create held-out/trial/chemistry evidence.
- A future change to either reconciled source needs a new addendum; any other
  source drift remains a hard failure.

## Phase-close validation

The one focused close test runs the compatibility validator and establishes
only hash-linked chronology/scope. It is not a P3 current-source green gate or
an evaluation, provider, chemistry, replication, training, paper, release, or
SOTA validation.

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/runtime/test_frontier_p2_p3_historical_source_compatibility.py -q
```

## Claim-evidence ledger

| ID | Claim type | Statement | Status |
| --- | --- | --- | --- |
| P23-C1 | provenance observation | The original P3 validator detects the two later P2 source changes. | Supported by its one recorded nonzero invocation. |
| P23-C2 | provenance observation | The two current drifts exactly match the P2 firewall addendum source hashes. | Supported by hash comparison only. |
| P23-C3 | inference | The frozen P3 source receipt validates the current runtime after the P2 patch. | Rejected. |
| P23-C4 | inference | This delta clears provider, P5/P6, chemistry, replication, training, release, or SOTA gates. | Rejected. |
| P23-C5 | unresolved uncertainty | A later current-source P3 validation is available. | Unresolved; it needs a separate reviewed revision. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P23-D1 | Preserve the original P3 receipt and validator byte-for-byte. | Altering either would erase the historical P3 hash boundary. | Delete only this compatibility delta; never rewrite P3 history. |
| P23-D2 | Permit exactly two declared current source hashes through the separate validator. | They are both pinned by the P2 firewall addendum. | Any further source change needs a new hash-pinned delta. |
| P23-D3 | Report historical-red and current-integrity outcomes separately. | A passing prose label cannot convert an obsolete source snapshot into a current green gate. | Keep the historical result visible in all future summaries. |
