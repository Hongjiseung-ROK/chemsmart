# ORCA excited states: one request, several words

ORCA 6.1.1 on CUHK Charles through the human CLI, PBE0/def2-SVP with
`ri_approximation: none`, every run the same `td:` section the other two
programs were sent.

## Two response approximations of one request (R10 Q7, Slurm 2150076)

Tree `7111e2a6`; s-trans acrolein at its Gaussian PBE0/def2-SVP minimum,
the six lowest singlet roots.

| file | response | ORCA prints |
|---|---|---|
| `acrolein_pbe0_def2svp_tda_singlet6.out` | Tamm-Dancoff | `Tamm-Dancoff approximation ... operative` |
| `acrolein_pbe0_def2svp_td_singlet6.out` | full TD-DFT | `Tamm-Dancoff approximation ... deactivated` |

The Gaussian logs of the same two requests are
`../../GaussianTests/tddft/acrolein_pbe0_def2svp_{tda,td}_singlet6.log`.
TDA lies above full TD-DFT root by root: +0.026 eV for the n->pi* S1 and
+0.44 eV for the bright pi->pi* S2.

## New manifold words (R10 Q8 oracle O1, Slurm 2150194)

Tree `4a01097a`.

| file | request | written as |
|---|---|---|
| `acrolein_pbe0_def2svp_td_triplet3.out` | `triplet`, nstates 3, tddft | `Triplets true` (ORCA has no triplet-only solve); the triplet block is served |
| `allyl_upbe0_def2svp_td_unrestricted6.out` | `unrestricted`, nstates 6, tddft | no spin option on the UKS reference |
| `allyl_upbe0_def2svp_tda_unrestricted6.out` | `unrestricted`, nstates 6, tda | no spin option on the UKS reference |

The allyl radical is at its Gaussian UPBE0/def2-SVP minimum (the same job).
ORCA prints each open-shell root's `Mult` as "estimated based on rounded
<S**2> value, RELEVANCE IS LIMITED!" (the sixth full-TD-DFT root is `6-4A`,
<S**2> 2.72). Its six TDA roots lack the bright 2B2 root at 6.704 eV
(f 0.56) that Gaussian's and PySCF's six-root windows hold: a Davidson
window, not a spectrum. Under full TD-DFT ORCA prints <S**2> 0.801 for the
first root where Gaussian prints 0.713; under TDA both print 0.756.
