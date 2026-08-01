# R3 — Bounded Specialists and Independent Reviews

## Objective

Add task decomposition and adversarial cross-examination only where immutable
scope, finite budgets, single ownership, typed outputs, and deterministic joins
make the work independently verifiable.

## Required work

1. Implement `SpecialistTaskPacket` with objective, source scope, immutable
   input refs, dependencies, role, narrow tools, permission scope, finite
   budget, expected schema/artifacts, completion predicate, write owner, merge
   key/order, and repair cap. Implement a result packet containing observable
   artifacts, usage, stable rule IDs, public summary, and terminal state only.
   A packet exposing literature search or retrieval requires a positive finite
   `max_network_requests`; reject absent, zero, exceeded, or digest-only usage.
2. Allow specialists only for source curation, SI extraction, molecular-state
   review, independently computable species, project/command counterexamples,
   and claim-artifact audit. The coordinator alone owns canonical molecule
   identity, charge/multiplicity, project signatures, and final command DAG.
3. Enforce the R2 matrix: H0/HC do not delegate, HA delegates at depth one, and
   HK at depth two. A leaf cannot spawn children. No specialist may approve,
   execute, write native input, broaden tools, or mutate a shared artifact.
4. Make joins all-or-nothing, retain the exact result packets, and recompute
   packet digest, dependency/lineage, owner, observed resource/repair budget,
   output-schema receipt, merge key/order, artifact hash, and conflict rules.
   Reject partial active-family joins and opaque validation/usage hashes.
5. Add three frozen-candidate reviews: domain/paper fidelity;
   command/evidence/YAML/units/preview; and adversarial omission/state-drift/
   approval-reuse/false-readiness. Reviewers are fresh and read-only. They
   cannot repair, approve, execute, close their own finding, or act as terminal
   authority.
6. Seed hidden critical and noncritical defects, including correlated model
   errors. Deterministic validators or independent expert adjudication resolve
   findings; another LLM's agreement is supplementary evidence only.

ChemSmart must not contact paper authors and must not add, propose, or execute
an unreported sensitivity calculation as a specialist workaround.

## Acceptance evidence

- Invalid ownership, budget, tool, depth, packet-digest, output-schema, or merge
  relationships fail with stable rule IDs before canonical state changes.
- Every accepted join is deterministic under input ordering and binds the
  exact immutable tasks/results/artifacts and observed receipt bodies it merged.
- Review findings bind reviewer independence, frozen target digests, severity,
  rule, evidence, expected/observed state, and disposition.
- Seeded-fault receipts report recall and false rejection without allowing a
  critic to turn its own finding green.

## Validation and exit

Run one focused delegation/merge/review/event suite after R3 is complete and
one evidence-based rerun at most. Passing contract tests does not adopt
subagents or critics; R5 measures their efficacy.
