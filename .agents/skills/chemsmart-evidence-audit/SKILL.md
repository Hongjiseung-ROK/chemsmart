---
name: chemsmart-evidence-audit
description: Audit ChemSmart PRP-10 paper-to-research-plan reconstructions, adaptive API campaigns, command workflows, calculations, agent traces, claims, benchmarks, or reports for reproducibility and evidence coverage. Use when verifying full text, Supporting Information, official XYZ provenance, hypothesis/oracle receipts, CommandWorkflowSpec and safe-preflight evidence, claim manifests, three-reviewer critique, adversarial tests, or independent component ablations.
---

# ChemSmart Evidence Audit

Use this skill to make a result inspectable and falsifiable. Read `AGENTS.md`
first. Treat a model-generated narrative as an interpretation to audit, not as
evidence.

## Audit workflow

1. Identify the claim type: observation, computed result, inference,
   literature statement, or unresolved uncertainty.
2. For a paper bundle, inventory main text, Supporting Information, figures,
   tables, data, code, cited protocols, and access/entitlement status. Reject a
   claim that relies only on a search snippet or an unlocated paraphrase.
   A critical inferred, unknown, or conflicting setting must remain blocked;
   reject author contact or an unreported sensitivity study as gap-filling
   evidence.
3. Bind every command claim to its typed IR, schema digest, trusted
   project/artifact bindings, canonical argv, safe-preview receipt, parser
   observation, and intent comparison. Bind every numerical statement to a
   stable artifact, parsed value, unit, validator, and calculation environment.
   Mark missing evidence rather than filling it from prose.
4. Verify scholarly metadata programmatically. Keep DOI/arXiv source, title,
   authors, venue, year, correction/retraction check, and retrieval timestamp
   outside the BibTeX file.
5. Generate reports and notebooks from the evidence manifest. Preserve
   ChemSmart-generated native inputs/outputs and structured records so
   rendering remains reproducible. Do not use a model-written native input as
   evidence or silently repair a command/input while auditing it.
6. Give an independent, read-only critic the artifacts and declared
   assumptions. Require it to cite a check, receipt, or source for every
   finding.
7. Resolve findings with deterministic validation, independent recomputation,
   or a human decision. Do not use majority vote as scientific arbitration.
8. End with supported, qualified, rejected, or unresolved claims and separate
   readiness from raw task completion.
9. For every adaptive API request or retry, verify its registered unique case
   ID, one changed factor, comparator, expected outcome, deterministic oracle,
   source/prompt/tool/configuration hashes, and novelty rationale. Treat request
   count as a metric; a retry keeps the case ID and adds an attempt ID, error
   class, and reason. Reject duplicates, quota-burning, top-up, or provider
   bypass. Confirm that concurrency, per-request tokens, task wall time,
   endpoint/purpose, and credential lease stayed within the recorded envelope.

## Red-team rules

Seed realistic failures: wrong charge/multiplicity, malformed geometry,
incompatible settings, nonconvergence, imaginary frequencies, truncated
output, bad units, contradictory literature, unavailable executable, and
approval mismatch. Bound review rounds and retain a blocked outcome.

Also seed command-compiler failures: shell injection, invented or
out-of-scope options, wrong option scope/order, stale schema/project/artifact
binding, charge/multiplicity drift, lost constraints, unsafe direct input
fallback, parser disagreement, and reused approval after a semantic change.
The critic may identify these defects but cannot repair, approve, execute, or
mark the command ready.

For active PRP-10, audit ten frozen papers spanning the six predecessor domains
plus open-shell, constrained scan, explicit cluster, and multilevel workflows.
Eligibility requires full text, SI, access/license evidence, critical methods,
and an exact official single-frame XYZ import receipt. Require three fresh,
read-only reviews—domain/paper fidelity, command/evidence integrity, and
adversarial omission/state/safety—and user adjudication for unresolved critical
disagreement. Safe preview is the execution ceiling.

Keep PRP-6, its `6/6 paper_complete_pass@1` rule, the seven-paper public pilot,
and `two-frontier-s0-2026-08-01` 128/24 caps as historical predecessor evidence.
Do not rewrite or relabel them as active PRP-10 results.

## Use the references

- Read [evidence-and-reports.md](references/evidence-and-reports.md) for the
  canonical manifest and reproducible-document requirements.
- Read [red-team-and-ablation.md](references/red-team-and-ablation.md) before
  designing a critique or component evaluation.
- Read [paper-plan-audit.md](references/paper-plan-audit.md) before judging a
  paper-to-research-plan reconstruction, active PRP-10, or historical PRP-6.

## Examples

Use this skill for: “audit a typed command preview receipt,” “audit every
claim in this calculation report,” “verify the BibTeX and provenance ledger,”
“verify an adaptive API hypothesis/oracle receipt,” or “compare a subagent
system to the single-agent baseline.”

Do not use it to execute a calculation, silently alter a method or native input
to pass a check, compile a model-written shell command, or grant approval for
an action.
