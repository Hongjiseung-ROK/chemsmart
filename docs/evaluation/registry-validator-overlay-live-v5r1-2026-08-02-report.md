# Registry Validator Overlay V5r1 Live Report

## Verdict

V5r1 did not establish a reliable default harness profile. One of six runs
passed every deterministic proposal oracle, but Runtime V2 then falsely
blocked that correct run. The campaign therefore has **zero strict end-to-end
successes**. Five runs produced accepted typed submissions, one run produced no
submission, and the evidence-bound outcome contract correctly downgraded five
runs to `failed`.

This is a development result only. No Gaussian, ORCA, or xTB engine was run;
no command, native input, project file, or scheduler job was produced.

## Frozen evidence

- Source commit: `61bbdf6dd776c6a10020c09026a26dc50851920a`
- Model observed on every request: `deepseek-v4-flash`
- Campaign-plan artifact SHA-256:
  `51c007464de721532511a8bef94a991959f285da3f1bd694bf7ea7aac3cf6e50`
- Campaign-plan semantic SHA-256:
  `a9c24e19b34658f8b7008c5fd3c431578083d520168dfa2a5cdddf1e03afd524`
- Campaign-receipt artifact SHA-256:
  `2f2f79c6387c04c9f4ef6e82ac0c61135a92b8beb01ea00d5efec9f764a6dc86`
- Campaign-receipt semantic SHA-256:
  `232be0e16b656504729df634142ccaf951467874b7f043d824615a5a9c001de5`
- Whole-public-artifact manifest SHA-256:
  `45837d5f390752ac3cc61a29a5f50ac836e2b250843b133dee75e76a341b828b`
- Private evidence manifest SHA-256:
  `bf4757bf48fc92dc398f5f7072004c51216adcbdce95cfc34cdf391714ebfc1f`

The public manifest binds all 32 original public campaign files, including the
outer outcome records that contain provider observations. A separate private
manifest binds 36 access-restricted session artifacts. Private artifacts are
not publication evidence and are not committed.

## Aggregate observations

| Metric | Observation |
|---|---:|
| Runs | 6 |
| Transport attempts | 21 |
| Input tokens | 192,787 |
| Output tokens | 37,443 |
| Cumulative wall time | 283,680 ms |
| Accepted submissions | 5 |
| Rejected submissions | 3 |
| Deterministic proposal passes | 1 |
| Strict runtime-plus-proposal passes | 0 |
| Engine, HPC, project-write, native-input actions | 0 |

All request bindings, model identities, tool schemas, archived comparators,
event chains, deterministic replays, public projections, artifact hashes, and
submit counts reconciled. Current credential values and hidden-reasoning keys
were absent from the 68 audited public and private files. All 32 public files
passed the absolute-path guard.

## What the model learned correctly

The request-bound evidence substantially improved literal scientific fact
extraction. In every accepted basis case, the element facts matched the pinned
BSE observation. The responses correctly reported, among other facts, that:

- `def2-TZVPPD` contains Pd orbital functions and a 28-electron Pd ECP but
  lacks Ce coverage in the pinned definition;
- `def2-ECP` is ECP-only for Pd and therefore lacks the orbital functions
  required when it is proposed as the sole basis; and
- the pinned `def2-TZVP` definition supplies Cl/Fe orbital functions without
  an Fe ECP.

This supports retaining request-bound basis evidence. It does not establish
scientific suitability, engine execution, or cross-paper generality.

## Defects exposed

1. **Model-inferred readiness ontology.** The same literal conflict was mapped
   by the model to adjacent but non-equivalent readiness labels. Readiness must
   be a deterministic projection of replayed evidence, not a model guess.
2. **Scientific-intent mutation.** The model repeatedly changed
   `ecp_intent: null` to `not_applicable`; one run normalized source literal
   `B3LYP` to `b3lyp`. Null means no applicability claim was supplied and is
   not equivalent to a scientific not-applicable assertion.
3. **Opaque serialization delegated to the model.** Three first submissions
   failed only because the model did not sort EvidenceRef digests. The host
   should own canonical serialization.
4. **Verbose evidence exhausted thinking output.** The Pd continuation ended
   with `finish_reason=length`; all 8,192 output tokens were reasoning tokens,
   leaving no assistant content or submit call. The loop nevertheless marked
   the empty turn complete before the post-run grader corrected the outcome.
5. **Free-text phase misrouting.** The token `project-readiness` was interpreted
   as a request to read a workspace project. Two cases were therefore forced
   through an unavailable `read_project_yaml` completion gate. Four other cases
   were routed as execution merely because the prohibition sentence contained
   the word `execution`.
6. **Inner-receipt provenance gap.** V5r1 stored provider observations outside
   the signed inner outcome. The added whole-artifact manifest closes the
   archival byte-binding gap, but the next outcome schema must bind provider
   observations directly and the campaign receipt must bind outer outcome
   bytes.

## Retain, revise, reject

- **Retain:** replayed request-bound BSE evidence, typed-project loader
  evidence, unpredictable observation receipts, deterministic grading, public
  event projection, and the prohibition on model-authored native inputs.
- **Revise:** expose one compact, content-addressed validator decision; include
  immutable typed settings; use one causal observation receipt; bind provider
  observations; fail closed on truncated output; and require an accepted
  experiment submission for a successful terminal state.
- **Reject:** verbose duplicate receipt payloads, model sorting of opaque
  digests, model-selected readiness labels, and free-text phase inference as an
  experiment completion authority.

The next paired campaign reuses only the five failed V5r1 cases. It changes the
model-facing evidence projection while retaining the same underlying receipts,
model, reasoning mode, task text, setting registry, and deterministic outcome
oracles.
