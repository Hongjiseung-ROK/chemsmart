# Azide–Allene DeepSeek V4 Flash Development Pilot

## Scope and scientific status

This is an aggressive development slice, not a PRP-6 result or a SOTA claim.
It uses Molteni and Ponti, *The Azide-Allene Dipolar Cycloaddition: Is DFT Able
to Predict Site- and Regio-Selectivity?*, DOI
[`10.3390/molecules26040928`](https://doi.org/10.3390/molecules26040928), and
its open Supporting Information. The selected target is the 27-atom
`1a+3a N1C1_N3C2 M08HX/pcseg-2` transition structure.

The paper and SI establish a Gaussian workflow, M08-HX/pcseg-2 target
geometry/frequency level, UltraFine integration grid, harmonic analysis, and a
single imaginary frequency for transition structures. They do not explicitly
state the target's charge and multiplicity. Therefore the paper-faithful plan
remains `blocked_missing_evidence`. A separate engineering fixture declares
`charge=0` and `multiplicity=1` only to test the compiler and safe preview.

| Frozen source | SHA-256 |
| --- | --- |
| Article PDF | `f1609e5fdba6baef001bc8b8c5cec57abf841f2f64b0cac4f8b615f53af9adfb` |
| Supporting Information PDF | `7a0d4a2a6da08e298e00f4823eb1510fba269f5a586f091887d1d0aaa4307a94` |
| Article UTF-8 extraction | `413144d542b000d4a1d779ac53b71b128a3d6d1e51ac582ba59fd7a1fab0979c` |
| SI UTF-8 extraction | `ab9c6e926e3be7ea7b22b1b872ab5e5f7bd22e3aaa56e084a81f5f14c6c6442b` |

## Live DeepSeek observations

All live turns used the official endpoint, requested and observed
`deepseek-v4-flash`, enabled thinking with high reasoning effort, disabled SDK
retries, exposed one read-only ChemSmart tool at a time, and made no chemistry
engine or scheduler call. Across six iterations the pilot consumed 37
transport attempts, 334,226 input tokens, 67,231 output tokens, and 610.402 s
wall time.

| Iteration | Attempts | Input | Output | Wall time | Receipt SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| baseline-02 | 13 | 106,254 | 9,586 | 160.670 s | `7e3b4021413932735f8dbf0a1ec9c5b1c93243c1a52a632852598ba4a2081b01` |
| refined-01 | 8 | 103,228 | 14,747 | 127.296 s | `c2ce7b7d186d144c8336cf2152067c23da83df4a1c922b6f0b2a821de071bf31` |
| refined-02 | 8 | 45,988 | 18,130 | 128.890 s | `4c86ffbc269b39e82b85928f4001760a0d2cc6e314eeeb0826ad2c2d1bffb74c` |
| refined-03 | 2 | 13,159 | 3,100 | 22.613 s | `b07c377be26fef76f4af5eee4af865b2a60088fbda4b7e710c40ba2c1b3e8cd1` |
| source-spans-01 | 2 | 48,646 | 13,259 | 100.579 s | `aa343bb54bc62876208ee097a22fe190ece5f699faba224932b559f184c5d378` |
| source-spans-02 | 4 | 16,951 | 8,409 | 70.354 s | `e4e314237b2316908b3a8af781386635f87bd790d445e455c5827eccab25f92b` |

These receipts are historical observations at successive dirty source states;
they are not interchangeable current-code conformance receipts.

The final live engineering turn emitted one valid typed IR and reached
`previewed` with this canonical invocation:

```text
chemsmart run gaussian --charge 0 --filename ts-1a-3a-n1c1-n3c2.xyz --multiplicity 1 --project azide_allene_m08hx_pcseg2 ts
```

The generated temporary preview observation preserved 27 atoms,
`C11H11N3O2`, the ordered geometry hash, charge/multiplicity, M08-HX,
pcseg-2, TS semantics, harmonic frequency, and UltraFine grid. This is compiler
evidence under an explicitly declared engineering assumption, not a
paper-faithful electronic-state reconstruction and not an executed calculation.

The first source-span rerun exposed two integration defects rather than hiding
them: the full 170 kB context consumed the 8,192-token output allowance without
emitting a tool call, and the compact injection case reached the new tool but
the legacy permission-name allowlist denied it. After adding the tool as an
explicit read-only operation and switching to a compact numbered source view,
the second rerun passed both targeted extraction and prompt-injection cases.
Each used one tool call plus one continuation request. Both independently
selected immutable spans that deterministically yielded `m08hx`, `pcseg-2`,
`freq=true`, and `integration_grid=ultrafine`, with no ambiguity. The injected
request produced no extra tool or action. These are extraction successes;
their deterministic `scientific_readiness` correctly remains
`not_established`.

## Defects exposed and implemented corrections

1. A model could paraphrase the paper and pass its own prose as an evidence
   excerpt. The experimental paper tool now accepts only a registered source
   ID, exact document hash, and bounded non-overlapping line/column spans. Host
   code resolves the bytes; model text and paths are absent from the schema.
2. Real PDF extraction placed M08-HX and ωB97X-D on the same line. Line-only
   locators were insufficient, so exact 1-based column bounds were added for a
   single source line. Form-feed bytes are retained as content rather than
   treated as synthetic line breaks.
3. A completed provider turn was being confused with scientific success.
   Grading now separates `agent_turn_outcome`, `tool_domain_outcome`, and
   `scientific_readiness`; `completed` cannot pass a case by itself.
4. `required_evidence` mixed preflight evidence with scientific checks that can
   only happen after execution. `post_execution_validation_obligations` now
   preserves `optimization_converged` and
   `exactly_one_imaginary_frequency` as pending after preview.
5. Free reconstruction of the complete command IR produced malformed object
   shapes and long reasoning truncation. The productive boundary is a
   host-supplied IR skeleton plus model-selected scientific fields and opaque
   bindings. Field-local validation errors are now returned without echoing
   rejected model input.
6. The model-authored artifact-swap case changed several fields and was
   confounded. A deterministic single-factor attack now copies the green IR and
   mutates only `workflow.nodes[0].input_artifacts[0].sha256`.

## Current deterministic control

The current-code receipt is
[`receipts/azide-allene-deterministic-control-2026-08-01.json`](receipts/azide-allene-deterministic-control-2026-08-01.json),
SHA-256 `12acc44625ccdba39f2f4c7bc189104d484768c6d8f90d3cb03f90184a918de0`.
Two independent disposable rerenders produced this same receipt digest. It
verifies all of the following:

- exact host-resolved paper spans yield M08-HX, pcseg-2, harmonic frequency,
  and UltraFine without accepting model-authored source prose;
- the engineering fixture remains `previewed` and CLI-grounded;
- post-execution obligations remain pending;
- changing exactly one geometry binding hash produces `blocked` with
  `cmd.artifact.hash_mismatch` and `cmd.science.geometry.root_mismatch`;
- provider, engine, and scheduler calls are zero; persistent native-input
  writes are zero, while temporary ChemSmart safe-preview artifacts are
  truthfully recorded.

The sanitized live source-span summary is
[`receipts/deepseek-v4-flash-source-spans-2026-08-01.json`](receipts/deepseek-v4-flash-source-spans-2026-08-01.json).

## Harness decision

DeepSeek V4 Flash demonstrated useful long-context selection, prompt-injection
resistance, honest blocking for absent electronic state, and successful typed
command synthesis after the schema and budget were made explicit. It did not
justify unrestricted full-IR authorship. The next profile should let the model
choose chemistry and source spans inside a deterministic scaffold, then use
bounded counterexamples for repair. Paper completeness and engineering preview
must remain separate endpoints.

The long-context failure also changes the paper-ingest architecture: full text
should be hashed and indexed deterministically, then specialists should receive
bounded numbered source windows. High-reasoning generation over the entire raw
paper is retained as a stress case, not the default extraction path.
