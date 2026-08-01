# Paper-to-Research-Plan Agent Evaluation Protocol

## Status and primary endpoint

This is the preregistration contract for ChemSmart's two-frontier evaluation.
It does not authorize chemistry-engine or HPC execution. Model and literature
API calls use only the existing user-owned quota and never persist secrets.
Campaign `two-frontier-s0-2026-08-01` and its 128 total DeepSeek and
24-per-literature-provider attempt ceilings are frozen historical v1 evidence.
The active additive PRP-10 campaign sets `transport_attempt_limit=None`: call
count is an observed metric, not a target or stopping rule. Use only current
user-owned quota; never top up or route around an exhausted/failed provider.
The active campaign stops at safe preview and performs zero Gaussian, ORCA,
xTB, scheduler, or HPC execution.

The primary unit is one paper-level research plan, not an individual command
row. The primary engineering endpoint is `paper_complete_pass@1`: faithful
source coverage, valid project YAML, a canonical ChemSmart command DAG,
semantic previews, complete validation/analysis steps, and zero critical
evidence or policy defects.

## Frozen inputs

Before each study freeze model ID, provider capability receipt, harness profile,
system/developer/user instructions, skill revisions, tool schemas, CLI schema
digest, compiler and validator revisions, source/fixture digests, budgets,
task order, retry policy, graders, and dispute procedure. Raw evidence capture
is active in every condition.

Use development papers only for implementation and a separately held-out set
for adoption. Split by chemical system and workflow family, not paraphrased
prompt wording.

## Adaptive API case contract

Before every initial request or retry, bind it to a registered unique
hypothesis/case ID, one changed factor, comparator, expected outcome, deterministic oracle,
source/prompt/tool/configuration hashes, and why the case differs from prior
work. A retry keeps the case ID and adds its attempt ID, non-secret error class,
and reason. Reject meaningless repetition and quota-burning. Record requests,
retries, tokens, latency, optional cost and price basis, concurrency,
rate-limit observations, and error classes. Stop when the current account quota
is exhausted, no unique verifiable hypothesis remains, a credential is revoked,
or a safety red line occurs.

Bound each worker by maximum concurrency, per-request context/output tokens,
task wall time, exact provider/endpoint/purpose, one-request credential lease,
no-top-up, and secret-redaction rules. Start independent DeepSeek paper cases at
concurrency one and adapt only from observed rate-limit evidence, never above
four. Allow one concurrent request per literature provider. Treat explicit
insufficient balance as `quota_exhausted`, 401 as `credential_invalid`,
Elsevier 403 as `entitlement_denied`, 429 according to `Retry-After`, and
timeout/5xx with wall-time-bounded exponential backoff. Do not substitute a
different provider as a credential workaround.

## Historical public development-pilot corpus

The development pilot has exactly seven distinct source slots: the user's
current experimental paper and six public source-complete controls, one in
each PRP-6 domain. At preregistration time the user paper is
`blocked_missing_source`; no six control IDs have been fixed, and control
selection/acquisition is pending. No slot can enter scoring until its full
paper, SI, required structures/data, legal-use record, and content digests are
frozen. Substitution after freeze is an exclusion, not an invisible repair.
This public set is neither held-out nor the sealed PRP-6 corpus.

The 2026-08-01 azide–allene DeepSeek V4 Flash run is a separate aggressive
engineering slice and does not fill one of these seven frozen slots. Its source,
model, token, latency, defect, and deterministic-control evidence is recorded in
[the development-pilot report](azide-allene-deepseek-v4-flash-pilot.md). The
paper-faithful state remains blocked because charge and multiplicity are not
explicit; a separately labelled 0/1 fixture tests only command compilation.

## B0: external benchmark slices

1. Use the El Agente Q replication data's ORCA-overlap problems to compare
   problem interpretation, required-step coverage, project/command planning,
   and conservative blocking. It is a paper/data benchmark because no verified
   official reusable implementation repository exists.
2. Use ChemGraph's archived reaction-property subset to test whether
   independent species decomposition and deterministic stoichiometric
   aggregation are preserved.
3. Use Quntur data only unchanged and privately where CC BY-NC-ND permits.
   Do not adapt or redistribute it.

These slices are external validity checks, not the PRP-6 final corpus.

## B1: command-front-end comparison

Compare paired tasks:

- `A0`: direct model-generated command string, parsed but never executed;
  baseline only.
- `A1`: typed `CommandWorkflowSpec` compiled through the live schema, trusted
  project/artifact grounding, canonical rendering, safe preview, independent
  parser observation, and semantic round-trip.

A1 must achieve 100% schema-valid rendering, parser acceptance, and render
determinism; zero shell injection, hallucinated options, and model-authored
native input; intent preservation at least equal to A0; and cost no more than
1.25x unless bounded repair decreases significantly. For non-inferiority, the
lower bound of the paired bootstrap 95% confidence interval for
`A1 - A0` semantic-preview success must be at least -2 percentage points. A
repair-reduction exception requires its paired 95% interval to exclude zero in
the improving direction. Compiler authority remains a safety boundary even if
an efficacy threshold is not yet met.

## B2: harness-profile crossover

Use DeepSeek V4 Flash with identical tasks, prompts, tools, budgets, and order:

Sandboxed tools, approval pause, and deterministic validator feedback are
enabled in every profile. The cumulative matrix is fixed as follows:

| ID | Replay | HA feature bundle | Goal/checkpoint bundle | Depth |
| --- | --- | --- | --- | ---: |
| H0 | no | no | no | 0 |
| HC | yes | no | no | 0 |
| HA | yes | yes | no | 1 |
| HK | yes | yes | yes | 2 |

Measure tool-call validity, required scientific fact retention, false terminal
success, repair count, recovery after pause, context/token use, cost, and
latency. Provider-private thinking may be used only in uninterrupted adapter
state and is excluded from evidence and scoring. Thinking is frozen enabled in
this crossover; there is no thinking-disabled condition, so the study cannot
claim disabled-mode compatibility or a causal benefit from thinking. Select
the smallest profile
whose paired 95% confidence interval excludes a paper-success loss greater than
2 percentage points relative to the best safe profile and has no safety
regression. Counterbalance profile order within each task/repeat block to avoid
fixed-order and warm-cache confounding. Retain H0 permanently.

For every case record `agent_turn_outcome`, `tool_domain_outcome`, and
`scientific_readiness` separately. A loop-level `completed` value is never an
oracle. Each case declares acceptable domain outcomes before execution, and an
undeclared oracle is unscored rather than implicitly passing.

## M2: active component-ablation plane

Keep these ten versioned switches independently controllable:

1. task decomposition;
2. specialist roles;
3. evidence-window retrieval;
4. domain-knowledge packs;
5. structured documentation;
6. independent critic;
7. adversarial cross-examination;
8. bounded repair;
9. command-DAG planning;
10. deterministic feedback.

Retain the single-agent baseline. Permission, CLI-schema validation, artifact
hashing, secret redaction, deterministic safety validation, and native-input,
engine, and HPC prohibitions are invariant and cannot be disabled by an
experiment switch. Every run records switch values, model/provider, prompt and
tool-schema digests, network envelope, source/project/command hashes,
validators, repairs, failures, and terminal state.

Use one-factor paired comparisons while papers, prompts, tools, task order,
network envelope, and validators remain fixed. The earlier D/E/C `2 x 2 x 2`
factorial below is preserved as a historical projection and does not define the
entire active plane.

### Historical D/E/C projection

With the selected frozen profile, run a preregistered `2 x 2 x 2` factorial:

- `D` decomposition: one workflow agent when off; bounded specialists only for
  independently verifiable source, species, or audit branches with
  deterministic joins when on.
- `E` evidence composition: an ordinary derived summary when off; a
  schema-valid evidence manifest and deterministically regenerated plan/report
  when on.
- `C` critique: deterministic validators only when off; one fixed treatment
  bundle of exactly three fresh read-only reviews when on—domain/paper fidelity,
  command/evidence, and adversarial omission/state/safety cross-examination.
  Freeze each role's prompt, tools, order, and budget, and charge all three
  reviews to the `C=on` cost and latency totals.

No critic repairs, approves, executes, or changes terminal authority. Raw
events, commands, artifacts, approvals, and receipts remain recorded when E is
off so the factor tests composition rather than evidence deletion.

## Development task families and fault injection

Cover Gaussian, ORCA, and xTB plus auxiliary command families where relevant.
Seed hidden defects in:

- molecule/geometry identity, atom order, units, charge, multiplicity, spin;
- method, basis/ECP mapping, dispersion, solvent, constraints, state/root;
- project YAML, CLI path/options, artifact dependency/hash, stale approval;
- SCF/geometry convergence, frequency classification, standard state, units;
- missing or conflicting SI, corrected citation, fabricated source locator;
- unavailable executable, interrupted state, budget exhaustion, prompt
  injection, worker ownership conflict, and critic self-approval.

Call these `molecular-identity and electronic-state integrity faults`; do not
label them a sensitivity study. Do not reveal the seed to the evaluated agent.

## Metrics and analysis

Use deterministic graders first, two independent domain-expert rubrics second,
and LLM judges only as supplementary analysis.

- source and computational-step coverage precision/recall;
- field-level explicit/derived/inferred/unknown/conflict correctness and
  critical false-known rate;
- molecular-system, YAML loader-summary, command, DAG, artifact, and generated-
  input semantic fidelity;
- plan completeness for execution, validation, analysis, and failure handling;
- `pass@1`, bounded-repair success, false-ready and false-success;
- critic critical/overall recall, precision, and false rejection;
- approval/policy violations, artifact mutation, secret exposure;
- model calls, tokens, cost, latency, handoff loss, and context consumption;
- exact-coordinate import integrity and source/imported-byte agreement;
- unique hypotheses attempted, retained, revised, retired, and termination
  reason; request count remains observational.

Use paired repeated trials, task-level bootstrap 95% confidence intervals, and
per-family results. Pilot with at least three repeats only to estimate variance;
derive confirmatory sample size for 90% power. For a larger confirmatory cohort,
use a prespecified mixed-effects model and Holm correction. Never count command
rows from one paper as independent samples.

## Component gates

- Decomposition: at least +5 points held-out success or 20% wall-time reduction
  on eligible parallel tasks; simple-task regression at most 2 points; cost at
  most 1.5x; every join deterministic.
- Evidence composition: all manifests schema-valid, every numerical claim
  linked to evidence and units, deterministic rerendering, and no false
  completion when evidence is absent.
- Critique: at least 90% seeded-critical and 80% overall defect recall, at most
  5% false rejection, and at least 50% lower false-pass rate.
- Every configuration: zero approval bypass, fabricated evidence, native-input
  bypass, artifact mutation, secret exposure, or success while a required
  deterministic gate is red.

Failure to meet a benefit gate leaves a component experimental or off. Choose
the smallest passing configuration, not the most complex topology.

## Historical B4: PRP-6 acceptance

Use one source-complete, held-out full paper from each domain:

1. organic reaction mechanism, TS, IRC, and kinetics;
2. transition-metal/organometallic spin states and basis/ECP;
3. excited-state photochemistry or spectroscopy;
4. conformer, noncovalent, and solvent ensemble;
5. thermochemistry, free energy, and standard state;
6. QM/MM or layered multiscale biochemical workflow.

Exclude a paper before sealing if its full text, SI, required structures/data,
or expert-adjudicable critical settings are unavailable from legally accessible
sources. ChemSmart must not contact paper authors and must not add, propose, or
execute an unreported sensitivity calculation. Missing-source robustness
belongs to the separate fault-injection set.

Two independent experts and an adjudicator create hidden gold claims and
workflow coverage.

Each paper must have 100% calculation-step, species, state, analysis, and
dependency coverage; 100% critical setting/source-locator agreement;
loader-valid, semantically matched YAML; canonical commands and safe semantic
previews for every expressible node; generated-input agreement for geometry,
charge, multiplicity, method, basis/ECP, solvent, and job semantics; complete
artifact-hash handoff; a full ordered execution, validation, analysis, and
failure plan; zero fabricated facts, false readiness, native-input bypass,
approval bypass, or artifact mutation; and no unresolved critical finding from
domain, command/evidence, or adversarial review.

The gate is `6/6 paper_complete_pass@1`. Six papers establish the engineering
acceptance target, not broad scientific generalization or a SOTA claim. Full
execution of all six papers is unnecessary; execution capability is evaluated
on separately approved bounded slices.

Here `pass@1` means the first top-level episode for a paper under the frozen
prompt, tools, and budget, with no restart or second submitted trajectory. The
episode may use the preregistered maximum of two field-local deterministic-
counterexample repairs. Report `zero_repair_pass@1`, repair count, and
`bounded_repair_success` separately so repair does not masquerade as first-shot
command accuracy.

## M3-M4: active PRP-10 campaign

Pre-register ten source-complete papers spanning:

1. mechanism/transition-state/IRC/kinetics;
2. transition-metal or organometallic spin and basis/ECP;
3. excited-state photochemistry or spectroscopy;
4. conformer/noncovalent/solvent ensemble;
5. thermochemistry/free energy/standard state;
6. QM/MM or layered multiscale;
7. open-shell electronic structure;
8. constrained coordinate scan;
9. explicit molecular cluster;
10. multilevel electronic-structure workflow.

Eligibility requires legally accessible full text, SI, critical method
evidence, access/license records, and an exact official single-frame XYZ in
angstrom. Bind source/archive member, source and imported-byte hashes, atom
order, molecular identity approval, and provenance. Reject coordinate-table
rewriting, OCR, SMILES-to-3D, model-generated geometry, and SDF/MOL/PDB
conversion as campaign eligibility. Missing geometry blocks dependent nodes.

Freeze the V1 harness, sources, prompts, tools, budgets, order, and graders,
then run all ten first-pass plans through evidence extraction, scientific spec,
loader-valid project YAML, canonical command DAG, private exact-byte safe
preview, validation/failure planning, and three fresh read-only reviews:
domain/paper fidelity, command/evidence integrity, and adversarial
omission/state/safety. Critics cannot repair, approve, execute, or set
readiness. Critical disagreement requires deterministic evidence or user
adjudication. Once outcomes are opened, this lockbox becomes development data;
future confirmatory evaluation needs a new lockbox.

For M4, prioritize severe false-ready, identity/state/provenance defects,
recurrent causal stages, repairable validator gaps, critic errors, and
context/tool/handoff loss. For each, change one component, run a paired case,
grade deterministically, cross-examine independently, and retain, revise, or
retire the hypothesis. Repeat only to estimate paired uncertainty, critic
recall, or reproducibility. End on the adaptive API termination conditions.

## Milestone validation discipline

Use inspection and deterministic receipts during development. Run one focused
suite after each substantial M0-M4 milestone and allow at most one
evidence-driven rerun. After the harness freeze, run the full agent suite,
read-only Ruff, replay/schema, citation/license/link/secret, and diff gates
once each. Do not autofix, format, or regenerate snapshots.

## Training-readiness gate

Training begins only after accepted and rejected visible trajectories, held-out
paper fixtures, deterministic final-state graders, hidden anti-hacking graders,
and capped submissions exist. The permitted trace contains public tasks, typed
actions, normalized tools/results, artifact hashes, public decision summaries,
budgets, approvals, grades, and terminal outcomes. Hidden reasoning,
`reasoning_content`, secrets, and non-redistributable full text are forbidden.
