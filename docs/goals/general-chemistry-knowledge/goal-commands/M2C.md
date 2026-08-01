# M2C goal command

~~~text
Goal: complete only M2C of the ChemSmart General Chemistry Knowledge program: implement sourced, scoped DomainKnowledgePack rules over settings ChemSmart can actually validate.

Read AGENTS.md, docs/design/chemsmart-agent-ultimate-goal.md, docs/design/paper-research-plan-v1.md, docs/goals/general-chemistry-knowledge/M2C-domain-knowledge-pack.md, and verified M2A-M2B artifacts. Re-audit branch, dirty state, existing DomainKnowledgePack contract, settings registry, source/evidence ledger, loaders, validators, and focused tests. Extend existing Runtime V2 and knowledge contracts additively; preserve K0, replay, and unrelated work.

Act as a transparent computational-chemistry expert. Keep paper facts, ChemSmart setting availability, sourced domain guidance, coordinator decisions, and unknowns distinct. Extend DomainKnowledgePack with exact domain and engine/version/job scope, source records and locators, registry setting IDs, applicability predicates, required evidence, allowed choices, prohibitions, uncertainty/conflict behavior, stable rule IDs, and deterministic validators. A pack cannot promote inferred/unknown/conflict to explicit, supply a customary default for a missing paper fact, invent identity/geometry/state, approve, execute, set readiness, or author native input.

Implement one fully auditable reusable core pack and one paper-relevant domain vertical slice. Prefer high-value rules for molecular/electronic-state completeness, method and basis/ECP pairing, solvent/dispersion/convergence declarations, frequency/thermochemistry obligations, and valid job sequencing, but include only rules supported by primary or authoritative sources and current loader coverage. Add positive, negative, out-of-scope, conflicting-source, stale-version, and fail-closed fixtures. Use a fresh read-only domain critic; deterministic evidence or user adjudication resolves critical findings.

API calls require unique one-factor hypotheses and deterministic oracles; request count is observational. Use current quota only; no top-up, bypass, duplicate prompting, quota-burning, or secret persistence. Stop on quota exhaustion, no unique hypothesis, credential revocation, or a safety red line. Safe preview is the ceiling; run zero chemistry engines/HPC and write no native input.

Run one focused M2C suite and at most one evidence-driven rerun. Report provenance coverage, empirical results, failures, unknowns, and retain/revise/reject. Commit only phase-owned changes and fetch-first non-force push; no PR and do not continue to M2D. Do not claim reproduction, generality, or SOTA.
~~~
