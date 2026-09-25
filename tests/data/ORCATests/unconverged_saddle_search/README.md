# A saddle search that did not converge, with frequencies printed on the way

ORCA 6.1.1, archived from the ax41 campaign (po3-r19 node `ts-esterc4`,
2026-09-12; the Hetzner mirror keeps the run directory). Written through
ChemSmart as `! OptTS Freq b3lyp def2-svp def2/j d3bj RIJCOSX` with
`%geom MaxIter 30 Calc_Hess True Recalc_Hess ...`: the triazole-forming
[3+2] cycloaddition saddle between a trifluoromethyl ynoate and benzyl
azide, 30 atoms, neutral singlet.

| file | what it is |
|---|---|
| `presaddle-esterc4_optts_optts.out` | 30 optimisation cycles, then "The optimization did not converge but reached the maximum number of optimization cycles ... ORCA will abort at this point of the run" before the requested frequency step |

It printed six complete frequency and thermochemistry sections anyway --
one for every Hessian the search computed or recalculated along its path --
at six different geometries, whose "Final Gibbs free energy" runs from
-1075.80439 to -1075.92317 Eh. None of them is at a stationary point. On
the tree before R10 Q21 the host derived a free energy from the last of
them (G = -1075.92317 Eh); one approved chain and two live sessions
delivered claims standing on it (among them dG(act) 23.194 kcal/mol and
ddG 0.614 kcal/mol), and a third session derived it without claiming.
sha256
`979a4f66bf379b7c766f1ec0ac28963db90a1efdb357c3129ff0f3180492bb20`.
