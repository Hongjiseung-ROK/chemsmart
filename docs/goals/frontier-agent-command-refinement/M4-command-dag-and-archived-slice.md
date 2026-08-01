# M4 — Command DAG and Archived Scientific Slice

## Objective

Extend the single-command compiler into a bounded multi-command workflow whose
nodes are canonical ChemSmart commands. Demonstrate provenance, validation,
claim, and report linkage with archived artifacts only; do not execute new
chemistry.

## Required work

1. Implement command-DAG dependencies, artifact handoff, independent branch
   eligibility, immutable worker packets, resource budgets, and deterministic
   joins. A node owns exactly one command; a shared mutable project or artifact
   has one owner.
2. Require an actual predecessor artifact receipt and matching hash before a
   downstream input binding resolves. At preview time, missing predecessors
   leave downstream nodes planned rather than executable.
3. Permit subagent dispatch only for independently computable branches such as
   separate species. Workers return typed command IR only; the coordinator
   recompiles against the live schema and owns merge verification.
4. Connect archived Gaussian, ORCA, and xTB artifacts to scientific
   specification, command/evidence/validation/claim/report graphs. Preserve
   native artifacts plus QCSchema-compatible records and an
   RO-Crate-compatible manifest.
5. Cover Gaussian, ORCA, xTB, and compatible auxiliary command families:
   thermochemistry, database, mol, grouper, nciplot, and iterate. Distinguish
   command-schema coverage from scientific fitness for every family.
6. Keep the experimental factors explicit: D is single agent versus eligible
   command-DAG decomposition; E is evidence-composer exposure while raw
   recording remains always on; C is one read-only command cross-examination.

## Acceptance evidence

- A DAG never resolves a dependent artifact from a guessed filename or missing
  receipt.
- Independent branches deterministically join; overlapping artifact ownership
  and non-typed worker output fail closed.
- Archived evidence rerenders a report deterministically and each numerical
  claim has artifact, validator, and unit links.
- The critic produces findings only; it cannot repair, approve, execute, or
  make a terminal pass.

## Test gate

Run one focused command-DAG/artifact/evidence-replay suite after M4 is
complete, with at most one evidence-driven rerun. No real engines, HPC, or
new literature model calls are part of this gate.
