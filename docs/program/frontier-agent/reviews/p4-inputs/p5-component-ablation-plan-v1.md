# P5 component-ablation plan captured for P4

## Capture boundary

This is the immutable P4 capture of the P5 planning input. Its source was
`docs/program/frontier-agent/05-component-ablation.md` with SHA-256
`83afb23232193b6feaf9dd68c07713c48b93faf35812a11146507e9869f1072d`
at P4 packet construction. This capture is not an execution receipt and does
not authorize a provider completion, chemistry engine, scheduler, or training.

## Planned objective and reference

P5 plans to measure decomposition, structured evidence/report generation, and
independent critique against the frozen single-agent reference, without
assuming a SOTA conclusion. The reference is the all-off configuration:
`decomposition=off`, `documentation=off`, `critique=off`.

The planned inputs are the P3 reference and fixtures, P4 review artifacts,
P1 provider receipts only if live conditions are enabled, and the frozen
`docs/evaluation/frontier-agent-ablation-protocol.md` protocol.

## Planned authority and budget

Allowed work is frozen harness configuration, deterministic grading,
fixture/archived-output evaluation, paired randomization, local analysis, and
read-only expert rubric scoring. Live model work requires the P1 provider
receipt plus identical provider/model/tool/prompt/budget conditions across a
compared pair. Real engine or scheduler work remains zero without separate
approval.

The planned study has exactly eight factor configurations and at least three
paired repetitions per held-out case/configuration. Before a first held-out
trial it must freeze model, prompt/skill, tools/schema, fixtures, order/retry
policy, graders, and resource ceilings. P1-verified existing allowance is the
only possible API source; no engine or scheduler call is authorized.

## Planned artifacts and gates

The planned artifacts are a preregistered configuration manifest, randomization
seed/order, development-versus-held-out split, raw per-trial receipts,
deterministic scores, separately labeled expert/LLM assessments, paired
confidence intervals, failure/red-line audit, and component adoption table.

The gates require: preregistration before held-out use; deterministic graders
before expert or LLM inputs; zero approval bypasses, fabricated evidence,
artifact mutation, secret exposure, or terminal success behind a red gate;
protocol-supported benefit with intervals; and enough input/environment/raw
evidence for independent rerun. A red line blocks default adoption.

## Planned blockers and claims

Missing allowance, unpinned model revision, missing held-out fixture,
nondeterministic grader, or incomplete P3/P4 artifacts block the corresponding
comparison. A configuration with a red line stays out of default consideration.
At close, a complete study would report every configuration, repetition,
paired interval, family outcome, false pass, blocked case, cost, and red line;
it would not tune after held-out results without a new preregistration.

P5-C1 (metric change), P5-C2 (default enablement), and P5-C3 (named-comparator
comparison) were all unresolved at the P4 capture. The planned decisions were
to retain the simplest passing configuration, report failures/blockers, and
treat a red-line failure as decisive against default adoption.
