# P1 — API and literature evidence

## Status

Blocked at 2026-07-31T18:16:39Z after bounded evidence collection and a passing
focused offline receipt check. P1-G1 and P1-G5 passed that check; P1-G2 has
three current account or usage outcomes and one denied Elsevier authentication;
P1-G3 remains red
because the configured DeepSeek provider uses a noncanonical alias and has no
P3 tool-surface contract; P1-G4 is deliberately mixed rather than promoted to
a blanket literature pass. No model completion, discovery query, full-text
download, or chemistry-engine action occurred in P1 itself. A later P3
one-call specimen is reconciled separately in
[`p1-post-p3-live-evidence-addendum-v1.md`](p1-post-p3-live-evidence-addendum-v1.md);
it did not normalize the active configuration and closed red on invalid tool
arguments.

## Objective

Establish only the external facts needed for later bounded evaluation: safe
credential-presence resolution, current account/usage/entitlement state, and
primary-source literature support. It must not infer a model capability from a
ping, a search snippet, an account response, or an abstract alone.

## Inputs

| Input | Required use |
| --- | --- |
| P0 receipt and source hashes | Detect source drift before collecting live evidence. |
| Provider configuration contract | Determine whether a configured OpenAI-compatible provider explicitly maps `DEEPSEEK_API_KEY`; do not infer it from a provider name. |
| Alias set | `DEEPSEEK_API_KEY`; `ELSEVIER_API_KEY` or `Elsivier_api_key`; `SERPAPI_KEY` or `SerpApi_api_key`; `TAVILY_API_KEY` or `Tavily_api_key`. |
| Existing literature ledger and citation audit | Candidate list only; timestamps and correction status are historical until refreshed. |
| Official API/provider/publisher metadata | Primary evidence for quota, entitlement, passages, and correction/retraction status. |

## Tools and authority

- A redacting resolver may return only `present`/`absent` and the selected
  variable *name*, never a value, length, prefix, path, or serialized config.
- Query one documented account or usage endpoint per configured service, using
  the smallest request that returns current allowance/entitlement. Never use
  verbose transport logging, environment dumps, shell tracing, or retry loops.
- DeepSeek, if configured, may be checked only through its account/usage or
  other documented quota endpoint in this phase; no completion is authorized
  here.
- Elsevier may retrieve a predeclared entitled full text only after entitlement
  evidence. SerpAPI and Tavily may discover candidates but their snippets are
  discovery records, never claim evidence.
- Verify an adopted literature statement against publisher text or a primary
  scholarly record, full metadata, a supported passage, and a correction or
  retraction check. Do not copy unentitled full text into the repository.

## Budget

| Resource | Ceiling |
| --- | --- |
| Credential inspection | Boolean presence and alias choice only; 0 secret values retained |
| Account/usage probes | At most one per configured provider/service; at most one bounded retry after a transport failure |
| DeepSeek completions and tool loops | 0 |
| Elsevier full-text retrieval | One predeclared entitled item per verified claim; no bulk download |
| SerpAPI/Tavily discovery | One query per predeclared research question; snippets retained only as discovery receipts |
| Spend, top-up, purchase, quota increase | 0 |

The discovered remaining allowance is a hard upper bound for later phases; an
unavailable, ambiguous, or exhausted allowance blocks the corresponding live
test rather than prompting a purchase.

## Artifacts

- `receipts/p1-api-usage.json`: redacted endpoint class, selected alias name,
  provider/model/base-URL digests, timestamp, HTTP outcome class, usage/limit
  fields when available, and zero secret material.
- `receipts/p1-literature-evidence.json`: discovery provenance, scholarly
  metadata, publisher/primary-source passage locator, correction/retraction
  result, and claim links.
- `receipts/p1-failure-ledger.json`: every P1 failure or qualified result,
  hypothesis, minimal change, evidence, result, limitation, and rollback
  boundary.
- [P1 post-P3 evidence addendum](p1-post-p3-live-evidence-addendum-v1.md):
  hash-linked reconciliation of the historical P1 records with the later
  red, non-executing P3 provider specimen; it does not rewrite P1 receipts.
- Updated claim and decision ledger entries in this document, plus SHA-256
  digests for receipts.

## Gates

| Gate | Pass condition | Red condition |
| --- | --- | --- |
| P1-G1: secret boundary | Receipt contains no credential value, prefix, path, prompt, or raw header. | Any secret exposure or unredacted transport capture. |
| P1-G2: quota boundary | A current, redacted account/usage outcome proves a non-negative existing allowance or explicitly reports its absence. | Inferred quota, payment, top-up, or an unbounded retry. |
| P1-G3: DeepSeek configuration | Configured provider, protocol, model, and allowed tool surface are explicitly recorded. | Provider-name guesswork or a generic OpenAI assumption. |
| P1-G4: literature evidence | A claim has verified metadata, primary supported passage, and correction/retraction status. | Search snippet, unverified abstract, or stale citation alone. |
| P1-G5: conservative close | Claims are classified supported, qualified, unresolved, or rejected. | Any current readiness or SOTA conclusion. |

## Blockers

- Missing keys, a disabled account endpoint, no remaining allowance, ambiguous
  entitlement, or a non-redactable client blocks the corresponding action.
- A source without an accessible primary passage, reliable metadata, or a
  correction/retraction check remains unresolved.
- Existing ChemSmart provider ping behavior is not a quota or usage receipt.

## P1 observed outcomes

| Area | Observation | Classification |
| --- | --- | --- |
| DeepSeek configuration | The requested canonical `DEEPSEEK_API_KEY` is absent. The selected OpenAI/Chat-Completions configuration instead names `DEEPSEEK-api-key`, model `deepseek-v4-pro`, and a redacted base-URL digest. The configured alias authenticated the official balance endpoint and reported USD 0.82 available. | Qualified historical P1 configuration fact; a later isolated P3 binding and red tool-schema specimen are recorded separately, not treated as normal configuration or tool-loop validation. |
| Elsevier | The permitted fallback alias was present, but one documented authentication request returned HTTP 403. No response body, entitlement token, full text, or retry was retained. | Blocked; do not infer entitlement or retrieve full text. |
| SerpAPI | One Account API request returned active status and 250 searches remaining; no discovery query was used. | Supported quota observation only; snippets remain non-evidence. |
| Tavily | One Usage API request returned zero reported use and a plan limit of 1,000; no discovery query was used. | Supported quota observation only; no source claim follows. |
| Literature | Current Crossref records returned empty `relation` and `update-to` fields for seven frozen DOIs. Current publisher passages support narrowly qualified ChemGraph, ACRA, ChemCrow, and Workflow Run RO-Crate design references. El Agente Q, DynaMate, and AiiDA stay unresolved. | Crossref result is a relation-field observation, not a definitive global retraction clearance. |

The complete redacted outcomes, source locators, and failure records are in the
three P1 receipts. Their fields intentionally preserve uncertainty rather than
turning a provider response or a source passage into a ChemSmart result.

## Phase-close validation

Validate the JSON receipt schemas, redaction patterns, source locators, hashes,
and claim links with a focused offline checker. Perform no completion or engine
call as part of the close check. Record each invocation and all blocked probes.

P1 remains closed blocked after its passing receipt check. The later P3 runner
bound the canonical alias only within its own process and did not alter the
active configuration; its strict v1 response was invalid, so it does not clear
P1-G3. Elsevier remains separately blocked unless an entitled official endpoint
becomes available; no retry is planned.

## Claim-evidence ledger

| ID | Claim type | Statement | Required evidence | Initial status |
| --- | --- | --- | --- | --- |
| P1-C1 | observation | A named API alias is usable for a bounded action. | Redacted account/usage receipts. | Supported for configured DeepSeek alias, SerpAPI fallback, and Tavily fallback; Elsevier is blocked. |
| P1-C2 | observation | A configured DeepSeek endpoint can support a later bounded harness test. | P1-G2/P1-G3 receipt and any separately redacted P3 specimen receipt. | Qualified at P1 close; later P3 v1 reached the endpoint but failed strict argument validation, so normal tool surface remains unresolved. |
| P1-C3 | literature statement | A reported paper result supports a narrowly specified design decision. | Metadata, primary passage, correction/retraction check, and limitation. | Qualified for ChemGraph, ACRA, ChemCrow, and Workflow Run RO-Crate; unresolved for El Agente Q, DynaMate, and AiiDA. |
| P1-C4 | inference | A source supports a SOTA claim for ChemSmart. | Controlled ChemSmart comparison and replication, not literature alone. | Rejected. |

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P1-D1 | Use alias-aware presence checks only. | Existing provider resolver is config-driven and external aliases are not all native provider features. | Replace only with a reviewed redacting resolver. |
| P1-D2 | Use discovery services only to locate sources. | Snippets do not establish propositions. | Adopt a claim only after P1-G4. |
| P1-D3 | Leave live completion budget at zero in P1. | Quota evidence and a fixed harness are prerequisites. | P3 may set a nonzero ceiling only from P1 receipts. |
| P1-D4 | Preserve the noncanonical configured DeepSeek alias without rewriting it. | It authenticated a redacted balance probe, but differs from the requested canonical alias. | The later P3 process-local binding is separately receipted and does not normalize the configuration or clear P1-G3. |
| P1-D5 | Preserve SerpAPI/Tavily quota for later source discovery. | Primary publisher URLs were already available; snippets would not be claim evidence. | Use one predeclared discovery query only in a later approved P1 revision. |
| P1-D6 | Stop Elsevier activity after one HTTP 403. | No entitlement was established; full text needs affirmative entitlement. | Do not retry or download without a new authorized endpoint/entitlement path. |
