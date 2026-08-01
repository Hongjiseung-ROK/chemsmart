# M2B — ScientificSettingsRegistry

## Objective

Give the agent a typed, inspectable map of scientific settings that the current
ChemSmart code can represent, without turning that map into scientific advice.

## Contract

Implement additive `ScientificSettingsRegistryV1` and
`ScientificSettingRecordV1` contracts. Each record binds a stable setting ID,
registry version, program and supported version scope, job-family scope,
project-YAML field path, canonical type, allowed values or numeric/unit domain,
default and omission semantics, compatibility/conflict rule IDs, CLI exposure,
loader/renderer validator IDs, and source-code/schema digests.

Generate or verify records from the live Click schema, Gaussian/ORCA/xTB
project models, settings loaders, and deterministic renderers. A hand-written
inventory cannot be the source of truth. Where introspection is incomplete,
record an explicit coverage gap rather than guessing. Defaults must be labeled
as software behavior, not as a paper-reported or recommended method.

Expose only narrow read-only operations such as listing settings by program
and job scope, inspecting a setting record, and validating a typed project
candidate. Return typed IDs and values, never native input fragments, shell
syntax, arbitrary paths, or executable commands. Project writing and command
compilation remain under their existing approval and deterministic boundaries.

## Validation

Seed cross-program name collisions, stale schema digests, wrong field scope,
invalid enums, missing units, ambiguous omissions, incompatible setting pairs,
unsupported program versions, and registry-to-loader disagreement. Require
canonical serialization, stable hashes, deterministic rerender, and exact
round trips through the real loaders. Preserve legacy behavior when the
registry tool is not exposed.

## Exit gate

The declared registry coverage is complete for its exact scoped slice, every
record resolves to current code and a deterministic validator, unsupported
coverage is explicit, and no registry result makes a scientific recommendation
or readiness decision. Run one focused registry/loader suite and at most one
evidence-driven rerun.
