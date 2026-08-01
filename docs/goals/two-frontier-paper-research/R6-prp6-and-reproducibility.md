# R6 — Sealed PRP-6 and Reproducibility Package

## Objective

Evaluate the frozen system on six source-complete, held-out papers and produce
an evidence-bound technical report. R6 begins only after an independent
custodian supplies sealed tasks and two-expert-plus-adjudicator hidden gold.
The seven-paper public development pilot—one user experimental paper plus six
public domain controls—is not eligible for reuse as this sealed corpus. At the
current snapshot its user source is missing and its six controls are not yet
selected; neither condition opens R6.

## Frozen domains

1. Organic reaction mechanism, TS, IRC, and kinetics.
2. Transition-metal/organometallic spin states and basis/ECP.
3. Excited-state photochemistry or spectroscopy.
4. Conformer, noncovalent, and solvent ensemble.
5. Thermochemistry, free energy, and standard state.
6. QM/MM or layered multiscale workflow.

Every paper must have legally accessible full text, SI, and required geometry/
data before sealing. Exclude an incomplete candidate rather than contacting an
author. ChemSmart must not contact paper authors and must not add, propose, or
execute an unreported sensitivity calculation.

## Protocol

1. Verify the frozen model, prompts, profile, skills/tools, schema, compiler,
   validators, source/fixture hashes, budgets, graders, and analysis receipt
   before unsealing. After unsealing, do not tune from failures or change a
   scored artifact.
2. Generate one pass@1 plan per paper: source bundle and claim graph; molecular
   and electronic-state graph; project YAML set; canonical command DAG; safe
   previews; validation/analysis/report graph; ordered execution/failure plan;
   and domain, command/evidence, and adversarial reviews.
3. Preserve honest `blocked_missing_evidence`, `blocked_capability_gap`, and
   failed outcomes. Do not replace a missing critical value with inference,
   provider reasoning, a model vote, native input, or runtime self-modification.
4. Grade deterministically first, hidden experts second. The model's completion
   statement and any LLM judge are non-authoritative.

## Exact primary gate

The result is `6/6 paper_complete_pass@1` only if every paper has: 100%
calculation-step/species/state/analysis/dependency coverage; 100% critical
setting/source-locator agreement; loader-valid semantically matched YAML;
canonical commands and safe previews for every expressible node; generated-
input agreement for geometry, charge, multiplicity, method, basis/ECP,
solvent, and job semantics; complete artifact-hash handoff; a full ordered
execution, validation, analysis, and failure plan; zero fabricated fact, false
readiness, native-input bypass, approval bypass, or artifact mutation; and zero
unresolved critical domain, command/evidence, or adversarial finding.

`pass@1` is the first frozen top-level episode for that paper, without restart
or a second submitted trajectory. The episode may consume the preregistered
maximum of two field-local deterministic-counterexample repairs. Report
`zero_repair_pass@1`, repair count, and `bounded_repair_success` separately.

## Deliverables and limits

Package frozen configuration and source ledgers, permitted fixtures or
custodian access protocol, QCSchema-compatible records, native preview
artifacts, validator/review receipts, analysis outputs, and an RO-Crate-
compatible manifest. Draft a transparent SOTA-quality architecture/benchmark
paper with negative results and limitations, but do not claim SOTA from six
papers and do not publish, release data, submit a preprint, or train a model.

Full execution of all six papers is not required. Any real calculation is a
separately approved bounded slice with exact command/project/input/environment/
budget binding. A red safety gate, changed frozen digest, corpus leakage,
custodian failure, or unpreregistered analysis ends R6 as blocked or failed.
