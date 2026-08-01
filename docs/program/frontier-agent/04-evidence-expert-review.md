# P4 — Evidence expert review

## Status

Mechanically complete and closed blocked at 2026-07-31T19:16:25Z. The frozen
packet, five role-isolated typed reports, deterministic join, and focused
offline validator passed. Four critical findings produce stop dispositions;
P1's provider gate, P3's fixture-only boundary, and all performance,
scientific-validity, replication, and SOTA claims remain red or unresolved.

The role reports are bounded read-only adviser containers derived from the
frozen artifacts. They are not five independent human expert reviews, do not
create scientific evidence, and cannot promote a claim. Review is a bounded,
independent, read-only cross-examination of immutable P3 artifacts; it cannot
change code, execute tools, or approve actions.

## Objective

Use independent chemistry, statistics, harness, citation, and red-team
advisers to find unsupported claims, scientific omissions, evaluation flaws,
provenance gaps, and safety bypasses. Findings require deterministic validation,
independent recomputation, or a human decision; majority vote is not
arbitration.

## Inputs

| Input | Required use |
| --- | --- |
| Immutable P3 evidence bundle | Trace, fixtures, artifact/claim/validator receipts, prompt/tool/budget digests, and declared assumptions. |
| P1 literature receipts | Verified metadata/passage/correction status for cited propositions. |
| P2 contract matrix and P5 preregistration | Review boundary and future evaluation criteria. |
| Review rubric | Typed finding schema: severity, claim type, cited receipt/source, defect hypothesis, impact, and proposed arbitration path. |

## Tools and authority

- Chemistry adviser: scientific specification, state, method/settings,
  convergence/frequency/units/stoichiometry interpretation.
- Statistics adviser: sampling, paired analysis, leakage, effect-size and
  confidence-interval protocol compliance.
- Harness adviser: event/approval/budget/replay/tool-scope integrity.
- Citation adviser: metadata, passage support, correction/retraction, and
  claim-source mapping.
- Red-team adviser: seeded failure coverage, false passes, artifact mutation,
  secret exposure, and approval bypass attempts.
- Each receives the same immutable packet plus its narrow rubric. Advisers are
  read-only: no evidence mutation, repair, execution, approval, or self-review
  of a repaired finding.

## Budget

| Resource | Ceiling |
| --- | --- |
| Review rounds | One independent round per frozen evidence-bundle digest |
| Adviser inputs | Immutable typed packet; no secret-bearing originals |
| Adviser actions | Read-only inspection and typed findings only |
| Resolution | One deterministic check, independent recomputation, or human decision per finding; no unbounded debate |

## Artifacts

- [Reviewer packet manifest](reviews/p4-review-packet-v1.json), with canonical
  digest `5e4aa931a5af685f942d70f187bd7d8e631935b1e68b9df5fbf0e1ccf4470c0a`.
  It pins P0-P3 documents/receipts, the public P3 reference/cases and relevant
  P3 source slice, and the P5 protocol. It excludes credential values, raw
  prompts, provider transcripts, reasoning traces, grader-only seeds, and
  mutable workspace paths.
- Five typed [role findings](reviews/) for chemistry, statistics, harness,
  citation, and red-team review. They are read-only and conflict-declared;
  they are not a substitute for an independently commissioned human review.
- [Deterministic join](reviews/p4-review-join-v1.json), mapping every finding
  to cited evidence, one arbitration path, a terminal disposition, claim
  status, and limitation. Its bundle digest is
  `cb8d01ec12d4f1ca713e3beeacec5beebc9e5f2bed30fd6efae3ff3a92e10eb3`.
- [Failure ledger](receipts/p4-failure-ledger.json) and
  [phase-close receipt](receipts/p4-evidence-expert-review.json).
- Failure and decision ledger updates; no reviewer-authored evidence overwrite.

## Gates

| Gate | Pass condition | Red condition |
| --- | --- | --- |
| P4-G1: independence | Advisers see artifacts and assumptions, not persuasive self-reports or mutable workspaces. | Adviser receives authority to repair/approve/execute. |
| P4-G2: evidence citation | Every finding names a receipt, check, or source locator. | Unsupported reviewer opinion is treated as a fact. |
| P4-G3: deterministic join | A coordinator maps each finding to an arbitration action and terminal disposition. | Majority vote or self-repair settles a scientific issue. |
| P4-G4: red-team integrity | Approval bypass, fabricated evidence, artifact mutation, secret exposure, and red-gate success are explicit stop conditions. | Any red condition is hidden or waived. |

## Blockers

- Missing bundle hash, inaccessible artifacts, secret-bearing packet, or a
  reviewer without a bounded rubric blocks review.
- A scientific disagreement without a deterministic check, independent
  recomputation, or human decision remains unresolved.

## Phase-close validation

Validate reviewer packet hashes, role isolation, typed-output schemas, evidence
locators, and join completeness with one focused offline check. Report finding
precision/recall only after P5 seeded evaluation; P4 itself makes no quality
claim from reviewer prose.

The recorded check was:

```bash
env -u PYTHONPATH conda run --no-capture-output -n chemsmart python -m pytest -p no:cacheprovider tests/agent/harness/test_frontier_review_bundle.py -q
```

It passed `4` tests in `0.07 s`. This validates a packet/role/join format and
the explicit red-gate handling only; it is not a product test, chemistry
calculation, provider test, expert-calibration result, or evidence that a
reviewer finding is true.

## Review join and close outcome

| Finding | Disposition | Resulting status | Limitation |
| --- | --- | --- | --- |
| P4-CH-01 | Stop | P3-C2/P3-C3 unresolved | No native or archived result trace is in P3. |
| P4-ST-01 | Stop | P5-C1/P5-C2/P5-C3 unresolved | No held-out, paired, repeated 2 x 2 x 2 outcomes exist. |
| P4-HA-01 | Stop | P2-C3 qualified; P3-C1 unresolved | Executor-side approval consumption is not implemented or exercised. |
| P4-HA-02 | Retain unresolved | P3-C1 unresolved | Duplicate-case rejection is a future scoring control, not a P3 error. |
| P4-CI-01 | Qualified | P1-C3 qualified; P1-C4 rejected | Passage and correction-status gaps remain. |
| P4-RT-01 | Stop | P1-C2 qualified; P3-C1 unresolved | The provider capability/tool-surface gate remains red; no completion occurred. |
| P4-RT-02 | Retain unresolved | P3-C1 unresolved | Checkout-visible development fixtures are not externally held out. |

P4 records no actual approval bypass, fabricated evidence, artifact mutation,
or secret exposure. The validator makes those classes explicit stop conditions;
absence in this offline packet is not a claim about an unexecuted live system.
The P2 source snapshot is retained through its receipt, and P4 reviews the
overlapping Runtime files through their P3-era hashes rather than relabeling
the current mutable worktree as P2 evidence. The P5 planning input is captured
under [`p4-inputs/`](reviews/p4-inputs/) so subsequent P5 state changes cannot
rewrite P4 evidence.

## Claim-evidence ledger

| ID | Claim type | Statement | Required evidence | Initial status |
| --- | --- | --- | --- | --- |
| P4-C1 | observation | A reviewer found a specific gap. | Typed finding plus cited artifact/check/source. | Supported as a process observation only. |
| P4-C2 | inference | The gap invalidates a result. | Deterministic arbitration or independent recomputation. | Unresolved. |
| P4-C3 | computed result | Critic precision/recall meets a threshold. | P5 seeded held-out labels and scoring output. | Unresolved. |

P4-C1 is supported only as a process observation: the frozen bundle contains
seven typed, evidence-located findings and a complete join. P4-C2 and P4-C3
remain unresolved. No P4 activity promotes a component, provider, chemical
result, reproducibility result, or SOTA claim.

## Decision ledger

| ID | Decision | Basis | Rollback boundary |
| --- | --- | --- | --- |
| P4-D1 | Keep critics read-only and independent. | Evidence-audit and approval boundaries. | Remove an adviser from the packet if it gains mutable authority. |
| P4-D2 | Resolve findings outside the critic. | Deterministic/arbitrated evidence rule. | Preserve unresolved status when no arbiter exists. |
| P4-D3 | Keep roles narrow rather than hierarchical. | Conditional utility and error-correlation risk. | Add a role only through P5 evidence. |
| P4-D4 | Freeze the packet before typed role reports and retain every stop disposition. | Hash-verified manifest and deterministic join. | Reissue a new packet revision if any included artifact drifts. |
| P4-D5 | Do not count the five role containers as independent human-expert calibration. | No commissioned expert review or P5 labels exist. | Keep critic-quality claims unresolved until the preregistered P5 evidence exists. |
