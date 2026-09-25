# R10 episode q20 -- one hard question across programs, take two (milestone B)

Base SHA: d5b15126c364478d07bce7849c350ed383b8150b (verified with
`git rev-parse HEAD` as the first action, 2026-09-25). Model:
claude-opus-5-5[1m]. Episode id `q20`.

## The question (as currently understood)

Through the merged hub, can the CHEMSMART Agent (deepseek-v4-flash-0731 via
alibaba-token-plan) carry one hard, scientifically meaningful, closed-shell
question across programs, from a structure to an answer comparable with the
literature, with every stage's evidence and lineage (identity, state, level,
geometry, producer evidence) intact in host records, where the crossing is
justified by capability? Where it breaks, whose break is it: the hub's (repair
in radius), a program's, the model's, or the science's?

First the known break on that road: a functional and dispersion pair that
previews green and dies inside the program (R10 Q15 g2: four Gaussian nodes,
`wb97x ... empiricaldispersion=gd3bj`, l301 "R6DS8: Unable to choose the S8
parameter", CUHK Slurm 2153334; R10 Q14 O1 L1: ORCA `wb97x ... d3bj`, "(D3BJ):
Non-parameterized functional used for dispersion correction" after the SCF,
CUHK Slurm 2152636).

## What the base tree does (read, provider-free, 2026-09-25)

- Gaussian (`jobs/gaussian/settings.py` `_get_level_of_theory_string`): any
  functional + any of d2/d3/d3zero/d3bj/gd2/gd3/gd3bj/pfd is written as
  `empiricaldispersion=<g-word>`; a `functional-Dn` shorthand is split into the
  base functional + `empiricaldispersion` (so `wb97x-d3bj`, `wb97x-d3`,
  `b97-d3`, `pw6b95-d3` become `wb97x`/`b97`/`pw6b95` + GD3/GD3BJ). The only
  dispersion refusals are conflicting declarations.
- ORCA (`jobs/orca/settings.py` `_get_route_string_from_jobtype`): the
  dispersion word is appended verbatim; no pair check; a shorthand literal
  (`b3lyp-d3bj`) goes to ORCA as a keyword.
- PySCF: the preflight probe (`jobs/pyscf/environment.py` `dispersion_detail`)
  asks PySCF 2.14's `parse_disp`/`check_disp`. Read in PySCF 2.14's own source
  on CUHK: `check_disp` checks only that the version word is in
  `DISP_VERSIONS`; the parameters are looked up only at run time by
  `dftd3.DFTD3Dispersion(mol, xc=method, version=...)` /
  `dftd4.DFTD4Dispersion` (pyscf-dispersion 1.5.0). PySCF's own comment: "wb97*-d3bj
  is wb97*-v with d3bj"; `wb97x-d`, `wb97x-d3` are black-listed.
- Enumerated with the hub's own settings classes (`census/hub_routes.py`):
  1,733 routes written (Gaussian 851, ORCA 882) for the vocabulary
  functionals x dispersion words; no pair is refused for parameters.

## Census D -- PRE-REGISTRATION (written before submission)

A slot job (16 cores) runs every unique route the hub writes (Gaussian,
ORCA) in the program itself on a fixed water dimer (S22 geometry, def2-SVP,
one core per run), and for PySCF runs the hub's own preflight probe
(`_PROBE_SCRIPT` + `_check_dispersion`) and then the writer's two lines
(`dft.KS(mol, xc=xc); mf.disp = disp; mf.kernel()`) for every (xc, disp) the
hub resolves from 59 functional literals x 12 dispersion literals. Each run
is classified by the program's own lines (ran / dispersion_unparameterized /
input or route rejected / other).

Predictions (never tuned after a result):
- D1 (known): Gaussian 16 C.02 refuses `wb97x ... empiricaldispersion=gd3bj`
  in l301 (R6DS8). D2 (known): ORCA 6.1.1 aborts `wb97x ... d3bj` after the
  SCF.
- D3: the class is general, not a wB97X accident: in each of Gaussian and
  ORCA more than 10 routes the hub writes green die on the program's
  dispersion parameters. FALSIFIED if 2 or fewer in a program.
- D4: B3LYP (Gaussian `b3lyp`, ORCA `B3LYP/G`) and PBE0 (`PBE1PBE`, `PBE0`)
  with D3(BJ) run in both programs.
- D5: ORCA's shorthand literals the hub passes verbatim (`b3lyp-d3bj`,
  `pbe0-d3bj`, `pw6b95-d3`) die in ORCA's input check before the INPUT FILE
  banner (probe-catchable, a different class).
- D6 (OPEN): whether PySCF's preflight marks `supported` any pair whose run
  then fails on missing parameters (the same class, for PySCF).
- D7: matched parameters are one correction: for B3LYP-D3(BJ) and PBE0-D3(BJ)
  the dispersion energies Gaussian, ORCA and PySCF print for the same
  geometry agree within 1e-7 Eh. FALSIFIED by a larger spread (then one name
  is two parameter sets, which the hub must state).

Scripts (uploaded to `/project/xlzhang/jiseung/r10/q20/cli/census/`, sha256):
hub_routes.py 4ce80c25..., census_run.py 84ea2bcb..., pyscf_pairs.py
54541cb0..., pyscf_run.py 3a862794...; the job prints the four digests.
Code: this commit's `chemsmart/` (identical to the base).

What the census decides: which pairs each program parameterises, measured on
the installed programs (Gaussian 16 C.02, ORCA 6.1.1, PySCF 2.14.0 with
pyscf-dispersion 1.5.0), the provenance the hub's table will carry.

## Census D -- READ (CUHK Slurm 2153534, chpc-cn072, 4 min; code b572f5bd
verified on the node; the four script digests printed)

Gaussian 16 C.02 (426 unique hub routes on the water dimer):
- 179 routes the hub writes green die in l301 before any SCF: "R6DS8: Unable
  to choose the S8 parameter" (GD3, GD3BJ) or "R6DS6: Unable to choose the S6
  parameter" (GD2), with Gaussian's own IExCor/IXCFnc for the functional.
- Parameterised, measured: GD3BJ only for B3LYP, B3PW91, BLYP, BP86, BPBE,
  PBEPBE, PBE1PBE, TPSSTPSS, BMK, CAM-B3LYP, B2PLYP, B97D, B97D3, B2PLYPD3,
  PW6B95D3; GD3 for those and M05, M052X, M06, M062X, M06HF, M06L; GD2 for
  B3LYP, BLYP, BP86, PBEPBE, TPSSTPSS, B2PLYP, B97D, B97D3, B2PLYPD3, WB97XD.
  wB97X, wB97, HSE, the Minnesota functionals with GD3BJ, B3P86, O3LYP,
  X3LYP, PW6B95 (bare) and 50 others die.
- PFD runs with every functional and prints the same `R6APFD ... FactS=
  1.050` for all 79: one model (APFD's), applied unchanged. APF + PFD equals
  APFD to every printed digit (-152.611906738 Eh).
- Gaussian's named keywords equal their base + GD3BJ to every printed digit:
  B97D3 = B97D + GD3BJ, B2PLYPD3 = B2PLYP + GD3BJ, PW6B95D3 = PW6B95 + GD3BJ
  (so a `-D3` shorthand split to GD3, zero damping, is not those keywords).
- 36 routes die at link 1 on a route word Gaussian has no keyword for, from
  the hub's shorthand split (`b97-d3` -> `b97`, `tpss-d3bj` -> `tpss`,
  `m06-2x-d3zero` -> `m06-2x`, `wb97m-d3bj` -> `wb97m`, ...) or from literals
  passed through (`wb97x-d`, `b97-d`, `*-d4`). No Gaussian probe exists.

ORCA 6.1.1 (768 unique routes):
- 96 routes die AFTER the INPUT FILE banner (after the SCF): "(D3BJ)/(D4):
  Non-parameterized functional used for dispersion correction" -- invisible
  to the input-check probe, which stops at the banner.
- ORCA's bare `D3` is D3(BJ) (every row identical to `D3BJ`); the hub writes
  `d3` for ORCA and `empiricaldispersion=gd3` (zero damping) for Gaussian: one
  word, two corrections.
- D3ZERO for an unparameterised functional is refused BEFORE the banner
  ("--> Change to D4 or D2", 68 routes), as are VV10 functionals + any D
  word, 3c composites + D words, unknown keywords (`b3lyp-d3bj` passed
  verbatim, 100) and double hybrids without AuxC (167, not dispersion):
  probe-catchable on the cluster, green on any host without ORCA.
- D2 never refuses: an unrecognised functional silently gets ORCA's default
  C6 scaling 1.200. That includes `B3LYP/G`, the spelling the hub writes for
  `b3lyp`: ORCA prints "The default B3LYP functional is recognized ... 1.050"
  for bare B3LYP and no recognition and 1.200 for B3LYP/G (-0.001571310 vs
  -0.001374896 Eh on the dimer). For D3BJ, D3ZERO and D4 it prints "Gaussian's
  B3LYP functional is recognized, using regular B3LYP params".
- D7 HOLDS for the pairs compared: B3LYP-D3(BJ) dispersion Gaussian
  -0.0021660520 (nuclear repulsion after/before the empirical term) vs ORCA
  -0.002166052 Eh; PBE0-D3(BJ) -0.0011237927 vs -0.001123793 Eh.

PySCF 2.14 preflight (the hub's own probe + `_check_dispersion`, 649 pairs):
513 GREEN -- every functional with every version word PySCF knows; the 136
refusals are only the words `d2` and `d3`. The run step crashed in my
script's JSON writer (a numpy scalar), not in PySCF: re-run as D-run2 with
the one-line fix (pyscf_run.py now sha256 9dd5b6a1...), no other change,
reading census D's own pyscf_probe.jsonl.

Predictions: D1, D2 PASS. D3 PASS (179 Gaussian, 96 ORCA). D4 PASS. D5 PASS
(before the banner). D6 OPEN until D-run2. D7 PASS for the two pairs read.

## The chemistry (chosen before any chemistry run)

The thermal 6pi-electrocyclic ring closure of (Z)-1,3,5-hexatriene (C6H8) to
1,3-cyclohexadiene, gas phase. Closed shell throughout (a disrotatory, aromatic
transition state; checked below with the hub's typed stability evidence before
any goal). Hard for reasons that are not the reference's electronic structure:
- the reactant's ground state is the planar tZt conformer, and the ring can
  close only from the helical cZc conformer, so a barrier taken from the
  reactive conformer is not the observed one: the kinetics measure the
  disappearance of the equilibrium conformer mixture;
- the reference is a gas-phase Arrhenius activation energy at 390-434 K, so
  the comparable quantity is an enthalpy of activation at that temperature;
- the TS must be located and connected, and a correlated energy is needed to
  claim more than a functional's luck.

Reference, read in the session from Guner, Khuong, Leach, Lee, Bartberger,
Houk, J. Phys. Chem. A 2003, 107, 11445 (author-hosted PDF; Table 1 read from
the rendered page, Table 9 and the text read as text): reaction 2,
"measured only once, and an experimental activation energy of 29.9 +- 0.5
kcal/mol was reported for the gas phase at 390-434 K" (Lewis and Steiner, J.
Chem. Soc. 1964, 3080; primary text not read, paywalled); Table 1: dH++ = 29.1
kcal/mol at 412 K (Ea - RT), log A 11.9, dS++ -7.0 cal/mol/K; reaction
enthalpy -14.5 (measured, Benson and O'Neal 1970) and -16.1 (from heats of
formation); Table 9 recommended dH++(0 K) 30.2 +- 0.5, dH_rxn(0 K) -15.3 +- 1.

Why crossing programs is justified by capability (not staged): in this hub
typed wavefunction-stability answers are PySCF's; the CCSD T1 diagnostic and
DLPNO-CCSD(T) are ORCA's; canonical CCSD(T) runs in ORCA and PySCF; Gaussian
and ORCA both locate saddles and walk IRCs; xTB is the cheap conformer
screen. A single-program route (ORCA alone can do every stage except typed
stability) is legitimate and is not B.

## Oracle O1 -- PRE-REGISTRATION (written before submission)

A CLI job (no Agent) on this commit's code (`chemsmart/` = base), 32 cores:
B3LYP-D3(BJ)/def2-TZVP (ORCA writes B3LYP/G + D3BJ, parameterised per census
D) opt+freq of tZt, tZc, cZc and 1,3-cyclohexadiene (CHD), OptTS+freq from my
guess, IRC both ways reading the saddle's Hessian; PySCF RKS stability
(B3LYP-D3(BJ)/def2-TZVP) at tZt, cZc, TS, CHD; canonical CCSD(T)/cc-pVTZ
(frozen core) at tZt, cZc, TS, CHD in ORCA, and at tZt and TS in PySCF.
Guesses built by me (RDKit/MMFF: tZt minimum; cZc and tZc with held
torsions; saddle guess and CHD guess from cZc with C1...C6 held at 2.25 and
1.53 A; `chem/build.py`); the Agent never sees them.

Predictions (never tuned after a result):
- O-A saddle: exactly one imaginary mode, |nu| in [300, 900] cm-1; forming
  C1...C6 in [2.05, 2.45] A.
- O-B IRC: the two branches move C1...C6 oppositely (one toward the ring,
  below 1.8 A; one toward the open chain, above 2.8 A).
- O-C stability (the check before committing to the system): RKS -> UKS
  stable at tZt, cZc, TS and CHD (lowest eigenvalue > 0). FALSIFIED (the
  system is abandoned for B) if the TS is RKS -> UKS unstable.
- O-D conformers: tZt is the lowest; cZc lies 2-7 kcal/mol above it (dE).
- O-E B3LYP-D3(BJ) dE++ (tZt -> TS) in [28, 35] kcal/mol.
- O-F CCSD(T)/cc-pVTZ // B3LYP: dE++ (tZt -> TS) in [28, 34]; dE_rxn
  (tZt -> CHD) in [-22, -12] kcal/mol.
- O-G ORCA T1 below 0.015 at all four structures.
- O-H ORCA and PySCF CCSD(T) totals agree within 1e-5 Eh at tZt and TS.
- O-I (the oracle's answer, with my own RRHO at 412 and 298.15 K from the DFT
  frequencies): dH++(412 K, from tZt) in [27.1, 31.1] kcal/mol and dH_rxn(298
  K) in [-18.0, -12.5]. If it misses, the bands below stay as written and the
  miss is reported.

## Physics bands for the live goal(s) (never tuned after a result)

- B1 saddle: one imaginary mode, |nu| in [300, 900] cm-1; C1...C6 in [2.05,
  2.45] A.
- B2 connectivity: one side is (Z)-hexatriene (C1...C6 above 2.8 A), the
  other 1,3-cyclohexadiene (C1-C6 in [1.49, 1.58] A).
- B3 activation enthalpy at 412 K relative to the equilibrium reactant: PASS
  in [27.1, 31.1] kcal/mol (29.1 +- 0.5 experiment, +- 1.5 for a
  CCSD(T)/TZ-class level and thermal model). A value referenced to the cZc
  conformer instead of the ground state is recorded as that error whatever
  its number (it is the question's trap). A DFT-only value in the band is
  "in band, method-limited".
- B4 reaction enthalpy at 298.15 K: PASS in [-18.0, -12.5] kcal/mol.
- B5 lineage: for every delivered number the host records name the geometry
  node, the level each program applied (functional as written, dispersion,
  basis, RI, frozen core), the state (0, 1), and the producer of every
  handed-on structure and Hessian.

## Live goal G1 -- PRE-REGISTRATION (written before submission)

- Task: goals/g1/TASK.md (sha256 in Jobs issued), posed as a scientist would:
  the activation enthalpy of the ring closure at 412 K and the reaction
  enthalpy at 298.15 K, gas phase, at a defensible level, with the TS's
  connectivity shown and what each number rests on; ORCA, PySCF, Gaussian
  and xTB named as available; no stage, program, conformer or reference
  state named. Workspace: hexatriene.xyz only (sha256 f1d003fa93384b0f...,
  the tZt MMFF structure, comment line naming only the molecule).
- Agent: deepseek-v4-flash-0731 via alibaba-token-plan; knowledge documents
  off (the default); approval `claude-researcher-q20-owner-delegated` (a
  delegated approval, never a human decision).
- Envelope (make_goal.py): orca, pyscf, gaussian, xtb on cpu; 32 cores, 100
  GB, node 3 h, episode 11 h, reserve 30 min, 30 engine calls, 0 excursion
  calls, 3 revisions; local dispatch.
- Code: r2 = this branch merged with r10-integration de13de96 (c0896a07,
  tree 5c72afb5); a g0 dry run (provider alibaba-dryrun, decision deny, no
  provider or engine cost) first checks the import path and the workspace.

Read from host records only (ledger, run streams, receipts, native output):
- R1 route: which programs for which stage, and the recorded reason for
  each crossing. A single-program route is recorded as the model's choice;
  B is then not claimed.
- R2 lineage per handoff: producer node, handoff receipt, atom order, state
  (0, 1), and the level each program applied (functional as written,
  dispersion, basis, RI, frozen core).
- R3 the numbers against B1-B4 and against O1b at matched level where one
  exists; which conformer the activation enthalpy is referenced to.
- R4 the host's words: settlement, anomalies, and whether each word is true
  of what it read.
- H-G1a (the repair, live): a dispersion pair census D found unparameterised
  is refused at project validation with its route and costs no engine call.
  FALSIFIED by any engine call that dies on dispersion parameters ("R6DS",
  "Non-parameterized functional", "No entry for"). "Not exercised" if the
  session never asks for such a pair.
Milestone B is claimed only if R1 shows an Agent-chosen cross-program route
with a recorded scientific reason, R2 holds on every handoff, B1-B3 pass (B3
referenced to the equilibrium reactant), and B4 is read as stated.

## Plan

1. Census D (above). Then the repair in radius: each settings class refuses at
   compile, with a route, a pair its program has no parameters for, from a
   table measured by D (Gaussian, ORCA) or from the program's own lookup
   (PySCF's probe loads the parameters); a witness red on the base with Q15
   g2's own project, green after; replay of Q15 g2's compile.
2. Choose the chemistry (closed-shell, trustworthy reference, crossing
   justified by capability), physics bands, oracle -- written here before any
   chemistry run.
3. Provider-free rehearsal; CLI oracle; live goal(s).

## The repair (in radius) and its evidence so far

- 3241d5df settings: Gaussian and ORCA each hold census D's table and refuse
  an unparameterised pair at validation (the diagnostic the session reads)
  and in the writer, with the program's own outcome and a route; ORCA
  refuses the word d3; Gaussian refuses a shorthand whose base is no
  keyword. Census D replayed through the repaired writers: every refused
  route refused, every route the program ran on its parameters (348
  Gaussian, 271 ORCA) written byte for byte, zero false refusals. Q15 g2's
  own preview command reproduces its archived input on the base and is
  refused here. Witness: 7 refusals red on the base, green here.
- 7424dbe5 shared: the ORCA route round-trip probe uses PBE for dispersion.
- 7f810aaa pyscf: the probe loads the method's parameters as get_dispersion
  does. Evidence is D-run3 below (the probe replayed on the target).
- 1a80c8f3 merge of r10-integration (Q19), clean; packed as r1 (tree
  81e437c5, uploaded to r10/q20/r1/code; O1 keeps running on code/).

## D-run3 -- PRE-REGISTRATION (the PySCF probe on the target)

The repaired `_PROBE_SCRIPT` (r1 code) is run by census D's own
`pyscf_pairs.py` over the same 649 (xc, dispersion) pairs. Prediction: every
pair whose D-run2 run died on the dispersion pair itself (197) is now not
GREEN, with PySCF's own message; every pair D-run2 ran (272) stays GREEN.
FALSIFIED by any pair that ran and is now refused (a false refusal) or any
dispersion death still GREEN.

## O1 -- a mechanical error of mine, corrected without changing a prediction

The CLI's ORCA ts command rewrites a label's "ts" to "optts"
(`chemsmart/cli/orca/ts.py:247`, `label.replace("ts", "optts")`), so my
saddle's output is `hx_optts.out`, and O1's five commands that read
`hx_ts.out`/`hx_ts.hess` (TS stability, both IRC branches, both TS CCSD(T))
fail on a missing file. They are re-issued unchanged as O1b reading
`hx_optts.*` once the saddle exists. Every O1 prediction stands as written.

Second error of mine, found before any prediction was read: O1's OptTS
started from my MMFF guess with an exact Hessian (`Calc_Hess True`), and at
that geometry the lowest mode was a soft torsion (eigenvalue -0.0013 au,
wandering between -0.0024 and +0.0050 for 21 cycles) while C1...C6 drifted
from 2.26 to 3.25 A. I cancelled O1 (2153554) after tZt and cZc had
converged (cZc a true minimum, lowest modes 78 and 101 cm-1). O1b re-issues
every remaining O1 command with one change of route: the saddle is sought
from a DFT constrained optimisation holding C1...C6 at the guess's 2.263 A
(ORCA modred, `Constraints {B 0 5 C}`), then OptTS with an exact Hessian
(labels without "ts"). ORCA ScanTS through the CLI crashed at write time
(`KeyError: 'coords'` in the scants modred path; found and left). All O1
predictions stand as written.

Third, the same kind of error: O1b's constrained start (C1...C6 held at
2.263 A from my MMFF guess) relaxed to a structure 31 kcal/mol above cZc,
about 9 above where the disrotatory saddle should lie, and OptTS from it
descended 25 kcal/mol in six cycles (the followed eigenvalue went -0.0118
-> +0.0019 au). I cancelled O1b (2153573). O1c seeks the saddle the
standard way, ORCA ScanTS from the optimised cZc along C1...C6 (3.1 -> 1.9
A, 13 points), with the scan given in the project's `ts:` section in the
shape the writer reads (the CLI's own ScanTS builder is the found-and-left
defect below); `--fake` writes `! ScanTS Freq B3LYP/G def2-tzvp d3bj` with
`B 0 5 = 3.1, 1.9, 13`. Every O1 prediction stands.

O1c (2153578) failed at ScanTS's first scan step in ORCA itself: "Error
(ORCA_GSTEP): could not find the Hessian file!" (it looked for
`hx_scan.carthess`). The ORCA writer puts the TS Hessian block (`Calc_Hess
True`, `Recalc_Hess 5`) in a ScanTS input too, and ORCA 6.1.1 then reads an
exact Hessian during the scan steps that was never computed -- a second
ScanTS defect, after the CLI's shape mismatch (found and left; ScanTS through
the hub cannot run). I cancelled O1c. O1d: the qualified plain relaxed scan
(`! Opt ... Scan B 0 5 = 3.1, 1.9, 13`) from the optimised cZc, the highest
point picked from ORCA's own scan table by a 20-line helper (pick_max.py,
sha256 376a336c...), OptTS from it with an exact Hessian, then every other O1
command. Predictions unchanged.

O1d (2153585): the relaxed scan from my cZc rose monotonically, 3.1 -> 1.9 A,
by 55.9 kcal/mol with no maximum. The cause is symmetry, and it is my error
of chemistry: the cZc I built and optimised is the C2 helix, a C2-symmetric
path along C1...C6 is the conrotatory closure (thermally forbidden for 6pi),
and a mirror-symmetric (Cs) path is the allowed disrotatory one; forces from
a C2 start keep C2, so O1, O1b and O1d all searched the forbidden path.
Cancelled (the OptTS from the scan's end was meaningless). O1e: the same
commands from a Cs start (torsions held +18/-18 deg, C1...C6 2.508 A, MMFF;
`chem/hold_cs.py`), scanning 2.50 -> 1.95 A in 12 points; the picker now
refuses a maximum at an end of the scan (pick_max.py sha256 9eb1ed3d...).
Predictions unchanged. The same trap is open to the Agent (its tZt start
relaxed along two single bonds most naturally reaches the helix).

O1e (2153621), first part READ before G1 was issued (the check the brief
asks for before committing to the system):
- The Cs relaxed scan has an interior maximum at C1...C6 2.25 A
  (-233.462827 Eh; 2.50 A -233.471631, 1.95 A -233.491007), the C2 path
  lying higher at every distance compared.
- OptTS from it converged: one imaginary mode, -570.2 cm-1 (O-A |nu| band
  PASS), E -233.462824585 Eh; B3LYP-D3(BJ)/def2-TZVP dE++ (tZt -> TS) 29.06
  kcal/mol (O-E PASS), 19.7 above cZc.
- PySCF stability at the saddle (host reader, PySCFOutput.scf_stability):
  RKS -> UKS lowest external eigenvalue +0.0642 Eh (stable; Q15's Bergman
  saddle was +0.0047, p-benzyne -0.064), internal +0.624, real -> complex
  +0.150 Eh. O-C PASS at the saddle: the question stays closed shell, and G1
  is issued on it.

O-D read from O1's finished part (B3LYP-D3(BJ)/def2-TZVP, ORCA, unscaled
RRHO of my own, which reproduces ORCA's 298.15 K enthalpy to 0.01
kcal/mol): tZt E -233.509133588 Eh, lowest mode 106 cm-1; cZc E
-233.494227090 Eh, lowest 78 cm-1, a true minimum. cZc - tZt: dE 9.35,
dH(412 K) 9.19 kcal/mol. O-D (cZc 2-7 above tZt) FAILS: the reactive
conformer lies 9.4 kcal/mol above the ground state, so the question's
conformer trap is about 9 kcal/mol.

## O1e -- READ (CUHK Slurm 2153621, all 17 commands exit 0; native outputs
and the host's PySCF reader)

- O-A PASS: one imaginary mode, -570.2 cm-1; C1...C6 2.253 A; torsions
  +32.9/-32.9 deg (the mirror-symmetric, disrotatory saddle).
- O-B PASS: IRC forward ends at C1...C6 2.992 A (open chain), backward at
  1.558 A (the ring), both reading the saddle's Hessian.
- O-C PASS: PySCF RKS -> UKS stable at tZt (+0.0495 Eh), cZc (+0.0608), the
  saddle (+0.0642) and CHD (+0.0611).
- O-D FAIL (recorded above): cZc 9.35, tZc 3.52 kcal/mol above tZt (dE).
- O-E PASS: B3LYP-D3(BJ)/def2-TZVP dE++ (tZt -> TS) 29.06.
- O-F PASS: CCSD(T)/cc-pVTZ // B3LYP-D3(BJ)/def2-TZVP dE++ 30.86, dE_rxn
  -17.02 kcal/mol.
- O-G PASS: ORCA T1 0.0115 (tZt), 0.0110 (TS), 0.0111 (cZc), 0.0106 (CHD).
- O-H PASS: ORCA vs PySCF CCSD(T) totals -7.2e-7 (tZt), -5.0e-7 Eh (TS);
  HF references within 2e-8 Eh.
- O-I PASS: with my unscaled RRHO from the DFT frequencies, dH++(412 K,
  from tZt) = 29.79 kcal/mol (experiment 29.1 +- 0.5; +0.7) and dH_rxn(298
  K) = -15.88 (experiment -14.5 measured, -16.1 estimated). Referenced to the
  reactive cZc conformer instead, dH++ would be 21.81, 7.3 below experiment:
  the size of the question's trap. The hub's CLI answers the question.

## G1 -- READ (CUHK Slurm 2153658, COMPLETED 11:31 HKT after 8 h 16 min;
code tree 5c72afb5 verified on the node; 88 provider turns, all
deepseek-v4-flash-0731)

- Settlement: `execution_wave_decision_pending` (the driver parks), 4 cycles,
  3 revisions admitted, 7 engine calls, no delivered claim. Reason: "the
  Agent made no execution-boundary decision on workflow
  hexatriene-rclosure-r4", with 23 engine calls and 13,323 s left and one
  previewed ORCA TS node ready.
- R1 route: ALL ORCA, by the Agent's recorded choice. It weighed Gaussian
  twice and kept ORCA for thermal-correction consistency ("mixing its TS
  frequencies with ORCA-minima frequencies would break thermal-correction
  consistency across the composite; it remains a fallback"). PySCF and xTB
  unused. A legitimate single-program route: B cannot be claimed on R1.
- What ran: B3LYP-D3(BJ)/def2-TZVP opt+freq of the reactant (= O1's tZt,
  E identical to 1e-9 Eh) and of 1,3-cyclohexadiene; DLPNO-CCSD(T)/def2-TZVP
  on both; three relaxed C1...C6 scans from the extended tZt minimum
  (5.8 -> 1.5 A, 22 points: 15 done in the 3 h node limit; 4.5 -> 1.6 A with
  RIJCOSX, 13 points: 11 done; 3.0 -> 1.9 A at def2-SVP: step 1 took 50
  optimisation cycles and ORCA aborted). No saddle was ever computed.
- R2: every handoff stayed inside ORCA (reactant -> scans, product -> DLPNO);
  no cross-program handoff to read.
- R3: no delivered number, so B1-B4 are not scored. My arithmetic on G1's
  own engine outputs (not a claim of the Agent's): dE_rxn DLPNO-CCSD(T)/
  def2-TZVP -17.24, dH_rxn(298 K) -16.09 kcal/mol, inside B4.
- H-G1a NOT EXERCISED: the session only ever asked for B3LYP-D3(BJ) in ORCA
  (parameterised); no validation, compile or engine call named dispersion.
  Its three invalid validations were an `rks` reference word ORCA does not
  take (x2) and a DLPNO node without AuxC.
- The model (host records):
  - It wrote its final execution decision in prose ("Wave selection:
    [ts-opt-freq, ts-irc, ts-sp-dlpno]") with finish_reason stop, twice,
    after the host's wake.execution_wave_decision_pending, while
    select_execution_wave was exposed (last exposure plan of that session)
    and it had called that tool in each earlier cycle. The host rightly read
    prose as no decision. The goal ended here.
  - Its cycle-2 decision named the folded s-cis conformer as the barrier's
    reference ("the measured kinetics are for the conformer that can
    close"), the trap worth 7.3 kcal/mol; cycle 3 took the validated tZt
    minimum as the reactant reference, and its final plan's thermochemistry
    used it. Never delivered, so never scored.
  - Its own cycle-4 diagnosis of the scan losses was correct and measured:
    the extended minimum has C1...C6 5.749 A, so every scan demanded 2.5-2.8
    A of compression. Its repair (host dihedral edits to a folded seed,
    C1...C6 2.574 A, torsions 0/45 deg, C1) was sound in kind.
- Hub finding (not a repaired layer): a timed-out ORCA scan hands on nothing.
  `bind_reached_geometry` refused both dead scans ("orca declares no geometry
  selector in the 'as_reached' structural state for jobtype 'scan'"), so 26
  converged scan points from 6 node-hours were lost to the goal.

Milestone B: NOT EARNED. The route was single-program by the model's
recorded, defensible choice, and the goal ended on the model's prose wave
decision. The dispersion repair was not exercised live. The oracle shows the
hub's CLI carries the question to experiment (29.79 vs 29.1 +- 0.5).

## Jobs issued

- 2026-09-25: census D, CUHK Slurm 2153534 (r10-q20-a), 16 cores,
  pre-registration f8ee9f8184ba, code a8dd1777 (tree b572f5bd, = Q15 g2's).
- 2026-09-25: D-run2 (PySCF run step only), CUHK Slurm 2153546,
  pre-registration 44967a4b7b9e.
- 2026-09-25: O1, CUHK Slurm 2153554, 32 cores, pre-registration
  b40a5f4a3218, code a8dd1777 (tree b572f5bd).
- 2026-09-25: D-run3, CUHK Slurm 2153567, pre-registration 5b104ca8acc3,
  code r1 (tree 81e437c5). READ: 0 problems -- all 272 pairs PySCF ran stay
  GREEN, all 299 that died on the dispersion pair are refused with PySCF's
  own message ("No entry for 'wb97x' present", ...). D6 answered: yes, and
  closed. D-run3 PASS.
- 2026-09-25: O1 cancelled by me (see above). O1b, next submission, code
  a8dd1777 (tree b572f5bd, the oracle's writers unchanged by the repair for
  B3LYP-D3(BJ)), in cli/o1b with O1's tZt and cZc outputs copied in.
- 2026-09-25: O1b, CUHK Slurm 2153573 (r10-q20-a), pre-registration
  9e6aa6783a44.
- 2026-09-25: g0 dry run, CUHK Slurm 2153574 (r10-q20-b), pre-registration
  97239de72052: imported r2 (tree 5c72afb5 verified on the node), admitted
  the workspace, and ended where the dryrun profile ends it ("context budget
  would be exceeded"), settlement returned_to_human, no provider turn, no
  engine call. The plumbing for G1 holds.
- Found and left (not in radius; on the road): ORCA ScanTS through the CLI
  crashes at write time. `chemsmart/cli/orca/ts.py:230` builds
  `{"coordinates": ..., "dist_start": <scalar>, ...}`; the writer
  (`jobs/orca/writer.py:929`, `_write_modred_if_dict`) reads the scan job's
  shape, `{"coords": ..., "dist_start": [<list>], ...}` (`utils/cli.py:629`).
  `tssearch_type` is project-settable and the coordinate belongs on the node,
  so a session can reach it; it fails at preview (no engine call).
- 2026-09-25: O1c (2153578), O1d (2153585) cancelled by me (see above);
  O1e, CUHK Slurm 2153621 (r10-q20-a), pre-registration 3831e8bd992c,
  running the rest of O1 (CHD, stabilities, IRCs, tZc, CCSD(T) in both
  programs).
- 2026-09-25: G1, CUHK Slurm 2153658 (r10-q20-b), pre-registration
  b081544206f8, started 03:15 HKT; code c0896a07 (tree 5c72afb5 verified on
  the node), 32 cpus.
- G1 files (sha256): TASK.md 8843eee2b482a0fe..., envelope.yaml
  aef67402..., goal.sh 38104bb0... (PYTHONPATH r2/code); g0 = the same
  task, envelope and code with provider alibaba-dryrun, decision deny.
- Merged r10-integration again (Q18, de13de96) as c0896a07; packed as r2
  (tree 5c72afb5); tests/agent 3147 passed on the merged tree; census D
  replayed through the merged writers unchanged (zero false refusals).

## Status

- 2026-09-25: base verified; governance, Q14/Q15 histories and the three
  settings classes read; gate open; census tooling written; census D
  pre-registered.
- 2026-09-25 (G1 and O1e running): WAITING ON JOBS 2153658 (G1) AND
  2153621 (O1e). Hand-back gates green on the code G1 runs: pristine export
  of baf9065c (chemsmart/ = c0896a07): full suite 23 failed (the baseline
  set: test_structures 19, test_pyscf_dispersion_conformance 2,
  test_PyscfSettings 1, test_aggregation 1), 4701 passed, tests/agent none
  failed; ruff, black, isort clean on the touched files. r10-integration
  111dc55e merged (a975f9fc, governance only).
  On resume read, in order: (1) G1's settlement and ledger (read_goal.py),
  (2) every node's program, level as written, dispersion, and whether any
  compile or validation refusal named dispersion (H-G1a), (3) the route and
  its recorded reasons, which programs, why (R1), (4) each handoff's
  producer, atom order and state (R2), (5) the saddle (imaginary modes,
  C1...C6), the reactant conformer the barrier is referenced to, and the
  delivered numbers against B1-B4 and O1e (R3), (6) the host's words (R4);
  then O1e's IRC, CCSD(T) (ORCA and PySCF), T1 and stabilities against
  O-B, O-C, O-F, O-G, O-H and the oracle's own dH++(412 K) and dH_rxn.
