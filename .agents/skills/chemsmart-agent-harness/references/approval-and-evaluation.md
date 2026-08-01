# Approval and evaluation reference

## Approval matrix

| Operation | Default | Required evidence |
| --- | --- | --- |
| Read-only inspection or schema generation | allowed | command and artifact receipt |
| Fixture or fake execution | allowed within task scope | deterministic validation result |
| Real local calculation | explicit approval | exact command, inputs, environment, cost/resource bound |
| Scheduler submission, cancellation, or retry | explicit approval | exact job artifact, scheduler target, resource bound |
| Paid API, remote execution, or publication | explicit approval | provider/target, budget, disclosure scope |

Invalidate approval whenever a bound input, project, executable, environment,
or command hash changes.

For a user-authorized API validation, resolve a short-lived credential lease,
using only the credential source recorded for that campaign. Verify liveness
and quota sufficiency without writing the secret, raw header, or licensed full
response into a public receipt. DeepSeek is the only
model-validation provider in this roadmap. Elsevier, SerpAPI, and Tavily are
literature-discovery or full-text-verification services, never chemistry
execution providers. Treat an Elsevier 403 as an entitlement result until
proven otherwise; do not label it an invalid key by default. Never top up,
change a plan, or exceed the user-owned quota. Once the user has authorized
the current development phase, calls within that recorded quota do not need
per-call approval; a new provider, target, quota expansion, or billing change
does.

`two-frontier-s0-2026-08-01` is frozen historical v1 evidence. Its initial
calls and retries counted against 128 DeepSeek transport attempts and 24 for
each literature provider, and it used the session environment without
Keychain fallback. Preserve those receipts and limits; do not project them
onto the active adaptive campaign.

For PRP-10 adaptive work, set `transport_attempt_limit=None`. Count requests,
retries, tokens, latency, optional cost, and error classes as observations, not
targets or count-based stop conditions. Before dispatch require a registered
unique hypothesis/case ID, one changed factor, comparator, expected outcome,
deterministic oracle, source/prompt/tool/configuration hashes, and novelty
rationale. Bind each retry to the same case plus attempt ID, error class, and
reason. Reject duplicates and quota-burning. Stop on current-account quota
exhaustion, no remaining unique verifiable hypothesis, credential revocation,
or a safety red line. Never top up or route around an exhausted/failed provider.

Every network-enabled packet must declare `AdaptiveNetworkBudgetV1` bounds for
concurrency, per-request context/output tokens, task wall time, exact
provider/endpoint/purpose, credential lease, and secret redaction. Start
DeepSeek at concurrency one and adapt only from observed rate limits, never
above four; literature providers remain one request at a time. Apply
`Retry-After` to 429, wall-time-bounded backoff to timeout/5xx, and terminal
classification to explicit quota failure, 401, or Elsevier entitlement denial.

## Bounded delegation

Dispatch only if subtasks have independent inputs and a typed merge operation.
The coordinator owns the task graph; workers own no shared mutable artifact.
Critics receive artifacts and declared assumptions, not persuasive self-reports.

## Evaluation rule

Keep a single-agent reference path. Compare it with any subagent or critic
configuration under fixed model, prompt, tool schema, task set, and budget.
Use deterministic outcome graders first. A component stays experimental until
it improves the preregistered metric without creating approval bypasses,
fabricated evidence, or false scientific passes.

PRP-10 is the active development campaign. Freeze ten source-complete papers,
their exact official single-frame XYZ coordinates, prompts, tools, and graders
before first-pass baseline runs. The seven-paper public pilot and PRP-6 remain
historical predecessor designs; retain their records but do not relabel them as
PRP-10 evidence.

Do not run pytest, Ruff, or broad checks after every edit. At a material
milestone run one focused suite, with at most one evidence-driven rerun. Run
the full test/lint/schema/link/citation/secret/diff gate only at the declared
freeze milestone.
