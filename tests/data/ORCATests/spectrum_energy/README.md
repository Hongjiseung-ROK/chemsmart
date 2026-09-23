# A spectrum's energy is its reference's

ORCA 6.1.1 on CUHK Charles, CUHK Slurm 2149487 (R10 q2 oracle 2), written
and run through the human CLI on tree `4f6d24b5`: water at one fixed
geometry, `functional: b3lyp` (written `B3LYP/G`), def2-SVP, ORCA's default
numerics.

| file | job | ORCA's own lines |
|---|---|---|
| `water_sp.out` | `sp` | `FINAL SINGLE POINT ENERGY -76.358268518392` |
| `water_td_tda3.out` | `td --response-method tda --nstates 3 --state-manifold singlet` | `E(SCF) = -76.358268518`, `DE(CIS) = 0.280293239 (Root 1)`, `FINAL SINGLE POINT ENERGY -76.077975279175` |

ORCA writes E(SCF) + DE(CIS) of root 1 as a fixed-geometry spectrum's final
energy, so the reader's `energy` on this `td` was root 1's total, labelled
`reference`, where PySCF's `td` answers the reference.
