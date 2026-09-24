# One basis name, the basis set ORCA built

ORCA 6.1.1 on CUHK Charles, R10 q12 oracle O1 (CUHK Slurm 2151772,
2151773), written and run through the human CLI on the base tree
`a03615af` (chemsmart/ identical to `1dbc9984`), `NoRI VeryTightSCF`
(and `DefGrid3` for the DFT run).

| file | project | ORCA printed | total (Eh) |
|---|---|---|---|
| `water_b3lyp_631gd.out` | `b3lyp`, `6-31G(d)` | Basis Dimension 18 (spherical) | -76.406807644167 |
| `hi_mp2_def2svp.out` | `mp2`, `def2-SVP` | Def2-ECP on I (28 core electrons), NCore=8 | -297.360082906 |
| `h_mp2_def2svp.out` | `mp2`, `def2-SVP` | no core, no NCore line | -0.499278406 |
| `i_mp2_def2svp.out` | `mp2`, `def2-SVP` | Def2-ECP on I (28 core electrons), NCore=8 | -296.746958855 |

Gaussian's MP2 on the same HI, H and I agrees to 1.4e-8 Eh with the same
frozen orbitals (4, 0, 4); the HI -> H + I bond energy is 71.43922
kcal/mol in both programs.
