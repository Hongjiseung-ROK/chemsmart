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
