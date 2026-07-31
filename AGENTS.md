# ChemSmart Agent Operating Contract

## Mission

Develop ChemSmart as a CLI-first, provider-neutral computational-chemistry
automation agent. Models may plan, ask, and explain. Deterministic ChemSmart
code owns CLI semantics, permission policy, execution, scientific validation,
and evidence recording.

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
- Do not install dependencies, alter environment pins, contact external
  systems, commit, push, or publish without authority for that action.

## Scientific workflow

Make these facts explicit before a calculation is treated as specified:

- molecule identity and stable artifact identifier;
- exact geometry frame and coordinate units;
- charge, multiplicity, electronic-state assumptions, and constraints;
- requested observable, program, job kind, method, basis/ECP, dispersion,
  solvent, temperature/standard-state convention, and resource target;
- required evidence, diagnostics, and limitations.

Ask instead of inventing a scientifically consequential missing fact. Never
infer geometry identity from a filename alone. Preflight through the real
parser and generated-input checks before execution.

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

## Agent architecture

- Keep provider-specific wire protocols and continuation state inside adapters.
  Persist only observable actions, concise public summaries, tool calls,
  artifacts, approvals, and outcomes. Never request, store, or use hidden
  chain-of-thought as scientific evidence.
- Give each task the smallest relevant tool surface and explicit token, tool,
  wall-time, and compute budgets.
- Use subagents only for bounded, independently verifiable work with declared
  immutable inputs, expected outputs, allowed tools, owner, and merge rule.
  One agent owns each mutable artifact.
- Use a critic as a fresh, read-only cross-examiner. A critic cannot approve,
  execute, or repair its own finding. Deterministic checks or independent
  computation arbitrate disagreements.
- End every run as complete, failed, blocked, or waiting for approval; do not
  loop indefinitely.

## Evidence and reporting

Record stable IDs, input and output hashes, engine and environment versions,
commands, working directory, timestamps, exit status, parsed values with
units, validator outputs, approval records, and claim-to-evidence links.

Separate observation, computed result, inference, literature statement, and
unresolved uncertainty. A report, notebook, or chat summary is a rendered view
of evidence, not the evidence source. Use QCSchema-compatible records where
practical, retain native engine artifacts, and make each numerical claim
traceable to a receipt.

## Project-local skills

Use the smallest matching skill set:

- `chemsmart-agent-harness` for provider adapters, tool loops, permissions,
  Runtime V2, task graphs, and harness evaluation;
- `chemsmart-scientific-workflow` for Gaussian, ORCA, and xTB task intake,
  preflight, execution, and physical validation;
- `chemsmart-evidence-audit` for provenance, claims, citations, reports,
  red-teaming, and evaluation.

## Validation and reporting discipline

- Run focused checks before broad suites and report the exact command and
  result.
- Keep product, runtime, scientific, and release readiness separate. A focused
  green check is not proof of product or scientific readiness.
- Report green checks, blockers, retired metrics, and unverified claims
  separately.
- Preserve backward replay of existing runtime events when evolving the agent;
  extend the current Runtime V2 nucleus instead of introducing a competing
  runtime.
