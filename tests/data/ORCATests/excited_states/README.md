# One acrolein td request by two response approximations

ORCA 6.1.1 on CUHK Charles, CUHK Slurm 2150076 (R10 q7 oracle O1), written
and run through the human CLI on tree `7111e2a6`: s-trans acrolein at its
Gaussian PBE0/def2-SVP minimum, the six lowest singlet roots,

```yaml
td:
  functional: pbe0
  basis: def2-svp
  response_method: tda   # or tddft
  state_manifold: singlet
  nstates: 6
  ri_approximation: none
```

| file | response | ORCA prints |
|---|---|---|
| `acrolein_pbe0_def2svp_tda_singlet6.out` | Tamm-Dancoff | `Tamm-Dancoff approximation ... operative` |
| `acrolein_pbe0_def2svp_td_singlet6.out` | full TD-DFT | `Tamm-Dancoff approximation ... deactivated` |

The Gaussian logs of the same two requests on the same geometry are
`../../GaussianTests/tddft/acrolein_pbe0_def2svp_{tda,td}_singlet6.log`.
TDA lies above full TD-DFT root by root: +0.026 eV for the n->pi* S1 and
+0.44 eV for the bright pi->pi* S2 -- two approximations of one root, which
is why a response method is part of the level a number was computed at.
