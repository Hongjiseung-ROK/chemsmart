# M3 — Approval and Command Provenance

## Objective

Bind every future executable command to its exact scientific intent, schema,
project, artifacts, environment, safe-preview receipt, and resource envelope.
Ensure a one-shot approval is consumed atomically under the Runtime V2 event
store lock before any future dispatch can occur.

## Required work

1. Add versioned, replay-safe events for command workflow, preflight,
   counterexample, approval request/resolution/invalidation, validation, claim,
   review, report, budget, pause/resume, and terminal state. Existing event
   logs must replay without changed behavior.
2. Bind approval to canonical invocation digest, input/project/artifact hashes,
   executable/environment identity, resource budget, and declared target.
   Invalidate on any semantic or material binding change.
3. Make approval consumption compare-and-append atomically in the event store.
   A duplicate, stale, mismatched, expired, or already-consumed approval must
   fail closed before tool dispatch.
4. Preserve public observable actions and opaque provider continuation only.
   Do not persist raw thought, secret material, or unbound provider state as
   scientific evidence.
5. Keep chemistry execution denied by policy in this phase. Exercise only
   test-only risky-tool fakes to verify atomicity and rejection paths.

## Acceptance evidence

- A CommandPreflightReceipt can be traced to typed intent, resolved objects,
  preview artifact, parser observation, and named validator rules.
- Event replay reproduces visible lifecycle state for old and new fixtures.
- A test-only dispatch consumes exactly one matched approval; races, stale
  bindings, and artifact/project mutations are rejected.
- No test or report labels a fake preview as executed or reproduced.

## Test gate

Run one focused approval/event-replay/provenance suite after the complete
milestone, with at most one corrective rerun. Do not enable engines or HPC.
