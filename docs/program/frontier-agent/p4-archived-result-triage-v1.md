# P4 archived-result triage v1

## Status

Closed as a read-only negative-result triage. It inspected committed
parser-regression bundles only. None is admitted as a Frontier chemical result,
and P4-CH-01/P5-RG-05 remain red.

## Objective

Determine whether the existing checkout contains a native or archived result
package that can safely clear the P4 chemical-result stop without running an
engine or constructing new scientific evidence. The required boundary is
stricter than successful parser input: a candidate must bind stable task and
geometry identity, method/settings, input/output hashes, environment/execution
provenance, parsed value and units, physical diagnostic, stoichiometric result,
approval provenance, and an independent recomputation path.

## Inputs

| Input | Required use |
| --- | --- |
| Frozen [P4 chemistry finding](reviews/p4-chemistry-findings-v1.json) | Preserve the exact P4-CH-01 stop criterion and independent-recomputation requirement. |
| Frozen [P4 close receipt](receipts/p4-evidence-expert-review.json) and [failure ledger](receipts/p4-failure-ledger.json) | Preserve P3-C2/P3-C3 unresolved status and the no-engine authority boundary. |
| Committed ORCA and xTB water parser-regression bundles | Inspect hashes and role only; do not parse, execute, or turn their values into a Frontier claim. |

## Tools and authority

- Allowed: repository-local filename/hash inventory, explicit test-fixture role
  classification, a deterministic admission checklist, and focused receipt
  integrity validation.
- Not allowed: invoking an engine, parsing a result into a new scientific
  value, running independent recomputation, changing a committed archive,
  emitting a chemistry result, provider/API use, scheduler use, install,
  commit, push, or P3/P5/P6 claim promotion.

## Budget

| Resource | Ceiling | Observed |
| --- | ---: | ---: |
| Candidate bundles inspected | 2 committed development bundles | 2 only |
| Native parser/result execution | 0 | 0 |
| Engine or independent recomputation | 0 | 0 |
| New parsed values or chemical claims | 0 | 0 |

## Candidate inventory and decision

| Bundle | Present committed files | Classification | Admission decision |
| --- | --- | --- | --- |
| ORCA water optimization | Input, output, geometry, gradient, and Hessian under `tests/data/ORCATests/` | Parser-regression development fixture | Rejected for Frontier evidence: no P3 task/approval/environment/execution receipt or independent recomputation. |
| xTB water frequency-support | Geometry, output, optimized geometry, gradient, and frequency-support output under `tests/data/XTBTests/` | Parser-regression development fixture | Rejected for Frontier evidence: no P3 task/approval/environment/execution receipt or independent recomputation. |

The files may be useful as a future provenance-audit corpus. They do not
retroactively become P3 artifacts merely because they look like program output
or are exercised by parser tests. No numerical value, diagnostic, method claim,
or chemical conclusion is repeated in this triage.

## Gates

| Gate | Current status | Evidence boundary |
| --- | --- | --- |
| P4A-G1 candidate hash inventory | Passed read-only | Two bounded candidate bundles have pinned committed-file hashes. |
| P4A-G2 development-fixture classification | Passed read-only | Both bundles reside under `tests/data/` and lack a Frontier evidence receipt. |
| P4A-G3 P3-result non-admission | Passed read-only | Neither bundle can update P3-C2/P3-C3 or P5-RG-05. |
| P4A-G4 independent recomputation | Unresolved | No separately authorized input/environment/recompute path was used. |
| P4-CH-01/P5-RG-05 | Red unchanged | No task-bound, approved, independently recomputable Frontier result exists. |

## Failure, hypothesis, and minimal-change ledger

| ID | Failure | Hypothesis | Minimal change | Evidence | Result | Limitation | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P4A-F1 | A native-looking test output could be misread as an authorized Frontier calculation. | Test-fixture role and hashes alone cannot bind output to P3 task, approval, or execution provenance. | Create this negative triage only; do not parse or reclassify a candidate. | Candidate paths/hashes plus P4-CH-01's stricter trace requirements. | Both candidates are explicitly non-admissible. | The triage does not prove either bundle's historical origin or chemical validity. | Replace only with a new artifact receipt that binds every required provenance field. |
| P4A-F2 | A parser-exercised bundle lacks an independent recomputation receipt. | Parsing a file can establish parser behavior but not a scientifically reliable result. | Retain P4A-G4, P4-CH-01, and P5-RG-05 as unresolved/red. | P4 review/failure records and absence of a task-bound recomputation record. | No value, unit, or reliability claim is emitted. | A future audited archive still requires separately authorized recomputation. | Do not promote without inputs, environment, diagnostics, and independent reproduction. |
| P4A-F3 | Bulk repository output scanning would mix success, error, synthetic, and unrelated fixtures. | A bounded two-bundle inventory prevents a test corpus from becoming accidental evidence. | Inspect only the two named water bundles and retain all others out of scope. | Repository role/path audit. | No broad archive admission occurs. | Other candidate files may merit a later review but remain unexamined here. | A later audit must be separately scoped and hash-pinned. |

## Blockers

- A legitimate result trace needs a separately authorized task and approval,
  stable geometry/frame and units, method/settings, input/output/environment
  hashes, parsed observable and unit, convergence or frequency diagnostic,
  stoichiometric result, and independent recomputation.
- Test-data outputs cannot satisfy that trace without an append-only evidence
  package and an explicit decision that their provenance is sufficient. No such
  authority or package exists.
- This does not change provider, held-out, executor, trial, replication,
  training, paper, release, or SOTA gates.

## Phase-close validation

One dedicated receipt validator checks source/candidate hashes, rejects any
claimed admissibility, and confirms that P4/P5 red gates remain unchanged. It
does not parse or execute the archived output.

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_p4_archived_result_triage.py -q
```

## Claim-evidence ledger

| ID | Claim type | Statement | Status |
| --- | --- | --- | --- |
| P4A-C1 | source observation | Two bounded committed water bundles exist as parser-regression development artifacts. | Supported by paths and hashes only. |
| P4A-C2 | inference | Either bundle is a task-bound, approved, scientifically valid Frontier result. | Rejected. |
| P4A-C3 | unresolved uncertainty | Either bundle can be independently recomputed with sufficient provenance. | Unresolved. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- |
| P4A-D1 | Do not parse numerical values in the triage. | A parsed value without task provenance would look like a result claim. | A future authorized archive package may parse a fixed allowlisted observable. |
| P4A-D2 | Keep candidate paths under a development-fixture classification. | Their location and missing Frontier receipt prevent evidence admission. | A later receipt must separately show task/approval/environment/recompute provenance. |
| P4A-D3 | Treat the negative result as a P4 safety finding, not evidence against ORCA/xTB. | Missing provenance limits admissibility, not scientific truth. | Do not infer a program-quality conclusion from this triage. |
