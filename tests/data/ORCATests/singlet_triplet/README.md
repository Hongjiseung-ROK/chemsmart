# One td request with singlets and triplets, read in two programs

ORCA 6.1.1 and Gaussian 16 C.02 on CUHK Charles, CUHK Slurm 2150076 (R10 q7
oracle O1), written and run through the human CLI on tree `7111e2a6`:
acrolein (s-trans) at its Gaussian PBE0/def2-SVP minimum, the project

```yaml
td:
  functional: pbe0
  basis: def2-svp
  response_method: tddft
  state_manifold: singlet_triplet
  nstates: 3
```

(ORCA's also `ri_approximation: none`), i.e. three singlet and three
spin-adapted triplet roots of full linear-response TD-DFT.

| file | program | written as |
|---|---|---|
| `acrolein_pbe0_def2svp_td_singlet_triplet3.out` | ORCA | `%tddft NRoots 3 TDA false Triplets true end` |
| `../../GaussianTests/tddft/acrolein_pbe0_def2svp_td_singlet_triplet3.log` | Gaussian | `TD(50-50,nstates=3,root=1)` |

ORCA prints its `STATE` table singlets first, then triplets, and its
absorption table in energy order (T1 2.976, T2 3.196, S1 3.622, T3 5.647,
S2 6.536 eV f = 0.381, S3 7.049 eV); Gaussian prints both in energy order.
The bright state is S2 in both.
