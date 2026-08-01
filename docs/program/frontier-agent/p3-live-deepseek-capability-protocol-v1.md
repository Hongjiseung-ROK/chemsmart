# P3 live DeepSeek capability specimen v1

## Status

Predeclared on 2026-08-01 before the first and only permitted request. The
request was made once at 2026-07-31T19:55:22Z and closed blocked: it returned a
single correctly named tool call but reached the 64-token ceiling with invalid
arguments. No tool was dispatched and no retry is permitted. This remains an
opt-in provider-surface specimen, not a revision of the frozen P3 fixture-only
reference, a `FaultTrace`, a deterministic grade, or a scientific task result.

## Purpose and bounded question

The specimen asks one narrow operational question: can the P1-pinned official
DeepSeek Chat-Completions surface return exactly one call to a harmless,
non-executing function when supplied a fixed schema and envelope? It cannot
establish a normal ChemSmart CLI/provider path, tool-loop behavior, fault
handling, chemistry competence, component benefit, or a SOTA comparison.

## Immutable contract

| Field | Fixed value |
| --- | --- |
| Related public case | `P3-F12`; linkage only, never a live `FaultTrace` or grade |
| Provider/model | official DeepSeek Chat Completions / `deepseek-v4-pro` |
| Endpoint record | `deepseek.chat.completions.v1`; the configured official-root URL is retained only as SHA-256 `a34e2a4708ed1c61008a151688838dcf1c44d4e7f08054633e72ba7c0b16cfc1` |
| Credential boundary | Resolve `DEEPSEEK_API_KEY` only in the specimen process from the P1-pinned legacy alias; restore/remove it in `finally`; do not change YAML, `api.env`, shell state, or CLI semantics |
| Model calls / retries | exactly 1 / 0 |
| Output-token / request-size ceiling | 64 / 4,096 bytes |
| Tool boundary | exactly one declared function call; `parallel_tool_calls=false`; zero execution, engines, schedulers, files, or follow-up calls |
| Time boundary | 15 s SDK/client timeout and local elapsed-time red gate |
| Reasoning boundary | request `thinking.type=disabled`; nonempty returned reasoning content is red; unreported reasoning-token detail stays qualified |
| Prompt and tool schema | sanitized, source-visible contract only; receipt retains hashes `08ea1463442983eaa9a65cced9f8b4eebeb67b67180da29da8fd719c90daee43` and `c0f1b10c1bb08804ac1dd97b2f17e0e41f20d6c19cce6dd684cd78d9084a8fcd`, not text/transcript |
| Full request contract | SHA-256 `0e4e6a7646481c011f36a653db2746763dc7ae459d40b8a3ae6c406df2b0db14`; 1,193 bytes |
| Cost boundary | USD 0.005 maximum; conservatively estimated at USD 0.00367488 from 4,096 input bytes plus 64 output tokens at twice the 2026-08-01 official `deepseek-v4-pro` prices |
| Allowance basis | P1's redacted USD 0.82 balance observation; it is a prior allowance observation, not a fresh balance assertion |

The runner pins `max_retries=0`, `temperature=0`, named `tool_choice`, and
the `thinking` request directly, rather than reusing ChemSmart's normal
provider adapter or tool loop. Both lack the required complete surface and the
tool loop could execute a returned call.

## Receipts and redaction

The command emits but does not write a sanitized JSON object. A reviewed
receipt may retain only model labels, public hashes, count/ceiling fields,
returned status classes, elapsed time, numeric usage, a hashed response ID,
and local structural-validation booleans. It must exclude credential values,
authorization headers, URLs beyond endpoint identity, prompt text, response
text, tool arguments, reasoning content, error text, and raw provider payloads.

One outcome closes the specimen: a valid structural observation is recorded as
`structural_tool_protocol_observed`; any transport/provider/structure/cost/time
failure is a red blocked receipt. Neither outcome is retried.

## Pre-call evidence

- P1 recorded an existing USD 0.82 DeepSeek allowance and the redacted official
  configuration facts. It did not make a completion.
- The code-level offline contract tests passed `6` tests before this specimen.
- The isolated dry run confirmed the P1 config digest/model/allowance boundary.
- Credential preflight resolved the canonical alias only in process and
  retained no value; it made no request.
- The sole request returned HTTP 200 in 2,112 ms, used 456 prompt plus 64
  completion tokens, and had a conservative peak-price upper bound of USD
  0.00050808. The exact response text, arguments, and reasoning content were
  discarded. The redacted result is in
  [`receipts/p3-live-provider-capability-v1.json`](receipts/p3-live-provider-capability-v1.json).

## Failure and decision ledger

| ID | Failure or decision | Hypothesis / minimal action | Evidence / limitation | Rollback boundary |
| --- | --- | --- | --- | --- |
| P3-LIVE-F1 | A script launched from `scripts/review` imported the installed package rather than this checkout. | Bind the checked-out repository root into the script import path before import. | The initial dry run raised an import failure; no API request occurred. This does not validate packaging/installability. | Remove the direct runner rather than changing installed packages or dependencies. |
| P3-LIVE-F2 | The provider file has two equivalent `deepseek-v4-pro` entries, so unique-model selection was too strict. | Accept only duplicate entries with the same redacted type/alias/official-root digest; block divergent entries. | Redacted preflight found two candidates with identical P1 surface. Provider names and values are not retained. | Return to block-on-ambiguity if the redacted surfaces diverge. |
| P3-LIVE-D1 | Keep this specimen separate from frozen P3 fixtures. | Do not create a `FaultTrace`, modify reference/case/seed files, or score a live response. | The deterministic grader treats any provider call as a reference-path authority violation. | Delete the optional specimen artifacts; frozen P3 remains unchanged. |
| P3-LIVE-D2 | Treat an API failure as evidence, not a reason to retry. | Retain the redacted failure class and stop. | One request only; no hidden recovery loop. | Any later run needs a new protocol, receipt, and explicit budget decision. |
| P3-LIVE-F3 | The named tool call did not complete within the 64-token envelope. | The strict argument shape may require more than 64 completion tokens under this model/protocol. Preserve v1; a future study would need a new frozen protocol with a shorter schema or separately approved larger ceiling. | `finish_reason=length`, one correctly named call, invalid arguments, and no retained transcript. The evidence cannot distinguish truncation mechanism from other invalid-argument causes. | No retry or in-place cap change. A new version needs a new budget/authority decision. |
