# P5/P6 Successor Integrity Reconciliation v1

## Status

Closed blocked, append-only receipt-level reconciliation. This package pins the
complete current-file provenance declared by P5A-v3 and P5H2, including their
predecessor artifacts, while preserving frozen P5, P6, P6A, and P6B bytes. It
does not amend P6A or turn local fixtures into custody, trials, analysis,
replication, training, release, paper, or SOTA evidence.

## Objective

P5A-v3 addressed a new cross-version policy-ingress defect after P6A was
frozen. Independently, the original P6B delta bound the P5H2 receipt and its
source set, but did not recursively enumerate P5H2's five base artifacts.
This reconciliation gives both later P5 successors a complete, inspectable
current-file graph without rewriting the historical candidate closure.

## Inputs

| Input | Required use |
| --- | --- |
| P5A-v1/v2/v3 receipts and declared artifacts | Verify the complete predecessor-to-v3 chain, fixture-only restrictions, and the qualified v2 scope. |
| P5H-v1/P5H2 receipts and declared artifacts | Verify the full base/source graph, including the preserved-but-qualified historical static guard. |
| P5 close, P4 review records, and P6 no-go core | Require P5-G4/G5 and P6-G2/G4/G5 to remain blocked. |
| P6A candidate closure and P6B delta | Pin their current bytes, retain P6A's 101-artifact scope, and prove neither includes the later successors. |

## Tools, budget, and authority

Only local JSON parsing, fixed-path SHA-256 verification, and a focused
validator test are in scope. Authority remains zero for providers, held-out
catalogs/cases, tool dispatch, execution, chemistry engines, schedulers,
network, installs, training, publication, commits, and pushes. No source,
fixture, receipt, or frozen decision is mutated.

## Artifact graph

```text
P5A-v1 ──> P5A-v2 ──> P5A-v3 ──┐
                                 ├─> P6 successor-integrity reconciliation
P5H-v1 ───> P5H2 ───────────────┤
                                 ├─> frozen P5/P6 no-go checks
P6A candidate closure ───────────┤
P6B P5H2 delta ──────────────────┘
```

Each listed predecessor graph is checked as explicit files and hashes; there
is no discovery-by-glob, held-out-content access, or invocation of a provider,
runner, engine, or scheduler.

## Gates

| Gate | Status | Boundary |
| --- | --- | --- |
| P6C-G1 P5A-v3 transitive integrity | Passed locally | Every artifact declared by P5A-v3 and P5A-v2 is hash-pinned as a current file. |
| P6C-G2 P5H2 transitive integrity | Passed locally, qualified control retained | Every P5H2 base/source artifact is pinned; P5H2-G1 remains qualified, not green. |
| P6C-G3 frozen P5/P6/P6A/P6B preservation | Passed locally | P5 and P6 decision bytes retain their recorded no-go identities. |
| P6C-G4 P6A scope boundary | Passed locally | P6A remains a 101-artifact historical closure excluding P5A-v3 and P5H2. |
| P5-G4/P5-G5 | Blocked unchanged | No trial, score, interval, provenance, or independent rerun exists. |
| P6-G2/P6-G4/P6-G5 | Blocked unchanged | No clean replication, eligible training corpus/authority, or release/compute authority exists. |

## Failure and decision ledger

| ID | Failure or decision | Minimal change | Evidence and limitation | Rollback boundary |
| --- | --- | --- | --- | --- |
| P56S-F1 | A legacy malformed policy record can cross the P5A-v2 type boundary. | Add P5A-v3 as a separate strict-admission successor. | Its fixture is local; it authenticates neither policy documents nor external custody. | Remove only P5A-v3 and this reconciliation; never rewrite P5A-v1/v2. |
| P56S-F2 | P6B verified P5H2's receipt and source set but not every declared P5H2 base artifact. | Recursively enumerate and hash-pin all P5H2 bases and sources here. | This proves local file integrity, not the independence of a custodian. | Remove only this reconciliation; leave P6B and historical P5H bytes intact. |
| P56S-F3 | P6A predates both later P5 successors. | Preserve its hash and exclusion boundary rather than changing its manifest. | The resulting package is a local reference graph, not portable reconstruction or replication. | Remove only this reconciliation; never alter P6A. |

## Claims

- Supported: this receipt validates the complete local declared artifact graph
  for P5A-v3 and P5H2 under current bytes, while P5/P6 no-go decisions remain
  unchanged.
- Qualified: P5A-v3 and P5H2 are synthetic prospective integrity controls;
  P5H2 retains its qualified historical-static-guard limitation.
- Unresolved: independent held-out custody, material analysis policy, live
  provider/executor/chemical provenance, paired outcomes and intervals,
  reproducible environment, independent replication, training authority,
  release, paper readiness, and SOTA.
- Rejected: that this reconciliation repairs P6A, makes P5 eligible, or
  supports a scientific/comparative/training/release/SOTA conclusion.

## Phase-close validation

The focused validator test and direct validator validate only local current
files, restricted fields, authority accounting, chronology, and frozen no-go
boundaries. They cannot execute a study or clear a red gate.

## Next safe action

Keep P5/P6 blocked. A live 2×2×2 study requires an independently held
custodian, explicit study envelope and analysis policy, executor evidence, and
separate chemistry-engine authorization where needed.
