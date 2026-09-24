# R10 Q12 -- one basis name, one basis set

Base SHA: 1dbc9984fc7585c8758b62bffc67d6624d245603 (verified `git rev-parse HEAD` at start)
Episode id: q12
Branch: worktree-agent-a08929a6f88400c34

## Question (as currently understood)

Does one basis-set statement in a CHEMSMART project mean one basis set in
every program the hub translates it for -- the angular functions
(Cartesian or spherical), the effective core potential, the auxiliary
set, and for correlated methods the frozen core -- and is each difference
either translated away, or recorded where the result can be read and
refused where it cannot be reconciled?

## What the tree says before any change (read, not yet run)

- Gaussian: `basis` is written verbatim on the route (def2 names are
  re-spelled, nothing else); no 5D/6D token is ever written, so Gaussian
  applies its own default. Archived logs print `Standard basis: 6-31G(d)
  (6D, 7F)` (40 archived logs) and `34 basis functions` for CH2O
  (tests/data/GaussianTests/method_totals/h2co_td_b3lyp_opt_root1.log).
- ORCA: spherical harmonics only (no Cartesian option exists in ORCA).
- PySCF: `pyscf.M(basis=...)` with PySCF's default `cart=False`; local
  PySCF 2.13 gives CH2O/6-31G(d) 32 functions spherical, 34 Cartesian.
- PySCF ECP: `_build_mole` passes no `ecp`; locally `gto.M(basis=
  'def2-svp')` on HI silently runs all-electron (54 electrons) on the
  ECP-valence basis, and with `ecp='def2-svp'` 26 electrons. The host
  refuses the first with `pyscf.environment.ecp_unmaterialized` -- but
  only at run time: the environment probe is skipped by `--fake`, so a
  plan/preview/approval passes and the refusal spends an approved node
  (local `run --fake` of an HI def2-SVP PySCF sp exits 0).
- PySCF aux names: `def2/J` (ORCA's spelling, 32 uses in 511 archived
  Agent project files) is not a PySCF basis name (`def2-universal-jfit`
  is); `aux_basis_unavailable` is likewise raised only at run time.
- Levels: `_level_identity` compares the basis by its name with hyphens
  removed, so Gaussian 6-31g(d) (6D) and ORCA 6-31g(d) (5D) are "one
  basis" to `expression_level_observations`. No level records an ECP or
  the angular form. `frozen_core` is recorded by all three readers (Q2).
- Agent usage (511 archived project files, R8-R10): 6-31g(d) 44,
  6-31+g(d,p) 3, 6-311+g(d,p) 8, def2 sets ~340; an R9 Gaussian goal (g2)
  planned PySCF IRCs at `6-31g(d)` from a Gaussian `6-31g(d)` saddle (not
  executed: envelope).

## Oracle O1 (pre-registered before submission; base tree, code == 1dbc9984)

CLI reference calculations through `chemsmart run`, private config
`/project/xlzhang/jiseung/r10/q12/config` (the R10 CUHK profile with only
SERVER NUM_CORES 8, NUM_THREADS 8, MEM_GB 32 changed; every program block
unchanged), 8 cores per command. Tight matched numerics everywhere:
Gaussian `scf=tight int=ultrafine`; ORCA `NoRI`, `DEFGRID3` (DFT),
`VeryTightSCF`; PySCF `defgrid3` (DFT), `scf_tol 1e-10`, no density
fitting. Basis literals as the Agent writes them (`6-31G(d)`, `def2-SVP`),
frozen core unset except PySCF `auto` where named.

Block P (job o1a, 72 runs): water, water cation (vertical), CH2O, HCN,
HNC, CH3Cl, CH3, Cl (Q2 geometries) x {HF, B3LYP} x {Gaussian as written
(G6), Gaussian with `5d 7f` (G5), ORCA, PySCF}; MP2 on water and CH2O in
the same four (PySCF `frozen_core: auto`).
Block H (job o1b): CH2O B3LYP/6-31G(d) `opt=verytight` in Gaussian as
written and with `5d 7f`; a PySCF B3LYP/6-31G(d) `hess` (tight) on each
reached geometry (records the gradient there).
Block E (job o1b): HI, H, I, CH3I, CH3 x {HF, B3LYP, MP2} in ORCA and
Gaussian at def2-SVP as written; CCSD(T) HI in both; PySCF HF HI
(def2-SVP) as written.
Block A (job o1b): PySCF B3LYP/def2-SVP water with no DF, with
`aux_basis: def2/J`, with `aux_basis: def2-universal-jfit`.

### Bands and falsifiers (written before any job ran; energies Eh)

P-A (what each program applied). Gaussian as written prints `(6D, 7F)`
and Cartesian counts (water 19, cation 19, CH2O 34, HCN 32, HNC 32, CH3Cl
40, CH3 21, Cl 19); G5 prints `(5D, 7F)` and the spherical counts (18, 18,
32, 30, 30, 38, 20, 18), as ORCA (`Basis Dimension`) and PySCF (`NR
cGTOs`) do. Premise falsified if Gaussian as written applies 5D or if
ORCA or PySCF apply the Cartesian count.
P-B (one basis set when translated). G5, ORCA and PySCF agree on every
species within 1e-6 (HF), 5e-6 (B3LYP), 2e-6 (MP2 totals). A larger
spread means a further difference hides behind `6-31G(d)` (a different
contraction or exponent in one program's library), itself a finding.
P-C (the premise, totals). G6 lies below G5 (variational: the Cartesian
set contains the spherical one) by more than 1e-4 on every species with
a heavy atom; expected 0.2-3 mEh per heavy atom. Falsified (inert in
totals) if |G6 - G5| < 1e-5 on every species.
P-D (relative energies). |dE(G6) - dE(G5)| for HCN -> HNC, CH3Cl -> CH3 +
Cl and the vertical IP of water, at HF and at B3LYP: material if any is
>= 0.1 kcal/mol; inert for relative energies if all are < 0.05 kcal/mol.
Expected: material for at least one at B3LYP. Recorded, never tuned.
P-E (handoff fingerprint). PySCF (spherical) max|gradient| at the
geometry Gaussian reached as written (6D) is >= 3x the value at the
geometry Gaussian reached with `5d 7f`, and the latter is <= 3e-5
Eh/Bohr. Falsified (hidden in a handoff at this convergence) if the
ratio is < 3.
E-A (ECP applied as written). ORCA and Gaussian each apply a 28-electron
core potential to I with def2-SVP: electron counts HI 26, CH3I 34, I 25.
Falsified if either runs I all-electron.
E-B (one ECP basis in ORCA and Gaussian). HF totals agree within 2e-6,
B3LYP within 1e-5 on all five species. Failure means a different ECP or
contraction behind `def2-SVP`.
E-C (base-tree PySCF). The PySCF HI run is refused before any SCF with
`pyscf.environment.ecp_unmaterialized` naming I. The `def2/J` run is
refused with `pyscf.environment.aux_basis_unavailable`; the
`def2-universal-jfit` run completes within 1e-4 of the no-DF run.
Falsified (PySCF already materialises the ECP) if the HI run completes
with 26 electrons.
E-D (frozen core with an ECP). Each program's MP2 output states its
frozen count; ORCA's and Gaussian's defaults are compared on HI and
CH3I (PySCF `auto` on the same molecules: 4 and 5 orbitals, local
PySCF 2.13). If the counts agree the MP2 correlation energies agree
within 2e-6 and the HI MP2 bond energy within 0.01 kcal/mol; if they
differ, the counts are recorded per program. CCSD(T) HI totals agree
within 5e-6 when the counts agree.

## Jobs issued

(none yet)

## Status

- step 1: tree read; O1 pre-registered above; code unchanged.
