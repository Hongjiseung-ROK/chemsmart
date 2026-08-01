# P2 executor-binding fixture protocol v1

## Status

Closed fixture-only prospective protocol at 2026-07-31T20:47:48Z. It addresses
P4-HA-01's unimplemented executor-side approval-consumption boundary without
changing the active Runtime V2, CLI, tool loop, or execution path.

## Objective

Specify and test the minimum one-shot approval evidence a future executor
would need before a **fake** dispatch may be recorded: exact approval binding,
command digest, preflight digest set, live-derived CLI-schema digest, execution
target, expiry, and one-shot consumption. This is a safety specification, not
a real executor or an authorization for any calculation.

## Inputs

| Input | Required use |
| --- | --- |
| Frozen [P4 harness finding](reviews/p4-harness-findings-v1.json) | Preserve the finding that executor-side consumption and dispatch are unimplemented. |
| Frozen [P2 receipt](receipts/p2-runtime-contracts.json) | Preserve additive Runtime V2 and no-CLI-semantic-change boundaries. |
| [P2 firewall addendum](p2-scientific-firewall-addendum-v1.md) | Keep secret-safe, fixture-only Runtime evidence behavior distinct from actual dispatch. |
| Current `ApprovalRequest` model | Record the practical observation that it lacks a CLI-schema digest field. |
| Current Click schema via `schema_with_metadata(build_chemsmart_cli_schema())` | Derive the schema digest inside a fixture; do not dump or change the CLI tree. |

## Tools and authority

- Allowed: in-memory typed fixture bindings, a live-derived schema hash,
  fake-dispatch counters, local source/hash validation, and focused tests.
- Not allowed: importing the module into active runtime paths, invoking
  `execute_chemsmart_command`, executing a command, provider/API access,
  credentials, engines, schedulers, installs, commits, or pushes.

## Budget

| Resource | Ceiling | Observed |
| --- | ---: | ---: |
| Live-derived Click schema construction | 1 fixture scope | 1 fixture scope |
| Fake dispatcher calls on valid fixture | 1 | 1 |
| Fake dispatcher calls on invalid fixture | 0 | 0 |
| Real command/engine/scheduler/provider calls | 0 | 0 |
| Active runtime/CLI/loop wiring changes | 0 | 0 |

## Failure, hypothesis, and minimal change

| Field | Record |
| --- | --- |
| Failure | `ApprovalRequest` has 19 fields and no `cli_schema_sha256`; P4 already records that approval consumption at dispatch is unimplemented. |
| Hypothesis | A prospective dispatch check must bind a live CLI schema digest in addition to existing request command/preflight/target hashes, then consume the exact binding once. |
| Minimal change | Add an unwired `frontier_executor_binding` fixture module and deterministic fake-dispatch tests only. |
| Evidence | One in-memory model-field observation, P4-HA-01, a live-derived schema fixture, and focused deterministic outcomes. |
| Result | The fixture blocks missing, mismatched, denied, expired, target-changed, schema-changed, command-changed, preflight-changed, and reused approvals before the fake dispatcher. |
| Limitation | The active runtime still does not persist this extended binding or enforce it around a real dispatcher. |
| Rollback boundary | Delete only this unwired fixture module/protocol if its proposed contract proves unsuitable; do not infer any change to the active approval or execution behavior. |

## Receipt-validation repair

The first receipt-wrapper invocation failed before evaluating the protocol:
when `PYTHONPATH` was deliberately unset, the standalone validator imported an
installed package instead of this checkout and could not locate
`scientific_contracts`. P2B-F2 records the bounded repair: bind only the
validator's own repository root to `sys.path` before its local contract import.
It changes neither package installation nor runtime import behavior. The one
targeted wrapper rerun passed after that repair.

## Fixture contract

`FixtureExecutorBinding` derives its existing-request part from
`ApprovalRequest.binding_sha256` and adds a current CLI-schema SHA-256. A
fixture resolution must name the new binding digest and be explicitly approved.
`FixtureApprovalLedger.consume()` checks all fields before marking a binding
consumed. It accepts no dispatcher, command string, process handle, engine, or
network client; a test-local list is the only fake-dispatch observation.

## Gates

| Gate | Current status | Evidence boundary |
| --- | --- | --- |
| P2B-G1 exact binding | Passed in fixture | Binding includes request, command, preflight set, schema, target, and expiry hashes/values. |
| P2B-G2 mismatch refusal | Passed in fixture | Nine missing/mismatch/expiry cases leave fake dispatch at zero. |
| P2B-G3 one-shot consumption | Passed in fixture | A second identical attempt is blocked after one fixture approval. |
| P2B-G4 active-path preservation | Passed narrowly | The new module is unwired; no active runtime, CLI, or loop source is changed. |
| P2B-G5 real executor enforcement | Unresolved | No persistent extended approval record or real dispatch integration exists. |

## Blockers

- A real executor needs a separately approved data-model revision, durable
  schema/preflight binding, atomic persistent consumption, integration review,
  and a non-engine test strategy before any engine-facing work.
- The fixture cannot validate actual user approval UI, provider behavior,
  process execution, chemical output, or scheduler behavior.
- P3 provider, P5 trial, P6 replication/training/release/SOTA gates remain
  entirely unchanged.

## Phase-close validation

The close used one focused fixture test and one dedicated receipt-validator
test. Both establish a prospective safety contract only; they do not make an
executor available.

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_executor_binding.py -q
```

## Claim-evidence ledger

| ID | Claim type | Statement | Status |
| --- | --- | --- | --- |
| P2B-C1 | source observation | The current `ApprovalRequest` lacks a CLI-schema digest field. | Supported by in-memory model inspection. |
| P2B-C2 | code observation | The prospective fixture blocks the declared mismatch cases and consumes one exact fixture binding once. | Supported by focused fake-dispatch tests only. |
| P2B-C3 | inference | The active executor consumes approval at dispatch. | Rejected; no active integration exists. |
| P2B-C4 | inference | The protocol authorizes a real command, chemistry engine, scheduler, or provider call. | Rejected. |
| P2B-C5 | unresolved uncertainty | A durable, current-schema-bound approval path is implemented and safe. | Unresolved. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- |
| P2B-D1 | Keep the extended binding outside the active Runtime V2 schema. | Adding a nullable field could alter historical approval-binding digests. | A future versioned event/approval migration needs its own design and authority. |
| P2B-D2 | Use a live-derived schema digest instead of a copied command list. | The Click schema is the executable source of truth. | Recompute through the current schema function in each future fixture. |
| P2B-D3 | Treat fake-dispatch success as a prospective safety check only. | It has no process or engine side effect. | Do not promote the result to execution enforcement. |
