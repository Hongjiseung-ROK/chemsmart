# P6 — Replication, paper, and training decision

## Status

Mechanically complete and closed blocked at 2026-07-31T19:32:16Z. P6 produced
an internal no-go evidence package: hash-pinned claim register, paper outline,
replication/training decision, and deterministic release-refusal verifier. It
does not claim independent replication, a chemistry result, a component effect,
training eligibility, publication readiness, or SOTA. Publication, new
dependency/model training, and real compute remain separately approval-bound.

## Objective

Decide, from P1–P5 evidence, whether ChemSmart has a reproducible paper
package, whether any bounded training experiment is justified, and whether a
controlled SOTA-comparison hypothesis remains supported, qualified, unresolved,
or rejected.

## Inputs

| Input | Required use |
| --- | --- |
| P0–P5 receipts and hashes | Full evidence chain, quota use, red lines, failures, and limitations. |
| Independent clean-environment replication receipt | Reconstruct required fixture artifacts, reports, and scores from pinned inputs. |
| Primary literature/citation records | Verify comparative propositions and correction/retraction state. |
| Frozen study results | All eight configurations, raw outcomes, scoring output, and analysis. |
| Training eligibility checklist | Verified visible action/outcome traces, rejected traces, deterministic labels, held-out anti-hacking plan, and resource authorization. |

## Tools and authority

- Allowed: offline evidence-bundle audit, deterministic rerender/score
  replication, paper-outline and methods/SI planning from verified evidence,
  and a conservative decision record.
- Not allowed without a separate explicit approval: publication/submission,
  dependency installation, fine-tuning/SFT/preference/RL run, paid model or
  compute use, real chemistry engines, or external benchmark execution.
- A paper narrative is a derived view of the manifest. It may not replace raw
  receipts, native/archived artifacts, or score outputs.

## Budget

| Resource | Ceiling |
| --- | --- |
| Replication | One independent clean-environment reconstruction per frozen release candidate; bounded repair only through a new receipt revision |
| Paper work | Evidence-derived outline, methods, SI manifest, and claim table only; 0 publication actions |
| Training | 0 runs and 0 new dependencies until the eligibility decision and separate approval |
| SOTA language | 0 unqualified claims; use only a named, controlled, replicable comparison result if one exists |

## Artifacts

- [Internal P6 no-go manifest](paper/frontier-p6-internal-no-go-v1.json),
  canonical digest `41cd0758023d2740b2e396824c1d290483f9db0f4e0a8aee863fe6cc712a76d4`.
  It pins the P0-P5 receipts and permits no external authority.
- [Evidence-derived paper outline](paper/frontier-paper-outline-v1.md), with
  a strict separation between supported infrastructure observations and
  unresolved scientific/comparative claims.
- [Replication and training no-go decision](paper/frontier-replication-training-no-go-v1.md),
  including an eligible-training-record count of zero and a future-only clean
  replication checklist.
- [P6 failure ledger](receipts/p6-failure-ledger.json),
  [phase-close receipt](receipts/p6-replication-paper-training-decision.json),
  and a focused release-refusal verifier.
- No RO-Crate compliance, QCSchema record, independent replication receipt,
  paper submission, training dataset, or publication artifact is claimed or
  created. Those need their own artifact and authority gates.

## Gates

| Gate | Pass condition | Red condition |
| --- | --- | --- |
| P6-G1: evidence completeness | Every reported numerical/comparative claim links to artifacts, units, validators, and citations as applicable. | Narrative-only or untraceable claim. |
| P6-G2: independent replication | A clean pinned environment rebuilds the declared fixture/report/score result within stated tolerance. | One-machine-only result or missing environment artifact. |
| P6-G3: paper integrity | Supported, qualified, unresolved, and rejected claims remain visibly distinct; failures and limitations are included. | SOTA/autonomy/readiness overclaim. |
| P6-G4: training eligibility | Visible verified traces, deterministic labels, held-out anti-hacking evaluation, and separate resource approval exist. | Training from hidden reasoning, unverified traces, or no approval. |
| P6-G5: release authority | Publication, training, dependencies, compute, commit, and push each have explicit user authority. | Implicit external state change. |

At close, P6-G1 and P6-G3 pass only for the internal no-go package: every
statement in its claim register has a receipt locator and its status is visible.
P6-G2, P6-G4, and P6-G5 are blocked. An empty result section is not evidence
completeness for a scientific paper; it is the reason the package refuses such
a release.

## Blockers

- Any P5 red line, missing raw receipt/hash, failed replication, unverified
  source, unresolved literature correction status, or unsupported claim blocks
  a paper/release/SOTA conclusion.
- Absence of verified outcome data blocks training; absence of explicit
  authority blocks training or publication even if evidence is green.

## Phase-close validation

Run the offline bundle/claim/replication verifier once against the frozen
candidate. Then produce a decision table. A red or unresolved gate yields
`blocked` or `keep experimental`, never a success by prose.

The recorded check was:

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_decision_manifest.py -q
```

It passed `4` tests in `0.06 s`. This validates only the internal no-go manifest
and release refusal; it does not test a paper submission, clean environment,
provider, model, chemistry engine, benchmark, or training run.

At the final program milestone, the focused P0-P6 validator group first exposed
P5-F9's documentation-only false positive, then passed `35` tests in `1.19 s`
after its wording-only repair. The group remains a deterministic source,
fixture, and no-go-package check—not product, chemistry, live-model, or release
readiness evidence.

## Final decision table

| Decision surface | Current decision | Evidence boundary |
| --- | --- | --- |
| Results/SOTA paper | No-go | No held-out paired comparison, named comparator, interval, or independent replication. |
| Scientific calculation claim | No-go | No native/archived result trace with values, units, diagnostics, and recomputation. |
| Clean replication claim | No-go | No independently controlled environment or reconstruction receipt. |
| Training | No-go | Zero eligible verified traces; no external held-out boundary or authority. |
| Publication/release | No-go | No explicit publication authority; the package is internal only. |
| Future experiment | Keep experimental/off | Requires the material P5 gates and separate authority to turn green. |

## Claim-evidence ledger

| ID | Claim type | Statement | Required evidence | Initial status |
| --- | --- | --- | --- | --- |
| P6-C1 | observation | The paper bundle can be reconstructed independently. | P6-G2 replication receipt and hashes. | Unresolved. |
| P6-C2 | inference | A controlled comparison supports a bounded SOTA statement. | P5 matched study, named comparators, intervals, and independent replication. | Unresolved. |
| P6-C3 | inference | Training is justified. | P6-G4 checklist, outcome evidence, and explicit approval. | Unresolved. |
| P6-C4 | unresolved uncertainty | A claim lacks a required receipt or arbiter. | Explicit missing-evidence record. | Unresolved until resolved or rejected. |

The P6 manifest also records supported infrastructure/process observations and
qualified P1 provider/literature observations, but it promotes none of them to
a scientific, comparative, replication, training, or release result.

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P6-D1 | Keep SOTA as a hypothesis unless controlled replication supports a named comparison. | Program charter and P5 evidence requirement. | Downgrade immediately on missing comparator/replication evidence. |
| P6-D2 | Defer training by default. | Verified traces and anti-hacking evidence are prerequisite. | No training until P6-G4 and separate approval. |
| P6-D3 | Keep paper package internal until publication authority is granted. | External publication boundary. | Do not submit, push, or publish automatically. |
| P6-D4 | Release an internal no-go package rather than a results manuscript. | Hash-pinned P0-P5 receipts and active blockers. | Replace only with a new candidate, independent replication receipt, and explicit release authority. |
