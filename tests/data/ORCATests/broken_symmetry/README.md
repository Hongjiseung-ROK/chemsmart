# The broken-symmetry request, as the hub writes it

ORCA 6.1.1 on CUHK Charles, R10 Q18 oracle O1 (CUHK Slurm 2153479), written
and run through the ordinary CLI on code `5da66f9c`, project
`gas: {functional: b3lyp, basis: def2-svp, broken_symmetry: true,
ri_approximation: none, scf_convergence: tight, defgrid: defgrid3}`, the fixed
geometries of oracle O0. The hub wrote `%scf HFTyp UHF / GuessMix 45 end`
(ORCA's B3LYP/G, the Gaussian VWN3 form).

| file | geometry | printed | reading |
|---|---|---|---|
| `o_h2_074_bs_gas_phase.out` | H2 at 0.74 A | `FINAL SINGLE POINT ENERGY -1.173496798071`, `<S**2>` 0.000000 | stayed spin-symmetric: the RKS energy |
| `o_pbenzyne_bs_gas_phase.out` | p-benzyne, regular hexagon | `-230.704724039355`, `<S**2>` 0.970279 | the broken-symmetry singlet; identical to the native GuessMix input of O0 (CUHK 2153330) to the printed digit |
