# R10 Q2 -- one name, one physics

Base SHA: b834057741edb1246d7d2762c374a0e83d4e4f33 (verified `git rev-parse HEAD` at start)
Episode id: q2
Branch: worktree-agent-a00bcce00d346c895

## Question (as currently understood)

Can one project statement mean one Hamiltonian wherever CHEMSMART
translates it, and one selector name one physical quantity whichever
program produced it -- with the host recording what was actually applied
and telling any operation that combines numbers when its inputs are not
comparable -- so that neither the Agent nor a reviewer needs a program's
conventions, and the model is no longer taught them?

## What the tree says before any change (read, not yet run)

- `functional: b3lyp` is written `B3LYP` for ORCA (VWN5 local correlation,
  ORCA prints `LDAOpt .... VWN-5`), `b3lyp` for Gaussian (IExCor 402), and
  resolved to `b3lypg` (libxc 402, the VWN-RPA form) for PySCF. Archived
  evidence already shows ORCA `B3LYP/G` (`LDAOpt .... VWN-3`) equals PySCF
  `b3lypg` to 1.1e-6 Eh on water (orca_differential/water_td_b3lypg.out
  E(SCF) -76.358315131 vs water_td_singlet -76.358316223).
- ORCA's `energy` on a `td` job is `FINAL SINGLE POINT ENERGY`, which ORCA
  writes as E(SCF)+DE(CIS) of root 1 (-76.080796713 on that same fixture),
  while the reader resolves its provenance to `reference` and PySCF's `td`
  `energy` is the reference -- one selector name, two quantities.
- Gaussian `energy` is `energies[-1]`, where `energies` returns the EUMP2
  list whenever any EUMP2 line exists and SCF Done energies otherwise.
- ORCA/Gaussian surfaces write `unknown` for dispersion, density fitting,
  frozen core; so no log-reader surface ever compares.

## Falsifiers and pre-registered bands (written before any job ran)

Oracle 1 (CLI reference, base tree = code identical to b8340577; jobs
`cli/oracle1a`, `cli/oracle1b`). Energies are Eh unless stated.

H0 (premise falsified) if ALL hold: matched-numerics programs agree
(P1), AND the VWN5-minus-VWN-RPA change in every relative energy of Block R
(vertical IP of water, HCN->HNC, C-Cl homolysis of CH3Cl) is below
0.1 kcal/mol, AND no archived plan combined values across programs or
levels. Then the divergence is inert and the episode narrows to the
wrong-number defects and deleting the taught convention.

P1 (numerics bound). At tight matched numerics (ORCA NoRI DEFGRID3
VeryTightSCF; Gaussian scf=tight int=ultrafine; PySCF defgrid3 conv_tol
1e-10), ORCA `B3LYP/G`, Gaussian `B3LYP` and PySCF `b3lyp` (b3lypg) totals
agree within 5e-5 on every species; ORCA `B3LYP` and PySCF `b3lyp5` agree
within 5e-5. Failure of P1 means a further Hamiltonian difference hides
behind the name (basis, ECP, grid pathology) and is itself a finding.

P2 (size). Same-program VWN5 minus VWN-RPA total offset is positive and
between 0.02 and 0.5 on every species, growing with electron count.

P3 (relative energies, the premise's live test). |Delta(VWN5) -
Delta(VWN-RPA)| for the water vertical IP, HCN->HNC and CH3Cl -> CH3 + Cl:
expected < 0.3 kcal/mol for the isogyric isomerisation and larger (0.3-5
kcal/mol) for the two electron-pair-changing ones. The band is recorded,
never tuned.

P4 (Gaussian `energy`). On the base tree the reader's `energy` returns the
EUMP2 value for MP3/MP4/CCSD/CCSD(T)/QCISD(T) routes (differs from the
log's own final method energy by > 1e-3), the SCF part for B2PLYP (differs
from E(B2PLYP) by the PT2 term), and the ground state for the TD
optimisation. HF and MP2 are correct. Any route where `energy` equals the
printed final method total falsifies that case.

P5 (dispersion). D3(BJ) dispersion energies of benzene from ORCA, Gaussian
and PySCF agree within 1e-7 if all three apply the same two-body form; a
difference of order 1e-5-1e-4 is a three-body term in one program.

P6 (frozen core). CH3Cl MP2/def2-SVP: ORCA default and Gaussian default
correlation energies agree within 1e-6; PySCF default (all-electron)
differs from them by > 1e-3; PySCF `frozen_core: auto` matches them within
1e-6.

P7 (handoff fingerprint). PySCF b3lyp (tight) max|gradient| at the
formaldehyde minimum ORCA reaches with `functional: b3lyp` (as the Agent
writes it) is at least 3x the value at the minima reached by ORCA
`B3LYP/G` and by Gaussian `b3lyp`.

## Oracle

Block F: water, 9 project literals x 3 programs, tight numerics.
Block R: water, water cation (vertical), HCN, HNC, CH3Cl, CH3, Cl, benzene
x {as-written defaults per program, ORCA B3LYP/G defaults, and at tight
numerics PySCF b3lyp / b3lyp5, ORCA B3LYP/G / B3LYP, Gaussian B3LYP}.
Block C: Gaussian water/cc-pVDZ HF, MP2, MP3, MP4, CCSD, CCSD(T),
QCISD(T), B2PLYP; ORCA and PySCF CCSD(T) (PySCF default and frozen_core
auto); Gaussian TD-B3LYP/6-31G* optimisation of formaldehyde root 1.
Block X: benzene B3LYP-D3(BJ) in three programs, D4 in ORCA and PySCF.
Block Z: CH3Cl MP2/def2-SVP frozen-core defaults.
Block H: formaldehyde optimised by ORCA b3lyp, ORCA B3LYP/G, Gaussian
b3lyp; PySCF b3lyp Hessian (and gradient) on each reached geometry.

Private config: /project/xlzhang/jiseung/r10/q2/config (SERVER cores 8,
threads 8, memory 24 GB; scratch under /scratch/s1/xlzhang/jiseung/r10/q2;
every program block otherwise unchanged).

## Jobs issued

- 2149277 (slot r10-q2-a, prereg a56f5029aa91) cli/oracle1a: blocks F, C, X,
  Z, H. 54 commands, code digest 01aa9588... (commit 8f2c3443, code == base).
  Three commands exited 1: Gaussian `pbe`, Gaussian `b3lyp5` (Gaussian
  refuses both keywords at l1), PySCF `d4` (no dftd4 in the compute env).
- 2149278 (slot r10-q2-b, same prereg) cli/oracle1b: block R, 67 commands,
  all exit 0.
- 2149487 (slot r10-q2-a, prereg f7fd12e1dca5) cli/oracle2: 57 commands,
  all exit 0, code 4f6d24b5 (digest b4500a64 verified on the node).
- 2149545 (slot r10-q2-a, prereg 57c05ea24893) goals/g1-hono: the HONO goal,
  code e3fdaaca (digest c5235f6a verified on the node). 03:09-03:32 +08:00,
  2 cycles, 1 revision, settled `achieved` (goal exit 0).

## Goal g1-hono results (host records: ledger, streams, engine outputs)

- The session wrote `functional: b3lyp` for all four ORCA projects and both
  PySCF projects. ORCA TS, cis and trans nodes: route `! ... B3LYP/G
  def2-svp`, `LDAOpt .... VWN-3` (R9: `b3lyp`, VWN-5). Band 1 met.
- PySCF IRC start max|g| 1.132e-4 Eh/Bohr on both branches (R9 3.605e-4):
  3.2x lower, 13% ABOVE the 1.0e-4 band I wrote, below the 3e-4 failure
  line. Band 2 missed as written. ORCA's own OptTS signalled convergence by
  its step rule with its internal MAX gradient 3.7e-4 (tolerance 3.0e-4, NO)
  and a Cartesian MAX gradient of 1.73e-4 at its last evaluated point; the
  R9 saddle had converged to 5.5e-5 on its own (VWN5) surface. The
  residual on PySCF's surface is now bounded by ORCA's own convergence, not
  by a functional mismatch -- but one run does not separate the two and I
  wrote the band without allowing for ORCA's step-rule exit.
- Claimed barriers 14.5238 (from cis) and 14.0890 (from trans) kcal/mol,
  equal to ORCA's printed energies (TS -205.519598391, cis -205.542743544,
  trans -205.542050611); R9 14.51 / 14.08: +0.014 / +0.009, band 3 met.
- IRC: forward ends cis (O=N-O-H -0.01 deg), backward trans (-179.89), as
  in R9. PySCF endpoints vs ORCA minima 2.0e-4 / 2.15e-4 Eh (default
  numerics); cis-trans gap 0.442 (PySCF) vs 0.435 (ORCA) kcal/mol.
- No `level_observations` were emitted: every combination was within ORCA,
  one level.
- Behaviour (deepseek-v4-flash-0731, one observation): cycle 1 read the
  functional receipts and wrote them into its decision ("b3lyp applied as
  B3LYP/G, vwn3_gaussian convention", citing the refs), and kept every
  barrier energy in one program "for internal consistency". The woken cycle
  2 session, which saw only the PySCF receipts, wrote that "ORCA B3LYP
  differs in the VWN correlation parameterisation" and flagged a possible
  residual gradient -- false for this run, with `applied_method: b3lyp` on
  both ORCA results in its own context. It reached no decision or claim.

## Oracle 1 results (read from the logs and artifacts, base tree)

P1 holds. Tight matched numerics: ORCA `B3LYP/G`, Gaussian `B3LYP`, PySCF
`b3lyp` totals agree within 2.2e-6 on all eight species (benzene worst);
ORCA `B3LYP` and PySCF `b3lyp5` within 8.6e-7. At the programs' default
numerics (ORCA RIJCOSX + DEFGRID2) the matched spread is <= 3.5e-4.

P2 holds. VWN5 minus VWN-RPA total offset, identical in ORCA and PySCF to
1e-6: CH3 0.0323, H2O+ 0.0334, H2O 0.0371, HNC 0.0517, HCN 0.0517, Cl
0.0653, CH3Cl 0.0982, benzene 0.1543 Eh (about 3.7 mEh per electron).

P3: the premise is NOT falsified. VWN5 minus VWN-RPA in relative energies
(tight, same program): water vertical IP -2.34 kcal/mol (0.102 eV); CH3Cl
-> CH3 + Cl -0.376; HCN -> HNC -0.011. Default-numerics spread of the same
relative energies across the three programs at one functional: <= 0.025
kcal/mol. The as-written ORCA `b3lyp` IP (283.95) differs from Gaussian's
and PySCF's (286.31) by 2.35 kcal/mol: the "about 0.1 eV" the crossprogram
charter recorded is this offset.

Screen (water, tight): one literal, one functional for blyp, cam-b3lyp
(ORCA prints VWN-5 and matches Gaussian and PySCF to 6e-7), m062x (7e-6),
tpssh (3e-6), pbe0 ORCA vs PySCF (1.0e-5), pbe ORCA vs PySCF (1.4e-5).
Two functionals: `b3lyp` (ORCA VWN5 vs the others VWN-RPA, 0.037) and
`bp86` (ORCA PW92 local correlation, `LDAOpt PW91-LDA`, 1.49e-3 below
Gaussian; Gaussian vs PySCF 8.0e-5). Gaussian `pbe0` is not PBE0: Gaussian
prefix-matched it to the PBE0-DH double hybrid (`SCF Done: E(RPBE0DH)`,
IExCor 1009, E2 printed), and the reader returned its SCF part,
-76.2397989, 0.0365 above PBE0 (-76.27627 in ORCA and PySCF).

P4 holds on every case. Gaussian `energy` on water/cc-pVDZ returned
EUMP2 -76.2284380 for MP3 (log -76.2354356), MP4SDTQ (-76.2406725), CCSD
(-76.2380047), CCSD(T) (-76.2410412), QCISD(T) (-76.2411041); the SCF part
-76.2884647 for B2PLYP (E(B2PLYP) -76.3530984); the ground state
-114.4864268 for the TD-B3LYP optimisation whose surface is root 1
(-114.3622683). HF and MP2 correct. ORCA CCSD(T) (FC default) agrees with
Gaussian's to 1.2e-7 and PySCF `frozen_core: auto` to 1e-7; PySCF's default
(all electrons) lies 2.1e-3 below.

P5 holds for D3(BJ): ORCA -0.01889787, PySCF -0.018897869850; Gaussian
prints no separate term and its total matches PySCF's to 2.2e-6 as without
dispersion, so no program adds a three-body term.

P6 holds. CH3Cl MP2/def2-SVP correlation: Gaussian (NFC 6) -0.2831213930,
ORCA -0.283121318, PySCF auto (6) -0.2831213750; PySCF default (0 frozen)
-0.2951009534, 0.0120 Eh (7.5 kcal/mol) away.

P7 FALSIFIED. PySCF b3lyp max|g| at the formaldehyde minimum reached by
ORCA `b3lyp` (VWN5) 2.33e-4 vs 1.86e-4 at ORCA `B3LYP/G`'s and Gaussian's:
1.25x, not 3x. At default optimiser convergence a minimum's residual
gradient hides the variant; the archived HCN saddle (4.4e-4 vs 2.8e-5) is
where it showed.

## Oracle 2 (pre-registered before submission; repaired tree)

Same CLI shape, private config, 8 cores. Blocks and bands:

V1. `functional: b3lyp` as the Agent writes it, default numerics, on water,
water cation, CH3Cl, CH3, Cl: ORCA now prints `LDAOpt .... VWN-3`; every
ORCA total within 3.5e-4 Eh of Gaussian's and PySCF's (oracle 1 default
spread; before: 0.032-0.098 Eh); the vertical IP and the C-Cl homolysis
agree across the three programs within 0.03 kcal/mol (before: 2.35 and
0.38). Failure: any ORCA total > 3.5e-4 away, or a relative energy > 0.05.
V2. ORCA `b3lyp` tight equals PySCF `b3lyp` tight within 2.2e-6 (water,
cation, CH3Cl, CH3, Cl).
V3. Gaussian `pbe0` now runs PBE1PBE and `pbe` PBEPBE: water totals within
2e-5 Eh of ORCA and PySCF (before: pbe0 0.0365 off, pbe a failed run); the
reader's `functional` answers `pbe0` and `pbe`.
T. ORCA `td` (TDA, three singlets, as written) `energy` equals the ORCA
water `sp` total at the same settings within 1e-6 (before: E(SCF) + DE of
root 1), and PySCF `td` `energy` agrees with it within 3.5e-4.
B (decision data, not a repair yet). bp86 tight in three programs on seven
species. Decision rule written now: if ORCA minus Gaussian differs in any
of IP(water), CH3Cl -> CH3 + Cl, HCN -> HNC by >= 0.1 kcal/mol, `bp86` is
two functionals for relative energies and gets a translation or a refusal;
if every difference is < 0.1 kcal/mol while totals differ > 1e-4 Eh, the
literal is recorded as program-specific for totals only.
Z2 (decision data). MP2/def2-SVP HBr and ZnH2: ORCA default, Gaussian
default, PySCF default, PySCF `auto`. Rule: PySCF's unset frozen core is
made `auto` only if `auto` freezes the same count as ORCA's and Gaussian's
defaults on both; otherwise the counts are recorded per program and no
default is claimed to be one Hamiltonian.

## Oracle 2 results (job 2149487, prereg f7fd12e1dca5, code 4f6d24b5, digest b4500a64)

57 commands, all exit 0, read through the repaired readers.
V1 holds. ORCA `functional: b3lyp` (as written) now prints VWN-3 and its
`functional` answers b3lyp; ORCA default totals sit 4.4e-5 to 2.15e-4 Eh
from Gaussian's and PySCF's; water IP 286.2962 / 286.3055 / 286.3056 and
CH3Cl -> CH3 + Cl 82.4200 / 82.3949 / 82.3954 kcal/mol (ORCA / Gaussian /
PySCF): spreads 0.009 and 0.025 (were 2.35 and 0.38).
V2 holds: ORCA b3lyp tight -76.358141128 = oracle-1 B3LYP/G tight.
V3 partly misses its band: Gaussian `pbe0` now runs PBE1PBE, -76.2762499
(ORCA -76.2762745, PySCF -76.2762643) and `pbe` runs PBEPBE, -76.2719830
(ORCA -76.2720149, PySCF -76.2720009): Gaussian - PySCF 1.4e-5 / 1.8e-5
(inside 2e-5), Gaussian - ORCA 2.5e-5 / 3.2e-5 (outside the 2e-5 band I
wrote). All three answer `functional` pbe0 / pbe. Before: 0.0365 off and a
failed run.
T holds: ORCA td `energy` -76.35826851818 vs ORCA sp -76.35826851839
(2e-10); PySCF td `energy` -76.35814183 (1.27e-4 away, default numerics).
B decides: ORCA - Gaussian bp86 totals -0.96 to -2.67 mEh; IP(water)
-0.737 kcal/mol, CH3Cl -> CH3 + Cl -1.060, HCN -> HNC +0.001; PySCF -
Gaussian 0.0003, 0.0024, -0.0001 (totals 6e-5-2.3e-4 Eh). By the rule
written above, `bp86` is two functionals for relative energies: ORCA now
refuses `bp86` (no simple-input spelling of the PZ81 form) and spells its
own form as the literal `bp86-pw92`, which Gaussian and PySCF refuse.
Z2 decides: HBr frozen orbitals ORCA 9 (18 e), Gaussian 9, PySCF auto 9
(totals within 3.8e-7); PySCF default 0, 0.0346 Eh (21.7 kcal/mol) lower.
ZnH2: ORCA 5, PySCF auto 5 (3.6e-6), Gaussian NFC 9 (65 mEh away), PySCF
default 0. By the rule written above, PySCF's default is NOT changed: no
default is one Hamiltonian for Zn. Each program's result now states its
frozen count in its level, and an expression is told when counts differ.

## Goal g1-hono (pre-registered before issue)

Same task text and start geometry as the R9 goal g2-hono (CUHK 2140679;
TASK.md sha256 9fa0570b..., trans_hono.xyz 5eea4455...), same envelope
numbers (orca, pyscf, xtb; 8 cores, 32 GB; node 3000 s; episode 5400 s;
7 engine calls; 2 revisions), delegated approval
`claude-researcher-q2-owner-delegated` (never a human decision), model
deepseek-v4-flash-0731 via alibaba-token-plan.
Before (host records of 2140679): ORCA TS route `! OptTS Freq b3lyp
def2-svp`, LDAOpt VWN-5; PySCF IRC start max|g| 3.6047e-4 Eh/Bohr on both
branches; barriers 14.51 / 14.08 kcal/mol from ORCA energies.
Bands: if the session writes `functional: b3lyp` for ORCA and PySCF, the
ORCA TS prints LDAOpt VWN-3 and PySCF's IRC start max|g| <= 1.0e-4
Eh/Bohr (matched functional: ORCA's own TS criterion plus RIJCOSX and
grid numerics; the matched HCN saddle gave 2.8e-5); barriers move by
< 0.05 kcal/mol from 14.51 / 14.08. Failure: start max|g| > 3e-4 with
b3lyp in both, or an ORCA TS result whose `functional` is not b3lyp. A
different valid route is recorded as the session's choice, not scored.
One goal is one observation.

## Check D (pre-registered before submission): does `b3lyp` + `d3bj` in ORCA
keep its dispersion after the translation?

Two ORCA single points on the oracle-1 benzene, tight numerics, code
e3fdaaca (the goal's): `functional: b3lyp` (now written B3LYP/G) and
`functional: b3lyp5` (written B3LYP), both `dispersion: d3bj`.
Expected: both print the dispersion correction -0.01889787 Eh that ORCA
B3LYP + D3BJ printed in oracle 1 (and PySCF d3bj, -0.018897869850), within
1e-8 -- one set of Grimme parameters for both forms. If ORCA refuses
B3LYP/G with D3BJ, or prints another number, then every ORCA project
saying `b3lyp` with `d3bj` changed more than its local correlation, and the
report says so; nothing is repaired in this episode.

## Status

- step 1: oracle 1 pre-registered; code unchanged.
- step 2: oracle 1 read; premise stands for charge- and pairing-changing
  energies; wrong-number defects confirmed (Gaussian energy, pbe0).
- step 3: repairs written (literal -> one functional per program, receipts
  for every program, Gaussian energy by route method, ORCA td energy);
  oracle 2 pre-registered above.
- step 4: oracle 2 read; bp86 translated/refused by the pre-registered
  rule; frozen-core default left per program by the pre-registered rule;
  levels for ORCA and Gaussian and the expression-level observation
  committed; r10-integration merged (a24dd189, no conflicts); the HONO
  goal issued.
- step 5: the goal read from host records (above); r10-integration merged
  again; final checks and hand-back.
