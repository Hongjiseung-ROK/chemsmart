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

## The same constrained optimum with its frequency step (R10 q21)

`h2o2_b3lypg_d3bj_def2svp_hooh90_freq.out`: ORCA 6.1.1, written by an Agent
goal on CUHK (**Slurm 2153623**, goal g1-hooh node `mod90`, code
`d32eeeef`) as `! Opt Freq B3LYP/G def2-svp d3bj` with the H-O-O-H torsion
held at 90 deg. The optimisation converged holding it (-151.423417917 Eh at
the last step); the frequency step ran at that constrained optimum and
ORCA printed `Final Gibbs free energy ... -151.41849362 Eh` (line 3282) --
a number describing no state, because the structure is not a stationary
point: the energy still slopes along the held torsion. The host refuses a
free energy there, and this is the file the goal's unreachability check
read the printed line from. sha256
`3863610af1300088bc6c9f255cb35c5c923814318b42c458631b3069d4a507a7`.

`h2o2_b3lypg_d3bj_def2svp_hooh90_freq.hess` is the Hessian sidecar ORCA
wrote beside that output in the same run (goal g1-hooh node mod90), copied
under the output's stem so the reader finds it; sha256
`0b8636d7c8569f4dac0a78dcee0b6f6def6fdb412812a11bea99a0df0e87eaa3`. The
host reads the held torsion's projected free energy from it (R10 Q27).
