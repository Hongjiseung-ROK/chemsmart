# R5 — Preregistered Pilot and Ablations

## Objective

Freeze and run the development/pilot studies that decide whether typed command
compilation, harness features, decomposition, evidence composition, and
independent critique improve paper-level planning. Citations make mechanisms
testable; only measured results can support adoption.

## Required work

1. Admit exactly seven public-development paper slots: one user experimental
   paper plus six public source-complete controls, one in each PRP-6 domain.
   At this snapshot the user paper is `blocked_missing_source`, no six control
   IDs are fixed, and control selection/acquisition is pending. Resolve and
   freeze those sources before scoring; do not silently replace a slot or call
   this development set the sealed PRP-6 corpus.
2. Freeze model/version, provider receipt, exact H0/HC/HA/HK matrix, prompts,
   skills, tools, CLI schema, compiler/validators, source/fixture digests,
   budgets, retry policy, counterbalanced order, graders, exclusions, and
   analysis before collection. Keep raw evidence recording on in all conditions.
3. Run external slices: El Agente Q paper/data tasks for interpretation and
   workflow coverage; ChemGraph `react2enthalpy`/`react2gibbs` for eligible
   independent-species decomposition and deterministic aggregation; Quntur
   unchanged/private only where its recorded terms permit.
4. Run paired A0 direct-string versus A1 typed-IR/compiler trials. A1 requires
   100% schema/render/parser determinism, zero shell/native-input/option defects,
   no worse intent preservation, and at most 1.25x cost. The paired bootstrap
   95% lower bound for `A1 - A0` semantic-preview success must be at least -2
   percentage points. A cost exception requires the paired repair-reduction
   interval to exclude zero in the improving direction.
5. Run the counterbalanced DeepSeek V4 Flash H0/HC/HA/HK crossover. Common
   sandbox, approval, and deterministic validation stay on. Select the smallest
   profile whose paired 95% interval excludes a success loss over 2 points from
   the best safe profile and has no safety regression.
6. With the selected profile, run `2 x 2 x 2`: decomposition off/on, structured
   evidence composer off/on, and critique off/on. `C=on` is one fixed treatment
   containing exactly three fresh read-only reviews—domain/paper,
   command/evidence, and adversarial—with all three costs and latency counted.
   Test composition, not evidence deletion; no critic repairs or decides success.
7. Keep DeepSeek thinking enabled as a frozen provider condition. Do not infer
   thinking-disabled compatibility or a causal benefit from thinking because
   this design contains no thinking-mode factor.
8. Use paired repeated trials, paper/task-level bootstrap 95% intervals, pilot
   variance for 90% confirmatory power, deterministic graders first, two expert
   rubrics second, and LLM judges only as supplementary evidence.

## Adoption gates

- Decomposition: at least +5 points held-out success or 20% wall-time reduction
  on eligible parallel tasks; simple-task regression at most 2 points; cost at
  most 1.5x; every join deterministic.
- Evidence composer: all manifests valid, numerical claims evidence/unit bound,
  rerender deterministic, and zero false success when evidence is absent.
- Critique: at least 90% seeded-critical and 80% overall recall, at most 5%
  false rejection, and at least 50% fewer false passes.
- Every configuration: zero approval, native-input, evidence, artifact, secret,
  or red-gate success violation.

ChemSmart must not contact authors or add/propose/execute an unreported
sensitivity calculation. Use only current session-environment credentials.
Count every initial call and retry against 128 total DeepSeek attempts and 24
attempts for each of Elsevier, SerpAPI, and Tavily, all still bounded by current
account quota. No chemistry engine or HPC execution is part of the pilot.

## Freeze and exit

After R5 artifacts freeze, run the full agent suite, read-only Ruff,
schema/replay, citation/license/link/secret, and diff checks once each. Do not
autofix or regenerate snapshots. Report negative results and leave a component
off/experimental when its gate fails. R6 cannot start without an independent
custodian's sealed corpus and blind gold/grader.
