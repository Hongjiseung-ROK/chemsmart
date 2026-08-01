# M2A — Checkpoint and K0 Freeze

## Objective

Preserve the current implementation and empirical evidence, then freeze a
replayable no-knowledge reference before adding model-visible scientific
settings or domain rules.

## Required work

Re-audit the branch, local/remote ancestry, dirty state, ignored private
artifacts, Runtime V2 streams, public receipts, and focused validation history.
Reconcile any terminal-event mismatch and distinguish provider-turn outcome,
tool-domain outcome, and scientific readiness. Do not rewrite historical
receipts.

Create a content-addressed `K0BaselineFreezeV1` manifest that binds:

- repository and commit, CLI schema, project-loader, command-compiler,
  validator, prompt, skill, tool-schema, provider configuration, and budget
  digests;
- the exact development cases and source hashes permitted for K0;
- disabled model-visible settings-registry and knowledge-pack switches;
- invariant safety controls that remain enabled;
- authoritative event streams, artifacts, graders, and known blockers; and
- the public/private evidence boundary.

K0 must exercise the same typed tool loop used by later conditions. It may use
existing evidence-only cases, but it must not acquire new scientific knowledge
through an undeclared prompt, hidden fixture, broad tool, or model-generated
native input. Record current API calls only when they test a unique frozen K0
hypothesis with a deterministic oracle.

## Exit gate

The checkpoint is reviewable and recoverable; local and remote SHA are
recorded; K0 rerenders and replays deterministically; all source, prompt, tool,
configuration, and budget hashes resolve; the two knowledge switches are
provably off; safety invariants remain on; and no receipt equates a completed
turn with scientific readiness. Run one focused checkpoint/K0 suite and at
most one evidence-driven rerun.

## Non-goals

Do not add a settings registry, author a knowledge pack, tune prompts, open a
PRP-10 lockbox, run chemistry engines or HPC, or claim a scientific or SOTA
improvement in this phase.
