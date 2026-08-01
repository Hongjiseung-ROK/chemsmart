# P5 — Component ablation

## Status

Structurally complete and closed blocked at 2026-07-31T19:24:07Z. P5 froze a
zero-call 2 × 2 × 2 preregistration and deterministic future-aggregation
controls. It did not execute a model, provider completion, chemistry engine,
scheduler, held-out case, paired trial, or statistical analysis. P5-C1 through
P5-C3 therefore remain unresolved, and no component, comparator, critic, or
SOTA claim is supported.

The frozen P4 input captures the prior P5 plan separately under
[`reviews/p4-inputs/`](reviews/p4-inputs/); this live phase page now records
P5's blocked close without rewriting P4 evidence.

## Objective

Measure whether decomposition, structured evidence/report generation, and
independent critique improve the frozen single-agent reference without a safety
regression. The study evaluates components, not an assumed SOTA conclusion.

## Inputs

| Input | Required use |
| --- | --- |
| P3 frozen single-agent reference | `decomposition=off`, `documentation=off`, `critique=off` comparator. |
| P3/P4 fixture and review artifacts | Development/held-out split, seeded labels, determinstic graders, and independent review rubric. |
| P1 provider receipt, if live conditions are enabled | Exact provider/model/capability and allowed existing-quota ceiling. |
| [`frontier-agent-ablation-protocol.md`](../../evaluation/frontier-agent-ablation-protocol.md) | Fixed metrics, red lines, repetitions, analysis, and adoption thresholds. |

## Tools and authority

- Allowed: frozen harness configurations, deterministic graders, fixture/
  archived-output evaluation, paired randomization, local statistical analysis,
  and read-only expert rubric scoring.
- Live model use requires the P1 receipt and identical provider/model/tool/
  prompt/budget conditions across the compared pair. No real engine or scheduler
  call is authorized by this phase.
- LLM judges may supplement analysis only; they cannot replace deterministic
  grades or expert rubric evidence.

## Budget

| Resource | Ceiling |
| --- | --- |
| Factor configurations | Exactly 8: decomposition × documentation × critique |
| Held-out repetitions | At least 3 paired trials per held-out case/configuration |
| Experimental surface | Frozen before first trial: model, prompt/skill, tools/schema, fixtures, order/retry policy, graders, and ceilings |
| API use | Existing P1-verified allowance only; exact token/tool/wall-time caps fixed before trial 1 |
| Real engine/scheduler calls | 0 unless separately approved |

## Artifacts

- [Frozen preregistration manifest](../../../tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json)
  with canonical digest `7d9803a31936642a7b8b16597e7efd3d5032d3d6d75d0484b1223ab47322051b`.
  It pins all eight configurations, their deterministic order, three future
  paired repetitions per held-out case, zero authority budget, the P3 reference,
  P1/P3/P4 receipts, and the protocol.
- [`frontier_ablation.py`](../../../chemsmart/agent/harness/frontier_ablation.py),
  which rejects duplicate configuration/source-case/future trial keys and
  refuses to materialize evaluation while the red gates remain.
- [Focused structural test](../../../tests/agent/harness/test_frontier_ablation_preregistration.py),
  [failure ledger](receipts/p5-failure-ledger.json), and
  [phase-close receipt](receipts/p5-component-ablation.json).
- No raw trial receipt, score, interval, adoption table, or result artifact
  exists. Those are required future evidence, not missing values to impute.

## Gates

| Gate | Pass condition | Red condition |
| --- | --- | --- |
| P5-G1: preregistration | Frozen configuration and task/evaluator manifests precede held-out runs. | Any post hoc condition switch or omitted failure. |
| P5-G2: deterministic first | Metrics derive first from deterministic graders, then expert rubrics. | LLM judge is the primary pass arbiter. |
| P5-G3: red lines | Zero approval bypasses, fabricated evidence, artifact mutation, secret exposure, and red-gate terminal success. | Any occurrence; configuration cannot become default. |
| P5-G4: component benefit | Protocol thresholds and confidence intervals support benefit with stated non-regressions. | Point estimate alone or unsupported interval. |
| P5-G5: replication readiness | Inputs, environment, raw receipts, and scoring outputs are sufficient for an independent rerun. | Missing artifact/digest or unreproducible report. |

P5-G1 passed only as an offline structural preregistration gate. P5-G2 and
P5-G3 are configured controls, not observed trial outcomes. P5-G4 and P5-G5
are blocked: there are no complete trial receipts, paired intervals, or
replicable study output. The following stop conditions are frozen in the
manifest: provider capability, live authority, external held-out boundary,
executor approval, chemical-result trace, complete trial set, integrity, and
duplicate-key aggregation.

## Blockers

- Insufficient existing quota, unpinned model revision, missing held-out
  fixtures, nondeterministic grader, or incomplete P3/P4 artifacts blocks the
  corresponding comparison.
- A red-line event ends adoption consideration for its configuration; it is a
  result, not a reason to discard the case.
- The current concrete blockers are P3-G5/P4-RT-01, missing external held-out
  custody, P4-HA-01's executor boundary, P4-CH-01's chemical-result boundary,
  and the absence of all trial receipts. No checkout-visible P3 case or seed
  may be reclassified as held out.
- The later P3 v1 capability specimen did not clear provider capability:
  its one bounded response reached the 64-token ceiling with invalid tool
  arguments. The frozen preregistration remains unchanged and
  `P5-RG-01-provider-capability` remains red.

## Phase-close validation

Run the fixed scoring and analysis once over the complete frozen receipt set.
Report all eight configurations, all repetitions, paired bootstrap intervals,
per-family outcomes, false passes, unsupported claims, blocked cases, costs,
and red lines. Do not re-run or tune after seeing held-out results without a new
preregistration revision and a separate decision.

For this blocked structural close, the recorded validation was:

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_ablation_preregistration.py -q
```

The initial invocation failed before any execution because a secret-shaped-data
guard falsely classified a public P3 settings-fixture identifier as a key.
P5-F0 records the hypothesis and minimal repair: require a substantially longer
credential-token shape while retaining the key/header guards. The one targeted
post-repair invocation passed `4` tests in `0.04 s`. These are structure and
red-gate checks only, not a factor-study result.

## Claim-evidence ledger

| ID | Claim type | Statement | Required evidence | Initial status |
| --- | --- | --- | --- | --- |
| P5-C1 | computed result | A component changes a preregistered metric. | Frozen raw scores and paired analysis. | Unresolved; no trial exists. |
| P5-C2 | inference | A component should be enabled by default. | P5-G3/P5-G4 evidence and replication readiness. | Unresolved; every component remains experimental/off. |
| P5-C3 | inference | ChemSmart exceeds a named comparator. | Controlled matched comparator evidence and independent replication. | Unresolved; no comparator is named or run. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P5-D1 | Preserve the simplest passing configuration. | Preregistered adoption rule. | Keep optional components experimental/off if gates are unsupported. |
| P5-D2 | Publish all failures and blockers in analysis. | Reproducibility and anti-hacking boundary. | Never exclude a failure solely to improve a metric. |
| P5-D3 | Treat red-line failure as decisive against default adoption. | Safety and integrity gate. | Component stays off pending a new preregistered study. |
| P5-D4 | Freeze a zero-call study plan rather than invent a live condition. | P1/P3/P4 red gates and no live authority. | Issue a new preregistration revision only after material authority, capability, and held-out inputs exist. |
| P5-D5 | Require external held-out custody and tuple-key uniqueness before any aggregate. | P4 red-team/harness findings. | Do not turn P3 public cases or seeds into held-out evidence. |
