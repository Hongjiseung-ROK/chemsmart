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
