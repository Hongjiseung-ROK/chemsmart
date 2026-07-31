---
name: chemsmart-scientific-workflow
description: Plan, construct, preflight, execute only with approval, or validate Gaussian, ORCA, and xTB workflows in ChemSmart. Use for molecular identity, geometry, charge and multiplicity, method and basis selection, solvent or constraints, CLI grounding, generated inputs, execution receipts, convergence, frequencies, units, and physical result checks.
---

# ChemSmart Scientific Workflow

Use this skill to turn a chemistry request into a bounded, reproducible
ChemSmart workflow. Read `AGENTS.md` first. A syntactically valid calculation
is not a chemically adequate result.

## Workflow

1. Make the scientific question and requested observable explicit. Separate a
   planned calculation from a completed result.
2. Identify the molecule from a stable artifact and geometry frame. Record
   coordinate units, charge, multiplicity, stereochemistry, fragments,
   constraints, and relevant conformer or spin assumptions.
3. Select a program and job kind from the current CLI schema. State the method,
   basis/ECP, dispersion, solvent, temperature/standard state, and resources;
   ask for any material missing choice.
4. Run deterministic preflight through the actual parser and generated-input
   checks. Do not replace native program rules with a generic prompt rule.
5. Obtain explicit approval before real local execution, scheduler submission,
   retry, cancellation, paid compute, or a material method change.
6. Record native inputs and outputs, executable and environment versions,
   hashes, timestamps, command, working directory, and termination state.
7. Parse values with units and apply job-specific validators before supporting
   a claim. Report missing diagnostics, assumptions, and uncertainty.

## Validation boundary

Check molecular identity, electron count, charge/multiplicity, method and
setting compatibility, SCF/geometry convergence, frequency/stationary-point
requirements, spin diagnostics where relevant, stoichiometry, comparability,
and units. A parser success, an exit code of zero, or a critic opinion alone
does not pass scientific validation.

## Use the references

- Read [scientific-task-contract.md](references/scientific-task-contract.md)
  for the required calculation specification and evidence receipt.
- Read [program-validation.md](references/program-validation.md) for
  engine-neutral checks and Gaussian/ORCA/xTB boundaries.

## Examples

Use this skill for: “preflight an ORCA transition-state optimization,” “check
whether an xTB solvation request is fully specified,” or “audit a Gaussian
frequency result before reporting a free energy.”

Do not use it to change provider protocols, approve a run, or write a research
claim without `chemsmart-evidence-audit`.
