# M2D — Settings × Knowledge Ablation

## Objective

Measure whether model-visible setting facts and sourced domain guidance improve
paper-to-plan behavior independently and jointly.

## Preregistered design

Use a paired `2 x 2` design over the same K0 scientific kernel:

| Arm | Settings registry visible | Domain pack visible |
| --- | --- | --- |
| `S0K0` | no | no |
| `S1K0` | yes | no |
| `S0K1` | no | yes |
| `S1K1` | yes | yes |

The underlying project loaders, registry resolver needed by deterministic
validation, permissions, schema, artifact hashing, command compiler, safe
preview, and native-input/engine/HPC prohibitions remain active in every arm.
The factors change only what typed guidance the model may inspect. If a domain
pack references registry IDs in `S0K1`, the host resolves them for validation
without exposing the registry browsing tool.

Freeze development papers, source windows, coordinates, prompt, model and
thinking mode, tool schemas, task order, per-request limits, wall time,
compiler, validators, graders, and review protocol. Each API request must bind
one arm/case hypothesis and one changed factor. Use paired repeated trials only
to resolve declared uncertainty, never to spend quota without a new oracle.

## Metrics and decisions

Primary metrics are explicit scientific-setting preservation, critical
coverage, loader-valid project candidates, command semantic correctness, safe
preview success, honest blocking, false-ready, and safety violations.
Secondary metrics are bounded repair, tool-call validity, critic recall/false
rejection, tokens, cost, and latency. Provider-turn completion is not a success
metric.

Estimate main and interaction effects with paired uncertainty intervals and
publish paper-level regressions. Retain a component only when it improves
aggregate scientific coverage without a safety regression and demonstrates a
generalizable causal mechanism. Otherwise revise or reject it. Select the
smallest safe non-inferior configuration for M3 and keep `S0K0` as a permanent
reference.

## Exit gate

All four arms replay and rerender deterministically, differ only by declared
factor exposure, have zero safety red lines, and produce an evidence-bound
retain/revise/reject decision. Run one focused ablation suite and at most one
evidence-driven rerun.
