# R10 episode q4 -- composition integrity

Base SHA: b834057741edb1246d7d2762c374a0e83d4e4f33 (verified with
`git rev-parse HEAD` as the first action, 2026-09-24).

## The question (as currently understood)

Which organ disagreements and verdicts actually break the multi-stage
routes chemists take (scan -> saddle refinement -> IRC -> endpoint
characterisation; a saddle's Hessian into its IRC; the same across
programs), and can each such question be answered by one function
derived from reader and registry declarations, with a guard that
forbids the bypass?

## Falsifier of the premise (first step, provider-free)

Replay every archived plan and run stream reachable (experiments-public
workspaces, tests/data fixtures, read-only cluster campaign records)
through the current organs and through one unified predicate; count the
verdicts that differ. If no real plan was ever affected, the
disagreements are latent: say so, make the smallest hygiene change, end.

## Status

- 2026-09-24: episode opened; reading charter topics and the organs.
