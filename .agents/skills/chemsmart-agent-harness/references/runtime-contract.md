# Runtime contract reference

ChemSmart already has `RuntimeV2Mode`, `TaskEnvelope`, `AgentDecision`,
`ToolReceipt`, `ArtifactRef`, `RuntimeEvent`, and a hash-chained event store.
Treat these as the extension point.

## Command-compiled extension

CommandWorkflowSpec v1 is the model-facing plan for calculation preparation.
It contains a workflow ID, task-spec ID, CLI-schema digest, ordered immutable
CommandNode records, and no executable shell or native-engine input text. Each
node declares a Click command path, canonical parameter-name/value map,
project reference and digest, input ArtifactBinding, charge, multiplicity,
execution intent, dependencies, and expected artifact classes. An
ArtifactBinding contains a stable artifact ID, hash, and producer-node ID; it
does not accept a model-selected path or placeholder.

The compiler emits CanonicalCommandInvocation and CommandPreflightReceipt
objects. Bind the rendered argv/display command to the schema, project, input,
environment, safe-preview artifact, independent parser observation, and
semantic round-trip result. A CommandCounterexample carries only a rule ID,
failed field, expected/observed values, and evidence reference for bounded
repair. It is not a prompt to regenerate a free-form command.

## Additive contracts

The working tree defines these versioned contracts without replacing the
legacy runtime. Their presence is not an integration or conformance result:

- `ProviderCapabilities`: protocol, structured-output support, continuation
  mode, context/tool limits, and supported parallelism;
- `ScientificTaskSpec`: molecule/artifact reference, electronic state,
  program, job kind, method settings, constraints, requested observable, units,
  assumptions, and expected evidence;
- `CommandNode` and `CommandWorkflowSpec`: immutable command intent,
  dependencies, project/artifact bindings, expected outputs, and compilation;
- `ResourceBudget`: token, tool-call, network-request, cost, wall-time, and
  compute ceilings;
- `SpecialistTaskPacket`, `SpecialistResultPacket`, `ReviewPacket`, and
  `ReviewFinding`: bounded delegation and read-only critique;
- `PaperSourceBundle`, `ProtocolClaim`, `MolecularSystemSpec`,
  `ProjectConfigSpec`, `PaperResearchPlan`, and `DomainKnowledgePack`.

The active experiment layer adds `AdaptiveApiCampaignPolicyV1` and
`AdaptiveNetworkBudgetV1`. The campaign policy has
`transport_attempt_limit=None`, per-provider quota/exhaustion state, observed
concurrency and rate limits, cumulative request/token/latency/cost/retry/error
metrics, a terminal reason, and the last valid hypothesis. The network budget
limits concurrency, each request's context/output tokens, task wall time,
provider/endpoint/purpose, and credential lease scope. It is not an unbounded
network grant and must encode no-top-up and secret-redaction rules.

Run component experiments in an additive, hash-chained experiment stream rather
than weakening Runtime V2. Record the independently versioned switches for
task decomposition, specialist roles, evidence retrieval, domain-knowledge
packs, structured documentation, independent critic, adversarial
cross-examination, bounded repair, command DAG, and deterministic feedback.
The safety-validator, permission, schema, artifact-hash, secret-redaction,
native-input, engine, and HPC boundaries remain invariant.

`ProviderCapabilities`, `HarnessProfile`, `ProviderConformanceReceipt`, and
`ProviderStateRef` live in `runtime/harness_profiles.py`. Specialist, merge,
budget, and read-only review packets live in `runtime/delegation_contracts.py`.
Paper/source/scientific/project/plan contracts live in `paper_research.py`.
`DomainKnowledgePack` lives in `domain_knowledge.py`. `ApprovalRequest`,
`ApprovalResolution`, generic `EvidenceRef`, `ValidationReceipt`,
`ClaimRecord`, and `ReportManifest` remain reserved interfaces; do not claim
they are implemented until their code and fixtures exist.

Version every new event payload and retain a registry from event kind to
payload model. Existing v1 events must replay unchanged. Opaque provider state
may support a continuation but is explicitly non-evidentiary.

## Provider-continuation boundary

Do not add a generic provider field such as `previous_response_id` to the core.
The current OpenAI adapter uses Chat Completions. Public and persisted history
contains sanitized assistant tool-call messages plus tool results. Some
providers, including DeepSeek V4 thinking mode, additionally require private
`reasoning_content` to be replayed between tool-call subturns. Keep that value
only in the uninterrupted in-memory adapter history and remove it from every
public projection. After `ask_user`, pause, or process restart, start a new
provider request from a deterministic public recap or fail closed; never
persist hidden reasoning to reconstruct the old wire turn. A Responses-style
continuation remains a distinct adapter capability with a distinct tool-output
protocol.

## Paper-research extension

Use the exact v1 names: `PaperSourceBundle`, `SourceArtifact`, `ProtocolClaim`,
`MolecularSystemSpec`, `ProjectConfigSpec`, and `PaperResearchPlan`. A paper
coordinator owns the source bundle, molecular identity, project signatures,
and final command DAG. Acquisition and extraction workers return
evidence-addressed facts; scientific workers return typed task candidates;
command workers return only `CommandWorkflowSpec` data; critics return
`ReviewFinding` records. No worker may silently convert an inference or unknown
into an explicit paper setting. Critical inferred, unknown, or conflicting
claims block paper-faithful readiness; no author contact or unreported
sensitivity calculation may fill the gap.

Use a versioned `DomainKnowledgePack` for scientific rules. Each pack binds
domain and engine/version scope, source locators and hashes, allowed settings,
prohibited conditions, stable rule IDs, and deterministic validator IDs. It is
not an execution or approval authority.

## Harness profiles

All four profiles retain sandboxed tools, approval pause, and deterministic
validator feedback:

- `H0` is the minimal single-agent typed loop;
- `HC` adds public event-prefix replay;
- `HA` adds progressive skills, fresh specialist contexts, deterministic
  hooks, structured handoffs, compaction, and delegation depth one;
- `HK` adds persistent goal state, checkpoint/fork/resume, and delegation depth
  two.

Profile labels are hypotheses, not claims of identical vendor internals. Admit
each provider/profile pair only after its required observable checks pass in a
`ProviderConformanceReceipt`.
Conformance is mode-specific: an enabled-thinking DeepSeek receipt cannot be
used as evidence for thinking-disabled behavior or for a causal accuracy gain.
The legacy 2026-08-01 H0 observation is `stale_invalidated` under the current
receipt schema and source snapshot, so it grants no current admission.

If a provider needs resumable state, bind an opaque adapter-owned checkpoint to
session/turn, provider and wire protocol, resolved model, tool-schema/scope
digest, sanitized-history digest, remaining budgets, and approval/resource
envelope. Store raw state in a private adapter sidecar, expose only an opaque
reference to public runtime state, and invalidate it on any mismatch. Replay
must be idempotent and must never carry an approval into a changed invocation.

## Event lifecycle

Additive v1 research payloads are designed to record source, claim, molecular system,
project, domain-knowledge binding, specialist dispatch/join, command preview,
three role-specific review gates, report graph, final plan validation, budget,
pause/resume, and an evidence-bound terminal state. A green terminal state
requires the same immutable plan digest, all three current green review-gate
digests, the current report-graph digest, and the final validation receipt.
Any upstream change invalidates these downstream gates.
A PRP-10 coordinate-import event or receipt must bind the official source and
archive member, exact source/imported-byte hashes, single frame, angstrom units,
atom order, molecular identity approval, and access/license record. A private
safe-preview artifact is retained byte-for-byte by hash; its bytes and local
path do not enter the public event stream.
A focused event-store/reducer/legacy-replay receipt is required before this
lifecycle may be described as integrated.

The longer authorized lifecycle remains:

`paper sources → claims → scientific specification → project/command graph →
safe preview → independent reviews → report → plan validation → approval →
execution → result validation → evidence-driven replan or terminal state`

Record terminal failure and blocked states explicitly. A report is not a
terminal success unless all mandatory receipts and validators are present.

For an advanced paper plan, require a source-bundle-bound
`RequiredProtocolCoverage` declared independently from the plan producer. The
validation event must carry the typed plan, validation context, derived result,
and a content-addressed receipt so replay can reproduce status and rule IDs.
Never accept an opaque caller-provided digest as a validator result.

A specialist join carries the exact `SpecialistResultPacket` objects. Re-run
the deterministic merge against the persisted dispatched packets, require the
whole active lineage family, and compare the recomputed receipt exactly.
Research terminal state is global and absorbing; idempotency replays only an
identical session, turn, event kind, and canonical payload.

Add future approval, execution, result-validation, and command-counterexample
payloads rather than replacing older `RuntimeEvent` payloads. Legacy logs must
replay without a migration-induced command or permission effect.
