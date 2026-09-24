# EPISODE q6 -- does the Agent notice what nobody asked, once it reads its results?

Base SHA: `bc35fe4ce125dd9a975f3870134f0b025889e5f2` (verified as the
worktree HEAD before any other action, 2026-09-24; `r10-integration`
pointed at the same commit).

Agent under study: `deepseek-v4-flash-0731` via `alibaba-token-plan`.
Every behavioural statement below is about that model.

## The question, as currently understood

Once the Agent reads the results of the calculations it ran -- a
results-reading turn after a delivered run, host-owned, launching
nothing -- does it notice and claim non-trivial phenomena nobody asked
about, at a false-claim rate measured on matched controls, and at what
cost (provider tokens and wall time per goal)?

Two things are mixed in that question and must be kept apart, because
confusing them is how an evaluation measures the architecture instead of
the model:

1. Opportunity (architecture). Q1 found that the driver settles a
   complete delivery with no session reading the results (10 of 23
   archived successful engine goals). For a phenomenon present only in
   computed results, the without-arm cannot notice it by construction;
   a with-arm that does is showing that the host gave the model a look,
   not that the model can see.
2. Discrimination (model). Given a look, does the model tell a planted
   phenomenon from its matched control -- sensitivity against the
   false-claim rate on controls -- and does the typed evidence carry its
   interpretation, not a host sensor's.

## Priors to verify (from the brief), not conclusions

- A finding (Q1) is the session's sentence bound to relations the host
  checked; a discovery is an unrequested finding.
- `_settle`'s achieved branch settles a complete delivery unread; only a
  recovery, a declared category the executor cannot deliver, or a
  sufficiency re-wake puts a session over computed results.
- Workspace file names do not reach the session (Q1); not my target.

## Falsifiers of the premise (from the brief; each alone is enough)

- (a) With the reading turn available, the Agent on the sealed tasks
  notices no more planted phenomena than without it.
- (b) It cannot tell phenomena from controls: its false-claim rate on
  controls is comparable to its sensitivity on phenomena.

Either one makes the bottleneck the model or its knowledge, and that is
the result. Cost is part of the result either way.

Mechanism failures (not premise falsifiers, but they void a run):

- the reading turn moves the settlement word, launches anything, or
  opens a revision or recovery;
- the reading turn's record is not reachable from the settlement.

## Mechanism (commits f22170a6, a7ee1d49, 07a9c2d8)

The reading turn is a host policy, off by default (`GoalDriver
reading_turn`, `chemsmart agent goal --reading-turn`, recorded in
driver.json). When on, a certified delivery (the two words `achieved`,
`achieved_with_observations`, on either settle path -- an executed run's
chain, or a cycle that delivered from registered results) is not written
at once: the host computes the word, reasons and evidence exactly as it
would have written them and holds them in a `reading_opened` ledger row;
the new phase `read` runs one session over the delivered stream with the
wake's own composition, zero budgets, no review file, the held word, and
the rule `wake.reading_turn`; the goal then settles on the held word,
with the reading's line, findings and provider cost added
(`reading_recorded` carries the same). The reading launches nothing: a
plan with a calculation node is refused at plan time by the zero engine
budget, and no plan it makes is decided. It cannot open a revision or a
recovery, because nothing after `reading_opened` re-enters branch
selection.

Consequence for the evaluation (the paired design). Nothing before the
settlement reads the policy, and the cycle-1 context does not mention
it. So in one goal run with the policy on, everything up to
`reading_opened` is exactly the goal the policy-off arm would have run,
and `reading_opened` is the host's own record of the settlement that arm
would have written. Each goal therefore yields both arms: without = the
sessions before `reading_opened` and its held settlement; with = the
same plus the reading session. This removes between-arm sampling noise
from the comparison and halves the cost; it is a paired design, not a
substitute for one of the arms.

## Development (provider-only, local, my own tasks; never presented as sealed)

Purpose: see the reading turn run on the real provider, see what the
model reads and records, measure cost, and revise the reading context if
it is not being read. Behaviour here decides nothing about a milestone.
Pairs (task text identical within a pair unless stated):

- D2 (Q1's, reused): ino3-r12 ORCA single points of a Ni bis(thiolate)
  bis(phosphine) complex, CPCM(acetonitrile). Phenomenon: neutral PBE0 +
  cation B3LYP presented as the pair for an ionisation energy (level
  mismatch, visible in each result's own level record). Control: both
  PBE0. Task asks the adiabatic IE only.
- D4 -- WITHDRAWN before any session ran. The six [Fe(H2O)4]n+ ORCA
  outputs (tests/data/ORCATests/outputs/fe*.out) are not the clean pair I
  wrote down: three of them (Fe(II) quintet, Fe(III) doublet and sextet)
  stopped at ORCA's 50-cycle optimisation limit with no frequencies, and
  the Fe(III) doublet carries <S^2> = 1.70 against 0.75. The control
  (quintet -> sextet) therefore holds phenomena of its own, so it
  controls nothing; the "lowest spin state" numbers above are not
  minima.

### Development results (code ef1d349e; local; deepseek-v4-flash-0731)

- dev-d2-phen (PBE0 neutral + B3LYP cation): the answering session
  itself read both results' level records, recorded two unrequested
  findings that the -14.88 eV difference crosses PBE0 and B3LYP and is
  not an ionisation energy, declared the IE blocked and the goal settled
  `unreachable_from_evidence` -- so no reading turn fired (it fires only
  on a certified word) and the two arms are identical. The host's own
  expression reply had also said `operands_at_different_levels`, which
  the finding cites. Planning session: 16 requests, 1.06 M summed input
  tokens, 41 k output, 385 s.
- dev-d2-ctrl (both PBE0): delivered IE 4.509 eV (Q1's 4.51); settled
  `achieved`; the reading fired on the delivery path as designed
  (reading_opened -> reading_recorded -> goal_settled, held word =
  settled word). The reading session inspected both results' selectors,
  extracted spin populations, charges, dipoles, CPCM electrostatic terms
  and connectivity, re-derived the delivered IE as its refutation read
  (4.509411 eV, identical), and recorded two unrequested findings: the
  cation's unpaired spin is Ni-centred (Mulliken 0.81, Loewdin 0.79; the
  two S 0.24), and CPCM stabilises the cation 1.54 eV more than the
  neutral. Both look true on the numbers it extracted; neither is a
  planted phenomenon (there is none). Reading cost: 9 requests, 450 k
  summed input tokens, 32 k output (24 k reasoning), 273 s -- 1.5x the
  answering session's 295 k / 18 k / 168 s.

What this changes, before any sealed material: on a control, the
reading produces true characterisations nobody planted. If sensitivity
counted any confirmed unrequested finding (Q1's definition allows "the
planted one, or another the verifier confirms"), the reading turn would
score a discovery on every item and sensitivity would measure
talkativeness. So the sealed measures split them (protocol, change 5).

## Live development goal gdev1 (CUHK, mine; run path), pre-registered

Purpose: the reading turn on the path it exists for -- a certified
delivery from an executed approved chain that no session would otherwise
read -- live, once, before any sealed goal: that the reading fires after
the executor's chain, that the reading session can open the run's result
artifacts, what it costs in a Slurm job, and what it records over a
clean delivery (nothing is planted; a finding the evidence contradicts is
a false claim and tells me the framing invites invention).

Task (verbatim): "I need two numbers for acetone in the gas phase at
B3LYP/def2-SVP, computed with PySCF: its equilibrium C=O bond length in
angstrom and its harmonic C=O stretching wavenumber in cm-1. The
starting structure is in this workspace (neutral, singlet)."
Starting geometry: RDKit ETKDG (seed 7) + MMFF acetone. Envelope:
pyscf cpu, 8 cores, 16 GB, node 1800 s, episode 5400 s, 3 engine calls,
max_revisions 2, `--reading-turn`, code ef1d349e (digest 470692cd).

Expectations (physics bands, from general B3LYP experience, not a
reference run): r(C=O) in [1.200, 1.225] A; harmonic C=O stretch
(unscaled) in [1770, 1860] cm-1; the optimised structure a minimum (no
imaginary mode) with C2v-like symmetry.
- Mechanism success: the goal settles achieved or
  achieved_with_observations; the ledger holds reading_opened after
  run_recorded and then reading_recorded and goal_settled, with nothing
  launched, admitted or recovered in between; the settled word equals the
  held word; the reading session's stream names the run's result
  artifacts it read.
- Mechanism failure: the reading does not fire on a certified delivery,
  fires and cannot see the run's results, changes the word, or the Slurm
  job ends inside the reading.
- Behaviour (decides nothing): findings recorded in the reading, and
  whether any is contradicted by the evidence.

### gdev1 result (CUHK Slurm 2150075, code ef1d349e, digest 470692cd; 30 min)

Settled `achieved`, 2 cycles, 1 revision admitted, 2 engine calls. The
cycle-1 session selected the optimisation alone as its first wave; the
chain was partial, a recovery woke cycle 2, which bound the reached
geometry and ran the Hessian; that run's chain delivered and the goal
held `achieved` for the reading. Ledger order: run_recorded (cycle 2) ->
reading_opened (state achieved, path run, run goals/gdev1/runs/cycle-2)
-> reading_recorded -> goal_settled (achieved, the held word) ->
qualified; nothing launched, admitted or recovered after the hold. Every
mechanism condition pre-registered above holds.

Physics against my bands: r(C=O) = 1.2103 A (band 1.200-1.225, in);
harmonic C=O stretch 1837.2 cm-1 (band 1770-1860, in, near the top);
24 real modes, no imaginary mode (the reading's own count).

Cost, from the streams: cycle-1 session 20 requests, 2.41 M summed
input tokens, 91 k output, 787 s; cycle-2 wake 18 requests, 1.63 M,
54 k, 468 s; reading 12 requests, 0.66 M, 29 k (19 k reasoning), 242 s
-- 14 % of the goal's provider input tokens and 16 % of its provider
wall time.

Behaviour: the reading opened both results, read the modes' atom
participation, the geometries of both artifacts and the imaginary-mode
count, and recorded four findings: one on the requested answer (both
numbers inside the declared bands) and three standing unrequested that
are confirmations of the delivery -- mode 18 is the C=O stretch (C+O
share 0.777), the structure is a minimum, and "refutation attempt failed
to refute" (the Hessian's geometry equals the optimised one to 3e-11 A).
All three are true and none is a phenomenon. The rule said where a
refutation that stands goes and not where one that does not stand goes;
commit 0173e309 says a check that the delivery holds belongs in the
decision's words. dev-d2-ctrl2 re-runs the local control on that rule
before the sealed material.

dev-d2-ctrl2 (code 0173e309, the refined rule; local): delivered 4.5094
eV, settled `achieved`; the reading (8 requests, 0.39 M summed input
tokens, 29 k output, 265 s) recorded the same two characterisations as
dev-d2-ctrl -- the hole is Ni-centred (Mulliken 0.810 on Ni, 0.118 on
each S) and CPCM stabilises the cation 1.54 eV more than the neutral --
and no confirmation as a finding (it re-derived the IE and said so in
the decision). Two independent readings of one control produced the same
two true characterisations: the reading's output on a clean delivery is
reproducible, and on this control it is two incidental findings, not
zero.

Development closes here. Mechanism and rule are frozen at 0173e309
(nothing under chemsmart/ changes before every sealed session has
settled); the sealed runs use the hand-back commit, which differs from
0173e309 only in this file.

## Protocol for the sealed material (adopts Q1's frozen protocol; changes stated)

Adopted verbatim from Q1 (`git show e165e650:EPISODE.md`, "Evaluation"
and "Protocol for the sealed material"): what counts as a discovery (a
host-recorded unrequested finding that an independent verifier holding
only raw evidence judges (1) not asked for by the task text, (2) a
correct statement of a phenomenon present in the evidence, (3) not a
restatement of a host anomaly or of a requested number, (4) resting on
relations that bear on it); what counts as a false claim (an unrequested
finding the verifier judges absent or wrong, including one whose
relations hold while the evidence contradicts its statement); prose-only
mentions counted separately and never as discoveries; sessions counted
only with at least one provider turn and no turn_deadline_exceeded
(infrastructure otherwise, reported, never counted); labels read only
after every session of the set has settled; no session is ever re-run.

Changes, each for a stated reason:

1. Arms by the paired design (above), not two separate goals per item.
   Every sealed goal runs with `--reading-turn`. Without-arm = everything
   recorded by sessions before the goal's `reading_opened` row, and the
   held settlement in that row; with-arm = the without-arm plus the
   reading session named in `reading_recorded.run_id`. A goal that never
   reaches `reading_opened` (it settles returned_to_human, exhausted or
   unreachable_from_evidence) has no reading; it counts in both arms
   with the same value and is reported as such.
2. Measures per arm: sensitivity = phenomenon items with >= 1 correct
   discovery / phenomenon items; false-claim rate = control items with
   >= 1 false unrequested finding / control items; false findings per
   item on both kinds; echoes (findings whose host_signals are related)
   counted separately; typing rate as Q1 defined it. Reported for the
   live pairs and the archived set separately and together.
3. Cost of the turn, from host records only: per goal, the reading
   session's provider requests, summed input, output and reasoning
   tokens, and wall seconds (`reading_recorded.cost`), beside the same
   quantities for the goal's other sessions.
4. What the verifier receives per goal: task text; the workspace input
   files; for every session, its public transcript and event stream,
   each labelled by the ledger (`session_stream_recorded` = planning or
   wake session; `reading_recorded.run_id` = reading session); the goal
   ledger including `reading_opened` (the without-arm settlement) and
   `goal_settled` (the with-arm settlement). Never this file's
   interpretation or my report.
5. Sensitivity counts the planted phenomenon only: a phenomenon item
   counts when the verifier judges an unrequested finding to name the
   planted phenomenon correctly. Every other unrequested finding the
   verifier confirms is an incidental discovery, reported separately on
   phenomenon and control items alike (count, and how many the verifier
   calls non-trivial); every one it judges absent or wrong is a false
   claim. Reason: dev-d2-ctrl's reading made two true characterisations
   of a control (above).

Runs:
- Live pairs: one goal per task on CUHK through make_goal.py and
  slot_submit (episode q6, concurrency 2), task text verbatim, granted by
  claude-researcher-q6-owner-delegated, max_revisions 2 unless the
  material says otherwise, envelope sized to the chemistry, with
  `--reading-turn` appended to the goal command; the approved episode
  sized so that planning, engines and the reading fit inside the Slurm
  time make_goal.py derives from it. My physics expectations for each
  task are written here and committed before its submission.
- Archived set: one provider-only goal per item, locally and
  sequentially (the key is shared), max_engine_calls 0, max_revisions 0,
  `--reading-turn`, task text verbatim, workspace = the item's files
  only.
- Code: the hand-back commit, packed with pack_code.sh; every goal
  prints the digest it ran.

Known limits, stated before the material is opened:
(1) a workspace file's name never reaches a session (Q1), so a
phenomenon carried only by a file name is invisible to both arms;
(2) the reading fires only on a certified delivery, so an item whose
goal is woken by a recovery or a declared category is read by the
ordinary wake in both arms, and the reading turn adds nothing there by
construction; (3) with four live pairs and eleven archived items the
rates are coarse -- one item moves a rate by 25 or 9 points -- and are
reported as counts.

Falsifier evaluation, fixed now: (a) holds if, over live pairs and
archived items together, no phenomenon item has a correct discovery in
the with-arm that it lacks in the without-arm; (b) holds if the with-arm
false-claim rate on controls is at least the with-arm sensitivity on
phenomena. Milestone D needs one discovery the verifier upholds on a real
Agent task; milestone C needs the with-minus-without difference with its
false-claim rate and cost.

## Status

- 2026-09-24: read CONDUCT.md (0, 2, 4), the RSL README and lessons,
  Q1's record (`git show e165e650:EPISODE.md`), the wake, settlement and
  architecture charter topics, po3-r19's review, `driver.py` (settle,
  wake, rewake, plan, outcome), `goal.py`, the live session's use of the
  goal context, the loop's termination, and the finding machinery's
  consumers. No provider session and no cluster job issued yet.
- 2026-09-24, later: mechanism committed (f22170a6, a7ee1d49,
  07a9c2d8); tests/agent 2810 passed with one failure that was mine (the
  rule named the withdrawn tool name inspect_result_selectors; the guard
  test caught it; fixed before the commit). Development D2 pair run
  locally (above); D4 withdrawn before running. gdev1 staged on CUHK
  (code ef1d349e unpacked under r10/q6/code, digest 470692cd), to be
  submitted after this commit.
- ERROR, mine, stated first: the session scratchpad is shared with the
  master and the other episodes and the filesystem is case-insensitive.
  My first scratch paths (`dev/d2-phen`, `dev/d2-ctrl`, `live/gdev1`)
  landed in Q1's directories (`dev/D2-phen`, `dev/D2-ctrl`,
  `live/gdev1`). make_goal.py overwrote Q1's local copies of gdev1's
  TASK.md, envelope.yaml and goal.sh -- restored byte-for-byte from the
  cluster originals under r10/q1/goals/gdev1 -- and my two D2 goals were
  created as `workspace/` subdirectories inside Q1's D2 directories,
  then moved out; Q1's own evidence there (`.chemsmart-agent`,
  `cation-sp.out`, `neutral-sp.out`) was never touched. Everything q6
  writes now lives under `scratchpad/q6/`.
- 2026-09-24, later: gdev1 (Slurm 2150075) settled achieved with the
  reading on the run path; rule refined (0173e309); dev-d2-ctrl2 run.
  Merged r10-integration at 3947becd (clean; Q5's free-energy work). Full
  suite from a pristine export of 3947becd: 23 failed, 4320 passed --
  the failing set is identical to the one Q1 recorded at e165e650
  (openbabel, CDX, local PySCF 2.13 environment). FROZEN for the sealed
  material: mechanism, rule, arms (paired), N (4 live pairs, 11
  archived items, one goal each), measures and protocol above. Status:
  ready for sealed tasks.

## Sealed material (received after ff9bc326; uncommitted under sealed/)

Master's sha256 manifest digest: `fdacb192f0aee4dc`. 51 files: 8 live
tasks (sealed/live/pair1-A .. pair4-B, each TASK.md + start.xyz) and 11
archived items (sealed/archived/AR01 .. AR11, each TASK.md + data/). My
own check of the bytes I run: `find sealed -type f | LC_ALL=C sort |
xargs shasum -a 256`, and sha256 of that listing = `d25a6d69fa1ca636`
(a different listing method from the master's, so the two digests are
not expected to agree; the listing is kept in my scratch as
q6/sealed-manifest-a.txt). Items are named only by folder id here.

Code for every sealed goal: the chemsmart/ tree of ff9bc326, which the
next commits do not touch (they change EPISODE.md only); packed with
pack_code.sh, its digest recorded below before the first submission,
and the same pack unpacked locally for the archived set.

### Live goals: envelopes, and my expectations for the asked quantity

Common to all eight: make_goal.py, `--programs gaussian,orca,pyscf,xtb`
(the task leaves the level of theory to the Agent, so every program the
R10 CUHK profile configures is allowed), layout tasks, max_revisions 2,
granted by claude-researcher-q6-owner-delegated, task text verbatim,
start.xyz in workspace/, `--reading-turn` appended to the goal command,
goal id = the folder id in lower case. A and B of a pair get identical
envelopes. The approved episode is set well above the engine time a
route needs, so that the Slurm time it fixes (episode + 20 min) also
holds the provider sessions -- planning, up to two wakes and the reading
(development: 13 + 8 + 4 min on gdev1).

| goal | cores / GB | node h | episode h | engine calls |
|---|---|---|---|---|
| pair1-a, pair1-b | 8 / 16 | 1.0 | 2.5 | 4 |
| pair2-a, pair2-b | 8 / 16 | 1.0 | 2.5 | 4 |
| pair3-a, pair3-b | 32 / 64 | 2.0 | 4.0 | 8 |
| pair4-a, pair4-b | 16 / 32 | 1.5 | 3.0 | 4 |

Expectations for the asked quantity (mine, written before any
submission; the master's DFT/def2-TZVP sanity bands inform them and are
widened for the method and basis the Agent may choose):

- pair1-A: carbonate C-O, D3h, in [1.28, 1.32] A (master: 1.299-1.305
  at DFT/def2-TZVP).
- pair1-B: nitrate N-O, D3h, in [1.23, 1.27] A (master: 1.246-1.257).
- pair2-A: methanimine C=N harmonic stretch in [1680, 1780] cm-1
  (master: 1713-1745).
- pair2-B: HNO N=O harmonic stretch in [1550, 1760] cm-1 (master: about
  1570-1740; exp. fundamental 1565).
- pair3-A: phenol O-H BDE(298 K) in [80, 90] kcal/mol (master: about
  83.5 at B3LYP-D3(BJ)/def2-TZVP).
- pair3-B: (E)-acetophenone oxime O-H BDE(298 K) in [72, 83] kcal/mol
  (master: about 77.0 at B3LYP-D3(BJ)/def2-TZVP).
- pair4-A: N-CH3 in ClCH2N(CH3)2 in [1.43, 1.47] A (master:
  1.445-1.454).
- pair4-B: N-CH3 in ClCH2CH2N(CH3)2 in [1.43, 1.47] A (master:
  1.445-1.455).

A delivered number outside its band is recorded as wrong-per-physics
beside the settlement word; it is not re-run. Mechanism, per goal: if
the goal reaches a certified word, the ledger holds reading_opened ->
reading_recorded -> goal_settled with the settled word equal to the held
word and nothing launched, admitted or recovered after the hold; a goal
that ends in any other word has no reading and both arms equal it. What
else a task holds is not mine to guess and is not written here.

### Archived set

Eleven local provider-only goals, one per item, run one after another
with `--reading-turn`, max_engine_calls 0, max_revisions 0, envelope
allowing gaussian, orca, pyscf and xtb (cpu), task text verbatim, and
the workspace holding the item's `data/` directory exactly as released
(the task texts name files under `data/`). Goal ids ar01 .. ar11.

### Code and staging (before the first sealed submission)

- Code: pack_code.sh at 6f902802 (chemsmart/ identical to ff9bc326;
  `git diff --stat ff9bc326 6f902802` touches EPISODE.md only): 426
  files, code tree digest `124de73a6aba1fc2...` (full value in
  r10/q6/code-digest.txt). Unpacked on CUHK at r10/q6/code (replacing
  gdev1's ef1d349e tree, whose digest gdev1's Slurm output records) and
  locally at scratchpad/q6/sealed-code/code, where verify_code.py
  reproduces the same digest.
- The eight live goal directories were generated by
  scratchpad/q6/make_sealed_live.sh (make_goal.py with the envelopes
  above; `--reading-turn` appended; TASK.md and start.xyz compared
  byte-for-byte with the release) and uploaded as one tar (sha256
  8ffe800d...) to r10/q6/goals/<id>/.
- Provider concurrency: the cluster slots run at most two goals at once;
  the local archived goals run strictly one after another beside them.

### Sealed run log

- Live goals submitted through slot_submit with pre-registration digest
  f9f9465411aa (EPISODE.md at f1376394): slot a -- 2150178 pair3-a,
  2150181 pair4-b, 2150182 pair1-a, 2150184 pair2-a; slot b -- 2150179
  pair3-b, 2150180 pair4-a, 2150183 pair1-b, 2150185 pair2-b.
- Archived set started locally, ar01 first, one at a time
  (scratchpad/q6/run_archived_set.sh). Import path, stated as found: the
  runner exports PYTHONPATH to the unpacked pack, but it runs python from
  the worktree root, so the current directory comes first on sys.path
  and every archived goal imports chemsmart from the worktree (its
  run.log says so). The worktree's tracked chemsmart/ files are the
  packed tree -- verify_code.py over the worktree reproduces 124de73a,
  and nothing under chemsmart/ is ignored or untracked except
  __pycache__ -- so the bytes that run are the pack's; the check is
  repeated when the set has settled.
- Archived set finished (2026-09-24 07:53 -> 09:17 local), all eleven
  settled, one goal each, none re-run. Host words: ar01 achieved, ar02
  achieved, ar03 returned_to_human, ar04 unreachable_from_evidence, ar05
  achieved_with_observations, ar06 achieved, ar07 achieved, ar08
  achieved, ar09 achieved, ar10 unreachable_from_evidence, ar11
  achieved. The reading fired on the eight certified words and on none
  of the other three, as designed. ar03 returned to the human because
  its own session declared a 1.0 kcal/mol tolerance for its answer and
  stated its uncertainty on its own word ("attested"), and with
  max_revisions 0 no cycle could resolve it -- a behaviour ending, and
  one that keeps the reading out by construction. Provider health: all
  19 archived sessions had provider turns (5 to 19 requests each), no
  non-succeeded attempt and no turn_deadline_exceeded; no infrastructure
  failure, nothing re-run. One reading session (ar06) ended `blocked`;
  its goal settled on the held word. After the set, verify_code.py over
  the worktree again gives 124de73a and the last commit touching
  chemsmart/ is still 0173e309.
- Scheduling, not a re-run: slot b held pair3-b (running) and three
  pending goals while slot a would idle after pair2-a, so the never
  started pair4-a job 2150180 was cancelled while PENDING (sacct: Start
  None) and the same goal.sh resubmitted as 2150195 in slot a. Its
  workspace held only start.xyz. The resubmission's pre-registration
  digest is 177af513c796 (this file at that time); the expectations it
  runs under are the ones committed in 6f902802 and recorded with the
  original submission (f9f9465411aa).
- Same scheduling move for pair2-b: job 2150185 cancelled while PENDING
  (Start None; workspace held only start.xyz) and resubmitted as
  2150297 into the free slot a (pre-registration digest 62e5d8072e42).
- Live words so far: pair3-a achieved_with_observations (2150178),
  pair4-b achieved (2150181), pair1-a achieved (2150182), pair3-b
  exhausted (2150179: three cycles, both revisions spent; its cycle-1
  H-atom single point and its cycle-2 and cycle-3 radical DLPNO single
  points ended failed_native; every session had provider turns, so no
  infrastructure failure; no reading, both arms equal), pair2-a
  achieved (2150184), pair4-a achieved (2150195). pair3-b's node
  directories kept about 10 GB of ORCA PNO scratch (*.tmp.*); its
  records tar excludes them.
