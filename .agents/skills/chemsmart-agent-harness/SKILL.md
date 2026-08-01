---
name: chemsmart-agent-harness
description: Design, audit, test, or document ChemSmart's provider-neutral command-compiled agent harness, including adaptive API campaigns, PRP-10 paper-to-research-plan task graphs, typed CommandWorkflowSpec proposals, CLI-schema grounding, deterministic compilation and safe preview, provider adapters and private thinking continuation, tool exposure, permissions, Runtime V2, bounded specialist and critic agents, and ablation evaluation. Use when changing or assessing chemsmart/agent runtime, provider, loop, registry, permission, paper-to-workflow orchestration, command synthesis, or agent-architecture behavior.
---

# ChemSmart Agent Harness

Use this skill to keep the agent loop auditable, bounded, and independent of a
single model provider. Read `AGENTS.md` first; it supplies repository-wide
authority, safety, and evidence rules.

## Working procedure

1. Inspect the active branch, dirty state, affected runtime contracts, and
   focused tests before proposing a change.
2. Convert a model proposal into typed ScientificTaskSpec and
   CommandWorkflowSpec data. Derive command and option behavior from the live
   Click schema, never a copied command list. Preserve the existing CLI
   contract unless the task explicitly changes it.
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
7. For a full-paper task, split acquisition, extraction, scientific
   reconstruction, command compilation, and independent review only through
   typed packets. Require every worker output to label explicit, derived,
   inferred, unknown, and conflicting facts with source locators.
   Derived facts require content-addressed deterministic derivation receipts;
   critical `not_applicable` facts require applicability receipts.
   A critical inferred, unknown, or conflicting setting ends as
   `blocked_missing_evidence`; do not contact authors or invent an unreported
   sensitivity calculation to close the gap.
8. During implementation, use source inspection and deterministic receipts.
   Run one focused runtime, permission, registry, or CLI-schema suite only
   after a material milestone; allow one evidence-driven rerun. Reserve broad
   suites and read-only lint for the declared integration freeze.
9. For the active PRP-10 adaptive campaign, bind every request or retry to a
   registered unique hypothesis/case ID, one changed factor, comparator,
   expected outcome, deterministic oracle, source/prompt/tool/configuration
   hashes, and novelty rationale. A retry keeps the case ID and records its
   attempt ID, error class, and reason. Request count is observed, not a stopping cap. Stop only
   when current quota is exhausted, no unique verifiable hypothesis remains, a
   credential is revoked, or a safety red line is reached. Never top up,
   duplicate calls to burn quota, or bypass a provider failure with another
   credential.
10. Bound adaptive network work by concurrency, per-request context/output
    tokens, task wall time, allowed provider/endpoint/purpose, and a one-request
    secret-redacted credential lease. Start DeepSeek concurrency at one and
    increase from observed rate-limit evidence only, never above four. Permit
    one concurrent request per literature provider.

## Scientific settings and knowledge surface

Treat `ScientificSettingsRegistryV1` as a read-only capability surface, not as
scientific advice. Its active basis source is the frozen BSE 0.11 catalog: 748
BSE names are serialized for all declared elements for Gaussian and the same
748 for ORCA. Upstream BSE 0.12 is reference-only. The queryable ORCA inventory
may additionally contain exact literals from the frozen ORCA-native overlay;
that overlay does not claim BSE membership or engine execution. xTB
`method.basis` returns `not_applicable`.

Only a canonical literal or registered alias may be `exact_registered`.
Fuzzy discovery is `candidate_only`, and an unrecognized value is
`unknown_unverified`; both fail closed and block a settings-validation receipt.
Do not let the model choose a fuzzy suggestion, substitute an ORCA-native
basis, or turn registry availability into chemical suitability.

Route `DomainKnowledgePack` activation deterministically from a
content-addressed host request. Bind the selected and excluded packs, trigger
rule IDs, exact source-ledger digest, critical missing-fact IDs, and the
separate model-exposure decision. Packs are read-only and may detect, preserve,
explain, or block; they cannot fill a missing paper fact, approve, repair,
execute, set readiness, or author native input.

Evaluate model-visible settings (`S`) and knowledge (`K`) with the four-arm
development block `S0K0`, `S1K0`, `S0K1`, and `S1K1`. Keep the host registry,
loaders, validators, permissions, hashes, and no-engine boundary active in all
arms. Freeze DeepSeek V4 Flash with thinking enabled and inspect only the
sanitized English response and public tool trace. Score exact-setting
preservation, honest blocking, and deterministic outcomes; do not score
fluency or provider completion as scientific success.

## Command-compiled boundary

The model may return a JSON CommandWorkflowSpec or a bounded repair proposal.
It must not return a shell command for execution, native Gaussian/ORCA/xTB
input text, arbitrary filesystem paths, shell operators, redirections,
environment assignments, option aliases, or quoting decisions.

The deterministic compiler owns this sequence:

1. validate the immutable command DAG and budget;
2. resolve the live Click path and option scope;
3. resolve trusted project and ArtifactBinding identifiers and hashes;
4. render canonical long-flag argv and a display string;
5. run the safe fake/test CLI preview;
6. obtain an independent parser observation and compare semantic intent;
7. persist a CommandPreflightReceipt with schema, project, input, environment,
   preview-artifact, and counterexample references.

Expose only workspace/project operations plus synthesize, repair, inspect, and
explain command-workflow tools to the frontier profile. Keep legacy
molecule/settings/job/input/execution builders in an explicit
`harness_jobs` compatibility profile only; absent tools must fail closed.
Raw direct-string synthesis and compact-v8 conversion are baseline/migration
inputs, not a Frontier Runtime V2 model surface or a way around typed
compilation.
Limit repair to two structured counterexamples and reject any repair that
changes an explicit program, geometry, charge, multiplicity, method, or
constraint.

## Required boundaries

- Do not make a model assertion, a valid command, or a successful tool call a
  scientific pass condition.
- Do not make a direct-string baseline, a compact-v8 compatibility adapter, or
  a legacy job-builder fallback the command authority. They are migration or
  evaluation inputs only.
- Do not persist hidden reasoning. Preserve provider continuation state only as
  opaque protocol state, never as evidence.
- Permit provider thinking only when required reasoning is replayed inside the
  uninterrupted in-memory tool loop and removed from every public or persisted
  artifact. Restart from a public recap after pause/resume. Treat a
  thinking-enabled receipt as evidence for that exact mode only; do not infer
  thinking-disabled conformance or a performance benefit from thinking.
- Do not let a planner, worker, or critic approve its own high-risk action.
- Do not enable autonomous execution, dynamic delegation, or a new provider
  protocol without a frozen single-agent baseline and an explicit evaluation.
- Keep H0, HC, HA, and HK as preregistered experiments over the same scientific
  kernel. Require an observed ProviderConformanceReceipt before enabling a
  provider/profile pair; choose the smallest safe non-inferior profile. A stale
  or invalidated observation grants no admission.
- Keep the ten PRP-10 experiment switches independently versioned: task
  decomposition, specialist roles, evidence retrieval, domain packs,
  structured documentation, independent critic, adversarial
  cross-examination, bounded repair, command DAG, and deterministic feedback.
  Never switch off permission, schema, artifact-hash, secret, native-input,
  engine, or HPC safety controls.
- Keep `two-frontier-s0-2026-08-01` and its 128/24 transport ceilings as frozen
  historical v1 evidence. Do not apply those caps to the additive adaptive
  campaign or rewrite its receipts.

## Use the references

- Read [runtime-contract.md](references/runtime-contract.md) before adding
  contracts, command workflow payloads, events, task graphs, provider
  capability fields, or replay logic.
- Read [approval-and-evaluation.md](references/approval-and-evaluation.md)
  before changing permissions, dispatch, budgets, or benchmark gates.
- Use the [source ledger](../../../docs/research/general-chemistry-knowledge-source-ledger.json),
  [BibTeX](../../../docs/research/general-chemistry-knowledge.bib), and
  [citation audit](../../../docs/research/general-chemistry-citation-audit.json)
  for the knowledge foundation's pinned provenance. These artifacts do not
  establish paper-level full-text scientific verification.
- Follow the [English knowledge-foundation milestones and Goal commands](../../../docs/goals/general-chemistry-knowledge/README.md)
  for the staged `ScientificSettingsRegistry`, `DomainKnowledgePack`, and
  `S x K` experiment work.

## Examples

Use this skill for: “compile a typed ORCA command workflow through the live
schema,” “decompose a full paper into typed research-plan tasks,” “add an
approval-bound task-graph event,” “audit whether a provider adapter leaks
reasoning state,” or “design a bounded subagent experiment.”

Do not use this skill to let a model hand-author a .com, .gjf, or .inp file,
to select a quantum-chemistry method without scientific review, to validate a
frequency calculation, or to publish a result. Combine it with
`chemsmart-scientific-workflow` or `chemsmart-evidence-audit` when appropriate.
