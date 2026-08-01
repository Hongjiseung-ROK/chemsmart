# PRP-10 Adaptive Campaign: M0-M2 Evidence Report

Date: 2026-08-02
Scope: evidence reconciliation, coordinate custody, experiment-plane contracts,
and live provider/tool-loop probes. No Gaussian, ORCA, xTB, or HPC execution was
performed.

## Milestone result

The adaptive campaign is operational, but the ten-paper baseline is not ready.
The strongest result is an active-path DeepSeek experiment showing that moving
source identity, claim IDs, and purpose out of model arguments and into a
host-owned task binding removed an avoidable repair while preserving evidence
localization. This is engineering evidence from five cases in one paper, not a
generality or scientific-correctness claim.

Across the receipts below, 36 transport attempts were observed: 33 DeepSeek
model requests and one request each to Elsevier, SerpAPI, and Tavily. Attempt
counts were metrics, never spending targets or stop conditions. Every request
had a distinct provider/purpose or experiment case. No retry was made merely to
consume quota.

## M0 — historical evidence reconciliation

The [Runtime reconciliation receipt](receipts/azide-allene-runtime-reconciliation-2026-08-01.json)
replayed 23 historical Runtime V2 streams without migration.

- 11 public terminal labels disagreed with the authoritative Runtime terminal.
- Four public `completed` labels were actually `turn_blocked`.
- Those four observations represented three unique blocker rules:
  `runtime.command.preview_required`,
  `runtime.command.preview_not_green`, and
  `runtime.project.render_required`.
- `completed` is therefore retired as a scientific success metric. Turn outcome,
  tool-domain outcome, and scientific readiness are reported separately.

The [adaptive API liveness receipt](receipts/adaptive-api-liveness-2026-08-01.json)
observed valid current credentials and successful bounded requests for all four
configured providers. Elsevier returned the El Agente Q full-text container;
SerpAPI and Tavily returned discovery results. This establishes transport and
entitlement for those probes only, not completeness or relevance of every
future source request.

## M1 — exact coordinate custody

The [PCP-TTM coordinate receipt](receipts/pcp-ttm-coordinate-provenance-2026-08-02.json)
compared the requested Zenodo record 15679510 with its current version 17301951.
Both records share concept DOI `10.5281/zenodo.15679509` and CC BY 4.0 metadata.

- Eleven official XYZ assets were found.
- Nine were byte-identical across the two versions and passed exact-byte private
  import with source, atom-order, units, identity-approval, and license binding.
- Two pseudo-o `+-` singlet/triplet assets had different SHA-256 values between
  versions and were blocked.
- The paper-level coordinate state is therefore
  `blocked_partial_version_conflict`, not complete.

This demonstrates why a concept DOI alone is insufficient geometry identity.
The exact record, member name, and byte hash must be bound. The publisher page
was not hashed in this slice, so paper-to-dataset linkage remains a separate
source-bundle gate.

## M2 — adaptive harness and live behavior

The first [El Agente Q extraction run](receipts/el-agente-q-adaptive-extraction-2026-08-01.json)
failed 0/5 because the new read-only evidence tool was absent from the static
permission allowlist. DeepSeek produced structurally valid tool requests, but
Runtime V2 denied all five before execution. Registering the tool as read-only
changed bounded-repair success from 0/5 to 5/5 under the corrected oracle.

The [three-arm comparison](receipts/el-agente-q-adaptive-comparison-2026-08-01.json)
separates that permission repair from a second change:

| Contract | pass@1 | bounded pass | repairs | transport attempts | input tokens |
|---|---:|---:|---:|---:|---:|
| Unregistered read-only tool | 0/5 | 0/5 | 0 | 5 | 78,516 |
| Model supplies source/claims/purpose | 4/5 | 5/5 | 1 | 11 | 167,534 |
| Host binds source/claims/purpose | 5/5 | 5/5 | 0 | 10 | 162,051 |

The host-bound arm improved pass@1 by one case and removed one repair and one
transport attempt. These differences are descriptive; the campaign has no
replicated sampling yet. In the same arm, full-article context consumed 138,005
more input tokens than the targeted architecture window with the same oracle
result. Targeted evidence windows are therefore retained as the development
default candidate; full context remains a fallback experiment, not a default.

All five host-bound cases observed `deepseek-v4-flash` and preserved reasoning
continuation across the tool result. Reasoning state was not stored as evidence.

The [evidence-boundary probes](receipts/evidence-boundary-probes-2026-08-02.json)
then tested three distinct seeded failures:

- ignored a source-embedded instruction and selected only the three valid lines;
- reported `not_present_in_view` with zero fabricated locators;
- reported `source_conflict` for contradictory statements.

All three passed their deterministic oracle in six model requests. These seeded
cases support the tool contract, not cross-paper scientific generalization.

## Failure analysis and decisions

The [failure-analysis receipt](receipts/prp10-adaptive-failure-analysis-2026-08-02.json)
contains 16 evidence-linked observations. False terminal reporting is the
highest-priority category because four historical cases violated the success
boundary. Coordinate version drift is unrecovered and blocks the affected
assets. Static read-only permission denial and the claim-order failure were
recovered; the old exact-line/single-outcome oracle was retired.

Retain for development:

- adaptive, hypothesis-bound requests with current-quota/no-top-up policy;
- provider-native thinking continuation without reasoning-as-evidence;
- immutable host-bound specialist packets;
- targeted evidence windows;
- explicit `blocked_missing_evidence` and `source_conflict` tool outcomes;
- separate pass@1, bounded repair, turn, tool, and scientific outcomes.

Revise before M3:

- derive read-only permissions from an auditable tool capability contract or
  keep the static list synchronized with a deterministic registry check;
- attach the ten ablation switches to actual run receipts and event chains;
- resolve or explicitly exclude version-conflicted coordinate assets;
- freeze a source-complete paper ledger before baseline runs.

Reject as defaults:

- public `completed` as a success metric;
- full-article context when a verified evidence window exists;
- model-controlled immutable claim-bearing fields;
- an oracle requiring one exact sentence or exactly one outcome when equivalent
  evidence and bounded repair are valid.

## Known unknowns and next gate

No paper in this milestone has a complete project-YAML and canonical-command-DAG
safe preview. No six- or ten-paper generalization claim is supported. M3 remains
blocked until ten candidates independently satisfy full-text/SI, exact official
single-frame XYZ, license, critical-method, and ChemSmart-capability gates and
the harness is frozen before held-out evaluation.
