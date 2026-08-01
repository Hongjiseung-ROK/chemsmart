# P1 AiiDA primary-source addendum v1

## Status

Closed qualified source refresh at 2026-07-31T20:34:18Z. This append-only
record adds a narrow, page-located version-of-record observation for AiiDA. It
does not rewrite the frozen P1 literature receipt or failure ledger, normalize
provider configuration, establish correction/retraction clearance, or change
any P3–P6 decision.

## Objective

Resolve only the prior P1 primary-passage gap for the AiiDA record with an
accessible publisher version of record. Admit at most a qualified architectural
precedent for evidence/provenance design, while retaining the explicit
correction-status and ChemSmart-claim limitations.

## Inputs

| Input | Required use |
| --- | --- |
| Frozen [P1 literature receipt](receipts/p1-literature-evidence.json) | Preserve its original unresolved AiiDA record and source-review budget. |
| Frozen [P1 failure ledger](receipts/p1-failure-ledger.json) | Retain P1-F3/P1-F4 rather than erase inaccessible-source or correction-status history. |
| [P1 post-P3 addendum](p1-post-p3-live-evidence-addendum-v1.md) | Keep provider configuration/tool-loop gates entirely separate from this literature refresh. |
| [AiiDA version-of-record PDF](https://www.nature.com/articles/s41597-020-00638-4.pdf) | Locate the primary publisher passages without retaining the PDF or copying its text. |
| Public Crossref metadata record | Record only a limited `update-to`/policy observation; never infer global correction or retraction clearance. |

## Tools and authority

- Allowed: one public publisher-PDF review, one public Crossref metadata
  observation, local hash/receipt validation, and one focused offline receipt
  test.
- Not allowed: credentialed APIs, Elsevier access, provider completions,
  discovery snippets as evidence, full-text retention, engine/scheduler work,
  dependency installation, commit, or push.

## Budget

| Resource | Ceiling | Observed |
| --- | ---: | ---: |
| Publisher primary-source retrieval | 1 | 1 |
| Public Crossref metadata request | 1 | 1 |
| Credentialed source/API requests | 0 | 0 |
| Discovery snippets used as evidence | 0 | 0 |
| Full-text/PDF copies retained | 0 | 0 |
| Focused offline receipt test | 1 | 1 |

## Primary-source record

| Field | Observation |
| --- | --- |
| Record | AiiDA 1.0, DOI [`10.1038/s41597-020-00638-4`](https://doi.org/10.1038/s41597-020-00638-4). |
| Publisher source | Nature *Scientific Data* version-of-record PDF linked above. |
| Passage locator 1 | PDF p. 1, unheaded front-matter abstract immediately before **Introduction**: automatic storage/preservation of full provenance in a queryable and traversable form. |
| Passage locator 2 | PDF p. 1, same front matter: workflow automation, error handling, and a plugin model for external simulation-software interfaces. |
| Passage locator 3 | PDF p. 2, **Architecture Overview**: calculation/workflow runs are automatically recorded in the provenance graph. |
| Narrow proposition | The authors describe automated workflow/calculation provenance recording with queryable/traversable records, workflow error handling, and external-code interfaces. This is a qualified architectural reference for Runtime V2 evidence/provenance boundaries. |

No text passage is copied into this repository. The proposition is deliberately
about the authors' described architecture, not an assertion that ChemSmart has
the same properties.

## Correction and retraction boundary

On 2026-08-01, the public Crossref works record reported `update-to` as null,
ordinary reference relations, and a Springer Crossmark update-policy link. That
is a current metadata observation only. No named independent
correction/retraction authority was verified, so the observation does **not**
establish that no correction, expression of concern, or retraction exists.

Accordingly, this addendum changes the AiiDA item only from an inaccessible or
insufficient-passage record to a **qualified source reference with unresolved
global correction status**. P1-G4 remains mixed; it is not a blanket literature
pass.

## Artifacts

- [Machine-readable addendum receipt](receipts/p1-aiida-primary-source-addendum-v1.json)
  pins the historical P1 artifacts, locators, limited metadata observation,
  claim classifications, and source hashes.
- [Dedicated validator](../../../scripts/review/validate_frontier_p1_aiida_primary_source_addendum.py)
  rejects source-hash drift, P1 gate promotion, raw-source/secret retention,
  and an asserted correction clearance.

## Gates

| Gate | Current status | Reason |
| --- | --- | --- |
| P1-G4 AiiDA passage support | Qualified | An accessible publisher PDF supports the narrow stated design precedent. |
| P1-G4 correction/retraction status | Unresolved | Current Crossref fields and a publisher policy are not a named independent authority. |
| P1-G4 overall literature gate | Mixed | This source does not cure the unresolved El Agente Q/DynaMate records or global correction-status gap. |
| P1-G3 provider configuration/tool surface | Red/unchanged | Literature evidence neither normalizes configuration nor repairs the P3 strict failure. |
| P5/P6 eligibility | Red/no-go unchanged | A literature source is not a provider capability, held-out trial, chemistry result, replication, training, or release result. |

## Blockers

- The AiiDA source cannot establish immutable lineage, restartability,
  ChemSmart correctness, physical validity, performance, reproducibility, or
  SOTA.
- A named independent correction/retraction authority remains unavailable in
  this bounded refresh.
- El Agente Q and DynaMate remain unresolved without accessible primary
  publisher passages and correction-status routes.

## Phase-close validation

The one focused close test runs the dedicated hash/claim-scope validator:

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_p1_aiida_primary_source_addendum.py -q
```

It validates the additive evidence record only. It is not a source-independent
correction clearance, model/provider test, chemistry calculation, ablation,
replication, paper, training, release, or SOTA validation.

## Claim-evidence ledger

| ID | Claim type | Statement | Status |
| --- | --- | --- | --- |
| P1A-C1 | source observation | The publisher version-of-record has the three stated page/section locators. | Supported by primary-source locators. |
| P1A-C2 | literature statement | AiiDA is a qualified architectural provenance/workflow reference for Runtime V2 design. | Qualified; external precedent only. |
| P1A-C3 | correction-status inference | The record has no correction, expression of concern, or retraction. | Rejected; no named independent authority supports it. |
| P1A-C4 | inference | The source supports a ChemSmart capability, chemistry, reproduction, or SOTA claim. | Rejected. |
| P1A-C5 | unresolved uncertainty | Global correction/retraction status and the remaining P1 source gaps are resolved. | Unresolved. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P1A-D1 | Admit only the narrow AiiDA architecture proposition. | It maps directly to locators and no broader outcome. | Remove only this addendum if a locator is shown inaccurate; do not edit frozen P1 artifacts. |
| P1A-D2 | Retain P1-G4 mixed and correction status unresolved. | Crossref fields/policy are not global clearance. | A future revision needs a named authoritative correction-status source. |
| P1A-D3 | Do not affect provider or P5/P6 decisions. | Literature cannot clear strict tool protocol, held-out, execution, chemistry, or authority gates. | Require separately typed evidence for each gate. |
