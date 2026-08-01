# P6A — Partial Local Evidence Closure

Status: an append-only, offline partial local evidence closure. It is not a
portable reconstruction, independent replication, release candidate, training
corpus, chemistry result, controlled comparison, or SOTA result.

## Objective

P6 requires a frozen candidate before a clean replication could even be
attempted. The existing P6 evidence index deliberately covers only a small
no-go chain. This addendum binds a wider P0–P6 local reference graph, including
phase artifacts, review records, P5/P5A controls, paper/no-go material,
citations, environment specifications, and required absent evidence.

It must preserve chronology honestly. Several hashes appear only in historical
receipts and their matching bytes are not available in the working tree or
reachable history. The closure therefore distinguishes `current_file`,
`frozen_capture`, `restricted_local`, `negative_evidence`, `git_object`, and
`receipt_only_historical` records instead of rewriting old receipts to match
new bytes.

## Inputs

| Input | Required use |
| --- | --- |
| P0 baseline receipt and baseline Git revision | Preserve the original worktree identity as a historical reference, not as current dirty-tree bytes. |
| P1–P6 receipts, addenda, paper artifacts, and review packet | Expand the local provenance graph and check every referenced `path`/SHA-256 binding that remains locally available. |
| P4 frozen P5 planning capture | Retain it as an immutable capture; do not substitute current P5 text. |
| P5/P5A records | Preserve the preregistration, custody fixture, historical P5A-v1, and fail-closed P5A-v2 without promoting a trial. |
| Citation and environment files | Bind their current bytes while recording that citation correction status and dependency resolution are not newly verified. |

## Historical-content gaps

The validator requires a declared `receipt_only_historical` record for each
locally unavailable source snapshot discovered while traversing the explicit
JSON roots. At closure v1 these are the historical P0/P2/P3 Runtime files,
P2 historical validator, P4's earlier P1/P3 document snapshots, and the
earlier P5 document snapshot retained by the program milestone record.

These gaps are evidence of chronology, not permission to use current files as
substitutes. They keep these facts explicit:

- local evidence references are hash-checked;
- historical content snapshots are incomplete;
- portable reconstruction is not established; and
- independent replication has not been performed.

## Tools and budget

Only local JSON parsing, SHA-256 hashing, graph checks, and focused fixtures
are allowed. The closure performs zero provider/network/executor/engine/
scheduler/training/publication/commit/push operations. It does not invoke the
live-provider runner or any chemistry workflow.

## Artifact and export rules

- P3 grader-only seeds are `restricted_local`, never exportable as review or
  training material.
- P4 archived parser fixtures are `negative_evidence`; they remain explicitly
  non-admissible as Frontier chemistry results.
- `environment.yml`, `environment-windows.yml`, `pyproject.toml`, and
  `Containerfile` are `environment_spec_unlocked`: no lockfile or resolved
  environment receipt exists.
- External custody, held-out content, raw trials, paired intervals, clean
  replication, and a training corpus are `absent_required` records, not empty
  fields to impute.

## Gates

| Gate | Status | Boundary |
| --- | --- | --- |
| P6A-G1 current local binding | Passed locally | Listed present files and recursive receipt bindings match their SHA-256 values. |
| P6A-G2 chronology preservation | Passed locally | Historical gaps are named rather than silently replaced by current files. |
| P6A-G3 partial-closure classification | Passed locally | The manifest rejects a full-content or portable-reconstruction status. |
| P6A-G4 restricted/negative/absent records | Passed locally | Seed, archived-parser, and required-missing evidence classes are enforced. |
| P6-G2 independent replication | Red | Historical content is incomplete and no clean environment reconstruction exists. |
| P5-G4/P5-G5 and all paper/training/SOTA gates | Red/no-go unchanged | No held-out controlled trial, chemistry result, replication, or authority exists. |

## Failure and decision ledger

| ID | Failure | Hypothesis | Minimal change | Evidence | Result | Limitation | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P6A-F1 | The existing evidence index did not traverse the broader P0–P6 package. | An explicit root graph plus recursive receipt bindings exposes coverage and drift. | Add a no-go closure manifest and offline validator. | Source inventory and focused closure checks. | Present local references are hash-checked. | It does not reconstruct absent history. | Replace only with a reviewed expanded closure revision. |
| P6A-F2 | Historical source hashes differ from current files after later repairs/addenda. | Explicit snapshot modes prevent a current hash from masquerading as historical bytes. | Register each discovered mismatch as receipt-only historical. | P2/P3 compatibility delta and P4/P6 receipts. | Chronology is preserved with no receipt rewrite. | Matching historic bytes remain unavailable. | Remove a gap only when the exact bytes are archived and independently verified. |
| P6A-F3 | A loose dependency specification could be mistaken for a reproducible environment lock. | Explicit unlocked status prevents false reconstruction readiness. | Classify all four environment specifications as unlocked. | Current environment and project files. | Portable reconstruction stays false. | No clean environment receipt exists. | Change only after a separately authorized resolved-environment capture. |
| P6A-F4 | Restricted seeds or archived parser fixtures could be exported or misread as results. | Export classes make non-admission machine-checkable. | Require restricted, negative, and absent artifact modes. | Focused malformed-export fixtures. | Boundary violations fail closed. | Classification does not create a held-out or chemistry result. | Replace only with a reviewed data-governance revision. |
| P6A-F5 | The first canonical digest rendered omitted optional fields as null after parsing, so an otherwise intact manifest could not reload. | The digest representation must preserve the serialized optional-field convention. | Omit absent optional fields from canonical artifact payloads. | Initial focused test failure, then focused reload fixture. | The exact serialized manifest and a recomputed tampered manifest now share one canonical digest rule. | This does not verify content outside the declared graph. | Change canonicalization only in a versioned closure revision. |
| P6A-F6 | The direct validator could not import the local harness when launched as a script. | A review entrypoint must locate its repository package without relying on ambient `PYTHONPATH`. | Prepend the repository root derived from the validator location. | One failed direct invocation before any closure verdict. | The dedicated validator becomes self-contained for the checked-out package. | This does not demonstrate a clean environment or independent reconstruction. | Replace only with a packaged entrypoint validated in a separately authorized environment. |
| P6A-F7 | Receipt self-validation found stale bound hashes after its validator was expanded. | A closure receipt must verify every bound byte before it can pass. | Update manifest/validator bindings atomically and rerun the validator. | One direct stale-hash failure. | Stale bindings are visible and corrected only by exact new hashes. | Local byte consistency is not independent reproduction. | Any later bound-source change requires a new receipt revision. |

## Phase-close validation

Run the focused closure test and dedicated validator once. They validate a
local reference graph only; neither is product, provider, chemistry,
replication, training, publication, or SOTA validation.

## Next safe action

Keep P5 and P6 blocked. A later clean replication requires separately
authorized environment construction plus complete historical bytes, raw
receipt/output provenance, independent custody, and a qualifying study.
