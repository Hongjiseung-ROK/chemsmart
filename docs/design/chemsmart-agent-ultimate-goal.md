# ChemSmart Frontier Agent: Ultimate Goal

## Mission

ChemSmart is a CLI-first, provider-neutral computational-chemistry research
agent. Its target is to convert a full paper and Supporting Information into a
scientifically faithful, reproducible research plan: evidence-addressed facts,
exact molecular states, validated project YAML files, a canonical ChemSmart
command DAG, generated preview inputs, validation/analysis steps, and an
evidence-bound report. Real execution proceeds only command by command after
exact approval.

The agent behaves as a transparent computational-chemistry collaborator. It
states what is known, derived, inferred, conflicting, or unknown; treats failed
gates as useful evidence; and consults bounded specialist and review agents.
Persona is not scientific authority. Versioned knowledge packs, source claims,
loaders, compilers, and validators are.

The canonical contract is [Paper Research Plan v1](paper-research-plan-v1.md).
The additive knowledge-foundation phases and copyable English Goal commands are
indexed in the [General Chemistry Knowledge Program](../goals/general-chemistry-knowledge/README.md).
Its pinned provenance is recorded in the
[source ledger](../research/general-chemistry-knowledge-source-ledger.json),
[BibTeX](../research/general-chemistry-knowledge.bib), and
[citation audit](../research/general-chemistry-citation-audit.json).

## Target lifecycle

```text
paper and SI
  -> PaperSourceBundle
  -> ProtocolClaim and MolecularSystemSpec graphs
  -> ProjectConfigSpec and validated project YAML
  -> ScientificTaskSpec and CommandWorkflowSpec DAG
  -> live-schema compilation and safe preview
  -> independent reviews
  -> complete research-plan package
  -> per-command approval and isolated execution
  -> deterministic validation, evidence-driven replan, and report
```

The model never writes or edits Gaussian, ORCA, or xTB native input. It proposes
typed scientific and command intent. ChemSmart owns CLI semantics, project
loading, artifact resolution, canonical argv, safe preview, permissions,
execution receipts, scientific validation, and terminal state.

The active PRP-10 campaign stops at safe preview. It invokes no Gaussian,
ORCA, xTB, scheduler, or HPC execution. A paper is eligible only when an
official source supplies an exact single-frame XYZ in angstrom. The import
receipt binds the source/archive member, source and imported-byte hashes, atom
order, identity approval, and access/license record. Coordinate-table
transcription, OCR, SMILES-to-3D, and model-generated or model-repaired
coordinates are forbidden. SDF/MOL/PDB conversion remains a separate general
input feature and cannot establish PRP-10 eligibility.

For paper-derived facts, a model may select only content-addressed source spans.
It cannot submit prose as its own evidence excerpt. The host resolves exact
registered document bytes and line/column spans, verifies their hashes, and only then
passes those bytes to a deterministic extractor. Non-contiguous facts such as a
functional, basis, integration grid, and frequency criterion remain separate
source spans with separate digests.

For command synthesis, the coordinator supplies the IR skeleton and immutable
workspace bindings. The model fills bounded scientific choices and typed slots;
it does not reconstruct the entire object shape from memory. This division is
an experimentally motivated harness rule, not a claim that the model lacks
scientific reasoning ability.

## Two-frontier architecture

### Computational-chemistry frontier

Adopt domain decomposition and traceable artifacts from El Agente Q as a
benchmark, not its model-authored native input boundary. Adopt ChemGraph-style
decomposition only when calculations are scientifically independent and a
deterministic merge checks species identity, stoichiometry, units, and hashes.
Use an ACRA-style critic only as a detector paired with deterministic
validation. Use QCSchema, AiiDA provenance, and Workflow Run RO-Crate as record
and packaging references.

Scientific rules live in versioned `DomainKnowledgePack` records with scope,
engine/version, literature provenance, rule IDs, allowed combinations,
prohibited conditions, and validators. They are not unstated prompt lore.

### Scientific settings and sourced-knowledge foundation

`ScientificSettingsRegistryV1` separates representability from scientific
judgment. Its active source snapshot uses the checked-in Basis Set Exchange
0.11 catalog. That catalog records 748 BSE names with all declared elements
serialized for Gaussian and the same 748 for ORCA. Upstream BSE 0.12 is a
pinned migration/reference source only. It cannot redefine the active catalog
until deterministic regeneration, drift review, and focused validation are
completed.

The ORCA setting surface is the union of the BSE-backed catalog and a frozen
ORCA-native exact-literal overlay. An ORCA-native resolution preserves a
program-scoped literal without claiming BSE membership, safe preview, engine
acceptance, combination compatibility, or scientific adequacy. For xTB,
`method.basis` is explicitly `not_applicable`. Canonical literals and
registered aliases may resolve `exact_registered`; fuzzy matches remain
`candidate_only`, and unmatched values remain `unknown_unverified`. The latter
two block the settings receipt and can never be promoted by model confidence.

A `DomainKnowledgePack` is activated by deterministic host routing over a
content-addressed domain/program/version/task request. The receipt records
positive and negative triggers, selected and excluded packs, exact source
ledger/catalog hashes, critical missing facts, and whether read-only model
exposure was requested. The pack may preserve, detect, explain, or prohibit a
scoped setting. It cannot supply a missing paper fact, convert epistemic
status, approve, repair, execute, set readiness, or author native input.

The knowledge source ledger and citation audit verify revisions, licenses,
reviewed resources, and bibliographic metadata within their declared evidence
ceilings. They do not establish that the full text of every cited article has
been scientifically verified. A paper reproduction plan still requires its
own full `PaperSourceBundle`, exact content hashes, and claim locators.

### General-agent frontier

Keep one scientific semantic kernel and separate provider-native envelopes.
The common kernel owns tasks, artifacts, claims, events, approvals, budgets,
reviews, and terminal states. Adapters preserve native tool and continuation
semantics without flattening provider state into prose:

- Codex-derived profile: replayable observe-act-verify loop, sandbox,
  approvals, stable instructions/tools, and validator feedback;
- Claude-derived profile: progressive skills, fresh specialist contexts,
  deterministic hooks, compaction, and structured handoff;
- Kimi-derived profile: explicit goals/budgets, persistent checkpoints,
  fork/resume, and verifier-oriented long-horizon operation.

No public evidence establishes one exact harness as native to every frontier
model. `ProviderConformanceReceipt` therefore records observed behavior, and a
controlled crossover chooses the smallest safe non-inferior profile.

## Additive public contracts

The design extends Runtime V2 rather than introducing another orchestrator.
Every additive event change must prove that frozen legacy logs replay
unchanged before it can be called integrated.

| Contract | Purpose |
| --- | --- |
| `PaperSourceBundle` / `SourceArtifact` | Freeze legally accessible paper, SI, data, code, geometry, protocol, and manual sources by hash. |
| `RequiredProtocolCoverage` | Independently declare source and critical-field completeness for the exact bundle so the planner cannot self-define coverage. |
| `ProtocolClaim` | Bind typed values and units to source locators and epistemic status. |
| `MolecularSystemSpec` | Preserve exact species, geometry, atom order, charge, multiplicity, fragments, and constraints. |
| `ProjectConfigSpec` | Bind reusable method settings and claim provenance to validated project YAML. |
| `ScientificSettingsRegistryV1` / `SettingResolutionV1` | Resolve frozen-source setting capability as exact, candidate-only, unknown, or incompatible without making a scientific recommendation. |
| `DomainKnowledgePack` | Externalize sourced domain and engine/version rules with deterministic validators. |
| `KnowledgePackActivationRequestV1` / `KnowledgePackActivationReceiptV1` | Route read-only packs deterministically and record scope, provenance, exclusions, missing facts, and model exposure. |
| `PaperResearchPlan` | Bind source, science, project, command, validation, analysis, review, and report graphs with separate plan/run states. |
| `SpecialistTaskPacket` / `SpecialistResultPacket` | Bound delegation by immutable input, tools, budget, owner, schema, and merge key. |
| `ReviewPacket` / `ReviewFinding` | Provide read-only, evidence-addressed cross-examination. |
| `ProviderCapabilities` / `HarnessProfile` / `ProviderConformanceReceipt` | Separate observed wire capabilities from orchestration profiles. |
| `ProviderStateRef` | Refer opaquely to adapter continuation state; never scientific evidence. |

Add research-stage events for source freeze, claim recording, system/project
specification, task dispatch/join, command preview, review, report, budget,
pause/resume, and terminal state. Each new payload is versioned and path-free
where public.
Advanced validation events retain the typed plan/context and exact specialist
result packets required to reproduce status and merge decisions. Hash-only
success assertions are rejected, and a terminal event absorbs all subsequent
events in that session.

## Scientific and approval boundaries

For every calculation preserve molecule identity, exact geometry and units,
charge, multiplicity, state assumptions, method, basis/ECP, dispersion,
solvent, constraints, program/version, temperature/standard state, resources,
expected artifacts, and validators. Search snippets locate sources but cannot
support these values.

A critical `inferred`, `unknown`, or `conflict` claim blocks paper-faithful
readiness. ChemSmart must not contact paper authors and must not add, propose,
or execute an unreported sensitivity calculation. A calculation explicitly
reported by the paper remains an ordinary sourced workflow node. A CLI
capability gap becomes a typed, separately reviewed development task; it never
triggers native-input fallback or runtime code generation.

Approval binds exact scientific spec, canonical argv, project/input hashes,
environment/executable, execution target, and resource budget. Any change
invalidates it. Critics, workers, and planners cannot approve or repair their
own findings.

## Harness profiles and experiments

Use DeepSeek V4 Flash for the active model-development pilot and preserve its
thinking/tool continuation only in ephemeral adapter state. Sandboxed tools,
approval pause, and deterministic validator feedback are enabled in every
profile. The cumulative profile matrix is fixed:

| Profile | Public event replay | Skills, fresh specialists, hooks, handoff, compaction | Persistent goal, checkpoint/fork/resume | Delegation depth |
| --- | --- | --- | --- | ---: |
| `H0` | no | no | no | 0 |
| `HC` | yes | no | no | 0 |
| `HA` | yes | yes | no | 1 |
| `HK` | yes | yes | yes | 2 |

Freeze model ID, prompts, skill/tool schemas, CLI schema, compiler, validators,
fixtures, budgets, and order. Select by tool-call validity, scientific fact
retention, false completion, repair count, context loss, cost, and latency.
Keep `H0` as a permanent reference path.

Grade three outcome layers independently. `agent_turn_outcome` describes only
whether the provider/tool loop ended. `tool_domain_outcome` records the literal
tool result, such as `needs_clarification` or `previewed`.
`scientific_readiness` is derived by deterministic gates and can never become
green merely because a turn ended with `completed`. Preflight evidence classes
are also distinct from post-execution scientific obligations such as
optimization convergence or exactly one imaginary frequency; a safe preview
records those obligations as pending and never as satisfied.

Campaign `two-frontier-s0-2026-08-01`, including its 128 total DeepSeek and
24-per-literature-provider transport ceilings, is frozen historical v1
evidence. Its retained H0 observation is `stale_invalidated`; neither its caps
nor its profile admission apply to the active campaign.

The additive PRP-10 campaign uses current user-owned quota without top-up or
provider bypass and has no fixed API attempt ceiling. Request count, retries,
tokens, latency, cost, and error classes are observations. Every request or
retry must first bind to a registered unique hypothesis/case ID, one changed factor,
comparator, expected outcome, deterministic oracle,
source/prompt/tool/configuration hashes, and novelty rationale. Continue only
while unique verifiable hypotheses remain; terminate on quota exhaustion,
credential revocation, or a safety red line. `AdaptiveNetworkBudgetV1` limits
concurrency, per-request context/output tokens, task wall time, exact
provider/endpoint/purpose, lease scope, and secret handling. DeepSeek starts at
concurrency one and may adapt from observed rate limits to at most four;
literature providers remain at one concurrent request each.

Run ten independently versioned switches on a separate experiment plane: task
decomposition, specialist roles, evidence retrieval, domain-knowledge packs,
structured documentation, independent critic, adversarial cross-examination,
bounded repair, command-DAG planning, and deterministic feedback. Permission,
schema, artifact-hash, secret, native-input, engine, HPC, and deterministic
safety gates remain on. The historical D/E/C `2 x 2 x 2` study remains a
reference projection rather than the complete active plane.

Before using settings or knowledge exposure as a development default, run the
paired `S x K` four-arm experiment:

| Arm | Model-visible settings registry | Model-visible domain packs |
| --- | --- | --- |
| `S0K0` | no | no |
| `S1K0` | yes | no |
| `S0K1` | no | yes, with host-only registry resolution |
| `S1K1` | yes | yes |

All four arms retain the same deterministic registry, project loaders,
compiler, validators, permissions, artifact hashes, and no-native-input,
no-engine, and no-HPC controls. Freeze the case/source, prompt, tool surface,
order, budgets, registry/catalog and validator digests, and DeepSeek V4 Flash
thinking-enabled mode. Persist and directly inspect a sanitized English
response plus public tool trace for each arm. Grade exact-setting preservation,
honest blocking, false-ready language, and deterministic outcomes; English
quality and turn completion are not scientific metrics. This is development
evidence, not a held-out generalization, full-text verification, or SOTA claim.

## Training boundary

Do not train before paper-level gold tasks, accepted/rejected trajectories,
deterministic final-state graders, hidden fixtures, and anti-reward-hacking
tests exist. Then proceed in order:

1. SFT on verified visible successful and rejected trajectories;
2. preference pairs from valid/invalid typed actions at identical state;
3. sandbox RL scored only from artifact/receipt state;
4. honesty curricula with missing, stale, conflicting, or failed evidence;
5. randomized harness profiles and long-horizon resume tasks.

Persist visible tasks, typed actions, normalized tool calls/results, artifact
hashes, public decision summaries, budgets, approvals, grades, and terminal
outcomes. Never train on hidden chain-of-thought, raw provider state, secrets,
or licensed full text that cannot be redistributed. A model's success claim is
never its reward.

## Active PRP-10 roadmap

| Phase | Deliverable | Gate |
| --- | --- | --- |
| M0 | Reconcile 23 Runtime V2 streams and adaptive API contracts | Runtime terminal state is authoritative; turn/tool/scientific outcomes separated; historical evidence unchanged. |
| M1 | Coordinate and preview custody | Exact official single-frame XYZ receipts and private exact-byte preview hashes; missing geometry blocks. |
| M2 | Settings/knowledge foundation and independent ablation plane | Registry and read-only sourced packs remain distinct; the `S x K` block and ten switches preserve every safety invariant and the single-agent baseline. |
| M3 | Frozen PRP-10 first-pass baseline | Ten eligible papers, frozen harness/sources/prompts/tools/graders, full plans through safe preview and three reviews. |
| M4 | Defect-driven adaptive expansion | One-factor paired hypotheses are retained, revised, or retired by deterministic grades and independent cross-examination. |

PRP-10 retains the six earlier scientific domains and adds one slot each for
open-shell, constrained scan, explicit cluster, and multilevel workflows. Each
paper needs full text, SI, access/license evidence, critical methods, and exact
official XYZ. Require three fresh read-only reviews: domain/paper fidelity,
command/evidence integrity, and adversarial omission/state/safety. Critical
disagreement requires deterministic evidence or user adjudication, not majority
vote. Opening PRP-10-V1 outcomes makes those papers development data; a future
confirmatory claim requires a new lockbox.

Run one focused suite after each substantial milestone and permit at most one
evidence-driven rerun. Run broad tests, read-only lint, replay/schema,
citation/license/link/secret, and diff gates once after harness freeze. Do not
autofix or regenerate snapshots.

## Historical predecessor roadmap

The following R0-R6/PRP-6 program remains referenceable historical design. It
is superseded as the active development target and must not be relabeled as
PRP-10 evidence.

| Phase | Deliverable | Gate |
| --- | --- | --- |
| R0 | Evidence refresh, operating contract, skills, API receipts | Source class/license/training-known boundaries verified; secrets absent. |
| R1 | Paper/source/claim/system/project/plan contracts | Canonical serialization, digest stability, critical-claim blocking, legacy replay. |
| R2 | Provider capabilities and H0/HC/HA/HK profiles | DeepSeek V4 Flash conformance receipts; no private state in public evidence. |
| R3 | Specialist packets, deterministic joins, three critics | Ownership/budget/schema gates and seeded-defect detection pass. |
| R4 | xTB YAML, command DAG, six-domain capability growth | Loader and semantic preview coverage; every gap typed, no native fallback. |
| R5 | External slices, profile crossover, A0/A1 and D/E/C pilot | Preregistered paper-level metrics, fixed artifacts, conservative adoption. |
| R6 | Sealed PRP-6 and reproducibility package | `6/6 paper_complete_pass@1`, zero safety red lines; no automatic SOTA claim. |

The historical PRP-6 acceptance set contains one source-complete held-out paper in each of
six domains: organic reaction mechanism/TS/IRC/kinetics;
transition-metal/organometallic spin states and basis/ECP; excited-state
photochemistry/spectroscopy; conformer/noncovalent/solvent ensemble;
thermochemistry/free energy/standard state; and QM/MM/layered multiscale. Full
execution of all six papers is not required; execution ability is validated on
separately approved bounded slices.

The preceding historical public development pilot is a distinct seven-paper set: one
user-supplied experimental paper plus six public source-complete controls, one
per domain. No control paper IDs are currently frozen. The user paper remains
`blocked_missing_source`, and control selection/acquisition remains pending.
None of these public-development slots may be relabeled as sealed PRP-6.

The current bounded pre-R4 compiler slice is not the full R4 command-DAG gate:
it supports a single root XYZ frame and a bounded set of job families. Downstream
producer-artifact geometry handoff and element-resolved `gen`/`genecp`
verification remain explicit capability gaps until receipt-bound validators
land.
