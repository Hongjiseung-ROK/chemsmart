# P1 post-P3 live evidence addendum v1

## Status

Closed blocked reconciled at 2026-07-31T20:11:40Z after one focused offline
validator passed. It does not reopen P1's historical account/usage probes,
alter their timestamps, consume another external quota, or repair the active
provider configuration.

## Objective

Preserve a complete negative-result chain of custody after P3's one bounded
DeepSeek request. Reconcile stale P1 wording without rewriting historical
receipts; distinguish a narrow transport/tool-name observation from a valid
tool protocol; and make each DOI's primary-passage and correction coverage
explicit.

## Inputs

| Input | Required use |
| --- | --- |
| P1 API, literature, and failure receipts | Immutable account, source, and limitation facts at their recorded time. |
| P3 v1 live protocol and receipt | One separate, redacted, non-executing provider observation. |
| Historical citation audit | Locator/title/venue/year snapshot only; never current correction or retraction clearance. |

## Tools and authority

- Allowed: local JSON/hash validation and static claim reconciliation.
- Not allowed: provider/API calls, discovery, publisher retrieval, model/tool
  execution, chemistry engines, schedulers, installs, commits, or publication.
- The addendum stores no credential, prompt, transcript, reasoning content,
  tool arguments, headers, raw response, or raw provider URL.

## Budget

| Resource | Ceiling |
| --- | --- |
| New external/API/model calls | 0 |
| Existing P1/P3 receipts rewritten | 0 |
| Citation evidence promoted | 0 without a new primary passage plus named correction/retraction authority |
| P1 addendum validation | one focused offline invocation at close |

## Artifacts

- [Machine-readable addendum receipt](receipts/p1-post-p3-live-evidence-addendum-v1.json)
  links the immutable P1 inputs to the P3 negative result by SHA-256.
- A dedicated offline validator will verify source hashes, redaction fields,
  gate classifications, and the seven-row DOI provenance matrix.
- The existing [P1 phase record](01-api-literature-evidence.md) remains a
  historical phase document; it will link this addendum rather than changing
  its original P1 account/usage outcomes.

## Gates

| Gate | Reconciled status | Reason |
| --- | --- | --- |
| P1-G1 secret boundary | Passed for the addendum if its redaction validator is green. | Only hashes and structural fields are linked. |
| P1-G2 quota boundary | Qualified historical observation. | The USD 0.82 balance was positive at P1 time; no fresh balance claim follows. |
| P1-G3 DeepSeek configuration | Red. | A process-local canonical binding enabled the isolated specimen, but the active configuration remains noncanonical and the strict v1 tool protocol failed. |
| P1-G4 literature evidence | Mixed. | Four narrow design references remain qualified; three primary propositions and named independent correction/retraction authority remain unresolved. |
| P1-G5 conservative close | Passed if classifications remain separate. | The addendum contains no readiness, performance, or SOTA promotion. |

## Blockers

- A valid normal ChemSmart provider/tool-loop condition is unobserved.
- `finish_reason=length` and invalid arguments reject the v1 strict tool-schema
  claim; the one-call protocol is exhausted and cannot be retried.
- El Agente Q, DynaMate, and AiiDA require accessible primary publisher
  passages before any proposition can be adopted.
- All seven records lack a named independent correction/retraction authority;
  the prior empty Crossref fields do not provide global clearance.

## Phase-close validation

Run the dedicated addendum validator once after the receipt and its source
hashes are frozen. The check validates local provenance and negative-result
classification only. It cannot refresh a source, validate a provider/model,
or change a P5/P6 no-go gate.

The close invocation was:

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_p1_post_p3_addendum.py -q
```

It passed `1` test in `0.04 s` at 2026-07-31T20:11:40Z. This is an offline
hash/classification check only; it does not validate current quota, a model,
or any publisher passage.

## Claim-evidence ledger

| ID | Claim type | Statement | Required evidence | Status |
| --- | --- | --- | --- | --- |
| P1-A1 | observation | The separate P3 request reached the P1-pinned model/endpoint and returned one correctly named call inside its cost/time/non-execution bounds. | P3 receipt, protocol, and linked P1 API receipt. | Supported narrowly. |
| P1-A2 | observation | The v1 request returned a valid fixed function record. | `finish_reason=tool_calls` and locally valid arguments. | Rejected; the recorded result is `length` with invalid arguments. |
| P1-A3 | inference | The normal configured provider or ChemSmart tool loop is validated. | An independently bounded normal-path trace and receipt. | Unresolved. |
| P1-A4 | literature statement | A selected reference supports a narrow design proposition. | Current metadata, located primary passage, named correction/retraction authority, and limitation. | Qualified only for the four P1 records already limited in the source receipt. |
| P1-A5 | inference | P1 evidence supports ChemSmart readiness or SOTA. | Controlled comparison, valid results, and replication—not literature or a transport result. | Rejected. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P1-A-D1 | Preserve P1 and P3 receipts as immutable records. | Their timestamps and phase budgets differ. | A new measurement needs a new receipt, never an edit to history. |
| P1-A-D2 | Treat P3 v1 as a red provider specimen, not a P1 quota refresh or tool-loop result. | The strict arguments failed under a one-call contract. | A future experiment needs a separately frozen protocol and budget. |
| P1-A-D3 | Retain literature uncertainty rather than infer clearance from Crossref emptiness. | No named independent authority is present. | Only a fresh primary-source and correction/retraction review may promote a claim. |
