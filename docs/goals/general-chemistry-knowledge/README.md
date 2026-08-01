# General Chemistry Knowledge Program

This package refines the active ChemSmart ultimate goal by separating two
capabilities that are too often conflated in an agent prompt:

1. a deterministic registry of scientific settings that ChemSmart can
   represent and validate; and
2. sourced domain knowledge that explains when a setting is applicable,
   prohibited, uncertain, or missing from a paper.

Read [the ultimate goal](../../design/chemsmart-agent-ultimate-goal.md),
[Paper Research Plan v1](../../design/paper-research-plan-v1.md),
[the ablation protocol](../../evaluation/frontier-agent-ablation-protocol.md),
and `AGENTS.md` before starting any phase.

## Why this sequence exists

A fluent model answer is not evidence that ChemSmart supports a setting or
that the setting is scientifically appropriate. The `ScientificSettingsRegistry`
answers the first question from live code, schemas, and loaders. A
`DomainKnowledgePack` answers the second from pinned scientific sources and
deterministic applicability rules. Keeping them separate makes their effects
measurable and prevents persona knowledge from silently becoming authority.

`K0` is the frozen reference condition: no model-visible settings registry and
no model-visible domain-knowledge pack. Production loaders, permissions,
schema validation, artifact hashing, secret redaction, and all execution
safety gates remain enabled in K0 and every other condition.

## Implementation sequence

| Phase | Objective | Goal command |
| --- | --- | --- |
| [M2A](M2A-checkpoint-and-k0-freeze.md) | Preserve the current checkpoint and freeze a replayable K0 reference. | [copyable command](goal-commands/M2A.md) |
| [M2B](M2B-scientific-settings-registry.md) | Build a schema-derived registry of expressible scientific settings. | [copyable command](goal-commands/M2B.md) |
| [M2C](M2C-domain-knowledge-pack.md) | Add sourced, scoped scientific decision rules without prompt lore. | [copyable command](goal-commands/M2C.md) |
| [M2D](M2D-settings-knowledge-ablation.md) | Isolate settings-registry and knowledge-pack effects in a paired ablation. | [copyable command](goal-commands/M2D.md) |
| [M3](M3-prp10-refreeze.md) | Freeze a new, untouched PRP-10 lockbox and run the safe-preview evaluation. | [copyable command](goal-commands/M3.md) |
| [M4](M4-defect-driven-expansion.md) | Expand only from reproducible, cross-domain defects and paired evidence. | [copyable command](goal-commands/M4.md) |

## Invariants

- The model never authors or edits Gaussian, ORCA, or xTB native input.
- ChemSmart project loaders, the live CLI schema, the command compiler, safe
  preview, and deterministic validators remain authoritative.
- New calculation work stops at `previewed`; chemistry engines, schedulers,
  and HPC are not invoked.
- API request count is observational, not a spending target. Every request or
  retry has a unique registered hypothesis, one changed factor, a comparator,
  an expected observation, a deterministic oracle, and frozen source, prompt,
  tool, configuration, and budget hashes.
- Calls use only current user-owned quota. No top-up, provider bypass, secret
  persistence, duplicate prompting, or quota-burning is permitted. Stop when
  quota is exhausted, no unique verifiable hypothesis remains, a credential is
  revoked, or a safety red line occurs.
- A paper, ten-paper engineering gate, or component win does not establish a
  general SOTA claim. Such a claim requires a separately frozen external
  comparison, declared baselines and metrics, uncertainty analysis, and
  evidence that directly supports the claim.
