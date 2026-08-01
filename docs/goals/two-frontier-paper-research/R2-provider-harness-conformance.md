# R2 — Provider-Native Harness Conformance

## Objective

Separate provider-native wire/continuation behavior from the provider-neutral
scientific kernel, then obtain sanitized DeepSeek V4 Flash receipts for the
smallest safe harness configurations. A declared capability is not admission.

## Canonical cumulative matrix

Sandboxed tools, approval pause, and deterministic validator feedback are on in
all profiles.

| Profile | Public event replay | Skills, fresh specialists, hooks, handoff, compaction | Persistent goal, checkpoint/fork/resume | Delegation depth |
| --- | --- | --- | --- | ---: |
| `H0` | no | no | no | 0 |
| `HC` | yes | no | no | 0 |
| `HA` | yes | yes | no | 1 |
| `HK` | yes | yes | yes | 2 |

## Required work

1. Keep `ProviderCapabilities`, `HarnessProfileSpec`, `ProviderStateRef`, and
   `ProviderConformanceReceipt` strict and content-addressed. Distinguish
   vendor-declared limits from behaviors observed by a named probe.
2. Connect the official DeepSeek adapter through the real AgentSession,
   UnifiedSessionRunner, and ToolLoop. Use `deepseek-v4-flash`, bounded output,
   a finite request/tool/token/cost envelope, and a command-only read/proposal
   tool surface. No standalone response can substitute for this path.
3. Keep documented thinking and tool continuation enabled inside an
   uninterrupted adapter turn. Replay provider-required `reasoning_content`
   only ephemerally; exclude it from public history, SessionState, events,
   receipts, logs, reports, and training records. Resume from a deterministic
   public recap or fail closed.
4. For campaign `two-frontier-s0-2026-08-01`, lease the DeepSeek credential
   only from the existing session environment and only to the official
   endpoint. Count every initial call and retry against the campaign-wide cap
   of 128 DeepSeek transport attempts as well as the existing user-owned quota.
   No per-call reapproval is needed inside those recorded limits, but no
   Keychain fallback, top-up, billing change, raw error dump, or unbounded retry
   loop is allowed.
5. Start with one H0 typed tool-call round trip and zero-engine inspection.
   Expand to HC/HA/HK only when each profile's required replay, pause,
   specialist, compaction, checkpoint, and budget checks can actually run.

ChemSmart must not contact paper authors and must not add, propose, or execute
an unreported sensitivity calculation.

## Current status and acceptance evidence

- The earlier 2026-08-01 H0 observation is retained in a
  [historical receipt](../../evaluation/receipts/deepseek-v4-flash-h0-2026-08-01.json),
  but it is `stale_invalidated`: it predates the current source snapshot, used
  a legacy short receipt ID, and lacks the current public-history digest. It
  admits no current H0 slice and is not an R2 completion receipt.
- A fresh current-schema H0 receipt must bind the exact source snapshot and
  satisfy all checks below before H0 admission. HC, HA, and HK require their own
  profile-specific receipts.
- The receipt binds source snapshot, model ID, endpoint/protocol, tool schema,
  public history, resource budget/usage, thinking mode, request count, profile,
  and every required check without secret or private reasoning.
- A current H0 receipt must demonstrate typed tool-call round trip, sanitized
  public history, and a deterministic validator gate with zero engine/HPC
  calls; the historical observation is not a substitute.
- Profile-specific checks are `pass`, `fail`, `not_supported`, or `not_run`;
  unobserved context/parallel/checkpoint support is never reported as observed.
- Provider errors are reduced to non-secret classes and terminate within the
  bounded request budget.
- Because the selected probe mode is thinking enabled, even a fresh passing
  receipt supports only that exact mode. It does not establish
  thinking-disabled conformance or that thinking caused an efficacy gain.

## Validation and exit

Run one focused provider/adapter/session/profile/conformance suite after R2 is
complete, plus at most one evidence-driven rerun. A minimal live probe is an
experiment receipt, not a chemistry or harness-superiority result.
