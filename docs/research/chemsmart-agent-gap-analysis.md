# ChemSmart API-Agent Gap Analysis

> Historical pinned-baseline analysis. It describes
> `cf986251077b7ee65f8afa951ee76052146c7613`, not the command-refinement
> implementation on top of it. The active boundaries are
> [CommandWorkflowSpec v1](../design/command-workflow-spec-v1.md) and
> [Paper Research Plan v1](../design/paper-research-plan-v1.md).

## Scope and evidence boundary

This is a source-grounded snapshot of
`cf986251077b7ee65f8afa951ee76052146c7613`, the base of the Frontier Agent
Foundation. It describes implemented behavior, feature-gated behavior, and
missing behavior separately. It does not claim that a passing parser, fixture,
or agent test demonstrates scientific readiness.

The accompanying [evidence ledger](frontier-agent-evidence-ledger.json)
records the exact CLI-schema hash, focused-test result, research sources, and
source limitations. The initial focused baseline passed 206 tests in 4.80 s;
the full-suite result is intentionally recorded only after this branch's
foundation changes are validated.

## Active working-tree delta

The table below is a source inspection of the uncommitted working tree based on
`887ab923d45e1a8a97f04441d3df843500e8f1df` on 2026-08-01. It is not a release
receipt. “Contract present” means the named strict type or rule exists in the
working tree; it does not mean integration, provider conformance, chemistry
execution, or PRP-6 acceptance has passed.

| Area | Contract present in the working tree | Evidence still required |
| --- | --- | --- |
| Paper state | `paper_research.py` defines source, claim, molecular-system, project, knowledge-pack binding, research-plan, readiness, and digest contracts. | End-to-end source acquisition, plan assembly, safe-preview linkage, and a frozen paper fixture remain to be demonstrated together. |
| Scientific knowledge | `domain_knowledge.py` defines versioned domain/engine scopes, source hashes, rules, prohibitions, and validator IDs. | Each of the six domains still needs reviewed pack content and implemented validators; selecting a pack is not evidence for a paper setting. |
| Harness profiles | `runtime/harness_profiles.py` defines `H0`, `HC`, `HA`, and `HK`, provider capabilities, opaque state references, and conformance receipts. The retained [2026-08-01 DeepSeek V4 Flash H0 observation](../evaluation/receipts/deepseek-v4-flash-h0-2026-08-01.json) is historical only. | The H0 observation is `stale_invalidated`: it predates the current source snapshot, has a legacy short receipt ID, and lacks the current public-history digest. It admits no current profile. HC, HA, and HK are also untested; thinking-disabled behavior and a causal thinking benefit are untested. |
| Delegation and review | `runtime/delegation_contracts.py` defines bounded specialist, result, merge, review, and review-gate envelopes. | Seeded-fault evaluation must show that ownership, budget, scope, join, and critic-independence rules work through the active runtime. |
| Runtime research events | Additive event payloads and projection work are present under `runtime/`. | Legacy replay, invalid transition rejection, idempotency collision handling, and terminal receipt binding require a focused integration receipt after the event milestone stabilizes. |
| Project coverage | The project loader and command grounding contain an xTB extension in addition to Gaussian and ORCA. | Loader, semantic-match, and generated-preview checks remain required; auxiliary and six-domain capability gaps must be recorded rather than bypassed. |

The largest remaining system gap is orchestration: these contracts must be
joined by one coordinator into a source-complete `PaperResearchPlan` without
inventing missing settings. ChemSmart must not contact paper authors and must
not add, propose, or execute an unreported sensitivity calculation. The final
unresolved empirical gap is PRP-6: no contract or focused test substitutes for
six sealed, held-out papers, hidden expert gold, and the exact acceptance gate.
The nearer public pilot is also incomplete: the user experimental paper is
`blocked_missing_source`, and the six public domain-control papers have not
been selected or acquired.

## Current agent surface

| Area | Implemented in the baseline | Boundary or gap |
| --- | --- | --- |
| CLI grounding | [`cli_schema.py`](../../chemsmart/agent/cli_schema.py) recursively serializes the real Click tree, resolves deferred groups without mutating the global cache, hashes the schema, and publishes guided completion metadata. The observed schema has 171 command nodes and primary Gaussian, ORCA, and xTB calculation paths. | A schema-valid command is not a scientific preflight or an execution result. Deep job semantics are uneven across command families. |
| Providers | [`providers.py`](../../chemsmart/agent/providers.py) supplies Anthropic Messages, OpenAI Chat Completions, and local-provider adapters. | There is no current Responses-API, MCP, provider-capability negotiation, or provider-neutral continuation-state contract. A future adapter must not conflate opaque provider state with public evidence. |
| Tool loop | [`registry.py`](../../chemsmart/agent/registry.py) groups 35 tools into synthesis, project-YAML, harness-job, execution, wizard, and diagnostics surfaces. [`loop.py`](../../chemsmart/agent/loop.py) bounds tool calls and resolves permission before handling. | Multiple tool calls are serialized; no task graph, isolation primitive, worker dispatch, deterministic join, or independent-review role exists. |
| Runtime nucleus | [`runtime/contracts.py`](../../chemsmart/agent/runtime/contracts.py) defines `TaskEnvelope`, `AgentDecision`, `ToolReceipt`, artifact references, and `RuntimeV2Mode`. [`runtime/events.py`](../../chemsmart/agent/runtime/events.py) provides versioned, hash-chained append-only events. | Runtime V2 has `off`, `shadow`, and `active` modes, but it does not yet model scientific specifications, task graphs, claim records, report manifests, or versioned validation payloads. |
| Artifacts and receipts | [`runtime/receipts.py`](../../chemsmart/agent/runtime/receipts.py) hashes file artifacts and records producer metadata. | Receipts do not yet require engine binary/environment identity, computational settings, parsed values with units, scientific validation, or claim-to-evidence links. |
| Permissions | [`permissions.py`](../../chemsmart/agent/permissions.py) has explicit approval modes and exact approval paths for risky work. | Approval is not yet a first-class immutable object bound to task, input, project, executable, environment, and resource hashes with invalidation on change. |
| Planning and critique | Legacy planning and project-YAML critique paths remain present; unified session metadata records a critic field. | The unified run finalizes no independent scientific critic verdict. Routing is not a dependency graph and does not support reproducible replanning or cross-examination. |
| Scientific support | Program settings, project parsing, generated-input checks, and calculation inspection tools exist. | There is no canonical scientific task specification, literature-retrieval policy, method applicability model, convergence/uncertainty evidence ledger, or standards-aware report generator. |
| Documentation and evaluation | Session metadata and deterministic agent tests exist. | No canonical methods/SI report, citation audit, QCSchema-compatible record, RO-Crate-style manifest, held-out multi-turn chemistry benchmark, or component ablation has been established. |

## Strengths to preserve

1. **The Click parser is the command source of truth.** The schema builder
   already resolves lazy commands and exposes per-command completion metadata.
   Future task planning must consume this surface rather than duplicate it.
2. **Runtime events and artifact hashes are a viable provenance nucleus.** A
   future evidence ledger should extend these structures, not replace them.
3. **Permissions are already deterministic.** Retain the existing policy as
   the enforcement point; do not move safety decisions into prompts or a
   reviewer persona.
4. **The tool registry already scopes capabilities.** The future dispatcher
   can refine its exposure by task without inventing a second tool ecosystem.

## Principal gaps and design consequences

### 1. Scientific state is not yet typed

The current task envelope records request and workspace context, not the
scientific meaning of a calculation. Introduce an additive `ScientificTaskSpec`
only after a schema, fixtures, and versioned event payloads exist. It must bind
molecule/geometry identity, charge, multiplicity, program/job kind,
method/basis/ECP, solvent, constraints, observable, units, assumptions, and
required evidence.

### 2. Event provenance is necessary but incomplete

Hash-chaining demonstrates an event sequence has not silently changed; it does
not prove the right geometry, method, executable, convergence criterion, or
physical interpretation was used. Future `ValidationReceipt`, `ClaimRecord`,
and `ReportManifest` payloads should therefore point to native artifacts,
environment/version data, parsed quantities, and named deterministic checks.

### 3. The current loop is not a task-decomposed agent system

ChemSmart has role labels and bounded tool calls, but no immutable task packets,
dependency DAG, budgeted workers, or merge verifier. A future subagent system
must be optional and limited to independent work—for example, separately
computable species with a deterministic stoichiometric merge—not a static
hierarchy of job titles.

### 4. Critique is not independent scientific validation

The existing project-YAML critic is valuable as an advisory check. It should
not become a final authority. A future critic must receive artifacts and
declared assumptions in a fresh, read-only context; deterministic validators or
independent recomputation resolve disagreement.

### 5. Documentation must be evidence-derived

ChemSmart cannot claim an end-to-end calculation is reproducible until a report
can be regenerated from structured, pinned artifacts. The target is a
QCSchema-compatible record plus native inputs/outputs and a workflow manifest,
not a polished narrative that omits failed checks or assumptions.

## Historical foundation limits

The pinned `cf986251...` foundation release was documentation-and-skill work
only. At that baseline it made no runtime, CLI, provider, permission, or engine
behavior change; made no live model request or chemistry/scheduler run; and did
not claim autonomy, production readiness, or scientific validation. Those are
historical release facts, not a description of the active working tree.

## Current development-slice boundaries

The active slice may add strict paper, provider, delegation, project, and
Runtime V2 contracts and may perform bounded provider/literature probes within
the existing user-owned quota. It still does not authorize:

- a real Gaussian, ORCA, or xTB calculation or scheduler/HPC job;
- a native-input model surface or runtime self-modification;
- GUI, desktop application, packaging, or Studio work;
- model training, publication, preprint submission, or dataset release; or
- a claim of paper reproduction, PRP-6 passage, broad generalization, or SOTA.

Each such boundary changes only through explicit phase evidence and applicable
user approval, not because a contract or API liveness probe exists.

The implementation blueprint and its gates are in
[chemsmart-agent-ultimate-goal.md](../design/chemsmart-agent-ultimate-goal.md).
