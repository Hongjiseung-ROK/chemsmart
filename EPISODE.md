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

## Jobs issued

- 2026-09-25: census D, CUHK Slurm 2153534 (r10-q20-a), 16 cores,
  pre-registration f8ee9f8184ba, code a8dd1777 (tree b572f5bd, = Q15 g2's).
- 2026-09-25: D-run2 (PySCF run step only), next submission.

## Status

- 2026-09-25: base verified; governance, Q14/Q15 histories and the three
  settings classes read; gate open; census tooling written; census D
  pre-registered.
