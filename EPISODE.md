# R10 episode Q14 -- the refusals a hub should see coming

Base: `7450777c8d0e64dcf54773c736432d9f53c97ea7` (verified `git rev-parse HEAD`
at start). Model: claude-opus-5-5[1m]. Episode id `q14`.

## The question (as currently understood)

When the Agent asks for a calculation a program will certainly refuse or
waste, for a reason the hub can know from the request alone (method, basis,
job type, molecule, resources), does the hub translate it into the
equivalent calculation the program can run (visible in the review) or refuse
it at validation with a program-neutral route -- rather than spending an
approved engine call and a revision on it? And is a run the program finished
never given a failure word that says the engine failed?

## Falsifiers (armed before any repair)

- Premise falsified if, over the archived CUHK R8-R10 goals (sealed
  `r10/q6/goals/` and `r10/q3/` excluded) and the ax41 campaign workspaces,
  the failures predictable from the request are only the brief's instances,
  or are a small minority of failed engine calls. Then: fix those, report
  the rate as the result.
- A translation is wrong if the program's own number under the translated
  input differs from the untranslated physics (for a zero-pair system the
  correlated energy must equal the reference SCF energy to the printed
  precision; a numerical Hessian must reproduce analytic frequencies of the
  same method within the usual finite-difference noise, ~1 cm-1).
- A refusal is wrong if it fires on a request the program runs.

## Census (provider-free; done before any repair)

Host derivation `derive_run_outcome` on the base tree over every goal run
stream, archive paths remapped to local copies; duplicates of one execution
collapsed; each failure's program output replayed through the current
`native_failure` summariser and classified from the program's own lines.

- CUHK R8-R10 goals (sealed excluded): 119 engine calls, 21 failed.
  P (request determined it, program refusal) 2: MDCI, H atom, 0 pairs
  (Q9 G1, Q12 g1-hi). H (program finished, host refused) 10: Gaussian
  dispersion method word x6 (Q5, since fixed 5383d679), ORCA atomic-guess
  sidecar x2 (Q12, fixed 642492b3), GFN-FF settings x2 (R9, fixed 90d93cfb).
  E 4, R 2, S 3.
- ax41 campaign workspaces: 917 unique engine calls (1229 records, 312
  duplicate records of one execution), 112 failed. P 32: bare RI with HF
  exchange 10, CCSD(T)+RIJK 4, RIJK/AutoCI analytic Hessian 6, ROHF 2,
  unrecognised native tokens 4, wB97X+D3BJ unparameterised 3, MDCI pairs 2
  (H2 at 2 ranks; DLPNO H atom), linear-bend scan 1. H 7. E 8, R 12, S 53.
- Together: 1036 engine calls, 133 failed; P 34 (26%), H 17 (13%),
  S 56 (42%), R 14, E 12. Premise partly falsified: most failures are
  science; a quarter were predictable from the request.
- On the current tree ORCA's input-check probe catches 26 of the 34 at
  preview (each dies in main_input_check before ORCA's INPUT FILE banner).
  Not caught, because they die after the SCF: MDCI ranks > pairs (4 here,
  plus Q3 g2's four and Q6 pair3-b, both sealed), wB97X+D3BJ (3),
  linear bend (1). Q3 g1's MP2 analytic Hessian abort is in
  main_input_check (line 4834, no INPUT FILE banner): probe-catchable.

## O1 -- ORCA's own rules (CUHK, ORCA 6.1.1, slot job; predictions first)

`cli/o1`: 28 `chemsmart run` lines on the base tree's writer (commit with
this file; chemsmart/ identical to base). %pal nprocs = -n.

Pair rule under test: ORCA's MDCI aborts when ranks > pairs; closed shell
pairs = n(n+1)/2 (n correlated doubly occupied orbitals), UHF pairs =
N(N-1)/2 (N correlated electrons); frozen core = the chemical-core table
(`result_readers.CHEMICAL_CORE_ORBITALS`); DLPNO compares against the
pairs kept as CCSD pairs (unknown before the run; >= n diagonal pairs).

- A1 H UHF CCSD(T)/def2-TZVP 1 rank: OPEN. X = normal termination with
  E(CCSD(T)) - E(UHF, A3) = 0 within 1e-9 Eh (serial MDCI handles zero
  pairs); Y = abort or crash (zero-pair systems need another route).
- A2 (2 ranks): abort "(2) ... pairs (0)". B1 H2 1 rank normal; B2 2 ranks
  abort "(2) ... (1)". C1 water CCSD(T)/def2-SVP 10 ranks normal; C2 11
  abort "(11) ... (10)". D1 OH UHF 21 ranks normal; D2 22 abort
  "(22) ... (21)". E1 Li 3 ranks normal, E2 4 abort "(4) ... (3)" (if E1
  aborts with (0), ORCA freezes Li 1s and the table is wrong for ORCA at
  Li). F1 Na 1 rank normal and states its frozen core; F2 2 ranks normal if
  ORCA freezes 1s only (36 pairs), abort "(2) ... (0)" if it freezes [Ne].
- G1 DLPNO H atom 1 rank: OPEN (normal with E_corr = 0, or crash). G2 2
  ranks: abort or crash. H1 water DLPNO 4 ranks normal; H2 11 abort
  "(11) ... (10)". I1 water dimer (Q3 g2 level) 8 ranks normal; I2 27
  normal; I3 28 abort "(28) ... (27)".
- J1 MP2 opt+Freq: abort within 2 s in main_input_check, before any INPUT
  FILE banner. J2 MP2 NumFreq: normal, 3 real modes. J3 RI-MP2 Freq: OPEN.
  J4 vs J5 HF analytic vs numerical: every mode within 2 cm-1.
- K1 B2PLYP Freq: OPEN. L1 wB97X + D3BJ: abort after the SCF ("Non-
  parameterized functional used for dispersion correction"), past the
  INPUT FILE banner. L2 wB97X-D3BJ keyword: normal.

### O1 results (Slurm 2152636, prereg f293c77fa8ab; read from raw outputs)

Every pre-registered pair prediction held: B1 runs / B2 "(2) ... (1)";
C1 10 runs / C2 "(11) ... (10)"; D1 21 runs / D2 "(22) ... (21)"; E1 Li
"NO frozen core", 3 correlated, 3 pairs, runs / E2 "(4) ... (3)"; F1/F2 Na
"chemical core (2 el)", 9 correlated, 36 pairs, both run; H1 water DLPNO
"10 OF 10 PAIRS ARE KEPT CCSD PAIRS" at 4 / H2 "(11) ... (10)"; I1 (8) and
I2 (27) dimer DLPNO both "27 OF 36 ... CCSD PAIRS", equal energies to
1e-12 Eh / I3 "(28) ... (27)".
OPEN questions answered: A1 = Y -- the H atom's UHF CCSD(T) aborts at ONE
process ("Number of processes (1) ... exceeds number of pairs (0)"): the
brief's "one MDCI rank" prior is falsified. G1/G2 DLPNO H atom: CopyBlock
crash at 1 and 2 processes. J3 RI-MP2 and K1 B2PLYP analytic Hessians:
the same main_input_check abort as MP2 ("MP2 analytic Hessian calculations
are not implemented - please use NumFreq"), before INPUT FILE (probe-
catchable). J1 as predicted. J4/J5 HF analytic vs numerical: 1750.42/
1749.87, 4148.52/4148.84, 4244.77/4244.88 cm-1 (all within 0.6). J2 MP2
NumFreq: 1654.07, 3895.19, 4010.90 cm-1, 30 s. L1 wB97X + D3BJ aborts after
the SCF (line 825 of the output, INPUT FILE at 214); L2 wB97X-D3BJ runs.

## Oracle

The program itself, run through `chemsmart run` in slot jobs: the refused
input and the translated input, side by side, on the same host (CUHK,
ORCA 6.1.1, PySCF 2.14.0).

## Commits so far

- 8ff25825 analysis: an atom's thermochemistry needs no Hessian.
- 5e85422f io: MDCI's process-count refusal is its own failure class.
- 4ed32f97 shared: %pal nprocs <= MDCI's certain pairs; zero pairs refused
  at compile (routed), translation stated in the compile reply and review.

## O2 -- the repaired writer on the inputs O1 saw abort (pre-registered)

`cli/o2`, code `r1` (this branch, all Q14 repairs), the same projects and
geometries as O1, the same -n that aborted there:
- A2r H atom CCSD(T): refused by the CLI before any input (exit 1, no ORCA
  output), the route text in the error.
- B2r H2 at 2 -> writes 1; C2r water at 11 -> 10; D2r OH at 22 -> 21; E2r
  Li at 4 -> 3; H2r water DLPNO at 11 -> 4; I3r dimer DLPNO at 28 -> 8. Each
  terminates normally with the energy O1 printed for the same calculation
  at a count that ran (B1 -1.168262381921, C1 -76.174711368878, D1
  -75.490145618429, E1 -7.468048553819, H1 -76.326547325817, I1/I2
  -152.692438608255 Eh) within 1e-8 Eh: the translation changes cores, not
  the calculation.
- J1r MP2 freq -> NumFreq: normal, the frequencies of O1 J2 (1654.07,
  3895.19, 4010.90 cm-1) within 0.01 (the same input). J3r RI-MP2 and K1r
  B2PLYP -> NumFreq: normal, three real modes; J3r within 2 cm-1 of J1r.
Falsified if any translated input aborts or any energy moves by more.

### O2 results (Slurm 2152810, prereg 5bf25eb91343, code r1 5b95c12f)

Every prediction held. A2r: the CLI refused before writing an input
(`ValueError: ORCA's ccsd(t) has no electron pair ...`), no ORCA run.
B2r ran on 1 process, C2r 10, D2r 21, E2r 3, H2r 4, I3r 8 ("Program
running with N parallel MPI-processes"; pairs included 1, 10, 21, 3, 10,
27), all ORCA TERMINATED NORMALLY, energies equal to O1's to every printed
digit: -1.168262381921, -76.174711368878, -75.490145618429,
-7.468048553819, -76.326547325817, -152.692438608255 Eh. J1r `Opt NumFreq
mp2`: 1654.07, 3895.19, 4010.90 cm-1 (= O1 J2). J3r RI-MP2 NumFreq:
1654.13, 3895.23, 4010.86 (within 0.06 of J1r). K1r B2PLYP NumFreq:
1651.64, 3841.66, 3944.25 cm-1, 43 s.

## G1 -- live Agent goal (pre-registered before issue)

Model deepseek-v4-flash-0731 via alibaba-token-plan (the only credential);
envelope ORCA only, 16 cores, 48 GB, node 1 h, episode 3 h, 10 engine
calls, 2 revisions; delegated approval
`claude-researcher-q14-owner-delegated`. Code: this branch at the commit
packed as `r1` (all Q14 repairs). Task (`goals/g1/TASK.md`): the O-H bond
dissociation enthalpy of water at 298.15 K, 1 atm, CCSD(T)/def2-TZVP
electronic energies, DFT geometries and thermal corrections of the model's
choice; only `water.xyz` is given (r 0.96 A, 104.5 deg). The text says
nothing of processes, pairs or the H atom.

Why this route hits the class: its natural nodes are CCSD(T) on water
(frozen core, 10 pairs < 16 granted: base aborts, Q3 g2's monomer), on OH
(21 pairs >= 16: unchanged) and on the H atom (0 pairs: base aborts at any
count, Q9 G1 / Q12 g1-hi); an atom's thermal correction (base refuses a
single point, Q9 G1).

Success (all must hold):
- S1: no engine call ends in MDCI's pair abort, and no correlated ORCA node
  on the H atom is approved (the compile refusal, a routed failure report
  with cost "no engine call", is what the model meets if it plans one).
- S2: a water CCSD(T) node, if planned, shows the translation in its
  compile reply and review observations (10 of 16 processes), its output
  says "Program running with 10 parallel MPI-processes" and "Number of
  pairs included ... 10", and it terminates normally.
- S3: E(H) enters the answer as E(UHF/def2-TZVP) = -0.499810 Eh (O1 A3,
  -0.499809832061) within 1e-6 Eh, or as a correlated energy from a route
  that gives the same number; the model's own route, not mine.
- S4: the goal settles achieved or achieved_with_observations with
  dH298 in the physics band 112-120 kcal/mol. The band's anchor: De(HO-H)
  at CCSD(T)/def2-TZVP about 122-124 (CBS about 126, recalled, not a
  registered constant), dZPE about 7.9, d(H298 - H0) about +1.2 (4RT for
  H2O, 3.5RT OH, 2.5RT H) -> about 116; experiment about 118.8 (recalled).
Failure: an MDCI abort; an approved correlated H-atom node; a host
refusal of an atom's thermochemistry; dH298 outside the band from host
arithmetic. A model that never plans a correlated node on water or H
(e.g. treats the task's level loosely) leaves S1/S2 untested: reported,
not re-rolled. Control: the base tree's outcome on this class is the
archived record (Q3 g2, Q9 G1, Q12 g1-hi), not a new run.

## Status

- Census: done (above). O1: done (above).
- Jobs issued: O1 2152636 (done).
