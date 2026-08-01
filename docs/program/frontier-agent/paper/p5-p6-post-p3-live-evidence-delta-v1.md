# P5/P6 post-P3 live evidence delta v1

## Status

Closed blocked delta at 2026-07-31T20:15:54Z after one focused offline
validator passed. It records a later P3 provider observation without modifying
the frozen P5 preregistration, P5 phase-close receipt, P6 no-go manifest, P6
phase-close receipt, P6 paper outline, or replication/training no-go record.

## Objective

Time-scope the historical P5/P6 no-provider-execution statements to their own
phase-close times, connect the later red P3 v1 receipt, and preserve the
unchanged no-go decision. This is not an ablation result, a provider capability
pass, a normal tool-loop result, a chemistry result, a training decision,
replication, a paper release, or a SOTA claim.

## Inputs

| Input | Required use |
| --- | --- |
| Frozen P5 receipt and preregistration | Establish the zero-call, eight-condition study boundary and all eight red gates at P5 close. |
| Frozen P6 manifest, receipt, and no-go documents | Establish the original internal no-go decisions and their hashes. |
| P3 v1 live receipt | Supply the one later bounded, non-executing provider observation and its strict failure. |
| P1 post-P3 addendum | Supply the provider/literature reconciliation without rewriting historical P1 evidence. |

## Tools and authority

- Allowed: local hash, chronology, and claim-scope validation.
- Not allowed: any new provider call, trial, held-out access, tool dispatch,
  engine, scheduler, training, dependency install, publication, commit, or
  push.
- The delta retains no credential, prompt, transcript, reasoning, arguments,
  raw response, or provider URL.

## Budget

| Resource | Ceiling |
| --- | --- |
| New external/model/trial calls | 0 |
| Changes to P5/P6 frozen artifacts | 0 |
| P5 configurations or held-out repetitions | 0 / 0 |
| Focused delta validation | one offline invocation at close |

## Artifacts

- [Machine-readable provenance delta](p5-p6-post-p3-live-evidence-delta-v1.json)
  pins all base artifacts by SHA-256 and provides its own failure/decision
  ledger.
- A dedicated validator will reject drift in P3/P5/P6 base artifacts, any
  red-gate promotion, secret-shaped raw content, or any assertion of a study,
  training, or release result.

## Gates

| Surface | Current status | Reason |
| --- | --- | --- |
| P5-RG-01 provider capability | Red | The one P3 v1 response had invalid arguments under its fixed 64-token protocol. |
| P5 evaluation eligibility | Red | No held-out boundary, normal live authority, executor gate, chemistry result, complete trial, or aggregation exists. |
| P6-B3 provider capability and live trials | Red | A narrow transport/tool-name observation is not valid provider capability or a trial. |
| P6 results/SOTA/replication/training/publication | No-go | All original P6 blocker conditions remain. |
| Frozen-artifact integrity | Required | The delta supplements chronology; it never changes an original manifest or receipt. |

## Blockers

- P3 v1 is exhausted; it cannot be retried or widened in place.
- The P5 2 × 2 × 2 study still lacks all execution authority and outcomes.
- P6 still lacks clean replication, held-out comparison, chemical-result
  evidence, training records/authority, and publication authority.

## Phase-close validation

Run the dedicated validator once after hashes are frozen. It establishes only
that the negative-result chain is internally consistent. It cannot change any
P5/P6 scientific, comparative, replication, training, or release conclusion.

The close invocation was:

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_p5_p6_live_delta.py -q
```

It passed `1` test in `0.05 s` at 2026-07-31T20:15:54Z. The result validates
only chronology, hashes, redaction, and unchanged no-go scope; it is not a
study, a capability pass, or a paper/training/release validation.

## Claim-evidence ledger

| ID | Claim type | Statement | Required evidence | Status |
| --- | --- | --- | --- | --- |
| P56-D-C1 | observation | A later P3 request was bounded, non-executing, and structurally red. | P3 v1 receipt. | Supported narrowly. |
| P56-D-C2 | inference | P3 v1 clears P5 provider capability or permits a P5 trial. | Valid protocol plus all P5 red-gate evidence. | Rejected. |
| P56-D-C3 | inference | P3 v1 changes the P6 no-go for results, SOTA, replication, training, or publication. | Full P5/P6 future evidence and authority. | Rejected. |
| P56-D-C4 | provenance observation | P5/P6 no-provider statements remain true at their own close times. | Original timestamps plus later P3 timestamp. | Supported time-scoped. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P56-D-D1 | Preserve all frozen P5/P6 artifacts. | Their source hashes and self-digests encode the historical no-go decision. | Delete only this additive delta; never edit the frozen records. |
| P56-D-D2 | Keep P5-RG-01 and P6-B3 red. | Strict tool arguments failed and no trial exists. | A future program revision needs new capability, authority, held-out, and trial evidence. |
| P56-D-D3 | Publish no scientific/paper/training conclusion from this delta. | It is provenance correction only. | Require separate authority and evidence even if a future protocol succeeds. |
