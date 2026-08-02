# V5r3 Seeded Validator-Repair Live Report — 2026-08-02

## Scope and evidence ceiling

This development campaign tested whether DeepSeek V4 Flash could obey a
deterministic ChemSmart counterexample and repair exactly one deliberately
corrupted field. It did not author projects, commands, coordinates, or native
engine inputs, and it performed no Gaussian, ORCA, xTB, scheduler, or HPC
execution. The result is live repair evidence for four registry-decision
fields; it is not evidence of paper generalization, calculation execution,
reproduction, scientific suitability, or state-of-the-art performance.

The preregistered source was clean, remote-matched commit
`19d67922fa0d6a4c697db17c746189fc5814a09b`. The campaign-plan digest is
`e707984b17e91990de7ba2e53174174118eaedbbe7c6936339ba1378f7797117`.
The exact plan and all per-run bindings are in
[`campaign-plan.json`](receipts/registry-validator-decision-seeded-repair-live-v5r3-2026-08-02/campaign-plan.json).

## Result

- Strict passes: **4/4**.
- Provider transports: **16**; exactly four per run.
- Tokens: **69,759 input**, **4,794 output**, and **2,421 reasoning**.
- Summed provider wall time: **45,432 ms**.
- Every tool sequence was exactly `inspect → reject → repaired submit → accept`.
- Every first rejection contained exactly the preregistered rule, field,
  expected value, observed value, evidence binding, and content-addressed
  counterexample.
- Every accepted submission reported `repairs_used=1`; no unrelated field
  changed.
- All four final English responses were byte-equal to the host-rendered
  canonical report and contained no unsupported positive claim.
- Runtime V2 replayed to one terminal `turn_completed` event per run only after
  the green submit receipt.
- Engine calls, HPC calls, project writes, and native inputs authored were all
  **zero**.

| Case | Seeded defect | Deterministic counterexample | Result |
| --- | --- | --- | --- |
| Gaussian def2-TZVPPD / missing Ce | `readiness=project_candidate` | `validator.proposal.readiness_mismatch` | repaired to `blocked_missing_evidence` |
| Gaussian non-atomic functional literal | zeroed decision digest | `validator.proposal.decision_binding_mismatch` | restored exact decision binding |
| ORCA def2-ECP / missing Pd orbitals | changed Pd `orbital_present` to `true` | `validator.proposal.element_findings_mismatch` | restored the receipt-derived Pd finding |
| ORCA def2-TZVP / Fe without ECP | false claim of scientific suitability and execution readiness | `validator.proposal.analysis_claim_unsupported` | restored the exact evidence-ceiling report |

The per-case outcomes, sanitized English responses, tool traces, provider
observations, and public Runtime V2 projections are archived in the
[`V5r3 receipt directory`](receipts/registry-validator-decision-seeded-repair-live-v5r3-2026-08-02/).

## Reproducibility bindings

- Final receipt:
  `223b639d2224ee05c08de9c7d312974671136d390ea70bedfcfdf01d4383853d`.
- Run receipt:
  `f6e5722a4c964e7c6a852d1e193ce413e408b9e0d076fcf3a3a7914e22bf6982`.
- Public semantic-audit receipt:
  `abda13e07be4917b51638d2444b965c401c9dd855cb56476186b7d04aed9fca5`.
- Public manifest: 27 bound artifacts, 224,775 bytes,
  `bc4972fb21fd9b3c409603bb49a5fff5e8b162522f3c80d48dd1f4219a114953`.
- Private manifest: 24 bound artifacts, 206,838 bytes,
  `2b40acc8b1e77cf022d690f94f25579bd426d3385225509a4098de005628dcbf`.

The private Runtime V2 archive is stored outside Git at
`/Users/hongjiseung/.codex/evidence/chemsmart/registry-validator-decision-seeded-repair-live-v5r3-2026-08-02`
with directories mode `0700` and files mode `0600`. Both public and private
manifests were reverified after durable copying. Secrets and provider-private
reasoning were neither copied to public evidence nor retained in the sealed
private evidence.

## Interpretation and next experiment

The evidence supports retaining deterministic, field-local counterexamples and
the required-green Runtime V2 completion gate. DeepSeek followed all four
type-valid repair challenges with thinking enabled, including one nested
element-evidence defect and one false-ready language defect.

The result does **not** isolate a causal improvement over V5r2: V5r2 was a
zero-repair baseline, whereas V5r3 deliberately injected faults and tightened
the final-response contract. It also reuses development registry cases. The
next high-value test is a novel-case generalization slice with previously
unseen program/setting combinations, followed by a coordinate-bound paper
slice only after the user supplies the coordinate import contract.

## Validation note

Before the live run, compile, deterministic campaign preparation, focused
read-only Ruff, and diff checks passed. The focused pytest milestone ran twice:
both runs reported 16 passes and one failure in an older fixture that changed
an unrelated summary during a field-local repair. The fixture was corrected,
but the suite was not run a third time because the milestone rerun allowance
was exhausted. The live campaign subsequently exercised the stricter repair
path four times and its persisted semantic audit replayed all four outcomes.
