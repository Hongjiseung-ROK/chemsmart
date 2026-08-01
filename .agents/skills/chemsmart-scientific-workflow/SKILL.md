---
name: chemsmart-scientific-workflow
description: Reconstruct, plan, command-compile, safe-preview, execute only with approval, or validate Gaussian, ORCA, and xTB workflows in ChemSmart. Use for PRP-10 full-paper and Supporting Information reconstruction, exact official XYZ provenance, molecular identity, charge and multiplicity, method and basis selection, solvent or constraints, ScientificTaskSpec and CommandWorkflowSpec grounding, generated-input inspection, execution receipts, convergence, frequencies, units, and physical result checks.
---

# ChemSmart Scientific Workflow

Use this skill to turn a chemistry request into a bounded, reproducible
ChemSmart workflow. Read `AGENTS.md` first. A syntactically valid calculation
is not a chemically adequate result.

## Workflow

1. Make the scientific question and requested observable explicit. Separate a
   planned calculation from a completed result.
2. For a paper task, inventory the article, Supporting Information, figures,
   tables, structures, datasets, code, cited protocols, and software manuals.
   Give every extracted setting a source locator and epistemic status. Never
   fill a paper omission from habit or an engine default without labeling it.
   If a critical field remains inferred, unknown, or conflicting, return
   `blocked_missing_evidence`. Do not contact authors or propose an unreported
   sensitivity calculation merely to close the gap.
3. Identify the molecule from a stable artifact and geometry frame. Record
   coordinate units, charge, multiplicity, stereochemistry, fragments,
   constraints, and relevant conformer or spin assumptions.
   For PRP-10, accept only an official exact single-frame XYZ in angstrom and
   bind its source/archive member, source and imported-byte hashes, atom order,
   identity approval, and license/access receipt. Do not transcribe coordinate
   tables, OCR coordinates, generate 3D coordinates from SMILES, or ask a model
   to create or repair geometry. Treat SDF/MOL/PDB conversion as a separate
   general-input path, not PRP-10 eligibility. Missing coordinates block only
   dependent nodes.
4. Record these choices in ScientificTaskSpec. Select a program and job kind
   from the current CLI schema; keep method, basis/ECP, dispersion, solvent,
   temperature/standard state in an approved project artifact. Put resource
   targets on typed command nodes. Ask for any material missing choice.
   Apply scientific rules only from a versioned DomainKnowledgePack whose
   domain, engine/version, sources, rule IDs, and validators match the task.
5. Propose CommandWorkflowSpec data, not a native input or executable shell
   string. Let the deterministic compiler resolve live schema options, trusted
   project/artifact references, canonical argv, safe preview, and independent
   semantic round-trip checks.
6. Inspect ChemSmart-generated input only as downstream preview evidence. Do
   not edit .com, .gjf, or .inp files to repair a model proposal; repair the
   typed command intent or approved project YAML instead.
7. Obtain explicit approval before real local execution, scheduler submission,
   retry, cancellation, paid compute, or a material method change.
8. Record native inputs and outputs, executable and environment versions,
   hashes, timestamps, command, working directory, and termination state.
9. Parse values with units and apply job-specific validators before supporting
   a claim. Report missing diagnostics, assumptions, and uncertainty.

## Validation boundary

Check molecular identity, electron count, charge/multiplicity, method and
setting compatibility, SCF/geometry convergence, frequency/stationary-point
requirements, spin diagnostics where relevant, stoichiometry, comparability,
and units. A parser success, an exit code of zero, or a critic opinion alone
does not pass scientific validation.

At this roadmap stage, a fake/test CLI preview can establish only
`previewed`. An archived artifact may support `validated` if its deterministic
receipt is complete. Do not call a new calculation `executed`, `reproduced`,
or SOTA without the separately required engine, environment, and evidence
receipts.
The active PRP-10 campaign performs zero Gaussian, ORCA, xTB, and HPC
execution. Its new-work ceiling is safe `previewed`, even when the paper plan
fully describes later validation and analysis.

## Use the references

- Read [scientific-task-contract.md](references/scientific-task-contract.md)
  for the required calculation specification and evidence receipt.
- Read [program-validation.md](references/program-validation.md) for
  engine-neutral checks and Gaussian/ORCA/xTB boundaries.
- Read [paper-research-plan-contract.md](references/paper-research-plan-contract.md)
  before converting a full paper or Supporting Information into calculations.

## Examples

Use this skill for: “reconstruct every computational step in this full paper,”
“compile an ORCA transition-state intent into a safe preview,” “check whether
an xTB solvation request is fully specified,” or “audit a Gaussian frequency
result before reporting a free energy.”

Do not use it to hand-write Gaussian/ORCA/xTB native input, change provider
protocols, approve a run, or write a research claim without
`chemsmart-evidence-audit`.
