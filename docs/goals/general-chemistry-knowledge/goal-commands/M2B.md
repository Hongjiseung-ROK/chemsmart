# M2B goal command

~~~text
Goal: complete only M2B of the ChemSmart General Chemistry Knowledge program: implement a deterministic ScientificSettingsRegistry without turning capability metadata into scientific advice.

Read AGENTS.md, docs/design/chemsmart-agent-ultimate-goal.md, docs/design/paper-research-plan-v1.md, docs/goals/general-chemistry-knowledge/M2B-scientific-settings-registry.md, and the verified M2A K0 freeze. Re-audit branch, dirty state, live Click schema, Gaussian/ORCA/xTB project models, settings loaders, renderers, validators, and focused tests. Preserve K0, historical receipts, unrelated work, and Runtime V2 replay.

Implement additive ScientificSettingsRegistryV1 and ScientificSettingRecordV1 contracts. Derive each record from current code and schema, binding stable ID, registry version, program/version and job scope, YAML field path, canonical type, values or numeric/unit domain, default and omission semantics, compatibility/conflict rules, CLI exposure, validator IDs, and source/schema digests. Record introspection gaps; never guess or call a software default a paper fact or recommendation.

Expose only narrow typed read-only operations to list, inspect, and validate settings/project candidates. Return IDs and values, never native input, shell text, arbitrary paths, or executable commands. Keep project writing, command compilation, approval, safe preview, and readiness under existing deterministic authority. Seed cross-program collisions, stale digests, invalid values, wrong scope, missing units, ambiguous omission, incompatible pairs, unsupported versions, and loader disagreement. Preserve behavior when registry access is off.

API calls require unique registered hypotheses and deterministic oracles; count is observational. Use current quota only, with no top-up, bypass, duplicates, quota-burning, or secret persistence; stop on quota exhaustion, no unique hypothesis, credential revocation, or a safety red line. Run zero chemistry engines/HPC and author no native input.

Run one focused registry/loader suite and at most one evidence-driven rerun. Report coverage, gaps, failures, unknowns, and retain/revise/reject. Commit only phase-owned changes and fetch-first non-force push; no PR and do not continue to M2C. A valid registry does not establish scientific correctness or SOTA.
~~~
