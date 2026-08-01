# Paper Research Plan v1

## Purpose

This contract defines ChemSmart's paper-to-research-plan boundary. Given a
legally accessible article, Supporting Information, and associated artifacts,
the agent reconstructs the reported computational work as evidence-addressed
scientific state, validated project YAML files, and a canonical ChemSmart
command DAG. It does not author or repair Gaussian, ORCA, or xTB native input.

The plan and the run are different objects. A complete plan may be produced
without executing a chemistry engine. A paper-faithful plan cannot be called
ready when a critical fact is inferred, unknown, or conflicting.

## Lifecycle

```text
full paper/SI ingest
  -> source bundle freeze
  -> computational claim coverage graph
  -> molecular and electronic-state graph
  -> project-setting signatures
  -> deterministic YAML render/load/validate
  -> typed ChemSmart command DAG
  -> live-schema compilation and safe preview
  -> domain, command/evidence, and adversarial review
  -> reproducible research-plan package
  -> exact per-command approval
  -> isolated execution
  -> deterministic scientific validation
  -> evidence-driven replan and report
```

ChemSmart must not contact paper authors and must not add, propose, or execute
an unreported sensitivity calculation. If the paper itself reports a
sensitivity calculation, represent it as a sourced workflow node. Otherwise a
missing critical setting produces `blocked_missing_evidence`.

## Versioned contracts

### `PaperSourceBundle`

Bind `bundle_id`, `paper_id`, canonical DOI/version identifier, title, declared
scientific domain, required artifact kinds, and content-addressed
`SourceArtifact` records. Source kinds include main text, SI, table, figure,
geometry, dataset, code, cited protocol, and software manual. Each artifact
records media type, legal-access class, locator,
content hash, byte size, retrieval-receipt ID, license when known, and source
lineage. A bundle digest is computed from canonical JSON. Search snippets are
discovery records, never scientific evidence. The declared domain must agree
with the benchmark registry and a matching `DomainKnowledgePack`; it is not
scientific evidence by itself.

Model-selected evidence is an opaque artifact ID, the exact registered document
SHA-256, and one or more sorted, non-overlapping line/column spans. The host resolves
those spans from its private source registry and records a digest for each span
and for their ordered aggregate. A model-authored quotation or paraphrase is
never upgraded to an `explicit` claim merely because it is passed to an
extractor.

### `ProtocolClaim`

Bind `claim_id`, field path, typed value, unit, criticality, source locators,
alternatives, deterministic derivation, and public rationale. Use exactly one
epistemic state:

- `explicit`: directly stated at a stable source locator;
- `derived`: produced by a deterministic documented transformation;
- `inferred`: a candidate not stated by the source;
- `unknown`: required but unavailable;
- `conflict`: authoritative sources disagree;
- `not_applicable`: the field does not apply.

Do not record model confidence as readiness evidence. A critical `inferred`,
`unknown`, or `conflict` claim blocks paper-faithful execution readiness.
`derived` values require a content-addressed deterministic derivation receipt;
a critical `not_applicable` decision requires a content-addressed
applicability receipt. Both receipts bind source artifact hashes and a stable
validator rule.

### `RequiredProtocolCoverage`

An advanced plan binds an independently produced coverage contract for the
exact source-bundle digest. It declares required source kinds, critical field
paths and units, molecular systems, project records, and workflows. The plan
producer and coverage declarer must be distinct. This prevents the planner
from defining completeness merely by omitting a field from its own claim list;
it does not replace the external custodian and expert gold process for PRP-6.
Each required source kind must bind retrieved, non-empty content. A public
metadata record or discovery snippet is not full-text, SI, geometry, or data
coverage.

### `MolecularSystemSpec`

Bind each species, conformer, fragment, and electronic state to exact atom
count, atom-order and geometry-frame hashes. Record units, charge,
multiplicity, fragment atom indices, constraints, and claim IDs. Record
stereochemistry, parent/region mapping, and other provenance as explicit typed
claims and constraint artifacts when applicable. A filename or figure label
alone is not molecular identity.

### `ProjectConfigSpec`

Bind program/version, the canonical method plus claim-bound additional method
settings, basis/ECP mapping, dispersion, solvent, grids, convergence,
temperature, standard state, and reusable engine settings to their
`ProtocolClaim` IDs. `CommandWorkflowBinding.project_ids` records consumers,
while resource targets remain on command nodes. Nodes sharing one canonical
settings signature reuse one content-addressed project YAML and loader receipt.

Gaussian and ORCA projects contain method settings. xTB projects may contain
reusable GFN, optimization, and solvation settings. Molecule-specific charge
and multiplicity remain on each command node. Auxiliary CLI operations that do
not use a project record `not_applicable` rather than a fabricated YAML.
Every xTB job family consumed by a workflow requires an explicit YAML block;
loader defaults for an absent `sp`, `opt`, or `hess` block are not paper
evidence. Paper-mode rendering does not fill an unstated basis, frequency
policy, solvent pair, or mixed-basis mapping.

### `PaperResearchPlan`

Bind source, claim, molecular-system, project, command-workflow,
`DomainKnowledgePack`, validation, analysis, three role-specific green review,
and report digests. Track `plan_state` independently from
`execution_state`:

- plan: `drafting | blocked_missing_evidence | blocked_capability_gap | planned |
  previewed | validated | failed`;
- execution: `not_started | waiting_for_approval | running | executed | blocked |
  failed | validated | reproduced`.

Plan-level `validated` requires loader-validated YAML, compilable commands,
safe-preview receipts, complete dependencies, and green domain,
command/evidence, and adversarial review receipts. It never implies execution.

`ScientificTaskSpec.required_evidence` names preflight evidence classes only.
`post_execution_validation_obligations` separately records checks such as
optimization convergence and transition-state frequency classification. A
preview may preserve those obligations but reports them as `pending_execution`;
only bound engine output and a deterministic validator can satisfy them.

`PaperResearchValidationContext` carries the actual ScientificTaskSpec,
CommandWorkflowSpec, exact YAML/loader records, preview receipts, independent
coverage contract, and review receipts consumed by validation. Each receipt is
content addressed and cross-checked against a fresh deterministic observation.
An arbitrary digest-shaped string cannot substitute for a receipt body.

`build_paper_artifact_layout()` deterministically maps the immutable plan to
relative `papers/<paper>/<plan>/` records for sources, claims, systems,
projects, workflows, knowledge bindings, graphs, reviews, and a derived report
view. Source records contain private locators and raw-content hashes; they do
not copy licensed full text into Git. Markdown remains a non-evidentiary view.

### Specialist and review packets

`SpecialistTaskPacket` carries immutable input references, role, objective,
source scope, allowed tools, budget, output schema, single write owner,
completion predicate, and merge key. `SpecialistResultPacket` returns only
typed claims, artifacts, capability gaps, findings, resource use, and terminal
state. It cannot return executable shell or native input.
The join event retains exact result packets and recomputes lineage, schema,
ownership, observed repair count, and family-wide resource use from the
dispatched packets. Partial-family joins and self-asserted validation hashes
fail closed.

`ReviewPacket` binds frozen candidate digests. A `ReviewFinding` contains
severity, rule ID, target, evidence, expected/observed value, and disposition.
Critics are read-only and cannot repair, approve, execute, or close their own
finding. Deterministic checks or an independent domain decision arbitrate.

### Provider and harness state

`ProviderCapabilities` records observed wire/tool/continuation behavior.
`HarnessProfile` is one of `H0`, `HC`, `HA`, or `HK` and changes orchestration,
not scientific semantics. `ProviderConformanceReceipt` records the probe,
model ID, schema digest, budget, and pass/fail observations. `ProviderStateRef`
is opaque, adapter-owned, and explicitly non-evidentiary. Hidden reasoning is
not persisted in events, evidence, or training data.

### `DomainKnowledgePack`

Bind computational-science rules to a semantic pack version, declared domain,
engine/version scope, source locators and hashes, allowed setting paths,
prohibited-condition IDs, stable rule IDs, and deterministic validator IDs.
The pack can detect or block a proposal but cannot supply an omitted paper
fact, approve execution, or become evidence merely because a model selected it.

## Coordination and ownership

Parallelize only independently verifiable source regions, species branches,
project candidates, or audit tasks. The coordinator alone owns the canonical
molecular identity graph, electronic state, project signatures, and final
command DAG. Joins must verify input digests, ownership, budgets, result schema,
dependency completeness, and non-conflicting merge keys.

The three required reviews are:

1. domain review for chemical adequacy and paper fidelity;
2. command/evidence review for YAML, schema, artifacts, units, and previews;
3. adversarial review for omissions, silent defaults, state drift, approval
   reuse, and false readiness.

## Evidence package

The canonical package contains source and geometry hashes, project YAML and
loader summaries, `ScientificTaskSpec`, `CommandWorkflowSpec`, canonical argv,
safe-preview receipts, ChemSmart-generated inputs, native outputs when run,
environment/executable versions, approvals, validator results, claims,
citations, reviews, and an RO-Crate-compatible manifest. QCSchema-compatible
records are preferred where they retain engine-specific settings. Markdown,
HTML, notebooks, and chat are regenerated views, not evidence sources.

## Capability gaps

If the live CLI cannot express a required paper step, emit a typed capability
gap with source claim, required semantics, closest command family, missing
compiler/validator capability, and affected plan nodes. A separately reviewed
development milestone may add a typed CLI command, compiler mapping, preview,
parser, and tests. Runtime self-modification and native-input fallback are
forbidden.

The first command-compiled scientific slice is limited to one root XYZ frame
and the currently validated Gaussian/ORCA/xTB job families. A
producer-to-consumer geometry handoff remains infeasible until an upstream
artifact receipt supplies the downstream ordered-geometry digest. Gaussian
`gen`/`genecp` likewise remains blocked at command-preview readiness until an
element-resolved basis/ECP validator is connected, even when a paper project
record preserves the proposed mapping.

## PRP-6 acceptance

Before PRP-6, the public development pilot uses exactly seven distinct source
slots: one user experimental paper and six public source-complete controls, one
per domain below. At this snapshot the user paper is
`blocked_missing_source`; no control IDs are fixed and control selection and
acquisition are pending. The pilot exercises development and ablation paths
but is not held-out, sealed PRP-6 evidence.

Use exactly one held-out, source-complete paper from each domain:

1. organic reaction mechanism, TS, IRC, and kinetics;
2. transition-metal/organometallic spin states and basis/ECP;
3. excited-state photochemistry or spectroscopy;
4. conformer, noncovalent, and solvent ensemble;
5. thermochemistry, free energy, and standard state; and
6. QM/MM or layered multiscale workflow.

Two independent experts plus adjudication create hidden gold claims and
workflow coverage.

Each paper passes only with 100% calculation-step, species, state, analysis,
and dependency coverage; 100% critical setting/source-locator agreement;
loader-valid, semantically matched project YAML; canonical commands and safe
semantic previews for every expressible node; generated-input agreement for
geometry, charge, multiplicity, method, basis/ECP, solvent, and job semantics;
complete artifact-hash handoff; a full ordered execution, validation, analysis,
and failure plan; zero fabricated facts, false readiness, native-input bypass,
approval bypass, or artifact mutation; and no unresolved critical finding from
domain, command/evidence, or adversarial review. The engineering gate is
`6/6 paper_complete_pass@1`; it is not by itself a statistical SOTA claim.
