# P2 — Runtime scientific contracts

## Status

Completed at the Runtime V2 contract boundary on 2026-07-31. P0 is complete
and P1 closed blocked with its red external gates retained. The one focused
runtime/replay/CLI group passed 59 tests in 2.54 s; this does not reinterpret
P1 provider receipts as execution authority or establish product/release
readiness.

## Objective

Extend the existing Runtime V2 nucleus with versioned, replayable scientific
and evidence contracts while preserving current Runtime V2 events, the Click
parser, CLI behavior, provider wire protocols, and the frozen single-agent
reference path.

## Inputs

| Input | Required use |
| --- | --- |
| P0 source receipt | Detect drift in Runtime V2, provider, schema, and test inputs. |
| P1 configuration/receipt policy | Bind external capability facts without retaining credentials. |
| Current Runtime V2 contracts, events, reducer, store, lifecycle, and tests | Add to the existing event stream; do not create a second runtime. |
| Harness and scientific-task contract references | Define `ScientificTaskSpec`, budgets, approvals, evidence, and validation minimums. |
| Frozen old-event fixtures | Prove v1 parse/reduce/replay behavior remains unchanged. |

## Tools and authority

- Allowed: additive Python contracts, deterministic event payload registry,
  fixture construction from archived/non-engine data, source review, and
  focused runtime/schema/permission tests.
- Not allowed: Click command or option semantic changes, migration of provider
  wire state into public evidence, real model or chemistry execution, new
  dependencies, broad test loops, or approval bypasses.
- Opaque continuation state remains adapter-owned, bound to provider/protocol/
  model/tool-schema/history/budget/approval digests, and non-evidentiary.

## Budget

| Resource | Ceiling |
| --- | --- |
| Runtime contract work | One additive versioned payload family at a time, each with fixtures and replay proof |
| CLI/schema changes | 0 unless separately approved by the user |
| Live API and chemistry-engine calls | 0 |
| Validation | One focused contract test group per completed payload family; full suite deferred to a major milestone |

## Artifacts

- [Typed scientific contracts](../../../chemsmart/agent/runtime/scientific_contracts.py)
  and an [event payload registry](../../../chemsmart/agent/runtime/events.py)
  under the optional `scientific_v1` namespace. `EventKind` and
  `RuntimeEvent.schema_version` remain unchanged.
- [Frozen v1 event-log fixture](../../../tests/agent/runtime/fixtures/runtime_v1_frontier_baseline.jsonl)
  and [focused contract tests](../../../tests/agent/runtime/test_scientific_contracts.py).
- Additive `ScientificTaskSpec`, `ResourceBudget`, immutable approval
  request/resolution/invalidation, validation/evidence, claim/review, report,
  budget-exhaustion, and phase-close records. They are declarative evidence
  records; none dispatches a chemistry engine or a provider.
- [P2 current-artifact receipt](receipts/p2-runtime-contracts.json), which
  records source and frozen-fixture hashes separately from the P0 Git baseline.

| Surface | Allowed content | Explicitly excluded | Runtime effect |
| --- | --- | --- | --- |
| `scientific_v1` event namespace | Model-safe geometry identity, method settings, budgets, approvals, evidence, validation, claims, review, phase gates | Prompts, reasoning, provider transcripts, credentials, host paths in geometry references | Registry validates without rewriting the hashed raw payload. |
| Approval request | Canonical action/input/project/executable/environment/budget hashes and a non-secret target | Raw command, secret-bearing argv, credentials, reusable consent | Binding changes cannot reuse a matching approval record. Executor enforcement remains out of scope. |
| Reducer state | Typed records keyed by stable record identifiers | A second orchestration system or implicit dispatch | Replays scientific records only when the optional extension is present. |
| Completion gate | Explicit task specifications, required evidence, and validation status | New behavior for legacy turns | Scientific completion gates apply only after an opt-in task specification. |

## Gates

| Gate | Pass condition | Red condition |
| --- | --- | --- |
| P2-G1: v1 replay | Frozen v1 JSONL logs still parse, hash-verify, and reduce identically. | Unknown old events, changed event bytes, or changed reduced meaning. |
| P2-G2: additive contracts | New fields are versioned and registered without a parallel store/policy engine. | Unversioned payload or replacement orchestration. |
| P2-G3: approval binding | One-shot approval binds exact task/input/project/executable/environment/resource hashes and invalidates on mismatch. | A changed invocation inherits approval. |
| P2-G4: scientific identity | A task cannot claim a calculation specification without stable geometry/frame, units, charge, multiplicity, method settings, expected evidence, and uncertainty. | Filename-only identity or invented consequential inputs. |
| P2-G5: CLI preservation | Current Click parser/schema behavior remains characterized. | Silent help/option/semantic drift. |

The focused group recorded in the P2 receipt passed P2-G1, G2, G4, and the
existing CLI characterization for P2-G5. P2-G3 passes only at the contract
fixture boundary: actual executor-side binding and one-shot consumption require
a separately authorized implementation and test boundary.

## Blockers

- P2 has a source-controlled v1 baseline fixture, not an external production
  corpus; broader historical replay diversity remains deferred to P3/P6.
- Existing generic artifact receipts may retain host paths. New geometry
  contracts use `OpaqueArtifactRef`; P2 does not retroactively expose old
  artifact paths to a provider.
- Executor-side approval binding, expiry, and one-shot consumption are not
  enforceable from this contract alone. No execution is authorized.
- A material chemistry method choice is not supplied by a generic contract and
  remains user- or project-bound.
- P1’s canonical DeepSeek alias/tool-surface red gate and Elsevier entitlement
  uncertainty remain red and are not bypassed here.

## Phase-close validation

Run the one focused runtime/permission/replay group and the existing
CLI-schema characterization test exactly once. Record its command, fixture
hashes, replay result, changed versus preserved semantics, and every failed
gate in the [P2 receipt](receipts/p2-runtime-contracts.json). Do not elevate
these checks to scientific, product, or release readiness.

## Claim-evidence ledger

| ID | Claim type | Statement | Required evidence | Initial status |
| --- | --- | --- | --- | --- |
| P2-C1 | observation | Runtime V2 can carry a specified payload family without breaking v1 replay. | Frozen logs, hash/reducer tests, source diff. | Supported observation. |
| P2-C2 | inference | Typed state improves scientific safety. | Fault-suite false-pass comparison, not type existence. | Unresolved. |
| P2-C3 | observation | Approval is bound to one exact invocation at the runtime-contract boundary. | Mismatch/invalidation fixtures. | Qualified contract observation; executor enforcement unresolved. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P2-D1 | Extend Runtime V2 rather than introduce a new orchestration system. | Existing event store and explicit design contract. | Revert the additive payload family if replay fails. |
| P2-D2 | Keep provider continuation opaque and adapter-owned. | Protocol differences and non-evidence rule. | Expose only a safe opaque reference if needed. |
| P2-D3 | Preserve the frozen single-agent path. | Required ablation reference. | Optional dispatch stays off until P5 gates pass. |
| P2-D4 | Use `scientific_v1` only on existing compatible v1 event kinds. | New event kinds/schema versions would break old readers; project/artifact reducers validate whole payloads. | Remove the namespace before changing v1 event semantics. |
| P2-D5 | Treat a contract approval as evidence, not execution permission. | The executor is outside this source scope and no engine authority was granted. | Add executor enforcement only with explicit approval and a dedicated fault suite. |
