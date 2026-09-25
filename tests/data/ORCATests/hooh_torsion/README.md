# H2O2 twisted about its O-O bond, read by the host's own thermochemistry

ORCA 6.1.1 on CUHK Charles, written by two Agent goals of R10 episode Q21
that asked for the Gibbs free energy of H2O2 held at H-O-O-H = 0, 90 and
180 deg (B3LYP/G-D3(BJ)/def2-SVP, ORCA's RIJCOSX defaults, 8 cores). The
files are byte-identical to the goals' own workspaces (sha256 below); each
`.hess` is the sidecar ORCA wrote beside its output, which the chemsmart
ORCA job keeps.

| file | goal, node (CUHK Slurm) | what it is | sha256 |
|---|---|---|---|
| `geometry-hooh-d180_opt_opt.out` | g1-hooh, opt180 (2153623) | `! Opt Freq` from the planar trans start: converged on the trans saddle, one mode at -245.88 cm^-1 (typed `failed_wrong_stationary_point`) | `8393f6634600c77ef0f61e4166e0baa0c7ba2a388884acace638f5186257ad6c` |
| `h2o2_opt_opt.out` | g2-hooh, calc-eq (2153668) | `! Opt Freq`: the equilibrium, H-O-O-H 120.66 deg | `7773c024c66faa5d59796ddab5724465ca71c203aebd616deb49f68c064072b7` |
| `h2o2_opt_opt.hess` | g2-hooh, calc-eq | its Hessian sidecar | `72af5a24eac53757fbae50c281ab4c597c61774b59ac004814c8489a3b6ca88a` |
| `geom-d0-hooh_modred_modred.out` | g2-hooh, calc-d0 | `! Opt Freq`, `Constraints {D 2 0 1 3 C}`: held at 0.00 deg | `faa4fa499a66ca5d5bedaced467cc230769e942cce40f22c08f6b1b2acba30f1` |
| `geom-d0-hooh_modred_modred.hess` | g2-hooh, calc-d0 | its Hessian sidecar | `8b05f52a36cbd14f6a72813359dacc74beef3272fbb025168d476902868e4677` |
| `geom-d180-hooh_modred_modred.out` | g2-hooh, calc-d180 | the same, held at 180.00 deg | `96834362cf34df6f511f006f8ef5112ba0cec2c02ac1936853c4bb3fa7b22416` |
| `geom-d180-hooh_modred_modred.hess` | g2-hooh, calc-d180 | its Hessian sidecar | `16a635f1ad07c89fa137380018d98801345d635c2ba92ceb8685be9ded5ea264` |
| `geom-cis-reached_optts_optts.out` | g2-hooh, calc-ts-cis (cycle 2) | `! OptTS Freq` from calc-d0's structure: the cis saddle, -610.78 cm^-1 | `55996cc65daeec8461dfbe7be353a0ea53ad9f4455774b98d7c115f3f2ef0931` |
| `geom-cis-reached_optts_optts.hess` | g2-hooh, calc-ts-cis | its final Hessian sidecar | `b42f4e24a99a9419b6424ff0d0e25e3254788813b67f67d7e35a5197d15b425f` |
| `geom-trans-reached_optts_optts.out` | g2-hooh, calc-ts-trans (cycle 2) | `! OptTS Freq` from calc-d180's structure: the trans saddle, -245.85 cm^-1 | `81db680581b82ef0d04cd1844f072a8430b1177c8441351e331f345ff58cd225` |
| `geom-trans-reached_optts_optts.hess` | g2-hooh, calc-ts-trans | its final Hessian sidecar | `3459ce097e85ead596f151e6c9523ff7f5ea809038af083d70b8e3e2bd059091` |

The torsion held at 90 deg is `../constrained_dihedral/h2o2_b3lypg_d3bj_def2svp_hooh90_freq.out`
(g1-hooh mod90), with its sidecar beside it.

What they show, read through the host's readers (R10 Q27): each `.hess`
reproduces its output's printed frequencies to 0.005 cm^-1; removing the
held torsion from the Hessian at 0 and 180 deg leaves exactly those
structures' five real modes (the imaginary mode is the torsion), which
the saddle searches reproduce to 0.3 cm^-1; the `.engrad` ORCA leaves
beside an `Opt Freq` pairs the final coordinates and energy with the
gradient of the cycle before, 1.6e-4 A away, and is not used.
