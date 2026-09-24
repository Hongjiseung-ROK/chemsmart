# R10 Q8 -- what an excited state is, as the hub serves it

Base SHA: a86d96581f6bfb290d2684cf88a86837f9f87c8b (verified `git rev-parse HEAD` at start)
Episode id: q8
Branch: worktree-agent-ac5d6ed8468ad4e58

## Question (as currently understood)

Is an excited state one typed physical object across Gaussian, ORCA and
PySCF (Fundamental 1)?

1. Requested in one vocabulary -- manifold, response approximation,
   number of states -- that every program either runs as the same
   calculation or refuses with a program-neutral edit that makes it
   runnable.
2. Identified by what it is (spin, manifold root, character, strength),
   not by its place in one program's list; the same selector name means
   the same state in every program.
3. Combined only when it is the same quantity: the host, not the model,
   knows when two roots come from different response approximations, and
   says what it can about a window that may be incomplete.

## Premises checked on the base tree (provider-free, before any change)

Probe P1 -- one `td:` section (PBE0/def2-SVP, tddft, nstates 3), varied
only in `state_manifold`, through `chemsmart run --fake` of the three
programs (formaldehyde closed shell; allyl radical doublet):

| manifold | Gaussian | ORCA | PySCF |
|---|---|---|---|
| singlet (closed shell) | TD(singlets) | TDA false, Triplets false | ok |
| triplet (closed shell) | TD(triplets) | REFUSED "Unsupported state_manifold 'triplet'" | ok |
| singlet_triplet (closed shell) | TD(50-50) | Triplets true | REFUSED "requires ... singlet, triplet, unrestricted" |
| unrestricted (open shell) | TD(nstates=3) | REFUSED "Unsupported state_manifold 'unrestricted'" | ok |

No refusal names a route. ORCA can run an open-shell (UKS) TD-DFT
natively and the hub cannot ask for it at all; ORCA has no triplet-only
option (ORCA 6.1.1 manual, section 5.6: `Triplets true` computes the
spin-adapted triplets *beside* the singlets; for a UHF/UKS reference
"multiplicity estimated based on rounded <S**2> value, RELEVANCE IS
LIMITED!"); PySCF can run a singlet and a triplet response on one
reference and the hub refuses to ask.

Probe P2 -- the archived real td outputs read through each reader
(`probe_readers.py`, scratch):

- CONFIRMED (brief). One two-manifold request serves two orders.
  Acrolein `singlet_triplet`, nstates 3: Gaussian `excitation_energies`
  = [T1 2.978, T2 3.196, S1 3.624, T3 5.648, S2 6.534, S3 7.052] eV
  (energy order); ORCA = [S1 3.622, S2 6.536, S3 7.049, T1 2.976, T2
  3.196, T3 5.647] (STATE-table order). Index 0 is T1 in one program and
  S1 in the other.
- NEW. ORCA `excited_state_indices` = [1, 2, 3, 1, 2, 3] on that run:
  the STATE number restarts per manifold, so the selector that is a
  unique rank in Gaussian and PySCF repeats in ORCA.
- NEW. Gaussian `td` declares none of `excited_state_manifold_roots`,
  `excited_state_multiplicities`, `singlet_*`, `triplet_*` (the accessors
  exist and answer correctly: [1,2,1,3,2,3], [3,3,1,3,1,1]); ORCA `td`
  declares no `triplet_*`. The excitations guide says "Excited-state
  selectors answer per manifold root, singlet and triplet apart" -- two
  programs refuse half of that.
- NEW. Gaussian's unrestricted run (radical anion, 50 roots) serves no
  `excited_state_manifold_roots` (the parser counts roots only for a
  resolved spin label) where PySCF's unrestricted hydroxyl serves 1..n.
- CONFIRMED (brief, Q7). ORCA's level carries no response method,
  manifold or root count (Gaussian's and PySCF's do); `LEVEL_IDENTITY_FIELDS`
  = method, basis, dispersion, solvation, frozen_core: a TDA and a full
  TD-DFT excitation combine with no observation.
- NEW. ORCA excitation energies are read from the STATE line's
  three-decimal eV (3.622) where ORCA also prints 3.622297 eV
  (absorption table) and 0.133117 Eh: 5e-4 eV of rounding inside
  cross-program bands of 3-5e-3 eV.
- CONFIRMED (Q7 O4). Nothing tells a session that the top root of a
  Davidson window may not be the n-th state.

## Falsifiers of the premise (from the brief)

Premise falsified if, on three chemically different systems (a
closed-shell chromophore with near-degenerate roots, an open-shell
system, one where singlet-triplet order matters), all three hold:
(a) every shared manifold or response word runs as the same calculation
or is refused with a program-neutral edit that makes it runnable;
(b) states read back paired and ordered so that identity-by-index is
already safe at the windows an Agent requests; (c) no operation the
Agent can call combines values from different response approximations
without an observation.

Status: NOT falsified on the base tree by the provider-free probes alone
-- (a) fails for ORCA triplet/unrestricted and PySCF singlet_triplet,
(b) fails for any two-manifold run (orders differ; ORCA indices repeat),
(c) fails (TDA + TDDFT combine silently). The oracle below measures (b)
at the top of a window on real runs.

## Plan

A. Provider-free, in radius, one general commit per defect:
   1. One state order and one set of names in every reader: states in
      ascending excitation energy with a unique rank; manifold roots and
      multiplicities declared in all three; `singlet_*`/`triplet_*`
      declared in all three; ORCA energies at ORCA's six-decimal
      precision; Gaussian's unrestricted manifold roots.
   2. ORCA's level states the response it ran; the level observation
      compares the response approximation of excited-root operands.
   3. The shared manifold words run everywhere they can be computed:
      ORCA `unrestricted` (UKS TD-DFT) and `triplet` (the triplet block
      of a `Triplets true` solve), PySCF `singlet_triplet` (two response
      solves on one reference) -- after a fact-finding run shows ORCA's
      real UKS output.
B. CLI oracle (pre-registered below before it is issued).
C. Live Agent goals where the answer depends on state identity.

## Pre-registration

(written before each job is issued; never edited after its result)

### O1 -- one td request per manifold word, three programs (CLI oracle, job cli/oracle1)

Tree: the packed commit in the job's code-commit.txt (61a46f4e or later,
the three request-side commits). Level PBE0/def2-SVP everywhere; ORCA with
`ri_approximation: none` (matched numerics, as Q7's O1). Geometries: Q7's
Gaussian PBE0/def2-SVP minima of formaldehyde and s-trans acrolein
(r10/q7/cli/oracle1/{form,acro}_opt.log, copied), and a Gaussian
UPBE0/def2-SVP opt+freq of the allyl radical (doublet) run first in the
same job from a rough C2v geometry. 25 CLI runs (commands.txt):
formaldehyde and acrolein `singlet_triplet` nstates 3 and `triplet`
nstates 3 in G/O/P; acrolein `singlet_triplet` nstates 6 in G/O/P; allyl
`unrestricted` TD-DFT nstates 6, TDA nstates 6, TD-DFT nstates 10 in G/O/P.
Same YAML for the three programs (ORCA adds NoRI).

Bands (success / failure), each state paired by (multiplicity, manifold
root) -- never by list position:
- B1 ORCA `triplet` (new translation, `Triplets true` with the triplet
  block served): its triplet roots equal the same program's
  `singlet_triplet` triplet roots within 0.001 eV; within 0.008 eV of
  Gaussian's `triplets` and PySCF's `triplet` roots.
- B2 PySCF `singlet_triplet` (new, two blocks on one reference): its
  triplet block equals PySCF's own `triplet` run within 1e-5 eV; its
  singlets within 0.003 eV of Gaussian's 50-50 singlets, and every state
  within 0.008 eV of ORCA's.
- B3 Gaussian vs PySCF, every paired closed-shell state: within 0.003 eV;
  vs ORCA-NoRI: within 0.008 eV (Q7 saw up to 0.0059, ORCA's TD kernel
  grid); f within 0.002 absolute or 5 % relative.
- B4 allyl `unrestricted`: ORCA runs UKS TD-DFT and TDA (a refusal by the
  engine is a finding: the hub would then have to refuse that pair with a
  route); G vs P roots within 0.005 eV, O within 0.010 eV of G; f within
  0.002 absolute or 5 %; <S^2> G vs O within 0.01; TDA >= TD-DFT - 0.001
  eV root by root in each program.
- B5 (fact-finding, no band): whether each program's smaller window
  (acrolein st3 vs st6; allyl u6 vs u10) equals the lowest roots of its
  larger window within 0.001 eV. This measures falsifier (b) at the
  windows an Agent requests.
- B6 physics (wide): acrolein and formaldehyde T1 < S1 with T1 f = 0
  exactly; acrolein T2 < S1 (Q7: 3.196 < 3.624); allyl's lowest doublet
  excitation between 2.5 and 4.0 eV and a bright root (f > 0.05) between
  4.0 and 6.5 eV.
- Falsifier of the translation: any paired state > 0.02 eV apart between
  programs for the same words, or ORCA `triplet` / PySCF `singlet_triplet`
  roots that are not the roots of the other manifold words = the hub
  translating one request into two calculations; no Agent goal is judged
  against O1 until it is explained.

### G1 -- acrolein's triplets relative to S1, in ORCA and PySCF (live goal, goals/g1-ladder)

Task (fixed before issue, `goals/g1-ladder/TASK.md`): acrolein from Q7's
rough planar s-trans geometry; relax at PBE0/def2-SVP (program the
session's choice), then full TD-DFT singlets and triplets at the minimum
independently in ORCA and in PySCF; per program S1, T1, T2, the S1-T1
gap, every triplet below S1, the brightest computed singlet with its f;
then a state-by-state comparison with the largest difference. Engines
allowed: gaussian, orca, pyscf. Code: the pack of this commit.

References (O1 at Q7's Gaussian PBE0/def2-SVP minimum; ORCA NoRI): ORCA
S1 3.6223, T1 2.9763, T2 3.1961, S2 6.5357 eV (f 0.381); PySCF S1 3.6243,
T1 2.9780, T2 3.1952, S2 6.5340 (f 0.381). ORCA's default RIJCOSX moved
acrolein roots by <= 0.002 eV (Q7 E4).
- Success: an ORCA and a PySCF td node executed under the approval chain,
  validated and parsed; per program S1, T1, T2 within 0.02 eV of the
  program's reference (a minimum reached by another program at the same
  level moves roots by less); S1-T1 = 0.646 +- 0.02 eV; exactly T1 and T2
  reported below S1 in both programs; the brightest singlet (if two or
  more were computed) S2 at 6.53 +- 0.02 eV with f 0.38 +- 0.02; the
  programs agree within 0.01 eV per paired state; settlement from the
  ledger.
- Failure: a state named by position across programs (a triplet called
  S1, T2 taken for S2, a k-th root compared with another program's k-th
  root of the other manifold); no td node in one of the two programs; a
  claim of agreement over differently paired states.
- Recorded, not scored: which manifold words and nstates the session
  chose (singlet_triplet or separate nodes), which selectors it read
  (singlet_*/triplet_* or multiplicities), which program optimised,
  whether it opened the excitations reference.

### G2 -- the allyl radical's doublet states up to 7 eV, in ORCA and PySCF (live goal, goals/g2-allyl)

Task (fixed before issue, `goals/g2-allyl/TASK.md`): the allyl radical at
the UPBE0/def2-SVP minimum O1 reached (supplied); full TD-DFT at
PBE0/def2-SVP independently in ORCA and in PySCF covering every state up
to 7 eV; per program energies and strengths of those states, the
strongest absorption, a measure of spin contamination where the programs
allow it; a state-by-state comparison with the largest difference.
Engines allowed: orca, pyscf.

References (O1, ten-root windows, NoRI ORCA): the states below 7 eV are
4.0024/4.0013, 5.9998/6.0003, 6.3125/6.3106 (f 0.388, the strongest),
6.4359/6.4356, 6.6357/6.6363, 6.9000/6.9000 eV (ORCA/PySCF); a six-root
PySCF window misses the 6.90 eV root and returns 7.080 as its sixth. Under
full TD-DFT the host serves no per-root <S^2> (b082d045) and names TDA as
the route; under TDA D1 has <S^2> 0.756 in ORCA, and a six-root ORCA TDA
window lacks the bright root.
- Success: an ORCA and a PySCF unrestricted td node executed, validated
  and parsed (the first Agent run of ORCA's `unrestricted`); the strongest
  absorption at 6.31 +- 0.02 eV with f 0.39 +- 0.02 in both; every state
  the session reports below 7 eV within 0.01 eV of the reference; where
  the two programs' lists differ (a window missing a root), the report
  says so rather than claiming agreement.
- Failure: no unrestricted td in one program; a claimed state-by-state
  agreement between lists that hold different states; a spin-contamination
  number presented that the host did not serve (e.g. a full TD-DFT <S^2>).
- Recorded, not scored: nstates and response chosen, whether the session
  checked that its top root lies above 7 eV, whether it ran TDA for <S^2>,
  whether it noticed a missing root (not asked).

### O2 -- what a PySCF root is made of, on the engine (CLI oracle, job cli/oracle2)

Tree 43862950 (the dominant-excitation record), unpacked beside the goals'
code so the running goals keep theirs. PySCF only, PBE0/def2-SVP, the O1
geometries: acrolein `singlet_triplet` nstates 3; allyl `unrestricted`
TD-DFT nstates 6 and 10; formaldehyde (Q7's minimum) `singlet` TD-DFT
nstates 6. Gaussian's and ORCA's labels are read from the archived O1 and
Q7 outputs.
- C1: every PySCF artifact validates with the new dataset (shape one row
  per root) and the host evaluator agrees.
- C2: acrolein st3 and allyl u10: PySCF's dominant excitation equals
  Gaussian's and ORCA's at every index; weights within 0.06 of Gaussian's.
- C3: where a window missed a root, character says so: allyl u6 PySCF root
  6 is not `beta HOMO -> LUMO+1` (the G/O sixth); formaldehyde nstates 6
  PySCF root 6 is `HOMO -> LUMO+2` (the f 0.47 root Q7's O4 found missing
  in G and O, whose sixth is `HOMO -> LUMO+3`).
- Falsifier: PySCF's labels disagree with G/O on a root all three windows
  hold (the offsets would then not be one description).

### G3 -- G2's task re-issued unchanged on the repaired tree (live goal, goals/g3-allyl)

Why: G2's cycle-1 stream (CUHK 2150296) showed ORCA's td bound no engine
on the allyl radical because the bootstrap fixture asked ORCA for a
singlet manifold on a doublet (repaired in 22e22752). G2 is reported as it
runs; G3 is a new observation of the same task (TASK.md byte-identical,
same allyl.xyz) on the tree that also carries 43862950 (what a root is
made of). Code: the pack of this commit, in its own directory.
- Bands: exactly G2's (above), plus: ORCA's unrestricted td binds and
  executes (the first Agent run of ORCA's open-shell TD).
- Recorded, not scored: whether the session reads
  excited_state_dominant_excitations to pair states, and whether a window
  gap (if its windows leave one) is found by character.

## Results read so far (host records, through ChemSmart's readers)

O1 (Slurm 2150194, code 4a01097a, tree digest 15fd46c4 recomputed on the
node, 9:34, all 25 commands exit 0, every PySCF receipt `validated` with
no findings; read through the readers of 28b8b48c/c2873226):
- Allyl radical UPBE0/def2-SVP opt+freq: E -117.025473919 Eh, lowest mode
  423.7 cm-1 (C2v minimum).
- B1 PASS. ORCA `triplet` (new, `Triplets true`, triplet block served):
  equal to ORCA's own singlet_triplet triplets to 0.000000 eV
  (formaldehyde and acrolein); within 0.0028 / 0.0018 eV of Gaussian's
  `triplets` and 0.0032 / 0.0016 of PySCF's `triplet`.
- B2 PASS. PySCF `singlet_triplet` (new, two blocks): its triplet block
  equals PySCF's own `triplet` run to 6e-8 / 5e-8 eV; singlets within
  5e-4 / 3e-4 eV of Gaussian's 50-50; every state within 0.0043 / 0.0024
  of ORCA's.
- B3 PASS. In all five closed-shell cases (formaldehyde and acrolein st3
  and trip3, acrolein st6) the three programs name the same state at
  every index (multiplicity and manifold root equal) -- the order and the
  names are one now; |dE| G-P <= 0.0009, G-O <= 0.0042 eV; |df| <= 0.0007.
- B4 FAILED at the top of the windows, and on <S^2>:
  - allyl TD-DFT nstates 6: G and O agree (0.0016 eV) but PySCF's root 6
    is 7.0798 eV where G/O have 6.9007/6.9000 (<S^2> 2.67): PySCF's
    Davidson missed that root; at nstates 10 all three agree to 0.0016 eV
    over ten roots and PySCF's 6.9000 is there.
  - allyl TDA nstates 6: ORCA's window lacks the bright 2B2 root at
    6.704 eV (f 0.56; G 6.7037, P 6.7035) and returns 7.083 and 7.092 as
    roots 5 and 6; PySCF lacks G's root 6 (7.084, <S^2> 2.67) and returns
    7.092. Only Gaussian's six roots are the six lowest (every root of
    every window is in the union). An ORCA TDA spectrum of allyl at six
    roots has no strong band below 7.1 eV, and nothing says so.
  - <S^2> of an unrestricted full-TD-DFT root: Gaussian 0.713 vs ORCA
    0.801 for D1 (0.714 vs 0.799 for the bright D3; 2.667 vs 2.724); under
    TDA the two agree to the printed digit (0.756/0.756, 0.811/0.811 ...).
    `excited_state_spin_square` names two quantities for full TD-DFT.
  - Where both windows hold the same root, G-P <= 0.0007 eV and G-O <=
    0.0016 eV; TDA >= TD-DFT root by root in every program (the shift is
    0.14 eV for D1).
- B5 (fact-finding): acrolein st3 -> st6 windows agree per manifold in all
  three programs (<= 1e-5 eV); allyl u6 -> u10: Gaussian and ORCA agree,
  PySCF does not (root 6, above).
- B6: T1 < S1 with f(T) = 0 for both closed shells; acrolein T2 (3.196) <
  S1 (3.624): PASS. Allyl's lowest excitation 4.0018 eV (G) -- the
  pre-registered 2.5-4.0 eV band MISSED by 0.002 eV; bright root 6.311 eV
  f 0.388 inside 4.0-6.5.
- The pre-registered falsifier FIRED (paired states > 0.02 eV apart:
  allyl root 6 at TD-DFT, roots 5-6 at TDA). Explanation, from the same
  job: Davidson windows incomplete at the top, in PySCF (TD-DFT) and ORCA
  (TDA) this time where Q7's O4 caught Gaussian and ORCA -- not a
  translation defect: every missing root is present in another program's
  window, and the ten-root windows agree. Premise (b) of the brief is
  therefore false at the windows an Agent requests: identity by index is
  unsafe even after one order, because a window can lack a state.

G1 (Slurm 2150295, code fcb115eb, digest cc7c2ef3 recomputed on the node,
settled `achieved_with_observations` at cycle 2, 4 engine calls):
- Cycle 1: the session relaxed acrolein independently in each program
  (orca-opt 117.9 s, pyscf-opt 86.7 s). Cycle 2: orca-td (42.2 s) and
  pyscf-td (97.9 s) on the two reached structures, both written as
  `response_method: tddft`, `state_manifold: singlet_triplet`,
  `nstates: 5` -- one set of words in two programs; PySCF's two-block
  request's first Agent run.
- The approved chain extracted `singlet_excitation_energies`,
  `singlet_oscillator_strengths`, `triplet_excitation_energies` from both
  programs (provenance excited_root) and paired S1-S1, T1-T1, T2-T2 by
  manifold and rank; no state was named by position.
- Claims: ORCA S1 3.6225, T1 2.9766, T2 3.1959 eV, S1-T1 0.6458 eV, brightest
  singlet f 0.3807; PySCF S1 3.6246, T1 2.9780, T2 3.1961, gap 0.6467, f
  0.3811; largest program difference 0.0021 eV (S1). Against the O1
  references every root is within 0.0009 eV and every f within 0.0005:
  PASS on the energy, gap and agreement bands.
- Partly met: that T1 and T2 lie below S1 is in the delivered numbers but
  not stated as a claim, and the brightest singlet's energy (S2, 6.53 eV)
  was not claimed beside its strength.
- Recorded by the host, unasked: the session's own expectation that T2 is
  a pi->pi* state at 3.8-5.4 eV was falsified in both programs (T2 3.196
  eV; its dominant excitation is HOMO-1 -> LUMO, O1) -- no reading turn
  followed, so nobody interpreted it; and geometry.results_indistinguishable
  between the two td nodes (heavy-atom RMSD 0.0002 A), whose recorded
  energy difference, -83.42 kcal/mol, was false: ORCA's IRoot total against
  PySCF's reference (repaired in 60c78113; the references differ by 0.02).
- Qualified by the host in the ledger: orca:cpu:td, pyscf:cpu:td,
  orca:cpu:opt, pyscf:cpu:opt.

G2 (Slurm 2150296, code fcb115eb, settled `unreachable_from_evidence` at
cycle 2, 1 engine call):
- FAILURE by its own pre-registration (no ORCA unrestricted td executed),
  and the cause is the host: the bootstrap probe's ORCA fixture asked td
  for `singlet` on the doublet, ORCA's td bound no engine
  (`binding.program.capability_red`, `execution_ready false`), and the
  session recorded it, rejected an ORCA sp carrying a td section as
  unreadable and a Gaussian substitution as outside the envelope, and ran
  PySCF alone. Repaired in 22e22752; G3 re-issues the task.
- What the session did with PySCF is good science, recorded not scored: it
  asked 25 roots with "a post-hoc >= 7 eV coverage validation" and
  delivered six states up to 7 eV (4.00, 6.00, 6.31, 6.44, 6.64, 6.90 eV;
  strongest root 3, f 0.388) with "root 7 at about 7.08 eV brackets the
  window from above" -- the 6.90 eV root O1's six-root PySCF window missed
  is here because the window was large. Spin: it reported the reference
  <S^2> 0.792 and that PySCF serves no per-root <S^2>. Every number is
  within 0.001 eV of O1's ten-root PySCF window.
- The settlement names the three ORCA observables unreachable with the
  typed receipts behind each: an honest refusal, not a claim.

O2 (Slurm 2150298, code 5d2dfc54, digest a120c3c8 on the node, 4 PySCF runs,
all receipts `validated`): C1 PASS (dataset shape valid, host evaluator
agrees); C2 PASS (acrolein st3 and allyl ten roots: PySCF, Gaussian and ORCA
name the same excitation at every index; PySCF's 2|X|^2 = Gaussian's 2c^2 to
0.001); C3 PASS (allyl six roots: PySCF's sixth is alpha HOMO -> LUMO+2 at
7.080 where G/O's is beta HOMO -> LUMO+1 at 6.901; formaldehyde six roots:
PySCF's sixth is HOMO -> LUMO+2 at 11.233, f 0.47, G/O's HOMO -> LUMO+3 at
11.254). Falsifier not met.

G3 (Slurm 2150299, code 68f77aa1, digest 6ae2ba3d on the node, settled
`unreachable_from_evidence` at cycle 2 after an analysis-only revision, 2
engine calls, 183 s engine wall):
- Cycle 1: an ORCA and a PySCF td node on the supplied minimum, both
  written `response_method: tddft`, `state_manifold: unrestricted`,
  `nstates: 30` (ORCA adds `reference: uhf`); the hub wrote ORCA's
  `%tddft NRoots 30 TDA false` with no Triplets line under `HFTyp UHF`.
  The first Agent run of ORCA's open-shell TD-DFT: executed, validated,
  parsed (69.5 s; PySCF 113.3 s).
- PASS on every pre-registered band. Claimed below 7 eV, ORCA (RIJCOSX) /
  PySCF: 4.0024/4.0013, 5.9992/6.0003, 6.3129/6.3106 (f 0.3876/0.3875, the
  strongest), 6.4351/6.4356, 6.6304/6.6363, 6.9001/6.9000 eV -- every state
  within 0.0053 eV of O1 (ORCA's largest shift is D5, RI vs NoRI) and PySCF
  within 1e-4; largest program difference 0.0059 eV (D5); the next root just
  above the window claimed in both (7.075/7.080). No per-root <S^2>
  presented: the reader refused ORCA's with the TDA route (b082d045), the
  session declared both per-root observables unreachable, the host verified
  each, and the reference <S^2> 0.7921 was delivered as context -- the
  settlement word is that honest refusal.
- Recorded, not scored: TDA considered and rejected in `approaches` ("the
  task explicitly requests full LR-TDDFT, and changing the response method
  would change the physical answer"); 30 roots for a 7 eV question; states
  paired by index with a stated uncertainty ("Roots are indices, not state
  identities ... with in-window gaps >= 0.09 eV, reordering within the
  window is unlikely") -- the dominant-excitation selectors were available
  and not read. Read through them (scratch analyse_g3.py), the six
  in-window states carry the same character at the same index in both
  programs, so the pairing was right. Above the window it is not: ORCA's
  30-root window lacks PySCF's 11.232 eV state (alpha HOMO-2 -> LUMO+3), so
  indices 29-30 hold different states (ORCA 29 = PySCF 30, beta HOMO ->
  LUMO+6, dE 0.0054 eV). The session's cycle-1 expression paired all 30
  roots by index (largest 0.067 eV, a different-state pair); its cycle-2
  claims kept to the window and claimed no agreement above it.
- Host defect, cycle 1: the session's own window check (each program's
  highest root >= 7 eV) failed as "scientific validation input is not typed
  evidence from its planned producer" because one extraction node beside
  the energies had a refused selector (ORCA's <S^2>) and the host's
  receipt-to-node relation was still node-level. Repaired in c726cb08.
  Provider-free replay of the approved cycle-1 chain (plan 55dfdadf) on the
  goal's own two outputs (scratch replay_chain.py): 438276d6 reproduces the
  live node states exactly; c726cb08 evaluates coverage-7ev (verdict 1).
  Note the check is necessary, not sufficient: O1's six-root PySCF window
  topped out at 7.080 eV and still lacked the 6.900 eV state.

## Jobs issued

| Slurm | slot | what | code | pre-registration |
|---|---|---|---|---|
| 2150194 | r10-q8-a | cli/oracle1: O1 (25 CLI runs) | 4a01097a | e562a1d51451 |
| 2150295 | r10-q8-a | goals/g1-ladder: acrolein S/T ladder, ORCA + PySCF | fcb115eb | f1f16826f111 |
| 2150296 | r10-q8-b | goals/g2-allyl: allyl doublets to 7 eV, ORCA + PySCF | fcb115eb | f1f16826f111 |
| 2150298 | r10-q8-a | cli/oracle2: O2 (4 PySCF runs, code-5d2dfc54 beside the goals' code) | 5d2dfc54 | 80f84d0ef09b |
| 2150299 | r10-q8-b | goals/g3-allyl: G2's task unchanged, repaired tree (code-68f77aa1) | 68f77aa1 | e48ed29b9a23 |

## Status

- step 0: base verified; probes P1 and P2 run on the base tree.
- step 1: request side committed -- 5bc66a8f (shared: one reference rule),
  6322d48e (shared: ORCA triplet + unrestricted; ORCA's %tddft reader),
  61a46f4e (PySCF singlet_triplet). Every program now takes the four words
  (fake previews green); none has run on an engine. O1 pre-registered.
- step 2: O1 read (above). Read side and level committed: 28b8b48c (one
  order, one set of names, ORCA precision, Gaussian open-shell roots),
  c2873226 (response in the level identity, ORCA's level states it),
  b082d045 (<S^2> only where it is one quantity; O1 fixtures), 6d982a50
  (guide sentences: manifold names, windows), 43862950 (what a root is
  made of, in all three programs).
- step 3: G1 and G2 issued on fcb115eb (before 43862950: the goals have no
  character selector); O2 queued on 5d2dfc54.
- step 4: G1, G2, O2 and G3 read (above). Repairs from what they showed:
  60c78113 (shared: the sibling-structure sensor compares the energies the
  readers serve), 22e22752 (shared: the bootstrap probe previews td on the
  manifold the molecule has), a3f552ab / 7045daa0 (the command lines take
  the shared words), 5d8a0c98 (PySCF character on 2.14 artifacts),
  c726cb08 (shared: a validation over delivered values is not refused for a
  sibling's absence). The full suite on a pristine export of 470f3257 had
  one new failure, the fixture-keys pin 22e22752 broke (2f0a635c, shared);
  438276d6 documents Gaussian's two new options.
- step 5: release records for the cells G1 and G3 qualified; merge
  r10-integration; hand back.
