# Program and physical-validation reference

Use current program manuals and ChemSmart-generated inputs for engine-specific
syntax. Do not universalize an engine default or a literature example.

## Universal preflight

- Confirm atom count/order, element identities, geometry units, charge, and
  multiplicity before input construction.
- Confirm that method, basis/ECP, dispersion, solvent, and constraints are
  explicit or deliberately inherited from a versioned project artifact.
- Confirm the requested task is compatible with the selected program and job
  kind through the live CLI schema. Resolve commands from typed
  CommandWorkflowSpec data through the deterministic compiler; do not accept a
  model-written shell command or a native-input fallback.
- Require the compiler to reject shell operators, redirects, environment
  assignments, unknown or out-of-scope options, untrusted paths, stale artifact
  hashes, and mismatched project settings before safe preview.

## Universal postflight

- Confirm normal termination and required SCF/geometry convergence.
- For minima and transition structures, inspect frequency count and mode
  character under the declared convention; do not infer a stationary point from
  an optimization exit code alone.
- Check spin, wavefunction, charge, multiplicity, and stability diagnostics
  when the method or system requires them.
- Check stoichiometry, atom mapping, standard state, units, and reference
  energies before comparing species or reporting a thermochemical quantity.

## Program boundary

Gaussian, ORCA, and xTB support different models and diagnostics. xTB `sp`,
`opt`, and `hess` are real current CLI leaves, but no xTB result should be
silently substituted for a requested ab initio or DFT result. Escalate a
cross-method comparison to an explicit scientific assumption and approval.

Do not assume that a transition-state CLI kind automatically includes a
vibrational analysis. In the current ChemSmart model, frequency settings can
be runtime/project-owned. For a TS-plus-frequency request, inspect the rendered
input and expected artifacts to prove that the requested vibrational step is
present before execution; require its receipt before a TS or barrier claim.
