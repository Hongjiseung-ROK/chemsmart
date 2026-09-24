# R10 episode Q18 -- an open-shell singlet the model can ask for without knowing any program

Base: `0ac28beccad766aa743945c4a693de7a5c0e4cec` (verified with `git rev-parse HEAD`
as the first action of the episode, 2026-09-24).

## The question as currently understood

Can the Agent ask for an open-shell (broken-symmetry) singlet as a typed
electronic-state request that the hub translates into each program's own
mechanism (ORCA, Gaussian, PySCF), states in the review, and refuses where no
native equivalent exists? Does the host then record which reference actually
ran and whether spin symmetry actually broke (<S**2>, the program's stability
answer), so the Agent can tell a real diradical from a collapsed closed shell?

## Falsifiers of the premise (armed before any census or run)

- F1 (census): if the archived goals contain no open-shell-singlet /
  broken-symmetry request other than R10 Q15's g1, repair that route and end.
- F2 (portability): if a typed request cannot mean one thing across programs,
  say exactly what is portable and what is not.
- F3 (the brief's prior about Gaussian): if a restricted `b3lyp ... guess=mix`
  route converges an unrestricted broken-symmetry solution, the prior
  "probably inert" is false.

## Census (2026-09-24, provider-free, model-authored text and tool arguments only)

Scope: public transcripts under /project/xlzhang/jiseung (r8, r9, r10/q1..q17
without q3 and q6/goals, the top-level R8-era campaign directories; 102 goal
workspaces) and the ax41 mirror (~/developer/chemsmart-hetzner-mirror, 712
workspace entries). Boundary incident: the first cluster sweep over `r10/`
also downloaded 9 files under r10/m and r10/m1 (the master's sealed
directories); none produced a census hit and none was opened; they were
deleted locally and on the cluster when the master's boundary arrived, and
the census was re-run without them (102 workspaces, same 17 with hits).

F1 is FALSIFIED as stated -- Q15 g1 is not the only case:
- Q15 g1 (Bergman, p-benzyne): FlipSpin 1,6 written three native ways in ORCA
  (`joboption`, `input_string`, `additional_route_parameters`; ORCA's input
  check aborted each), then Gaussian `additional_route_parameters: guess=mix`
  on restricted routes. The Gaussian nodes were never launched: the launch
  gate refused them on the ORCA input-check abort recorded for the same node
  id in planning (a stale, cross-program check; see defects found and left).
  So F3 cannot be read from Q15's records; O0 answers it.
- R8-era twisted ethylene (pyscf-agent-knowledge-20260919 g2-ethylene): the
  session wrote "Broken-symmetry UKS single point at 90 deg ... not selectable
  through the job-level state" and delivered the restricted 97.3 kcal/mol
  barrier against the experimental ~65.
- ax41 NOVEL-3 ino2-dinickel-exchange (2026-09-05/06): `reference: uhf` +
  `additional_route_parameters: FlipSpin 1,2` passed validation and preview
  and died at ORCA's input parse; the session then substituted the M=3 UKS
  determinant for the Ms=0 broken-symmetry state. Its own spin populations
  show a local spin change (Ni1 0.04, Ni2 1.68; <S**2> 2.79) rather than
  antiparallel sites, and the J it delivered (|J| 1040-1690 cm-1, against a
  susceptibility bracket of <= ~4 cm-1) rests on that substitution.
- R10 Q17 hc1 dA-o2gap (S1, U1, P1): sessions named a broken-symmetry UKS
  singlet as the correct description of O2 a1Delta_g and had no route to it
  (zero-engine tasks, so a limitation, not a loss).
- R10 q1 gdev1, q13 o2r and dans, q16 l1-o2r: sessions searched the capability
  surface for "unrestricted broken symmetry initial guess" project settings
  and found none (the tasks did not require one).
- Considered and rejected on scientific grounds (not a capability gap):
  R8-era ozone (BS-UMP2 would change the requested level), R9 g2-stability.

## Design under test (to be revised by O0)

One typed stage field, `broken_symmetry: true`, with one meaning in every
program: an unrestricted determinant at Ms = 0 (bound multiplicity 1) started
from a guess whose alpha HOMO and LUMO are mixed 50:50, so the SCF can reach a
spin-polarised (broken-symmetry) solution where one lies below the
spin-symmetric one. Each writer translates it into its own program's
mechanism and says so; the readers state the reference that ran; the host
states, from <S**2> as the program printed it, whether spin symmetry broke.

## Oracle O0 (native mechanisms, no ChemSmart) -- pre-registered expectations

Geometries (fixed, Angstrom): H2 at 0.74 and 2.00; ethylene planar and 90 deg
twisted (C=C 1.339, C-H 1.086, HCC 121.5); p-benzyne as a regular hexagon
(C-C 1.395, C-H 1.085, H removed on C1 and C4). HF (not p-benzyne) and B3LYP in
its Gaussian (VWN3) form (Gaussian B3LYP, ORCA B3LYP/G, PySCF b3lypg),
def2-SVP spherical, tight SCF, no RI, fine grids. Variants: restricted;
restricted + guess=mix (Gaussian); unrestricted without a symmetry-breaking
guess; unrestricted with each program's mixing guess (Gaussian guess=mix, ORCA
GuessMix 45, PySCF alpha HOMO/LUMO 45 deg rotation, and PySCF's own default
init_guess_breaksym=1); stability following (Gaussian stable=opt from R and
from U, ORCA STABPerform, PySCF R -> U external then internal); ORCA
BrokenSym 1,1 from the triplet; the triplets.

- E1 (F3): Gaussian restricted + guess=mix prints `E(RB3LYP)`/`E(RHF)` and an
  energy equal to the plain restricted run within 1e-6 Eh on every system.
- E2: unrestricted with a spin-symmetric guess collapses (<S**2> < 1e-3, E
  equal to the restricted energy within 1e-6 Eh) in all three programs on all
  five systems.
- E3: with a mixing guess, H2 at 2.00, twisted ethylene and p-benzyne break
  (<S**2> > 0.1, E below the restricted energy by more than 1 kcal/mol; more
  than 10 kcal/mol for twisted ethylene); H2 at 0.74 and planar ethylene
  collapse (<S**2> < 1e-3, E equal to restricted within 1e-6 Eh).
- E4: where all three programs break, E agrees within 1e-5 Eh (HF) and 2e-4 Eh
  (B3LYP), <S**2> within 0.01. A larger difference is a different solution
  (F2: the particular solution is not portable), reported as such.
- E5: PySCF's default breaksym and the explicit HOMO/LUMO mix reach the same
  energy within 1e-6 Eh.
- E6: ORCA BrokenSym 1,1 and GuessMix reach the same energy within 1e-5 Eh.

## Jobs issued

(none yet)

## Status

- 2026-09-24: episode opened; gate open; census done (F1 falsified as stated).
