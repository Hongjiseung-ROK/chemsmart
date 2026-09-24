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

## Status

- Census: done (above). O1: done (above).
- Jobs issued: O1 2152636 (done).
