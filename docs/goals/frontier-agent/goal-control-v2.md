# ChemSmart Frontier Agent Goal Control v2

## Purpose

This document controls future Codex Goal sessions for the ChemSmart frontier
agent. It preserves the ultimate ambition—a reproducible, CLI-first
computational-chemistry agent and a defensible SOTA paper—while making each
active Goal small, falsifiable, and stoppable.

The P0–P6 program under `docs/program/frontier-agent/` is frozen historical
evidence. Do not edit it to make an old receipt green. New work uses this
control document, `goal-state-v2.json`, and one milestone-specific receipt.

## Diagnosis of the first Goal session

The first session was scientifically conservative but operationally
inefficient:

- It correctly refused SOTA, replication, training, and publication claims
  when empirical gates were red.
- It added a useful optional `scientific_v1` Runtime V2 event contract and
  preserved legacy replay behavior.
- It demonstrated one bounded, non-executing DeepSeek function-call response.
- The DeepSeek specimen bypassed the active ChemSmart session, provider/tool
  loop, permission-consumption, CLI, and engine paths; it therefore did not
  validate the real harness.
- Multiple fixture-only v1/v2/v3 successors, reconciliation documents, local
  validators, and focused test reruns accumulated after the program had already
  closed P6 as no-go.
- Existing receipts are internally cautious, but a historical receipt plus a
  validator of that receipt is not independent external evidence.
- The work remained a large, changing, uncommitted tree, which made review,
  rollback, and ownership harder.

The process failure was not insufficient caution. It was optimizing artifact
coverage after the next empirical blocker was already known.

## Governing optimization rule

Maximize **blocker-reducing empirical information per changed line**, not the
number of contracts, receipts, validators, tests, or phase labels.

A proposed change is admissible only when all answers below are yes:

1. Which current blocker does it reduce?
2. What observation could falsify the change?
3. Does it exercise the active product path or a necessary deterministic
   boundary immediately adjacent to that path?
4. Is it smaller than documenting or testing another future-only abstraction?
5. Can one milestone receipt describe the result without another reconciliation
   layer?

If any answer is no, do not implement the change.

## Goal granularity

One Codex Goal equals one bounded vertical milestone. The ultimate SOTA program
is context, not the active Goal objective. Completing a milestone completes its
Goal; a later milestone starts a new Goal after user review.

Allowed state transitions are:

`paused -> ready -> in_progress -> review -> complete | blocked`

- Do not move backward to an older phase implicitly.
- Reopening a milestone requires a user-authorized state update that names the
  new evidence or defect.
- A blocked milestone does not authorize unrelated hardening, a successor
  fixture version, or work on a later phase.
- When the same material blocker survives three consecutive Goal turns and no
  useful in-scope observation remains, mark the Goal blocked instead of seeking
  more local work.

## Evidence admission hierarchy

From strongest to weakest:

1. Independently reproduced native calculation or held-out trial with hashes,
   environment, units, validators, and uncertainty.
2. Active ChemSmart path trace with provider, tool, approval, event, artifact,
   and terminal receipts.
3. Deterministic parser, replay, permission, or scientific-validation result
   over a pinned real artifact.
4. A defect-reproducing fixture that directly protects an active-path change.
5. A future-only fixture, schema-shape check, document validator, model opinion,
   or narrative.

Levels 4–5 may support implementation safety but cannot close an empirical
product, chemistry, benchmark, replication, or paper gate by themselves.

## Current next milestone: M1 active-path non-executing provider slice

### Objective

Prove one bounded DeepSeek tool-call turn through the real ChemSmart session,
provider adapter, tool loop, permission decision, Runtime V2 event store, and
terminal state while executing no tool, chemistry engine, scheduler, or HPC
action.

### Required path

`unified session -> configured provider adapter -> active tool loop -> existing permission policy -> Runtime V2 event/event store -> blocked terminal receipt`

The earlier direct `frontier_live_provider_v2` specimen is an input and
regression reference, not M1 completion evidence.

### Required behavior

- Use the current Click-derived CLI/tool schema; do not maintain a copied
  command inventory.
- Require an explicit `--live`, equivalent human approval flag, or exact
  approval record before any external completion. A runner must default to
  dry-run/no-request.
- Resolve the configured DeepSeek credential without exposing it. Record only
  `allowance_sufficient: true|false` for the declared cap; do not retain exact
  account balance, plan, headers, raw prompt, raw response, or credentials.
- Fix provider compatibility inside the provider adapter. Do not add another
  standalone provider protocol copy.
- Bind the permission decision to the exact model, tool schema, task, budget,
  and invocation hashes. The active dispatch boundary must reject absent,
  changed, expired, or already-consumed approval.
- Persist observable events and a terminal blocked state. Do not execute the
  returned tool.
- Preserve the single-agent reference path and all legacy event replay.

### Exit gates

M1 is complete only if one receipt proves all of the following:

- exactly one authorized completion, zero retries, and cost within the declared
  existing-quota cap;
- the production provider/tool-loop path produced one schema-valid tool call;
- deterministic permission logic prevented dispatch;
- the Runtime V2 log replays to the same blocked terminal state;
- no credential, hidden reasoning, raw provider payload, tool execution,
  engine call, scheduler call, artifact overwrite, or unsupported scientific
  claim occurred;
- a negative case with a changed binding is refused by the same active path.

If the real path cannot satisfy these gates, M1 ends blocked with one failure
ledger entry. Do not substitute the direct specimen or a new fixture protocol.

## M1 budgets

| Resource | Hard ceiling |
| --- | ---: |
| DeepSeek account/allowance probes | 1, only if current sufficiency is unknown |
| DeepSeek completions | 1 |
| Retries or prompt-tuning calls | 0 |
| Returned tool executions | 0 |
| Chemistry engine, scheduler, HPC, training, publication | 0 |
| New production modules | 2 |
| New focused test files | 2 |
| New milestone documents including receipt | 3 |
| Focused pytest invocations | 1, plus at most 1 rerun after one minimal repair |
| Standalone validator invocations | 1 at milestone review |
| Broad suites, Ruff, formatter, schema regeneration | 0 |
| Writable subagents | 0; read-only advisers may be used with immutable inputs |

Exhausting a ceiling blocks the milestone. It does not authorize a larger
budget, another model call, or a neighboring task.

## Artifact and validation discipline

- Keep one current state file and one milestone receipt. Historical receipts
  remain append-only inputs; do not create cross-phase reconciliation chains.
- Do not create a new versioned fixture successor unless it directly protects
  code wired into the active path in the same milestone.
- Prefer extending an existing adapter, permission boundary, event, or test over
  adding a parallel harness namespace.
- During implementation use inspection, type-aware reasoning, and minimal local
  diagnostics. Run the declared focused test group only after the vertical
  slice is complete.
- After one failed focused run, make at most one evidence-backed repair and one
  rerun. A second failure closes M1 blocked.
- A document/link/hash check is part of the single milestone review; it is not
  a separate mini-milestone.
- Full agent, lint, formatting, and release checks occur only after a separately
  authorized release milestone.

## Authority boundaries

The user has authorized existing-quota DeepSeek and literature API use only
within a declared milestone budget. This never authorizes a calculation,
scheduler job, purchase, top-up, retry, dependency install, commit, push,
publication, or disclosure of account telemetry.

Elsevier HTTP 403 remains unresolved. Do not retry or claim the key invalid
without a new entitlement path. SerpAPI and Tavily account availability does
not make snippets evidence. Literature work belongs to a later bounded
milestone and must use primary-source passages plus correction/retraction
checks.

## Required handoff

At Goal termination, report only:

1. milestone outcome: complete or blocked;
2. active-path behavior actually observed;
3. exact external quota used, expressed as calls/tokens/cost cap rather than
   private account balance;
4. focused validation invocation(s) and results;
5. changed files and rollback boundary;
6. remaining blockers and the single proposed next milestone.

Do not claim that a passing fixture, a provider response, or a generated report
establishes chemical correctness, comparative superiority, replication, or
SOTA.
