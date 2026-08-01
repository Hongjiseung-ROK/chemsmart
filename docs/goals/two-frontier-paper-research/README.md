# Two-Frontier Paper Research Agent Roadmap

## Purpose

This is the active R0–R6 roadmap for turning a source-complete computational-
chemistry paper into a faithful ChemSmart research plan. It supersedes the
[historical command-refinement roadmap](../frontier-agent-command-refinement/README.md)
without deleting its command-compiler lineage.

The ultimate objective, scientific state, and evaluation contract are:

- [Ultimate Goal](../../design/chemsmart-agent-ultimate-goal.md)
- [Paper Research Plan v1](../../design/paper-research-plan-v1.md)
- [CommandWorkflowSpec v1](../../design/command-workflow-spec-v1.md)
- [Evaluation Protocol](../../evaluation/frontier-agent-ablation-protocol.md)
- [Two-Frontier Evidence Review](../../research/frontier-agent-landscape.md)

The machine-readable [phase-status ledger](phase-status.json), validated
against [its schema](phase-status.schema.json), is the authority for phase
admission. At this snapshot no phase has passed and `R0` is the next required
gate. A document or implementation file is never a completion receipt by
itself. The next gate is the first ordered record not in `validated` state;
later implementation may be inspected in parallel but cannot validate ahead of
an earlier record.

## Non-negotiable outcome

For a legally accessible full paper, SI, and required data, ChemSmart must
construct source-located claims, exact molecular/electronic states, validated
project YAML files, a canonical ChemSmart command DAG, safe previews, three
independent reviews, and an ordered execution/validation/analysis/failure plan.
The model proposes typed state; it never writes or edits Gaussian, ORCA, or xTB
native input. ChemSmart must not contact paper authors and must not add,
propose, or execute an unreported sensitivity calculation.

The final engineering gate is exactly `6/6 paper_complete_pass@1` on one sealed,
held-out, source-complete paper from each PRP-6 domain. It is not automatically
a SOTA claim, a publication decision, or proof that all six papers were run.

Before that sealed gate, the public development pilot has exactly seven source
slots: the user's current experimental paper plus six public source-complete
controls, one per PRP-6 domain. No fixed control IDs have been selected. The
user paper is `blocked_missing_source` until its article, SI, and required
artifacts are supplied; control selection and acquisition are pending. These
seven development papers are not sealed PRP-6 evidence.

## Phase order

| Phase | Contract | Exit evidence |
| --- | --- | --- |
| [R0](R0-evidence-and-scope-freeze.md) | Evidence and authority freeze | Verified source classes, pins, licenses, API status, instructions, and explicit gaps |
| [R1](R1-paper-contracts.md) | Paper and scientific-state contracts | Stable serialization/digests, conservative readiness, additive replay |
| [R2](R2-provider-harness-conformance.md) | Provider-native adapter and profiles | Sanitized DeepSeek conformance receipts for the exact cumulative matrix |
| [R3](R3-specialists-and-reviews.md) | Bounded specialists and critics | Deterministic joins and independent seeded-fault review gates |
| [R4](R4-scientific-command-coverage.md) | Six-domain project/command growth | Loader-valid YAML, safe semantic previews, typed capability gaps |
| [R5](R5-preregistered-ablation.md) | Frozen pilot and ablations | External slices, A0/A1, profile crossover, D/E/C estimates, freeze receipt |
| [R6](R6-prp6-and-reproducibility.md) | Sealed PRP-6 | `6/6 paper_complete_pass@1` or an honest blocked/failed report |

Do not infer that a predecessor passed from its filename. Each session must
inspect current branch, dirty state, source, tests, and receipts before acting.
Use the next incomplete phase only. R6 remains blocked until an independent
custodian supplies the sealed corpus and blind gold/grader.

## Development discipline

Use DeepSeek V4 Flash for bounded model experiments and Elsevier, SerpAPI, and
Tavily for literature discovery/acquisition only. For campaign
`two-frontier-s0-2026-08-01`, credentials come only from the existing session
environment. Count every initial transport attempt and retry against a hard
campaign cap of 128 total DeepSeek attempts and 24 attempts for each literature
API. These finite caps are inside the existing user-owned quota; do not top up,
fall back to Keychain, or persist secrets. A thinking-enabled receipt supports
only thinking-enabled behavior and cannot establish either thinking-disabled
compatibility or a causal benefit from thinking. The earlier H0 observation is
`stale_invalidated` and admits no current profile.

During a milestone use inspection and deterministic receipts. Run one focused
suite only after the material milestone is complete and at most one
evidence-driven rerun. Run the full agent suite and read-only integration checks
once at the R5 freeze. Do not autofix, regenerate snapshots, run chemistry
engines/HPC, publish, or start training without the phase's separate gates.

Copy only a fenced body from [goal-commands](goal-commands/README.md) into a new
Codex Goal. Every body is measured below 3,500 Unicode characters and 3,500
UTF-8 bytes.
