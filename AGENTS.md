# ChemSmart Agent Operating Contract

## Mission

Develop ChemSmart as a CLI-first, provider-neutral computational-chemistry
automation agent whose ultimate benchmark is paper-to-research-plan
reconstruction.
Given a legally accessible article, Supporting Information, and associated
artifacts, the agent must reconstruct the complete computational protocol as
typed evidence, project settings, command workflows, ChemSmart-generated
inputs, validation procedures, and a conservative experiment plan. A model
may plan, ask, explain, and propose typed ScientificTaskSpec and
CommandWorkflowSpec objects. It must not author, patch, or treat as
authoritative Gaussian, ORCA, or xTB native input text. Deterministic ChemSmart
code owns CLI semantics, command compilation, permission policy, execution,
scientific validation, and evidence recording.

Do not resume GUI, desktop-app, packaging, Studio, or visual-design work unless
the user explicitly reopens it. Do not treat an installed tool, a valid command,
or a plausible model answer as evidence that a calculation or scientific claim
is correct.

## Authority and scope

Use this precedence order:

1. Explicit user request and approval for the current task.
2. This file and the nearest applicable repository instructions.
3. The checked-out CLI parser, configuration, job, runtime, and test contracts.
4. Generated artifacts, deterministic validators, execution receipts, and
   primary sources.
5. Model output and legacy guidance.

`CLAUDE.md`, `.clinerules/`, and `memory-bank/` retain useful historical or
tool-specific material, but they must not weaken this contract. Treat dated
metrics and collection instructions there as historical unless the user
explicitly reactivates that work.

## Before changing anything

- Inspect the branch, ancestry, dirty state, relevant instructions, source
  contracts, and focused tests.
- Preserve unrelated or partial user work. Never reset, clean, stash, or
  overwrite it without explicit authority.
- State assumptions that materially affect chemistry, execution, cost, or
  scientific interpretation.
- Derive CLI behavior from the current Click parser and generated schema; do
  not maintain a hand-written command inventory as ground truth.
- Treat the command compiler as the only authority that turns a model proposal
  into argv. It must resolve live schema options, trusted project and artifact
  references, canonical long flags, and shell-safe rendering. A model never
  supplies executable shell syntax, arbitrary paths, option ordering, aliases,
  quoting, or a native-engine fallback.
- Do not install dependencies, alter environment pins, contact external
  systems, commit, push, or publish without authority for that action.
- For a paper task, inspect the main article, Supporting Information, figures,
  tables, deposited structures/data, cited protocols, and repository records
  before declaring the computational method extracted.

## Scientific workflow

Make these facts explicit before a calculation is treated as specified:

- molecule identity and stable artifact identifier;
- exact geometry frame and coordinate units;
- charge, multiplicity, electronic-state assumptions, and constraints;
- requested observable, program, job kind, method, basis/ECP, dispersion,
  solvent, temperature/standard-state convention, and resource target;
- required evidence, diagnostics, and limitations.

Ask instead of inventing a scientifically consequential missing fact. Never
infer geometry identity from a filename alone. Compile the typed intent through
the live schema, trusted project/artifact resolver, safe CLI preview, and
independent parser observation before an action can be called previewed.
Generated native inputs are downstream evidence produced by ChemSmart, not a
model-editable interface.

For the active PRP-10 campaign, a paper is eligible only when an official
source supplies an exact, single-frame XYZ geometry in angstrom. Bind the
source locator and archive member, source and imported-byte hashes, atom order,
coordinate units, identity approval, access/license record, and import receipt.
Do not reconstruct coordinate tables, use OCR, generate 3D coordinates from a
line notation, or let a model create or repair coordinates. SDF, MOL, and PDB
may enter a separately validated general-input conversion path, but conversion
does not make a paper eligible for PRP-10. Missing coordinates block the
affected nodes without blocking unrelated source inspection.

For every paper-derived field, record exactly one epistemic status:
`explicit`, `derived`, `inferred`, `unknown`, `conflict`, or `not_applicable`.
An explicit value requires a source locator. A deterministic conversion may be
derived only with a content-addressed deterministic derivation receipt; a
critical `not_applicable` value requires a content-addressed applicability
receipt. An inferred value must be presented as a candidate, never silently
promoted to the paper's method. A critical inferred, unknown, or conflicting
value requires `blocked_missing_evidence`; the agent may document the gap but
must not contact authors or invent an unreported sensitivity calculation to
fill it. A sensitivity calculation explicitly reported by the paper remains a
normal workflow node.

Use these mutually exclusive outcome labels precisely:

- **planned**: intent is recorded, but no executable input exists;
- **previewed**: input or command was rendered but not run;
- **executed**: an engine or scheduler was invoked and a receipt exists;
- **validated**: required deterministic checks passed;
- **reproduced**: an independently rerun, pinned environment produced the
  declared result within the stated tolerance;
- **waiting for approval**, **blocked**, or **failed**: a required condition
  remains unmet.

Do not call a run complete when a required receipt, validator, artifact, or
approval is absent.

## Approvals and execution

Planning, read-only inspection, deterministic validation, and fixture-based
simulation may proceed within the user's scope. Require explicit approval for:

- real local calculations, scheduler/HPC submission, cancellation, or retry;
- writes outside a disposable task workspace or overwrites of user artifacts;
- paid model or compute use, networked external execution, and publication;
- a material change to the agreed molecular model, method, electronic state,
  resource budget, or scientific claim.

Bind approval to the exact command, inputs, project, executable/environment,
and artifact hashes. Invalidate it when any bound value changes. Keep secrets
out of prompts, logs, commits, and evidence bundles.

Use a paid DeepSeek model call or literature lookup only through an existing
user-owned quota and a short-lived credential lease. Record one credential
source for each campaign and do not silently fall back to another source. The
historical S0 receipts used credentials already present in their session
environment and did not read Keychain items. The active campaign uses only its
recorded ignored secret source. Lease only the value needed by the selected
provider and never copy it into project configuration or evidence. Never print,
persist, transmit in a prompt, or infer a secret. Record only the provider,
endpoint class, key-validation outcome, quota-sufficiency outcome, and
non-secret error class. Do not top up a quota, change a billing plan, or turn a
provider credential into general network authority. Once a user has authorized
the current development phase, lease-bound calls within its recorded quota may
proceed without per-call reapproval; a new provider, target, quota expansion,
or billing change needs new authority.

The completed campaign `two-frontier-s0-2026-08-01` is historical evidence.
Its frozen policy counted every initial call and retry, limited DeepSeek to 128
aggregate transport attempts, and limited Elsevier, SerpAPI, and Tavily to 24
attempts each. Do not rewrite those receipts or reinterpret those ceilings as
the active policy.

The active additive PRP-10 campaign has no fixed transport-attempt ceiling;
`transport_attempt_limit=None`, and request count is an observed metric rather
than a target or stopping rule. Before every initial request or retry, bind it
to a registered unique hypothesis/case ID, one changed factor, comparator, expected outcome,
deterministic oracle, source/prompt/tool/configuration hashes, and why the case
is not a duplicate. A retry retains that case ID and adds its attempt ID,
non-secret error class, and deterministic retry reason. Reject meaningless
repetition and quota-burning calls.
Continue only while a unique, testable hypothesis remains and stop on current
account quota exhaustion, credential revocation, or a safety red line. Never
top up, evade quota exhaustion through another provider, or broaden a
literature credential into model or execution authority.

Use `AdaptiveNetworkBudgetV1` to bound concurrency, per-request context and
output tokens, task wall time, permitted provider/endpoint/purpose, credential
lease scope, and secret redaction. Start independent DeepSeek paper work at
concurrency one and increase only from observed rate-limit evidence, never
above four. Permit at most one concurrent request per literature provider.
Classify explicit insufficient balance as `quota_exhausted`, 401 as
`credential_invalid`, Elsevier 403 as `entitlement_denied`, 429 according to
`Retry-After`, and timeout/5xx through wall-time-bounded exponential backoff.
Do not route a failed purpose to another provider as a credential workaround.

Elsevier, SerpAPI, and Tavily may acquire or locate full text, Supporting
Information, datasets, code, and cited protocols for a paper-source
bundle. Search snippets alone are discovery evidence, not support for a
scientific setting. Preserve licensed full text only in a private evidence
store; commit only permitted metadata, locators, hashes, and claim mappings.

## Agent architecture

- Keep provider-specific wire protocols and continuation state inside adapters.
  Persist only observable actions, concise public summaries, tool calls,
  artifacts, approvals, and outcomes. Never request, store, or use hidden
  chain-of-thought as scientific evidence.
- A provider may use private thinking during an uninterrupted turn. Replay any
  provider-required reasoning only in ephemeral adapter history and strip it
  from public history, SessionState, logs, training records, and evidence. On a
  pause or restart, begin from a deterministic public recap or fail closed;
  never persist hidden reasoning to make continuation work.
- Keep scientific expertise in versioned `DomainKnowledgePack` artifacts, not
  persona lore. Every pack declares domain and engine/version scope, source
  locators and hashes, allowed settings, prohibited conditions, stable rule
  IDs, and deterministic validator IDs. A pack cannot approve or execute work.
- Treat `PaperSourceBundle`, `ProtocolClaim`, `MolecularSystemSpec`,
  `ProjectConfigSpec`, and `PaperResearchPlan` as the canonical full-paper
  state. Keep plan state separate from execution state and make a CLI
  capability gap an explicit content-addressed blocker.
- Require an independently declared, source-bundle-bound
  `RequiredProtocolCoverage` before an advanced paper plan can pass. Validate
  that every required source kind resolves to retrieved content with a
  positive byte size; a metadata-only record never satisfies full-text or SI
  coverage. Validate
  the actual plan, scientific tasks, command workflows, project YAML, loader
  observations, previews, and review packets—not caller-supplied digest
  strings. A runtime validation event must embed enough typed material to
  deterministically reproduce its status and rule IDs.
- Keep `H0`, `HC`, `HA`, and `HK` as experimental orchestration profiles over
  one scientific kernel. Admit a provider/profile pair only through an observed
  `ProviderConformanceReceipt`; provider claims and opaque continuation state
  are not scientific evidence.
- Run adaptive ablations on a separate experiment plane. Independently version
  and record ten switches: task decomposition, specialist roles, evidence
  retrieval, domain-knowledge packs, structured documentation, independent
  critic, adversarial cross-examination, bounded repair, command-DAG planning,
  and deterministic feedback. Retain a single-agent baseline. Permission,
  schema validation, artifact hashing, secret redaction, deterministic safety
  validation, and the native-input/engine/HPC prohibitions stay enabled in
  every condition and are not experimental factors.
- A DeepSeek receipt obtained with thinking enabled supports only that exact
  mode. It does not establish thinking-disabled conformance or a causal benefit
  from thinking. The earlier 2026-08-01 H0 observation is stale and invalidated;
  it grants no current profile admission.
- Expose the frontier calculation-preparation surface only as typed project
  operations plus synthesize, repair, inspect, and explain command workflow
  operations. Legacy molecule/settings/job/input/execution builders may remain
  in an explicit compatibility profile, but must be absent and fail closed from
  the command-compiled frontier profile.
- Treat raw legacy direct-string synthesis and compact-v8 conversion as
  baseline or migration inputs only. They are not Frontier Runtime V2
  model-surface authorities and may not bypass typed compilation, preview, or
  evidence gates.
- Let a CommandWorkflowSpec bind a workflow ID, task-spec ID, live CLI-schema
  digest, and ordered immutable command nodes. Nodes contain only trusted
  artifact IDs/hashes, project references, declared intent, dependencies,
  constraint IDs, and expected artifact classes. The compiler performs DAG checking, schema
  resolution, canonical argv rendering, safe preview, parser observation, and
  intent round-trip comparison. A structured counterexample may support at
  most two constrained repairs; it must not silently change an explicit
  program, geometry, charge, multiplicity, method, or constraint.
- Bind every repair to the immediately preceding ScientificTaskSpec and
  preflight-receipt digests. In the active command profile, a terminal success
  requires a deterministic `previewed` receipt; a model assertion, command
  string, or proposed repair is never a completion substitute.
- Give each task the smallest relevant tool surface and explicit token, tool,
  wall-time, and compute budgets.
- Use subagents only for bounded, independently verifiable work with declared
  immutable inputs, expected outputs, allowed tools, owner, and merge rule.
  One agent owns each mutable artifact.
- A specialist join must retain the exact result packets and deterministically
  recompute schema, lineage, ownership, repair-count, and aggregate-budget
  gates against the dispatched packets. A result or resource-usage digest
  asserted without the observed receipt body is not authoritative.
- For paper reconstruction, separate acquisition, method extraction, molecular
  identity, scientific workflow reconstruction, command compilation, domain
  critique, and evidence audit into typed tasks when their inputs and merge
  rules are independent. Critics receive the source bundle and candidate
  artifacts, not the producing agent's persuasive rationale.
- Emit versioned, path-free Runtime V2 research events for source freeze,
  claims, molecular/project specs, domain-knowledge bindings, specialist
  dispatch/join, preview, review, report, budget, pause/resume, and terminal
  state. Existing event logs must
  replay into an empty research projection without migration side effects.
- Use a critic as a fresh, read-only cross-examiner. A critic cannot approve,
  execute, or repair its own finding. Deterministic checks or independent
  computation arbitrate disagreements.
- End every run as complete, failed, blocked, or waiting for approval; do not
  loop indefinitely.
- A research terminal event is absorbing for the entire Runtime V2 session,
  including legacy tool and turn events. An idempotency key may replay only an
  identical session, turn, kind, and canonical payload.
- When the current CLI or scientific validator cannot express a requested
  task, return `needs_clarification` or `infeasible` with a structured reason.
  Neither state permits a native-input fallback.

## Evidence and reporting

Record stable IDs, input and output hashes, engine and environment versions,
commands, working directory, timestamps, exit status, parsed values with
units, validator outputs, approval records, and claim-to-evidence links.

Separate observation, computed result, inference, literature statement, and
unresolved uncertainty. A report, notebook, or chat summary is a rendered view
of evidence, not the evidence source. Use QCSchema-compatible records where
practical, retain native engine artifacts, and make each numerical claim
traceable to a receipt.

The active development gate is PRP-10: ten frozen papers with full text, SI,
reuse/access records, critical methods, and exact official single-frame XYZ
coordinates. Retain the six earlier domains—mechanism/TS/IRC,
transition-metal spin/ECP, excited state, conformer/noncovalent ensemble,
thermochemistry/free energy, and QM/MM/multiscale—and add one slot each for
open-shell, constrained scan, explicit cluster, and multilevel workflows. A
paper may satisfy only its preregistered slot. Freeze the harness, sources,
prompts, tools, and deterministic graders before first-pass baseline runs.

Each PRP-10 paper requires loader-valid project YAML, a canonical command DAG,
safe-preview receipts for every currently expressible node, complete
validation/analysis/failure planning, and exactly three fresh read-only reviews:
domain/paper fidelity, command/evidence integrity, and adversarial
omission/state/safety. Critics do not repair, approve, execute, or determine
readiness. The current campaign performs zero Gaussian, ORCA, xTB, or HPC
execution; its highest new-work state is `previewed`.

PRP-6 and the seven-paper public pilot remain historical predecessor designs.
Their `6/6 paper_complete_pass@1` and 128/24 campaign records must remain
referenceable, but they are superseded as the active development target and
must not be relabeled as PRP-10 evidence.

## Project-local skills

Use the smallest matching skill set:

- `chemsmart-agent-harness` for provider adapters, tool loops, permissions,
  Runtime V2, task graphs, and harness evaluation;
- `chemsmart-scientific-workflow` for Gaussian, ORCA, and xTB task intake,
  preflight, execution, and physical validation;
- `chemsmart-evidence-audit` for provenance, claims, citations, reports,
  red-teaming, and evaluation.

## Validation and reporting discipline

- During a milestone, prefer source inspection, schema/receipt checks, and
  narrowly scoped deterministic probes. Do not repeatedly run pytest, Ruff, or
  broad checks after each edit. Run one focused suite when a material milestone
  is complete; allow at most one evidence-driven rerun for that milestone.
- Run full agent tests, read-only Ruff, schema/link/citation/secret checks, and
  diff checks only at the preregistered integration/freeze gate. Do not
  autofix, format, or regenerate snapshots unless separately authorized.
- Keep product, runtime, scientific, and release readiness separate. A focused
  green check is not proof of product or scientific readiness.
- Report green checks, blockers, retired metrics, and unverified claims
  separately.
- Preserve backward replay of existing runtime events when evolving the agent;
  extend the current Runtime V2 nucleus instead of introducing a competing
  runtime.
- Active adaptive network packets require explicit concurrency, per-request
  token, wall-time, provider/endpoint/purpose, and credential-lease bounds.
  They do not require a campaign-wide request-count ceiling. A valid credential
  does not grant unbounded targets, billing authority, or permission to make a
  request without a unique hypothesis and deterministic oracle.
