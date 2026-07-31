# Runtime contract reference

ChemSmart already has `RuntimeV2Mode`, `TaskEnvelope`, `AgentDecision`,
`ToolReceipt`, `ArtifactRef`, `RuntimeEvent`, and a hash-chained event store.
Treat these as the extension point.

## Additive future contract

Introduce versioned payloads only after their fixture and replay requirements
are specified:

- `ProviderCapabilities`: protocol, structured-output support, continuation
  mode, context/tool limits, and supported parallelism;
- `ScientificTaskSpec`: molecule/artifact reference, electronic state,
  program, job kind, method settings, constraints, requested observable, units,
  assumptions, and expected evidence;
- `TaskNode` and `TaskGraph`: immutable inputs, dependencies, allowed tools,
  budget, approval scope, expected outputs, verifier, and deterministic join;
- `ResourceBudget`: token, tool-call, cost, wall-time, and compute ceilings;
- `ApprovalRequest` and `ApprovalResolution`: exact hashes, scope, actor,
  expiry, and one-shot decision;
- `EvidenceRef`, `ValidationReceipt`, `ClaimRecord`, `ReviewFinding`, and
  `ReportManifest`.

Version every new event payload and retain a registry from event kind to
payload model. Existing v1 events must replay unchanged. Opaque provider state
may support a continuation but is explicitly non-evidentiary.

## Provider-continuation boundary

Do not add a generic provider field such as `previous_response_id` to the core.
The current OpenAI adapter uses Chat Completions, where continuation is the
sanitized assistant tool-call message plus tool results in history. A
Responses-style continuation is a distinct adapter capability with a distinct
tool-output protocol.

If a provider needs resumable state, bind an opaque adapter-owned checkpoint to
session/turn, provider and wire protocol, resolved model, tool-schema/scope
digest, sanitized-history digest, remaining budgets, and approval/resource
envelope. Store raw state in a private adapter sidecar, expose only an opaque
reference to public runtime state, and invalidate it on any mismatch. Replay
must be idempotent and must never carry an approval into a changed invocation.

## Event lifecycle

Use the future lifecycle only after typed contracts exist:

`goal → scientific specification → task graph → preflight → approval →
execution → validation → review → evidence-bound report → terminal state`

Record terminal failure and blocked states explicitly. A report is not a
terminal success unless all mandatory receipts and validators are present.
