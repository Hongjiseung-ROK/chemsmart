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

- 2151772 (slot r10-q12-a, prereg 851ba5b1ab25) cli/o1a: block P, 72
  commands, all exit 0. Code a03615af (== base chemsmart/), digest
  fbd2b58a... verified on the node.
- 2151773 (slot r10-q12-b, prereg 851ba5b1ab25) cli/o1b: blocks H, E, A,
  40 commands; 38 exit 0, commands 37 (PySCF HI) and 39 (PySCF def2/J)
  exit 1 as pre-registered (refusals).

## O1 results (read from raw outputs, not through a CHEMSMART reader)

P-A holds. Gaussian as written prints `Standard basis: 6-31G(d) (6D, 7F)`
and the Cartesian counts (19, 19, 34, 32, 32, 40, 21, 19); with `5d 7f`
it prints `(5D, 7F)` and the spherical counts, which ORCA (`Basis
Dimension`) and PySCF (`NR cGTOs`) print for every species.
P-B holds. G5, ORCA and PySCF agree within 2.0e-7 (HF), 8.5e-7 (B3LYP),
4.0e-8 (MP2, frozen 1 and 2 orbitals in all three).
P-C holds (premise): G6 lies below G5 on every species, by 0.25-1.97 mEh
at HF and 0.78-4.12 mEh at B3LYP. The magnitude I expected (0.2-3 mEh per
heavy atom) is exceeded once: Cl at B3LYP, 3.45 mEh. MP2 totals move
2.9 (water) and 4.2 (CH2O) mEh, 1.5 and 3.5 of it in the correlation.
P-D material: G6 - G5 in kcal/mol, HF / B3LYP: HCN -> HNC -0.130 /
+0.044, CH3Cl -> CH3 + Cl +0.167 / -0.069, water vertical IP -0.178 /
+0.184. ORCA, PySCF and G5 agree to 0.0004 kcal/mol in all six.
P-E holds. PySCF max|g| 9.45e-5 Eh/Bohr at the CH2O minimum Gaussian
reached as written, 8.6e-7 at the one it reached with `5d 7f`: 110x.
E-A holds. ORCA prints `Type I ECP Def2-ECP (replacing 28 core
electrons)`; electron counts 26 / 34 / 25 in ORCA and Gaussian; Gaussian's
nuclear repulsion (8.2221443586 Eh for HI) is the one of Z_eff(I) = 25.
E-B holds. ORCA - Gaussian: HF <= 1.2e-8, B3LYP <= 1.7e-6 on all five.
E-C: both PySCF refusals as predicted, but only at run time
(`ecp_unmaterialized` naming I; `aux_basis_unavailable` for def2/J). The
DF band FAILED: def2-universal-jfit minus no-DF is 1.92e-4 Eh, not <=
1e-4 -- PySCF's `density_fit()` fits exchange with the same auxiliary set,
so a Coulomb-only set (ORCA's def2/J, paired there with COSX) is the
wrong set for PySCF. A translation `def2/J -> def2-universal-jfit` would
make PySCF's approximation worse than ORCA's, not the same.
E-D holds. Frozen orbitals ORCA / Gaussian: HI 4/4, CH3I 5/5, I 4/4 (=
PySCF auto 4, 5, 4 on local PySCF); MP2 totals within 2.1e-8; HI MP2 bond
energy 71.43922 kcal/mol in both; CCSD(T) HI within 1.5e-8.

Replay through the host's own extraction and expression handlers (base
tree, provider-free) on these outputs:
- ORCA MP2 HI -> H + I and Gaussian MP2 CH3I -> CH3 + I, each one level of
  theory, are both reported `operands_at_different_levels` on
  `frozen_core` (counts 4/None/4 and 5/1/4): the level compares a
  per-molecule orbital count, so every correlated reaction energy between
  different species carries a false "different levels" word.
- Gaussian 6-31G(d) as written minus ORCA 6-31G(d) (1.92 mEh apart, two
  basis sets) and PySCF minus Gaussian as written: no observation; both
  levels say `basis: 6-31g(d)` and nothing else about the basis.

## Status

- step 1: tree read; O1 pre-registered above; code unchanged.
- step 2: O1 read (above). Premise holds for the angular form; ORCA and
  Gaussian are one def2 basis on iodine (ECP and frozen core); PySCF
  refuses it at run time; the level record is silent on the angular form
  and ECP and false on frozen core across species.
