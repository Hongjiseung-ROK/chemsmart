---
name: chemsmart-agent-harness
description: Design, audit, test, or document ChemSmart's provider-neutral agent harness, including CLI-schema grounding, provider adapters, tool exposure, permissions, Runtime V2, event replay, task graphs, bounded subagents, and harness evaluations. Use when changing or assessing chemsmart/agent runtime, provider, loop, registry, permission, or agent-architecture behavior.
---

# ChemSmart Agent Harness

Use this skill to keep the agent loop auditable, bounded, and independent of a
single model provider. Read `AGENTS.md` first; it supplies repository-wide
authority, safety, and evidence rules.

## Working procedure

1. Inspect the active branch, dirty state, affected runtime contracts, and
   focused tests before proposing a change.
2. Derive command and option behavior from the Click schema, never a copied
   command list. Preserve the existing CLI contract unless the task explicitly
   changes it.
3. Keep provider-specific request, tool-call, and continuation conversion in
   adapters. Normalize only observable decisions, tool calls, artifacts,
   approvals, and outcomes.
4. Put authorization, idempotency, budgets, and validation in deterministic
   code rather than a prompt. Require exact, one-shot approval for material
   execution or state changes.
5. Extend the current Runtime V2 contracts and event stream additively. Keep
   old event logs replayable and do not introduce a parallel orchestration
   system.
6. Use subagents only when a task is independently verifiable or genuinely
   parallel. Give each worker immutable inputs, a limited tool set, a budget,
   an expected artifact, and a deterministic merge check.
7. Run focused runtime, permission, registry, and CLI-schema tests before a
   broader suite. Report behavior, evidence, and readiness separately.

## Required boundaries

- Do not make a model assertion, a valid command, or a successful tool call a
  scientific pass condition.
- Do not persist hidden reasoning. Preserve provider continuation state only as
  opaque protocol state, never as evidence.
- Do not let a planner, worker, or critic approve its own high-risk action.
- Do not enable autonomous execution, dynamic delegation, or a new provider
  protocol without a frozen single-agent baseline and an explicit evaluation.

## Use the references

- Read [runtime-contract.md](references/runtime-contract.md) before adding
  contracts, events, task graphs, provider capability fields, or replay logic.
- Read [approval-and-evaluation.md](references/approval-and-evaluation.md)
  before changing permissions, dispatch, budgets, or benchmark gates.

## Examples

Use this skill for: “add an approval-bound task-graph event,” “audit whether a
provider adapter leaks reasoning state,” or “design a bounded subagent
experiment.”

Do not use this skill alone to select a quantum-chemistry method, validate a
frequency calculation, or publish a result. Combine it with
`chemsmart-scientific-workflow` or `chemsmart-evidence-audit` when appropriate.
