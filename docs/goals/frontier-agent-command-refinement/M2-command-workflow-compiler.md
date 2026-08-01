# M2 — CommandWorkflowSpec and Deterministic Compiler

## Objective

Make CommandWorkflowSpec v1 the canonical source of command intent while
retaining compact-v8 as a migration reader. Replace hand-written option/path
resolution with live Click-schema-derived resolution except for named,
evidence-tested scientific cross-field rules.

The current typed surface and its deliberately narrow verified job families
are specified in [command-workflow-spec-v1.md](../../design/command-workflow-spec-v1.md).

## Required work

1. Implement typed ScientificTaskSpec, CommandWorkflowSpec, CommandNode,
   ArtifactBinding, CanonicalCommandInvocation, CommandCounterexample, and
   extended CommandPreflightReceipt contracts. Prohibit untrusted paths and
   upstream-geometry placeholders.
2. Compile in one fixed order: typed IR, DAG check, live schema path/option
   resolution, project/artifact grounding, canonical long-flag argv, display
   rendering, parser/safe-preview validation, and semantic intent comparison.
3. Resolve method, basis/ECP, solvent, and other project-owned settings through
   a validated project artifact. If a project is absent, produce a candidate
   YAML only through the existing project workflow and require approval before
   writing it. Never fall back to native input.
4. Reject shell operators, redirects, environment injection, aliases,
   malformed scope, unknown options, stale digest/binding, and semantic drift.
   Preview with the real safe CLI path; independently parse the resulting
   invocation and generated input semantics.
5. Make repair CEGIS-like: return only a structured minimal counterexample,
   bind it to the immediately preceding task-spec and preflight-receipt
   digests, allow at most two constrained repairs, and block on repeated rule
   IDs or budget exhaustion. Reject any change to explicit program, geometry,
   charge, multiplicity, method, or constraints.
6. Implement the deterministic A0 direct-string versus A1 typed-IR/compiler
   comparison harness using fixed fixtures and captured M1 traces only. The
   live paired API ablation, token/cost measurement, and efficacy decision are
   reserved for M5's frozen pilot. Do not claim adoption from a single success.

## Acceptance evidence

- Equivalent legal aliases/orderings normalize to the same canonical argv.
- IR to argv to observed-intent preserves program, kind, project/input,
  charge, multiplicity, constraints, resources, and expected artifacts.
- A1 achieves deterministic schema-valid/parser-accepted rendering and zero
  native-input/shell-injection/hallucinated-option cases on its declared set.
- The active typed profile cannot report completion unless its latest
  deterministic preflight receipt is `previewed`.
- Record deterministic fixture outcomes, explicit-intent preservation, repair
  count, and failure taxonomy now. Add live token/cost and paired efficacy
  evidence only in M5 under its frozen provider and budget record.
- The A0/A1 observation ledger must be path-free and must always report
  `experimental_not_adopted` before the M5 paired study; it may not turn a
  fixture pass into an efficacy claim.

## Test gate

After implementation, run one focused compiler/schema/parser/safe-preview
suite. Use one evidence-driven rerun at most. Keep the full suite for M5.
