# Paper-to-research-plan contract

## Source bundle

Before reconstructing calculations, bind stable hashes and legal-access status
for the main article, Supporting Information, figures and tables, deposited
geometries/data, code repositories, cited method protocols, and relevant
software manuals. Search results locate sources but do not establish settings.

For PRP-10 eligibility, require an exact official single-frame XYZ in angstrom.
Preserve the source locator and archive member, source and imported-byte hashes,
atom order, identity approval, and access/license evidence in a
`CoordinateImportReceipt`. Do not rewrite SI coordinate tables, use OCR,
convert SMILES to 3D, or accept model-generated coordinates. SDF/MOL/PDB may be
handled by a separately validated general converter but cannot satisfy this
campaign gate. Missing coordinates yield evidence-linked blocked nodes.

## Epistemic fields

Label each molecular, electronic-structure, workflow, resource, validation,
and analysis field as exactly one of:

- `explicit`: stated in a locatable source;
- `derived`: obtained by a deterministic documented transformation;
- `inferred`: a scientifically motivated candidate not stated by the paper;
- `unknown`: required but unavailable;
- `conflict`: sources disagree;
- `not_applicable`: the field does not apply.

Keep the source locator, quoted-field paraphrase, units, and derivation or
inference rule. Never use model confidence as evidence. A critical `unknown`,
`inferred`, or `conflict` blocks paper-faithful execution readiness. Do not
contact authors or add an unreported sensitivity calculation to resolve such a
gap. If the paper itself reports sensitivity analysis, retain it as a sourced
workflow node.

## Required research plan

For every distinct species, state, conformer, method layer, calculation step,
and analysis, provide:

- stable molecule/geometry identity and provenance;
- charge, multiplicity, fragments, constraints, and state assumptions;
- program/version, method, basis/ECP, dispersion, solvent, grids, thresholds,
  temperature, standard state, and resources;
- dependencies, restart and failure policy, expected artifacts, parsers,
  validators, numerical conventions, and comparison to the paper;
- validated project settings, a typed command node, and a ChemSmart-generated
  safe-preview input when the current CLI can express the task.

If ChemSmart cannot express a required step, return a typed capability gap.
Do not hand-write a native input to make the plan appear complete.

Before an advanced state, bind an independent `RequiredProtocolCoverage` to
the exact source bundle. It enumerates required source kinds, critical
fields/units, systems, projects, and workflows. Validate actual project YAML,
loader observations, ScientificTaskSpec, CommandWorkflowSpec, generated
preview evidence, and receipt bodies; digest-shaped strings alone are not
evidence. A required source kind must resolve to retrieved, non-empty content;
metadata-only records and discovery snippets do not satisfy full-text or SI
coverage.

For xTB, require an explicit YAML block for every used job family. In the
current single-frame slice, block downstream geometry handoff until the
producer receipt provides an ordered-geometry digest. Block `gen`/`genecp`
preview readiness until an element-resolved mapping validator exists.

Scientific rules that supplement extraction must come from a versioned
`DomainKnowledgePack` with matching domain and engine/version scope, cited
sources, stable rule IDs, prohibited conditions, and deterministic validators.
The pack may detect or block; it cannot supply a missing paper fact.

## PRP-10 adaptive campaign

Freeze ten distinct papers only after full text, SI, access/license record,
critical methods, and the official exact XYZ are content-addressed. Retain the
six predecessor domains:

1. organic reaction mechanism, transition state, IRC, and kinetics;
2. transition-metal or organometallic catalysis with spin/ECP choices;
3. excited-state photochemistry or electronic spectroscopy;
4. conformational, noncovalent, and solvent/ensemble workflows;
5. thermochemistry, free-energy corrections, and standard-state analysis;
6. QM/MM or another explicitly layered multiscale biochemical workflow;
7. open-shell electronic structure;
8. constrained coordinate scan;
9. explicit molecular cluster;
10. multilevel electronic-structure workflow.

Each paper requires an independent domain review, command/evidence audit, and
adversarial research-plan review. Freeze sources, prompts, tools, harness,
validators, budgets, and task order before the PRP-10-V1 first pass. Once its
outcomes are opened, use it for development rather than claiming it remains
held out; future confirmatory evaluation requires a new lockbox. Safe preview
is the execution ceiling for the active campaign.

PRP-6 and its seven-paper public pilot are historical predecessor contracts.
Preserve their `6/6 paper_complete_pass@1` records without relabeling them as
PRP-10 results.
