# M5 — Pilot and Preregistration

## Objective

Freeze a reproducible public-fixture pilot that first evaluates A0 versus A1
command front ends, then estimates the 2 x 2 x 2 command-workflow study. Use
the pilot to decide feasibility and power, not to claim a component is default
or scientifically superior.

## Required work

1. Freeze model/version, provider capability snapshot, prompts, skills, tool
schemas, CLI-schema digest, compiler/validator revision, project fixtures,
task order, budgets, trial policy, and deterministic graders before collection.
2. Build a public development/pilot corpus covering Gaussian, ORCA, xTB,
   auxiliary command families, paraphrases, option aliases/order, program-kind
   confusions, TS/opt, scan/modred, DIAS/WBI, IRC/QRC, QMMM regions, xTB
   solvent pairs, stale project approvals, parser disagreement, and artifact
   mutation.
3. Measure command-path/job correctness, required-setting coverage,
   charge/multiplicity/geometry/project preservation, canonical equivalence,
   safe-preview and generated-input semantics, clarification precision,
   bounded repair, false-ready/false-success, cost/tokens/latency, approval
   bypass, and DAG artifact resolution.
4. Use paired repeated trials and bootstrap confidence intervals. Estimate the
   sample size for at least 90 percent power of the confirmatory study. Prepare
   an external-custodian sealed-corpus specification and blind grading plan.
5. Run the one allowed integration freeze gate: full agent tests, read-only
   Ruff, schema/link/citation/secret checks, and diff check. Do not autofix,
   format, or regenerate snapshots.

## Adoption thresholds

A1 must have 100 percent schema-valid rendering, parser acceptance, and
render determinism; zero native-input authoring, hallucinated options, and
shell injection; no more than two points semantic-preview regression versus
A0; and cost/tokens at most 1.25x or a significant repair reduction.

For D, require either five points held-out success or 20 percent wall-time
reduction on declared parallel tasks, no more than two-point simple-task
regression, and cost/tokens at most 1.5x. For E, require all manifests valid,
all numerical claims bound with units, deterministic rerendering, and no false
success on missing evidence. For C, require at least 90 percent recall of
seeded critical defects and 80 percent overall, at most 5 percent false
rejection, and at least 50 percent fewer false passes. Every configuration
requires zero approval bypasses, fabricated evidence, artifact mutation, or
success with a required red deterministic gate.

## Exit decision

Report pilot variance, confidence intervals, negative results, blockers, and
the exact frozen corpus/protocol digests. Leave every component experimental
unless the preregistered evidence passes. M6 cannot begin without an
independent custodian's sealed corpus.
