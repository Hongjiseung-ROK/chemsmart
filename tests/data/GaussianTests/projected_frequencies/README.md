# Gaussian's own `freq=projected`, at a held torsion

Gaussian 16 C.02 on CUHK Charles, CUHK Slurm 2153717 (R10 Q27 oracle O1b),
written by the human CLI on tree `83b9bfbd` as a single point whose route
parameter asks for the projected frequency analysis:
`# b3lyp def2svp empiricaldispersion=gd3bj freq=projected`, at the H2O2
structures an `opt=modredundant` run holding H-O-O-H (atoms 3-1-2-4)
reached in oracle O1 (Slurm 2153713).

| file | held at | Gaussian printed | sha256 |
|---|---|---|---|
| `g_sp90_gas_phase.log` | 90.00 deg | 5 modes (3N-7): the gradient's direction removed, which here is the torsion's to 0.4 cm^-1 | `643c8a74c6cb3dff7f5eed9555f21746b23a149dc945ca4cf4befdf7bfeeb76f` |
| `g_sp0_gas_phase.log` | 0.00 deg | 5 modes: -612.87 cm^-1 (the torsion) kept and the 3778 cm^-1 O-H stretch lost | `3c74faebbc7b4f645163f7e81d52c47ef9d2a37e320cdeca270e9ca70e902a82` |

At 0 deg the gradient is 1.8e-5 Eh/Bohr and, by symmetry, orthogonal to
the torsion, so the projection Gaussian takes from it (Baboul & Schlegel
1997, Eq. 3) removes a stretch, and Gaussian's own "Sum of electronic and
thermal Free Energies" is 5.4 kcal/mol below the cis saddle's
transition-state free energy. Written through an `opt=modredundant ...
freq=projected` route instead (O1), the option reaches only the first job
step, and the frequency step Gaussian generates (`Geom=AllCheck ... Freq`)
runs the ordinary analysis.

Each job also prints Gaussian's own convergence check at its structure,
with the exact Hessian (R10 Q33): at 90 deg a maximum internal force of
3.17e-3 against 4.5e-4, not a stationary point; at 0 deg 9e-6, the cis
saddle.
