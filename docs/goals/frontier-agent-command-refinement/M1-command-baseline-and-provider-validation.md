# M1 — Command Baseline and Provider Validation

## Objective

Freeze a truthful baseline for direct-string command synthesis, compact-v8
compatibility input, schema pruning, semantic gates, and tool exposure. Then
observe one command-only DeepSeek proposal through the real AgentSession,
UnifiedSessionRunner, and ToolLoop without real chemistry execution.

## Required work

1. Inspect the active Click schema, compact signatures, schema-pruning logic,
   direct-string synthesis, v8 adapter, semantic gate, safe-preview harness,
   and model-command parser. Record implemented, feature-flagged, mocked, and
   absent behavior without projecting future behavior onto the baseline.
2. Define the command-only frontier profile: workspace/project operations plus
   synthesize, repair, inspect, and explain. Ensure legacy molecule/settings/
   job/input/execution builders are unavailable and fail closed there while
   remaining available only in explicit harness-jobs compatibility fixtures.
3. Wire the official DeepSeek adapter through the actual session/runner/loop,
   not a standalone adapter probe. For tool-bearing calls to the official
   api.deepseek.com endpoint only, disable provider thinking according to the
   adapter contract; do not change other OpenAI-compatible providers.
4. Obtain the API secret only through a standard Keychain lease. Record
   provider, endpoint class, non-secret liveness result, and current-quota
   sufficiency. Never show or persist a key. Stop on insufficient quota.
   The canonical accounts under `com.chemsmart.agent.credentials` are
   `deepseek_api_key`, `elsevier_api_key`, `serpapi_api_key`, and
   `tavily_api_key`; the legacy `Elsivier_api_key` alias is lookup-only.
5. Use one zero-engine safe preview to observe a proposed command. A safe run
   preview uses fake/no-scratch and a submission preview uses test/fake.

## Acceptance evidence

- Baseline ledger separates direct-string behavior from the future compiler.
- A command-only tool-surface receipt proves forbidden legacy tools cannot be
  reached through the frontier profile.
- The provider observation records no secret, no raw hidden reasoning, no
  native input authoring, no engine/HPC execution, and no billing change.
- Any unavailable key, quota, or provider result terminates as blocked with a
  non-secret reason rather than a retry loop.

## Test gate

After the complete M1 change set, run one focused provider/session/tool-profile
suite. Rerun it only once if an evidence-based correction is made. Do not run
the full agent suite or automatic formatters.

## Exit decision

M1 establishes an observed command-only baseline. It does not prove compiler
correctness, chemistry readiness, execution, or model superiority; those are
M2 and later questions.
