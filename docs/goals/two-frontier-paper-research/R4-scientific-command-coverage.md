# R4 — Six-Domain Scientific and Command Coverage

## Objective

Grow paper-derived project YAML and canonical ChemSmart command planning across
the six PRP domains, using archived/public fixtures and safe previews only.
Every unsupported paper step becomes a typed capability gap.

## Required work

1. Complete loader-backed project tooling for Gaussian, ORCA, and xTB. Reuse a
   project YAML only when its canonical setting signature matches exactly.
   Charge and multiplicity remain command-node properties. Auxiliary CLI
   families record project `not_applicable` where appropriate.
   Require an explicit xTB YAML block for every consumed job family; loader
   defaults for absent blocks are not paper evidence.
2. Build domain knowledge packs and deterministic validators incrementally for:
   organic mechanism/TS/IRC/kinetics; transition-metal spin/basis/ECP;
   excited-state photochemistry/spectroscopy; conformer/noncovalent/solvent
   ensembles; thermochemistry/free energy/standard state; and QM/MM/multiscale.
3. Convert sourced scientific state into `ScientificTaskSpec`, validated
   `ProjectConfigSpec`, and `CommandWorkflowSpec`. The live Click schema and
   command compiler own paths, flags, argv, quoting, project/artifact
   resolution, safe preview, independent parser observation, and intent diff.
4. Represent a multi-step study as a command DAG. Each node owns one canonical
   command; downstream input resolves only from an actual predecessor receipt
   and hash. An unavailable predecessor leaves the node planned.
5. Reparse ChemSmart-generated preview inputs and compare geometry, atom order,
   charge, multiplicity, method, basis/ECP, solvent, constraints, state/root,
   job semantics, expected outputs, units, and dependency handoff.
   Until receipt-bound validators exist, keep downstream ordered-geometry
   handoff and element-resolved `gen`/`genecp` preview readiness as explicit
   capability gaps rather than claiming the single-frame slice covers them.
6. For an inexpressible required step, record source claim, required semantics,
   closest CLI family, missing typed command/compiler/parser/validator support,
   affected nodes, and review status. Add capability only as a separately
   reviewed milestone; never generate a native-input fallback.

ChemSmart must not contact paper authors and must not add, propose, or execute
an unreported sensitivity calculation. Missing critical settings block.

## Acceptance evidence

- Declared project YAML loads and semantically matches every bound source claim
  and consumer node; stale YAML invalidates preview/approval bindings.
- Every expressible node has deterministic canonical argv and a safe-preview
  receipt; every inexpressible node has a reviewed capability-gap receipt.
- Artifact handoff cannot resolve from a filename, placeholder, guessed path,
  stale hash, or model assertion.
- Six-domain coverage tables separate schema presence, project support,
  preview/parser support, scientific validator support, and unresolved gaps.

## Validation and exit

Run one focused loader/compiler/DAG/safe-preview/generated-input suite after
the R4 slice is complete and at most one corrective rerun. Do not run real
Gaussian/ORCA/xTB calculations, HPC, or broad integration checks.
