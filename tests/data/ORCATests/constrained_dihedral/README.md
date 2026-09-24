# One constrained optimisation, read in two programs

ORCA 6.1.1 and Gaussian 16 C.02 on CUHK Charles, CUHK Slurm 2150076 (R10 q7
oracle O2), written and run through the human CLI on tree `7111e2a6`:
hydrogen peroxide from a geometry with its H-O-O-H torsion D(3,1,2,4) at
exactly 90 degrees, `functional: b3lyp`, `basis: def2-svp` (ORCA's also
`ri_approximation: none`), `modred -c '[[3,1,2,4]]'`.

| file | program | written as |
|---|---|---|
| `h2o2_b3lyp_def2svp_hooh90.out` | ORCA | `! Opt B3LYP/G def2-svp NoRI`, `%geom Constraints { D 2 0 1 3 C } end end` |
| `../../GaussianTests/constrained_dihedral/h2o2_b3lyp_def2svp_hooh90.log` | Gaussian | `# opt=modredundant freq b3lyp def2svp`, `D 3 1 2 4 F` |

Both converged holding the torsion at 90.00 degrees; the totals are
-151.421893002 (ORCA) and -151.421889474 Eh (Gaussian), 3.5e-6 Eh apart,
and each equals its own relaxed scan's 90-degree point to 1.2e-6 Eh
(ORCA) and 1.2e-7 Eh (Gaussian). Gaussian also ran the frequency step its
project's default asked for; no reader serves that spectrum at a
constrained optimum.
