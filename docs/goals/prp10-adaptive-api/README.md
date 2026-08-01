# PRP-10 Adaptive API Goals

This package is the active implementation sequence for the ChemSmart PRP-10
adaptive campaign. Read [the ultimate goal](../../design/chemsmart-agent-ultimate-goal.md),
[the evaluation protocol](../../evaluation/frontier-agent-ablation-protocol.md),
and `AGENTS.md` before a phase document.

| Phase | Objective | Goal command |
| --- | --- | --- |
| [M0](M0-evidence-reconciliation.md) | Reconcile historical outcomes and add adaptive API contracts. | [copyable command](goal-commands/M0.md) |
| [M1](M1-coordinate-and-preview-custody.md) | Bind exact official XYZ and private preview bytes. | [copyable command](goal-commands/M1.md) |
| [M2](M2-independent-ablation-plane.md) | Make ten components independently switchable. | [copyable command](goal-commands/M2.md) |
| [M3](M3-prp10-frozen-baseline.md) | Freeze and run the ten-paper first-pass baseline. | [copyable command](goal-commands/M3.md) |
| [M4](M4-defect-driven-adaptive-expansion.md) | Run one-factor, oracle-graded adaptive experiments. | [copyable command](goal-commands/M4.md) |

The older `two-frontier-s0-2026-08-01` 128/24 ceilings, R0-R6 plan, PRP-6,
and seven-paper pilot are frozen historical evidence. Preserve them; do not use
them as active PRP-10 authority or relabel their results.

All phases remain safe-preview-only: zero Gaussian, ORCA, xTB, scheduler, and
HPC execution. API calls use current user-owned quota without top-up or provider
bypass. No fixed attempt cap means that count is observational; it does not
permit calls without a unique hypothesis, deterministic oracle, and bounded
network envelope.
