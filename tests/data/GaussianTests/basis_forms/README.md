# One basis name, the basis set each program built

Gaussian 16 C.02 on CUHK Charles, R10 q12 oracle O1 (CUHK Slurm 2151772,
2151773), written and run through the human CLI on the base tree
`a03615af` (chemsmart/ identical to `1dbc9984`), at `scf=tight
int=ultrafine`.

| file | project basis | Gaussian printed | total (Eh) |
|---|---|---|---|
| `water_b3lyp_631gd_as_written.log` | `6-31G(d)` | `(6D, 7F)`, 19 functions | SCF -76.4087309161 |
| `water_b3lyp_631gd_5d.log` | `6-31G(d)` plus `5d 7f` | `(5D, 7F)`, 18 functions | SCF -76.4068084894 |
| `ch3i_mp2_def2svp.log` | `def2-SVP` | 34 electrons (28 on I replaced), NFC=5 | EUMP2 -336.50219934008 |
| `ch3_mp2_def2svp.log` | `def2-SVP` | 9 electrons, NFC=1 | EUMP2 -39.659303150974 |
| `i_mp2_def2svp.log` | `def2-SVP` | 25 electrons, NFC=4 | EUMP2 -296.74695884306 |

ORCA's B3LYP/G on the same water at 6-31G(d) (`NoRI DefGrid3
VeryTightSCF`, `../../ORCATests/basis_forms/water_b3lyp_631gd.out`) is
-76.406807644, 8.5e-7 Eh from the second file and 1.92 mEh above the
first. The iodine logs print no pseudopotential table; their nuclear
repulsion energies are the ones of an effective iodine charge of 25
(HI: 8.2221443586 Eh).
