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

## Repairs committed (before O2)

- adc130b1 pyscf: the driver attaches the core potential the basis defines
  (PySCF's own library entry), records per-element core electrons; the
  validator counts explicit electrons with them; CPU no longer refuses,
  GPU refuses by name.
- ab42ab5d gaussian: `5d` is written for the basis names Gaussian builds
  with Cartesian d (manual list: 3-21G, 6-21G, 4-31G, 6-31G family,
  CEP-31G, D95, D95V) unless the route names an angular form.
- 4002da10 analysis: levels state `basis_functions`,
  `ecp_core_electrons` per element and, for correlated levels,
  `frozen_core_conventions`; the expression observation compares a frozen
  core by rule, core potentials per shared element, and the angular form
  among operands that state it.

## Oracle O2 (pre-registered before submission; repaired tree 4002da10)

Same private config, geometries and tight numerics as O1; the comparison
values are O1's. Job o2a: PySCF at def2-SVP on HI, H, I, CH3I, CH3 (HF,
B3LYP, MP2 `frozen_core: auto`), MP2 with frozen core unset on HI, I, H,
CCSD(T) auto on HI, HF/def2-TZVP on HI in PySCF and ORCA, the HF/def2-SVP
Hessian of HI in PySCF and ORCA (analytic `Freq` and `NumFreq`). Job o2b:
Gaussian as written now (B3LYP/6-31G(d) water, CH2O, CH3Cl, Cl; MP2 CH2O;
B3LYP water at 6-31+G(d,p), 6-311+G(d,p), D95V, CEP-31G; CH3Cl at
3-21G*), ORCA B3LYP/6-31+G(d,p) water, and the CH2O handoff (Gaussian
opt=verytight as written, PySCF Hessian on the geometry reached).

E2-A. PySCF HF/def2-SVP totals within 1e-6 Eh of O1's ORCA on all five
species; recorded core electrons {I: 28} on the iodine species, 0
elsewhere; electrons 26 / 1 / 25 / 34 / 9; every PySCF receipt
`validated`. Failure (a different potential or basis behind the name, or
a wrong record) if any total is further or any validation finding.
E2-B. B3LYP within 1e-5 Eh of ORCA on all five.
E2-C. MP2 auto: frozen orbitals 4 / 0 / 4 / 5 / 1 (ORCA's and Gaussian's);
totals within 2e-6 of ORCA; HI -> H + I MP2 bond energy within 0.01
kcal/mol of 71.43922.
E2-D. MP2 frozen core unset (all electrons): HI and I lie more than 1 mEh
below their auto totals; the HI bond energy change is recorded, expected
below 1 kcal/mol. Replay: PySCF-default HI minus ORCA HI carries a
`frozen_core` observation; PySCF-auto HI minus ORCA HI carries none.
E2-E. CCSD(T) auto HI within 5e-6 Eh of O1's ORCA and Gaussian.
E2-F. HF/def2-TZVP HI: PySCF within 1e-6 Eh of ORCA.
E2-G. HI HF/def2-SVP harmonic wavenumber (r = 1.609 A, not a minimum):
PySCF analytic within 1 cm-1 of ORCA analytic, within 2 cm-1 of ORCA
NumFreq; PySCF's recorded max|gradient| within 1e-5 Eh/Bohr of ORCA's
printed gradient.
P2-A. Gaussian prints `(5D, 7F)` for every Gaussian run in o2b, with no
`5d` written for 6-311+G(d,p).
P2-B. Gaussian B3LYP/6-31G(d) as written within 1e-6 Eh of O1's G5 and
within 1.5e-6 of O1's ORCA on water, CH2O, CH3Cl, Cl; MP2 CH2O within
1e-7 of O1's G5.
P2-C. Gaussian B3LYP/6-31+G(d,p) water within 1e-6 Eh of ORCA's.
P2-D. CEP-31G water: Gaussian's level states {O: 2, H: 0} core electrons.
H2. PySCF max|g| at the CH2O minimum Gaussian reaches as written now
<= 3e-5 Eh/Bohr (O1: 9.45e-5 as written then, 8.6e-7 with `5d 7f`).

## O2 jobs and results (read from raw outputs and receipts)

- 2151888 (slot a, prereg 10922bcd81be) cli/o2a, code a930b54b, digest
  9a95ee79 verified on the node: 24 commands, 10 exit 0, 14 exit 1.
- 2151890 (slot b, same prereg) cli/o2b: 13 commands, all exit 0.

E2-A FAILED as pre-registered, on the record and not the physics: every
PySCF run on an iodine species ran to normal termination and was refused
by its own validator, `pyscf.result.atom_identity_mismatch` -- the driver
wrote `mol.atom_charges()`, which under a core potential is Z less the
core (25 for iodine). My local check had read the electron counts and not
run the whole validator. Repaired in 1b5ae687 (records Z). The physics
held: PySCF HF/def2-SVP minus O1's ORCA 9.5e-11 (HI), 8.5e-11 (I), 1.7e-10
(CH3I), 3.5e-13 (H), 1.6e-11 (CH3) Eh; electrons 26/1/25/34/9; recorded
cores {I: 28}; H and CH3 validated.
E2-B holds: B3LYP PySCF minus ORCA <= 1.42e-6 Eh.
E2-C holds: MP2 auto froze 4/0/4/5/1; totals within 1.75e-8 of ORCA; HI
MP2 bond energy 71.43923 (ORCA 71.43922), CH3I 60.20161 in both.
E2-D holds: all-electron HI and I lie 14.87 and 14.44 mEh below auto; the
HI bond energy rises by 0.271 kcal/mol (71.711).
E2-E holds: CCSD(T) auto HI minus ORCA -6.1e-10 Eh.
E2-F holds: HF/def2-TZVP HI minus ORCA -1.5e-10 Eh (56 functions each).
E2-G holds: HI wavenumber PySCF analytic 2421.80, ORCA analytic 2421.81,
ORCA NumFreq 2421.80 cm-1; PySCF max|g| 3.043316e-3 vs ORCA 3.043338e-3.
P2-A holds except one name: `(5D, 7F)` for 6-31G(d) (four species),
MP2/6-31G(d), 6-31+G(d,p), 6-311+G(d,p) (no `5d` written), D95V, 3-21G*;
CEP-31G printed `(5D, 10F)` -- the manual's "all built-in sets use pure
f" does not hold for CEP; the writer now states `5d 7f` (8c4a7169).
P2-B holds: Gaussian B3LYP/6-31G(d) as written now equals O1's G5 to every
printed digit on all four species, within 8.5e-7 Eh of ORCA; MP2 CH2O
equals O1's G5.
P2-C MISSED its band: Gaussian minus ORCA at B3LYP/6-31+G(d,p) is 1.38e-6
Eh, over the 1e-6 I wrote (28 functions in both; the diffuse set's grid
error; 0.0009 kcal/mol).
P2-D holds: the CEP-31G level states cores {O: 2, H: 0} (Gaussian printed
no table; read from its electron count and nuclear repulsion energy). The
same level had no `basis` -- the Gaussian route reader's prefix list
lacked D95/CEP/SDD/STO names (4107e350).
H2 holds: PySCF max|g| 8.6e-7 Eh/Bohr at the CH2O minimum Gaussian reached
as written now (O1 as written then: 9.45e-5).

## Oracle O2' (pre-registered before submission; tree 4107e350)

The iodine PySCF runs O2 refused, re-run on the repaired record, and the
references a live goal at CCSD(T)/def2-TZVP will be read against.
O2'-A. PySCF HF/def2-SVP HI, I, CH3I and MP2 auto HI, I, CH3I, MP2 unset
HI, CCSD(T) auto HI, and the HF/def2-SVP Hessian of HI: every receipt
`validated`, atomic numbers [1, 53], [53], [6, 53, 1, 1, 1]; totals equal
to O2's within 1e-9 Eh; HI wavenumber 2421.8 +- 0.1 cm-1.
O2'-B (goal references). CCSD(T)/def2-TZVP at r(HI) = 1.609 A, ORCA
defaults and PySCF `frozen_core: auto`, HI, H, I: De(HI) from the two
programs within 0.01 kcal/mol, in 70-82 kcal/mol (scalar-relativistic, no
spin-orbit; experiment De 73.7 with I's spin-orbit lowering about 7).
PySCF with frozen core unset: De within 1 kcal/mol of the frozen one.
B3LYP/def2-TZVP HI optimised and its Hessian in PySCF: r_e 1.60-1.63 A,
one real mode 2250-2400 cm-1, both receipts validated.
O2'-C. Gaussian CEP-31G water as written now prints `(5D, 7F)`.

## O2' results (CUHK Slurm 2152029, prereg d4bf3f737d3a, code d31f1170)

20 commands, 19 exit 0. O2'-A holds: all nine PySCF iodine runs
`validated`, atomic numbers [1, 53] / [53] / [6, 53, 1, 1, 1], totals equal
to O2's within 3.4e-13 Eh, HI HF wavenumber 2421.80 cm-1. O2'-B holds:
CCSD(T)/def2-TZVP De(HI) 75.89057 kcal/mol from ORCA and from PySCF auto
(difference < 1e-5); PySCF with the frozen core unset 76.13738 (+0.247).
ORCA's CCSD(T) of the H atom failed (`orca_mdci`: "Number of processes
(8) in parallel calculation exceeds number of pairs (0)"); its reference
energy, exact for one electron, stands in (-0.499809832 Eh, equal to
PySCF's). PySCF B3LYP/def2-TZVP HI optimised to r_e 1.6155 A, its Hessian
one mode at 2299.88 cm-1 (max|g| 2.9e-6), both validated. O2'-C holds:
CEP-31G `(5D, 7F)`.

## Goal g1-hi (pre-registered before issue; code d31f1170, packed as code-r2)

Task (TASK.md, verbatim): "The attached structure is hydrogen iodide (HI,
neutral, singlet) at a bond length of 1.609 Å. I would like its bond
dissociation energy, HI → H + I, as an electronic energy (no zero-point
correction), at CCSD(T)/def2-TZVP at this geometry. Please compute it with
both ORCA and PySCF, and report the value each program gives in kcal/mol
and whether the two programs agree." Workspace: hi.xyz. Envelope: orca,
pyscf on CPU; 8 cores, 24 GB; node 1800 s; episode 5400 s; 10 engine
calls; 2 revisions; delegated approval
`claude-researcher-q12-owner-delegated` (never a human decision); model
deepseek-v4-flash-0731 via alibaba-token-plan. One goal is one
observation. The task names no core potential, frozen core or angular
form.

Base-tree control (not re-run): O1 E-C -- on 1dbc9984 a PySCF def2-SVP HI
run passed `run --fake` and was refused at run time
(`ecp_unmaterialized`), so this task could not have been done in PySCF.

Success (capability): every PySCF node on an iodine species executes and
its receipt is `validated` with core electrons {I: 28} recorded; the
reported ORCA De equals O2'-B's ORCA reference within 0.01 kcal/mol.
If the session's PySCF frozen core is `auto` (or a count equal to
ORCA's), its PySCF De equals ORCA's within 0.01 kcal/mol; if it is unset,
PySCF's De is O2'-B's all-electron value within 0.01 kcal/mol, and any
expression combining an ORCA and a PySCF energy carries a `frozen_core`
level observation (none on the basis, angular form or core potential).
Settles achieved or achieved_with_observations; each reported number
reproduces from the receipts' energies.
Failure: a PySCF iodine node refused or not validated; a reported De not
reproducible from the receipts; a De outside 70-82 kcal/mol; an
observation naming the basis, the angular form or the core potential
between ORCA and PySCF.
Recorded, not scored (behaviour of this model): whether the session
names the core potential or the frozen core, and what it says about any
difference between the programs.

## Goal g2-nh3 (pre-registered before issue; code d31f1170, packed as code-r2)

Task (TASK.md, verbatim): "The attached structure is ammonia (NH3,
neutral, singlet). I would like the proton affinity of ammonia at
B3LYP/6-31G(d), as the electronic energy difference between NH3 and NH4+
each at its own optimised geometry (no zero-point or thermal
corrections). Please compute it with both Gaussian and PySCF, and report
the value each program gives in kcal/mol and whether the two programs
agree." Workspace: nh3.xyz (N-H 1.017 A, 106.3 deg, not optimised).
Envelope: gaussian, pyscf on CPU; 8 cores, 24 GB; node 1800 s; episode
5400 s; 10 engine calls; 2 revisions; same delegated approval and model.
The task names no angular form. One goal is one observation.

Counterfactual (not re-run): on 1dbc9984 Gaussian builds 6-31G(d) with
Cartesian d and PySCF spherical; O1 P-D moved a charge-changing relative
energy (the water IP) by 0.18 kcal/mol between the two forms.

Success: every Gaussian node's route carries `5d 7f` and its level says
`basis_functions: spherical`; the two programs' proton affinities agree
within 0.05 kcal/mol (default numerics, independent optimisations); the
value lies in 205-215 kcal/mol; any expression combining a Gaussian and a
PySCF energy carries no `basis_functions` observation; settles achieved
or achieved_with_observations; reported numbers reproduce from receipts.
Failure: a Gaussian route without the angular statement for a 6-31G name,
a level saying cartesian_d, a difference over 0.05 kcal/mol, or numbers
that do not reproduce.

## Goals issued

- 2152052 (slot b, prereg 1fd17df834b4) goals/g1-hi, code d31f1170
  (digest verified on the node).
- 2152096 (slot a, prereg 9d5d7b3df135) goals/g2-nh3, same code.

## Status

- step 1: tree read; O1 pre-registered above; code unchanged.
- step 2: O1 read (above). Premise holds for the angular form; ORCA and
  Gaussian are one def2 basis on iodine (ECP and frozen core); PySCF
  refuses it at run time; the level record is silent on the angular form
  and ECP and false on frozen core across species.
- step 3: repairs adc130b1, ab42ab5d, 4002da10; O2 read: physics held,
  the PySCF iodine record did not (1b5ae687); CEP f form (8c4a7169);
  Gaussian basis vocabulary (4107e350).
- step 4: O2' read (all iodine PySCF runs validated); ECP fixtures and
  witnesses (9e4d39ab); goals g1-hi and g2-nh3 issued; r10-integration
  merged (c8edd0fc, no conflicts).
