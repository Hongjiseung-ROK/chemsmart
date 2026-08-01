# M2C — DomainKnowledgePack

## Objective

Move computational-chemistry judgment from persona lore into sourced,
versioned, falsifiable rules that reference settings ChemSmart can actually
represent.

## Contract

Extend the existing `DomainKnowledgePack` contract rather than creating a
parallel knowledge runtime. A pack binds its domain, engine/version and job
scope, source records and exact locators, supported `ScientificSettingRecord`
IDs, applicability predicates, required evidence, allowed choices, prohibited
conditions, uncertainty and conflict behavior, stable rule IDs, and
deterministic validator IDs.

Separate four layers explicitly:

1. paper facts extracted from the frozen source bundle;
2. ChemSmart setting availability from the registry;
3. sourced domain guidance about applicability and limitations; and
4. a coordinator decision that remains reviewable and may be blocked.

A pack cannot convert `unknown`, `inferred`, or `conflict` into `explicit`,
invent a missing coordinate or electronic state, approve a project, compile a
shell command, author native input, execute a calculation, or decide readiness.
When a paper-faithful setting is absent, the pack must preserve
`blocked_missing_evidence`; it may not fill the gap with a customary default.

## Initial vertical slice

Implement one small, reusable core pack and one paper-relevant domain pack
whose sources, engine scope, and validators can be fully audited. Favor rules
for molecular/electronic-state completeness, method and basis/ECP pairing,
solvent/dispersion/convergence declarations, frequency/thermochemistry
obligations, and valid job sequencing. Expand only when evidence and loader
coverage exist; record every unsupported rule as a gap.

## Exit gate

Every rule has primary or authoritative provenance, an exact applicability
scope, a registry-resolvable setting surface, deterministic positive and
negative fixtures, and a fail-closed outcome. A fresh read-only domain critic
finds no unresolved critical provenance or scope defect. Run one focused
knowledge-pack suite and at most one evidence-driven rerun.
