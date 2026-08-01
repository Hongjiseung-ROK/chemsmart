# Settings × Knowledge Diagnostic Reconciliation

Date: 2026-08-02 KST

Scope: the original `settings-knowledge-live-v2-2026-08-02` launch and its
partial `r1` retry. The raw campaign artifacts were not changed.

The authoritative machine-readable record is the
[diagnostic reconciliation](receipts/settings-knowledge-live-v2-2026-08-02-diagnostic-reconciliation.json).
Both launches are retained as harness-development evidence and excluded from
all settings × knowledge component-effect estimates.

## Disposition

| Launch | Observable result | Valid evidence ceiling | Statistical disposition |
| --- | --- | --- | --- |
| Original | 12 runs rejected by the tool-schema binding gate before transport; zero model responses | Pretransport fail-closed harness diagnostic | Exclude from model, scientific, token, cost, latency, arm, and ablation metrics |
| `r1` | Eight response-bearing turns; all 26 tool outcomes skipped; eight terminal streams blocked on `repeat_signature`; campaign stopped during the first xTB session without a terminal or campaign receipt | Partial invalid-pipeline behavior diagnostic | Exclude from scientific and component-effect metrics; inspect model text qualitatively only |

The original campaign's `oracle_passes=0` is not a `0/12` model score. No
request reached DeepSeek. Its empty response and tool-trace files are sentinel
projections of the rejected runs.

The `r1` text is genuine provider output, but it did not pass through the
intended tool path. The public traces contain 26 requested tool calls and 26
`skipped` outcomes. Two typed proposals were extracted from unexecuted request
arguments, so they are not validated tool results. ORCA and Gaussian produced
four public arm projections each; xTB produced none. The complete three-case,
four-arm block and campaign receipt are absent.

## Provenance and retention

- The original 25 raw public artifacts contain 99,990 bytes and have manifest
  SHA-256 `0f1b682433fde079595bf388d4403e4377686afa4dbbe2212e9151b3200fbf72`.
  The exact campaign-receipt file SHA-256 is
  `37f37328c378ca265566bd63e173ea219669b48f5bf46fa1ab0d25a1b7ae908f`.
- The `r1` 16-file partial public artifact set contains 21,586 bytes and has
  manifest SHA-256
  `a030571e7dd8a6317c6fa1d65f26e717e5cc9649eb12296de7312d6f405ba797`.
- Twelve original event logs and nine `r1` event logs were promoted to the
  repository-ignored private evidence locators
  `tmp/private-evidence/settings-knowledge-live-v2-2026-08-02/sessions` and
  `tmp/private-evidence/settings-knowledge-live-v2-2026-08-02-r1/runtime`.
  All 21 copied files match the previously recorded SHA-256 values. Their
  aggregate manifest hashes, per-case hashes, terminal states, stable locator
  hashes, and verified Git-ignore status are recorded in the reconciliation
  JSON. These private files are stable workspace evidence, not tracked Git
  artifacts.

## Readiness consequence

Neither launch satisfies the preregistered M2D exit gate. No conclusion about
the value of settings-registry exposure, domain-knowledge-pack exposure, their
interaction, generality, scientific correctness, or SOTA performance may be
drawn from them. A replacement run must retain separate identity and retry
lineage and must not overwrite either diagnostic source directory.
