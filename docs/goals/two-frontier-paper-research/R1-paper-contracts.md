# R1 — Paper and Scientific-State Contracts

## Objective

Implement the strict, content-addressed state needed to turn a source-complete
paper into a `PaperResearchPlan` without changing command-compiler authority or
claiming execution. Extend Runtime V2 additively so legacy logs still replay.

## Required work

1. Implement and document `PaperSourceBundle`, `SourceArtifact`,
   `ProtocolClaim`, `MolecularSystemSpec`, `ProjectConfigSpec`,
   `DomainKnowledgePack`, `RequiredProtocolCoverage`, and `PaperResearchPlan`
   with strict schemas, stable canonical JSON, digests, unique IDs, closed
   references, and no host paths in public events.
2. Preserve article, SI, figures, tables, geometries, data, code, cited
   protocols, and software manuals by locator and hash. Search snippets remain
   discovery evidence only; licensed full text stays in a private store.
3. Require exactly one epistemic state per claim: `explicit`, `derived`,
   `inferred`, `unknown`, `conflict`, or `not_applicable`. Every explicit claim
   needs a stable source locator. A derived claim requires a content-addressed
   deterministic derivation receipt; a critical `not_applicable` claim
   requires an applicability receipt. A critical inferred/unknown/conflicting
   claim deterministically yields `blocked_missing_evidence`.
4. Preserve exact atom order, geometry frame and units, species/conformer,
   charge, multiplicity, fragments, constraints, method, basis/ECP, dispersion,
   solvent, grid/convergence, temperature, standard state, program/version,
   consumers, and source claims.
5. Keep `plan_state` independent from `execution_state`. A CLI limitation is a
   content-addressed `blocked_capability_gap`, never native-input fallback.
6. Add versioned research events and reducer projection for source freeze,
   claims, molecular/project state, plan validation, budget, pause/resume, and
   terminal state. Reject digest rebinding, unsafe transition, idempotency-key
   collision, and receipt-free completion while preserving frozen legacy replay.
7. Make advanced validation consume the actual typed plan, independent
   coverage, task/workflow contracts, exact YAML/loader records, previews, and
   reviews. Persist a content-addressed derived result; never accept a
   digest-shaped validation assertion without its body.

ChemSmart must not contact paper authors and must not add, propose, or execute
an unreported sensitivity calculation. A paper-reported sensitivity node is
allowed only with its source claim.

## Acceptance evidence

- Canonical serialization and digest results are deterministic under declared
  ordering rules; extra fields and broken references fail closed.
- Source completeness and critical-claim readiness produce stable rule IDs.
- A knowledge pack is domain/engine/version scoped, source hashed, validator
  bound, and unable to approve, execute, or supply an omitted paper fact.
- Advanced plan states require the relevant source, scientific, project,
  command, review, and report digests; `validated` never implies `executed`.
- Independent coverage detects a critical field omitted from the planner's own
  claim list, and runtime replay reproduces the exact validation status/rules.
- Old Runtime V2 JSONL fixtures replay identically, while invalid new event
  sequences are rejected before persistence.

## Validation and exit

Complete the whole R1 contract/event milestone, then run one focused contract,
digest, validation, event-store, reducer, and legacy-replay suite. Permit one
evidence-driven rerun only. No provider call, engine, HPC, training, or broad
integration check belongs to R1.
