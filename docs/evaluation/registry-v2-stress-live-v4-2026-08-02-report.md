# Registry V2 Stress Campaign V4

Date: 2026-08-02 KST

Status: completed development experiment; not a held-out generalization or
SOTA result.

## Evidence boundary

The immutable campaign evidence is in
[`receipts/registry-v2-stress-live-v4-2026-08-02/`](receipts/registry-v2-stress-live-v4-2026-08-02/).
The campaign plan digest is
`23353fa15348bcbdeee5dde1a4f92d6ddd72efb7744bee5e901e3b59878a6b87`,
the campaign receipt digest is
`edadd44587cb0e4006a98fd6a12ae0631e55222d55209115d5306994ba4e3ba1`,
and the reconciliation digest is
`dcb157a9a712e2a547b86ada24c6c8ed1d7c0425c5b5f677e0e3c587b1c1b6f6`.
The experiment used source commit
`1674b70be3c5e8b5d4908ca4fbab1c960c1dc807` and observed model
`deepseek-v4-flash` with thinking enabled. Provider-private reasoning is not
part of the scientific evidence.

All 44 preregistered runs finished after 121 transport attempts. They consumed
881,806 input tokens and 278,633 output tokens over 2,580,922 ms. The matrix,
not quota exhaustion, ended the campaign. Verification covered 44 typed
outcome contracts, 132 response/tool-trace/event artifacts, and 44 Runtime V2
hash-chain replays. No engine, HPC, project-write, native-input, secret-value,
credential-shape, or private-reasoning event was observed.

## Observed results

| Arm | Runs | Raw pass | Set-order semantic pass | Accepted pass | Normalizer-dependent |
| --- | ---: | ---: | ---: | ---: | ---: |
| Minimal | 14 | 0 | 0 | 2 | 2 |
| Registry V1 | 14 | 1 | 1 | 2 | 1 |
| Registry V2 | 14 | 2 | 3 | 9 | 7 |
| Registry V2 plus advisory pack | 2 | 0 | 0 | 1 | 1 |

Registry V2 produced a development gain in accepted outcomes, but the raw
contract evidence is much weaker than 9/14. Seven accepted V2 outcomes needed
the case-bound normalizer, six needed explicit-setting binding, and one needed
set-order normalization. Registry V2 therefore remains experimental rather
than a default-ready model interface.

The strongest positive examples were:

- Gaussian `B3LYP/pcseg-2`: the English response correctly separated BSE name
  discovery from materialization and observed B3LYP through the repaired
  registry sidecar. It passed raw, semantic, and accepted grading.
- ORCA `B97M-D4/def2-SVP`: the V2 response preserved the compound functional
  and passed all three grades.
- ORCA `ma-def2-TZVP`: V1 passed directly; V2 passed semantic and accepted
  grading after set ordering was canonicalized.

The most consequential failures were:

- Every Fe, Pd, Ce, and ECP-only case lacked a model-visible request-bound
  element receipt. Responses either encoded an unknown element fact as false
  or, in one contained repair, asserted a 28-electron Pd ECP without tool
  evidence. The deterministic grader did not accept these claims.
- The Gaussian separate-D4 case showed that a non-exhaustive registry cannot
  decide actual ChemSmart project support. The model blocked it as merely
  unverified even though the deterministic project renderer already classified
  it as unsupported.
- The advisory knowledge pack did not improve either eligible case over V2.
  One response regressed from a raw pass to a normalizer-dependent pass, and
  the other introduced a malformed submission. It remains opt-in.
- One malformed JSON submission and three schema-validation errors were
  observed. Typed recovery failed closed: no malformed tool executed and no
  permission was consumed. One `tool_request_rejected` event was recorded.

## Metric corrections and retained changes

The V4 exactly-one metric counted rejected submit attempts as submissions.
A post-hoc success-only regrade affected three runs but changed no accepted
outcome. V4 remains immutable; future campaigns count only successful typed
submissions.

Retain case-bound lookup schemas, the additive Gaussian B3LYP registry repair,
and fail-closed malformed-tool recovery. Revise the V2 model surface before
default adoption. Do not retain the advisory pack as a default.

## Next causal experiment

The next paired experiment changes one authority at a time:

1. expose a request-bound, content-addressed BSE element/ECP receipt and require
   every submitted element fact to cite that receipt;
2. expose a content-addressed project-render and required-job semantic receipt
   as the authority for actual ChemSmart project readiness; and
3. compare the unchanged V2 arm with V2 plus those deterministic receipts on
   the failed element and unsupported-setting cases.

The safety ceiling remains read-only validation and safe preview. Chemistry
engines, schedulers, native-input authoring, and project writes remain disabled.

## Known provenance defect

The exact public event copies retain an absolute repository path in the 44
`session_started` payloads. This is not a credential or scientific-evidence
failure, but it is an unnecessary host-provenance disclosure. The immutable V4
events remain unchanged for replay; future public projections must replace the
host path with a repository identity while retaining a private exact event
stream.
