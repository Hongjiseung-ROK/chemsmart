# Red-team and ablation reference

Use preregistered paired studies before enabling optional agent components.
Hold paper/source hashes, model/provider revision, prompt, tool schema, task
order, network envelope, and deterministic validators fixed. Change one factor
per pair and retain a single-agent baseline.

Before the factorial study, compare the direct-string command front end (A0)
with typed CommandWorkflowSpec plus deterministic compiler (A1). Require A1 to
have 100% schema-valid rendering, parser acceptance, and render determinism,
zero raw native-input authoring/hallucinated options/shell injection, no more
than a two-point semantic-preview-success regression, and either at most 1.25x
token/cost or a significant bounded-repair reduction. Compiler authority is a
safety boundary; efficacy language requires this paired evidence.

## Active PRP-10 experiment plane

Version and toggle these ten factors independently:

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

Permission, CLI-schema validation, artifact hashing, secret redaction,
deterministic safety validation, and the native-input/engine/HPC prohibitions
remain enabled in every condition. The earlier D/E/C `2 x 2 x 2` design is a
preserved historical projection, not the whole active plane.

Measure task success, chemical validity, clean-environment reproducibility,
false-pass and unsupported-claim rate, approval violations, critic precision
and recall, tool/parser errors, time, token use, cost, and handoff loss.

Adopt a component only when its preregistered benefit is supported without a
safety regression. Required red lines are zero approval bypasses, fabricated
evidence, artifact mutation, and successful completion with a required failed
deterministic gate.

Use deterministic graders first, expert rubrics second, and LLM judges only as
supplementary analysis.

`two-frontier-s0-2026-08-01` and its 128 DeepSeek/24-per-literature-provider
ceilings are frozen historical evidence. The active adaptive campaign has no
fixed attempt cap. Every initial request and retry binds to a registered unique
hypothesis/case, single changed factor, comparator, expected result, deterministic oracle,
source/prompt/tool/configuration hashes, and novelty reason. Stop on current
quota exhaustion, no unique hypothesis, revoked credential, or safety red line;
never top up, repeat merely to spend quota, or bypass a provider failure.
Store provider, endpoint class, entitlement/error class, and aggregate usage,
never credentials or raw authorization headers. Classify Elsevier 403 as
entitlement denial unless independent evidence proves otherwise.
