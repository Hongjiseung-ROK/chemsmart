# ChemSmart API-Agent Gap Analysis

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

## Explicit non-goals of this foundation

- No runtime, CLI, provider, permission, or engine behavior changes.
- No live model requests, real Gaussian/ORCA/xTB runs, or scheduler jobs.
- No GUI, desktop application, packaging, or Studio changes.
- No claim that the current agent is autonomous, production-ready, or
  scientifically validated.

The implementation blueprint and its gates are in
[chemsmart-agent-ultimate-goal.md](../design/chemsmart-agent-ultimate-goal.md).
