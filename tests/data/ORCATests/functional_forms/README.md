# One water, two B3LYPs

ORCA 6.1.1 on CUHK Charles, CUHK Slurm 2149277 (R10 q2 oracle 1), written
and run through the human CLI on the base tree `8f2c3443`: water at one
fixed geometry, def2-SVP, `NoRI DefGrid3 VeryTightSCF`.

| file | route | `LDAOpt` printed | FINAL SINGLE POINT ENERGY |
|---|---|---|---|
| `water_route_b3lyp_vwn5.out` | `! b3lyp ...` (what the literal `b3lyp` was written as before d94706a2) | `VWN-5` | -76.320992034412 |
| `water_route_b3lypg_vwn3.out` | `! B3LYP/G ...` (what it is written as now) | `VWN-3` | -76.358141128119 |

Gaussian's B3LYP on the same water at `scf=tight int=ultrafine`
(`../../GaussianTests/functional_forms/water_b3lyp.log`) is -76.3581417839,
6.6e-7 Eh from the second; PySCF's b3lyp (b3lypg, defgrid3) is
-76.3581416723 and its b3lyp5 -76.3209925787, 5.4e-7 Eh from the first.
