# M2 — Independent Ablation Plane

## Objective

Make optional agent behavior independently switchable and fully observable
without weakening Runtime V2 or any safety invariant.

## Required work

Version ten switches: task decomposition, specialist roles, evidence retrieval,
domain-knowledge packs, structured documentation, independent critic,
adversarial cross-examination, bounded repair, command DAG, and deterministic
feedback. Retain a single-agent baseline.

Record switch state, model/provider, prompt/tool-schema digests, network
envelope, source/project/command hashes, validators, artifacts, failures,
repairs, usage, and terminal state in a separate additive hash-chained
experiment stream. Pair cases with identical papers, prompts, tools, task order,
budgets, and validators while changing one switch.

Permission, CLI schema, artifact hashes, secret redaction, deterministic safety
validators, and native-input, engine, scheduler, and HPC prohibitions remain on
in every condition. Exactly three review roles are available when enabled:
domain/paper fidelity, command/evidence integrity, and adversarial
omission/state/safety. They are fresh, read-only, and non-self-approving.

## Gate

All ten switches change only their declared behavior; replay and rerender are
deterministic; invariant controls cannot be disabled; every comparison proves a
single changed factor. Run one focused milestone suite and one evidence-driven
rerun at most.
