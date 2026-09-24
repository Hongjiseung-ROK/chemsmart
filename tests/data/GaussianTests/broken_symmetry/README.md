# The broken-symmetry request, as the hub writes it

Gaussian 16 C.02 on CUHK Charles, R10 Q18 oracle O1 (CUHK Slurm 2153479),
written and run through the ordinary CLI on code `5da66f9c`, project
`gas: {functional: b3lyp, basis: def2-svp, broken_symmetry: true}`, the
fixed geometries of oracle O0. The hub wrote `# ub3lyp def2svp guess=mix`.

| file | geometry | printed | reading |
|---|---|---|---|
| `g_h2_074_bs_gas_phase.log` | H2 at 0.74 A | `E(UB3LYP) = -1.17349679516`, `<S**2>` 0.0000 | the request stayed spin-symmetric: the restricted energy (O0's RB3LYP, to the printed digit) |
| `g_pbenzyne_bs_gas_phase.log` | p-benzyne, regular hexagon | `E(UB3LYP) = -230.704724145`, `<S**2>` 0.9703 | the broken-symmetry singlet, 24.87 kcal/mol below the restricted solution; ORCA's GuessMix run reaches it within 1.1e-7 Eh |
