# Scientific Settings Registry × Domain Knowledge Pack: Live Development Result

## Status

This is a transported, thinking-enabled DeepSeek V4 Flash **development**
ablation over three project-planning cases. It is not a paper-reproduction,
execution, held-out generalization, or SOTA result. The immutable raw campaign
is [preserved here](receipts/settings-knowledge-live-v2-2026-08-02-r2/campaign-receipt.json).
The [additive reconciliation receipt](receipts/settings-knowledge-live-v2-2026-08-02-r2-reconciliation.json)
owns corrected exposure and readiness metrics because two derived fields in
the raw receipt were defective.

The campaign exercised:

- `S`: model-visible ScientificSettingsRegistry inspection, off/on;
- `K`: model-visible DomainKnowledgePack inspection, off/on;
- ORCA 6.1 B3LYP/ma-def2-TZVP/D3BJ;
- Gaussian 16 M08-HX/pcseg-2/UltraFine; and
- xTB 6.7.1 GFN2-xTB/ALPB water.

Every run used Runtime V2, a case-bound read-only tool surface, the same
English prompt for a case, deterministic project-YAML rendering and loading,
semantic round-trip grading, and replay-verified terminal events. No
coordinate, command, project file, native engine input, chemistry calculation,
or scheduler job was created or executed.

## Confirmed observations

| Arm | Passed / runs | False-ready | False-block | Transport attempts | Total tokens | Summed latency |
|---|---:|---:|---:|---:|---:|---:|
| S0K0 | 1 / 3 | 0 | 1 | 3 | 14,911 | 69.718 s |
| S0K1 | 2 / 3 | 1 | 0 | 6 | 23,794 | 51.827 s |
| S1K0 | 3 / 3 | 0 | 0 | 6 | 19,830 | 27.023 s |
| S1K1 | 3 / 3 | 0 | 0 | 6 | 26,034 | 38.843 s |

All 12 runs reached one replay-valid terminal event, all 21 provider
transports reported `deepseek-v4-flash`, and all public artifact hashes,
run-record hashes, outcome contracts, and regraded oracle sets verified.
Reasoning continuation was observed in all nine tool-using runs. The campaign
recorded zero engine calls, HPC calls, project writes, and native-input
authoring.

Across the 36 explicit setting fields, 34 were exact. Project loading and
project semantic equivalence each passed 10/12 runs. The two losses were both
the xTB `gfn_version="2"` representation in registry-disabled arms.

Case-level behavior was more informative than the aggregate:

1. **ORCA:** the unassisted arm preserved all values but conservatively
   returned `blocked_missing_evidence`; either registry or knowledge exposure
   led to the correct `project_candidate` state.
2. **Gaussian:** every arm preserved the values and correctly blocked because
   the current registry verifies `pcseg-2` but not M08-HX or UltraFine. The
   general knowledge catalog had no applicable Gaussian pack.
3. **xTB:** both registry-enabled arms emitted canonical `gfn2` and correctly
   blocked on unverified ALPB/water. Both registry-disabled arms emitted the
   noncanonical value `2`; the knowledge-only arm additionally declared an
   invalid `project_candidate`, producing the campaign's only false-ready.

## Supported interpretation

The ScientificSettingsRegistry is retained as a
`development_default_candidate`. Across this small block it changed the
combined settings-off result from 3/6 to settings-on 6/6 and removed the xTB
representation error. This is evidence that a typed canonical setting value
is useful at the model boundary; it is not yet evidence of cross-paper
generality.

DomainKnowledgePack exposure is **not** retained as an unconditional default.
With registry exposure already enabled, it improved no oracle outcome while
increasing total tokens from 19,830 to 26,034 (1.31×) and summed latency from
27.023 s to 38.843 s (1.44×). Without registry exposure it helped the ORCA
readiness decision but did not supply the canonical xTB representation and
coincided with a false-ready. The pack should remain a scoped advisory module
whose activation explicitly cannot establish setting validity or readiness.

The smallest safe supported profile after this block is therefore:

`ScientificSettingsRegistry on + DomainKnowledgePack off by default`, with a
knowledge pack exposed only when a deterministic router finds an applicable
pack and the registry remains the setting/readiness authority.

## Defects discovered and corrected

The raw campaign's per-run `exposure_use.offered` used a stale preparation-loop
variable. Condition membership itself is still bound by each content-addressed
`run_spec.exposure`, the model-visible tool-schema hash, and the public tool
trace. The reconciliation derives `offered`, `requested`, and `succeeded` from
those authorities.

The raw arm summary also labeled every readiness mismatch `false_ready`. This
conflated the conservative ORCA false-block with the unsafe xTB false-ready.
The grader now emits `correct`, `false_ready`, `false_block`,
`wrong_block_state`, or `wrong_terminal_state`, and the reconciliation uses
that classification. The raw files were not rewritten.

Two earlier launch attempts remain diagnostic-only:

- the first stopped before transport because preregistration omitted Runtime
  V2's mandatory virtual `ask_user` schema; and
- `r1` transported but skipped every model tool call because the retry-budget
  semantics rejected the first occurrence.

Neither attempt contributes model-quality or treatment-effect evidence.

## Unknowns and next experiment

Three hand-selected settings cases do not reveal whether the registry benefit
persists across aliases, near-miss literature spelling, version boundaries,
ECP/element coverage, state ambiguity, or multi-project paper plans. The pack
interaction is also confounded by eligibility: the current catalog activated
for ORCA and xTB but not Gaussian.

Exact public reconstruction of nine continuation requests is intentionally
unavailable because DeepSeek reasoning state remained ephemeral. Their public
messages, tool requests/outcomes, provider observations, and Runtime V2 event
streams are retained and hash-verified, but hidden reasoning is not evidence.
The campaign also began before its uncommitted runner source was
content-addressed; current-source reconstruction supports the findings but is
not exact generation-source provenance. Future launches must bind the source
tree/diff digest before the first transport.

Before PRP-10, run a new development stress block with unique hypotheses and
fixed deterministic oracles. Stratify applicable and inapplicable packs, test
exact alias versus fuzzy candidate versus unknown setting states, and include
at least one transition-metal basis/ECP case and one solvent-model case. The
primary question is whether the registry-enabled minimal profile prevents
false-ready while preserving explicit literals. The revised knowledge arm
must expose its new authority ceiling and must not treat pack activation as
evidence that a setting is registered.

Adopt a component only after the new block has zero false-ready, zero semantic
round-trip loss, replay determinism, and no safety-plane violations. Keep
PRP-10 frozen until that gate is satisfied.
