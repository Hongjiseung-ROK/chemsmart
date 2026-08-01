# M0 — Evidence Reconciliation and Adaptive API Contract

## Objective

Reconcile the 23 historical Runtime V2 streams without rewriting them, retire
loop-level `completed` as a scientific success metric, and add the adaptive
campaign and network-budget contracts.

## Required work

1. Make the hash-chained Runtime terminal event authoritative and record turn,
   tool-domain, and scientific-readiness outcomes separately.
2. Preserve every original stream and public receipt. Record each mismatch,
   stable rule ID, source hash, and reconciliation receipt. Distinguish event
   count from unique causal rules.
3. Add `AdaptiveApiCampaignPolicyV1` with no fixed attempt limit, per-provider
   quota/exhaustion state, observed concurrency/rate limits, cumulative usage,
   terminal reason, and last valid hypothesis.
4. Add `AdaptiveNetworkBudgetV1` for concurrency, per-request tokens, task wall
   time, provider/endpoint/purpose, lease scope, no-top-up, and redaction.
5. Bind every request/retry to a registered unique case ID, comparator, one
   changed factor, expected outcome, deterministic oracle, relevant hashes, and
   novelty rationale. A retry retains the case and records its attempt ID,
   error class, and reason. Reject duplicates and quota-burning.

## Gate

Historical 128/24 v1 evidence remains byte-stable and replayable. Reconciliation
is deterministic. Adaptive termination is quota exhaustion, no unique valid
hypothesis, credential revocation, or safety red line—not request count.
Run one focused milestone suite and at most one evidence-driven rerun.
