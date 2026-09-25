# R10 episode q32 -- a decision the Agent writes reaches the host, and work already paid for is not thrown away

Base SHA: 3f3331c0ff340941be349def7e996e6656c3684b (verified with
`git rev-parse HEAD` as the first action, 2026-09-25). Model:
claude-opus-5-5[1m]. Episode id `q32`. Brief sha256 prefix 395d1565b2f869d1.

## The question (as currently understood)

When a goal session ends with a decision stated in prose instead of the
typed act its phase expects (a wave selection, a recorded decision, a
refusal), and when an engine run ends early with valid partial results (the
converged points of a relaxed scan), does the goal lose work the Agent and
the cluster already paid for? If so: the host returns the missing act's
absence to the session once, naming the typed tool and never inferring the
decision from the words; and partial results carry forward as exactly what
they are (constrained minima, never a saddle).

## What the base tree does (read before any census, 2026-09-25)

- `loop.py` (~l.612): a turn with no tool call under a goal gets, once per
  session, `host.termination_notice()`, then one further turn; a second
  no-tool turn ends the session. The notice is either
  `wake.execution_wave_decision_pending` (an undecided wave with ready
  nodes; `tool_runtime._wave_decision_pending`) or `wake.termination_notice`
  (declared observables undelivered while budget remains).
- The wave notice's text (rules.py `wake.execution_wave_decision_pending`)
  asks the session to "Choose the complete outcomes you want to observe
  together ... or explicitly continue reasoning" and names neither typed act
  (`select_execution_wave`, `continue_execution_reasoning`). The
  termination notice names no tool either.
- `driver._execute` parks `execution_wave_decision_pending` when the
  session's decision is not `selected`; a resumed park stays parked.
- G1 of R10 Q20 (CUHK 2153658), cycle-4 transcript read: message 116 is a
  prose close ("The plan is finalised, previewed green, approved for
  execution"), 117 the host's wave notice (ready: ts-opt-freq), 118 the
  decision in prose ("Wave selection: `[ts-opt-freq, ts-irc,
  ts-sp-dlpno]`"), finish_reason stop; the session terminated
  `waiting_for_approval`, the revision was admitted, and the driver parked
  with 23 engine calls and 13,323 s left.
- The repair menu (`driver.REPAIR_MENU`) tells a `timeout_terminated` node
  "bind_reached_geometry carries it forward" and a
  `failed_nonconverged_scan_step` node "Where the scan itself did not
  complete, bind_reached_geometry carries the structure the run reached";
  for an ORCA scan the reader refuses exactly that ("orca declares no
  geometry selector in the 'as_reached' structural state for jobtype
  'scan'"). ORCA's `scan_profile` reads only the final "Calculated Surface"
  table, which a killed scan never prints, so `scan_point_records` is empty
  and `bind_scan_point_geometry` has no point to offer, although ORCA wrote
  `<stem>.NNN.xyz` for every converged point (G1 cycle-1 scan directory
  holds .001-.012 at least).

## Census -- PRE-REGISTRATION (written before reading any archive beyond G1)

Population. Every goal ledger under `/project/xlzhang/jiseung/` on CUHK
(R8, R9, R10 and the dated campaign directories beside them), excluding
the deployed checkout, `r10/m*`, `r10/master`, the sealed and private
directories of q3, q17 and q29; plus the 195 goal ledgers in the ax41
mirror (`~/developer/chemsmart-hetzner-mirror/2026-09-14/`). Goals are
de-duplicated by (goal_id, goal_sha256); copies are counted once. Every
directory read is named in the result.

Unit P: a goal planning session (a stream a ledger records with
`session_stream_recorded`). Denominator: sessions with at least one
`provider_turn_observed`; a session with none, or ending on
`turn_deadline_exceeded`, is infrastructure and reported apart.

P-mechanical (host records only): the session's last provider turn has
`tool_calls_present: false` (it ended on text) AND an act was pending when
it ended, by the host's own records:
- W (wave): the stream holds `execution_wave_decision_pending` with no
  later successful `select_execution_wave` or
  `continue_execution_reasoning`, or the ledger parks that cycle
  `execution_wave_decision_pending`;
- O (observables): the stream holds `termination_notice_delivered`, or
  the goal settled after that cycle with declared observables undelivered
  and no verified refusal.

P-text (read by me from the public transcript, final assistant message
and, where a notice fired, the one before it; never the hidden
reasoning): the text states the content the pending act's required
arguments carry --
- W: at least one node id presented as chosen to run now (or an explicit
  deferral of dispatch), i.e. what `select_execution_wave(workflow_id,
  node_ids)` or `continue_execution_reasoning(workflow_id)` would record;
- O-refusal: a declared observable (id or meaning) stated as not
  deliverable with a reason, with no `record_scientific_decision` in the
  session carrying it in `unreachable_observable_ids`;
- O-decision: a stated choice (a route taken or rejected, or standing by a
  result against a failed criterion) presented as this cycle's decision,
  with no `record_scientific_decision` succeeding after it became due.
Otherwise "no act stated" (a summary, a question, a plan description).

Unit T: an executed engine node whose terminal state is
`timeout_terminated`, `failed_nonconverged_scan_step`,
`failed_nonconverged_geometry`, `memory_limit_terminated` or `failed_native`
and whose native output holds converged partial results: for a scan, at
least one converged scan point (ORCA: a `RELAXED SURFACE SCAN STEP` block
that reaches `THE OPTIMIZATION HAS CONVERGED`; Gaussian: `Optimization
completed` inside a scan); for an optimisation, a reached geometry. T is
"thrown away" when no later act of the goal carried any of it forward (no
successful `bind_scan_point_geometry` or `bind_reached_geometry` on that
result), and the census records whether the goal tried and was refused.

Falsifier of the premise (the brief's): P (all subclasses, text-stated)
two or fewer beyond G1 AND T two or fewer beyond G1 -> narrow to G1's
cases, say so, hand back. A class that recurs (three or more beyond G1)
is repaired; one that does not is left with its count.

## Census -- READ (2026-09-25; provider-free, host records only)

Directories read. CUHK (pulled as one archive, `r10/q32/pull/cuhk-census.tgz`):
the 87 roots in `census-roots.txt` -- every campaign directory under
`/project/xlzhang/jiseung/` except the deployed checkout, `miniforge3`,
`r10/m*`, `r10/master` and the sealed and private directories of q3, q17
and q29 (r8/{gaussian,integration,orca,pyscf,xtb}, r9/{gaussian,master,
orca,pyscf,xtb}, r10/q1-q31 bar q17's and q29's sealed parts (q23 holds no
goal), agent-smoke, agent-surface-20260921, agent-surface-eval-20260921,
level-heartbeat, losartan-micropka-r2, po3-atorvastatin-pka-concurrency,
pyscf-{agent-knowledge,irc,ts-irc}-*, round-a-*, sm3-*, wave-heartbeat,
xtb-ir-acetamide-pyscf-stability-r2..r10). ax41: the mirror's
`2026-09-14/campaign/ax41-refine-100` and `2026-09-14/research`.
Denominator: 148 + 195 ledgers; 2 CUHK dry-run copies outside
`.chemsmart-agent` not walked; 333 unique goals (143 CUHK, 190 ax41) by
(goal_id, goal_sha256); 602 goal sessions, 18 with zero provider turns
(infrastructure), 584 counted; 573 of them ended on a no-tool turn.

P (a typed act written as prose):
- The wave notice fired in 65 sessions. With `select_execution_wave` in the
  exposure plan in force when it fired: 60, answered by a typed act in 59
  and in prose in 1 -- G1 (R10 Q20, cycle 4). With the tool not in view: 5,
  all prose, all parked (CUHK R8 2026-09-20: r8/gaussian g1 and g2,
  r8/orca goal-irc, r8/xtb goal and goal3) -- the goals that earned 3dc3069c
  ("a workflow that may run is offered the decision that runs it"). Every
  one of the 8 ledger parks is accounted for: G1, those 5, R10 Q15 g2 (no
  ready node; repaired by R10 Q22) and losartan-micropka-r2 cycle 4 (a
  selection a later plan replaced; `_undecided_boundary_reason`).
- Refusal or decision in prose: 0. The termination notice fired in 159
  sessions; the 48 that had recorded no wave were read in full, and the 38
  refusal-language hits on returned or unsettled goals across all 573
  text endings were read: every refusal was recorded by
  `record_scientific_decision` (some the host did not verify), or the
  session declined both a claim and a refusal because the observable was
  reachable and not yet computed, or the goal predates a host that read
  refusals (ax41, 2026-09-05).
- P beyond G1 with the typed act in view: 0 (the brief's prior of a class
  is not borne out: one session in 60).

T (converged partial results thrown away), read from the native outputs:
- G1 (R10 Q20) scan-c1c6: timeout after 10815 s, 14 steps converged of 22
  planned (step 15 killed); scan-c1c6-r2: timeout after 10808 s, 10
  converged of 13 (step 11 killed); both refused by `bind_reached_geometry`
  ("orca declares no geometry selector in the 'as_reached' structural state
  for jobtype 'scan'"). The brief's "15 of 22 and 11 of 13 converged"
  counts steps started; converged points are 14 and 10 (24, not 26).
  Cycle 2's last converged point is C1...C6 = 2.325 A at -233.464022 Eh
  (RIJCOSX), 0.07 A from O1e's saddle (2.253 A, -233.462825 Eh): the
  thrown-away surface held the transition-state seed cycle 3 went looking
  for, and cycle 3's replacement scan from the extended minimum died at its
  first step.
- R10 Q4 g1 (binaphthyl racemisation) orca-scan: timeout after 18010 s, 17
  converged of 18 started (0-160 deg); the decision recorded "the cycle-1
  scan timed out and its result resolves no surface quantities".
- ax41 e4p-cyclohexane-b2 scan-chair: timeout, 11 converged of 13; ax41
  e2-cyclohexane-c scan-ring-dihedral: timeout, 10 converged; neither
  carried forward, both goals returned to the human.
- Marginal: R10 Q24 g2r and Q27 g1 (1 converged point each, then a native
  failure); not counted. Not partial: G1 scan-bracket-r3 and R9 g5
  (step 1 never converged), R10 Q15 g2 (died in l301).
- Also found: ORCA writes `<stem>.NNN.xyz` for a step that did NOT converge
  (G1 scan-bracket-r3 holds .001.xyz with step 1 unconverged), so a point
  file is not evidence of convergence; `ORCAOutput.scan_profile` and
  `scan_point_records` read only the final "Calculated Surface" table, which
  a killed scan never prints, while both docstrings promise a truncated
  surface as partial evidence; and the repair menu tells both
  `timeout_terminated` and `failed_nonconverged_scan_step` that
  `bind_reached_geometry` carries a scan's reached structure, which the
  reader refuses for every ORCA scan.
- T beyond G1: 3 goals, each with at least 10 converged constrained minima
  lost. T recurs; P does not.

Decision (by the pre-registered rule): the partial-scan class is repaired;
the prose-act class narrows to G1's case.

## Oracles for any repair (fixed before the repair is written)

- R-replay (provider-free): G1's cycle-4 planning session replayed through
  the host on c0896a07 (the commit G1 ran) must reproduce the archived
  notice (`content_sha256` 9d6af724...) and the archived park (settlement
  `execution_wave_decision_pending`, reason "the Agent made no
  execution-boundary decision on workflow hexatriene-rclosure-r4"); only
  then is the same replay on the repaired tree believed. HOME fenced.
- R-control (provider-free): every archived session that called
  `select_execution_wave` or `continue_execution_reasoning` before its end
  is replayed or re-read through the repaired predicate; the return must
  fire in none of them.
- R-matched (behaviour, deepseek-v4-flash-0731, engine-free): G1's cycle-4
  prefix through message 116 replayed through each tree's host, then real
  provider turns (at most 3 per sample) answering that tree's notice; N = 12
  samples per arm. Outcome per sample: a typed wave act
  (`select_execution_wave` or `continue_execution_reasoning` succeeds)
  before the session ends, or not. Prediction: base arm at most 4 of 12,
  repaired arm at least 9 of 12. FALSIFIED if the repaired arm is not at
  least 5 samples above the base arm. A sample with zero provider turns or a
  `turn_deadline_exceeded` is infrastructure, reported, never counted, never
  re-rolled.

## Repairs committed (base merged with r10-integration df78d69d as 85619913)

- af4721ca shared: ORCA `scan_points_converged` reads each converged step
  (held value, final-evaluation energy and structure, point file when
  present); the table readers keep their meaning. Checked over every
  archived ORCA scan (62 unique outputs, CUHK + ax41): 36 of 36 completed
  scans' steps equal ORCA's own table (5e-6 in the held value, 5e-8 Eh);
  25 truncated scans hold 176 converged points; every converged step's file
  equals the printed coordinates. Witness red on the base (AttributeError).
- 451f5435 shared: `bind_scan_point_geometry` carries a converged step of a
  scan that stopped early and says what it is (constrained minimum, not a
  saddle; source normal termination, recorded ending, steps started,
  planned, converged); refuses an unconverged step naming the steps that
  converged; `inspect_run` lists the partial surface; REPAIR_MENU
  (timeout_terminated, failed_nonconverged_scan_step, failed_native) names
  the routes that serve a scan; rule recovery.scan_points_that_converged on
  the tool. Witness red on the base ("records no scan surface").
- 1b388d75 wake: the pending-decision notice names select_execution_wave and
  continue_execution_reasoning (rule wake.execution_decision_is_a_call) and
  says no text is read as a decision; the park reason adds, from the
  session's own stream, that it was told once and ended on text. Witness red
  on the base (no call named).
- fccd4d89 shared: the `bind_reached_geometry` refusal G1's cycle 3 met
  twice now names the route a scan has (inspect_run,
  bind_scan_point_geometry). Witness red on 1b388d75.
- tests/agent on a pristine export of 1b388d75: 3289 passed, 20 skipped, 2
  xfailed, exit 0.

## R-control -- READ (provider-free, 602 archived goal sessions)

The park-reason predicate (told once, no decision call after, last turn
text) fires on exactly 6 sessions -- G1 cycle 4 and the 5 R8 sessions --
and on none of the 59 that answered the notice with the call. The notice's
own predicate is unchanged (`_wave_decision_pending`), so a session that
called the tool is never told.

## R-replay -- a local attempt failed to be faithful (2026-09-25)

Replaying G1 cycle 4 on c0896a07 on the Mac diverged before the notice:
the replayed session made 0 previews and ended `planned`, and cycle 3's
derived outcome lost its terminal states, because the run evidence names
`/lustre/...` paths and the previews need CUHK's program environment. A
replay that does not reproduce the archive is not evidence; the replay
runs on CUHK, in place, read-only (replay 1 below).

## Replay 1 -- PRE-REGISTRATION (written before submission)

A slot job (4 cores, 24 GB, 2 h; provider-free: archived transcripts; no
engine call -- only ORCA's input-check probe and the CLI's `--fake`
previews) runs `tools/replay_cycle.py` (R10 Q16's harness extended: the
host's own review resolution runs; HOME fenced before import) over G1's
archive in place, writing only under `r10/q32/replay/`:
- r2-c4: cycle 4 on the tree G1 ran (`r10/q20/r2/code`, c0896a07).
  Expected: the replayed notice's text equals the archived one and its
  event `content_sha256` is 9d6af724...; the ledger's
  `execution_wave_decision_pending` row equals the archived one (ready
  ts-opt-freq, reason "the Agent made no execution-boundary decision on
  workflow hexatriene-rclosure-r4"). FALSIFIER of the replay: any
  difference -- then no q32 replay result is believed.
- q32-c4: cycle 4 on fccd4d89 with the same archived turns. Expected: the
  notice names both calls and the workflow; the park row equal except its
  reason, which gains "; the session was told once that the decision was
  pending and ended on text, calling neither select_execution_wave nor
  continue_execution_reasoning, and the host reads no decision from text".
- r2-c3 / q32-c3: cycle 3 with the archived assistant turn at transcript
  message 21 (the two refused `bind_reached_geometry` calls) replaced by
  scripted calls -- host reachability in the real woken context, never
  model behaviour: bind_reached_geometry, inspect_run and
  bind_scan_point_geometry(point 10) on `orca-result-99fd69768f6248ea` (the
  cycle-2 scan), then the binding again once its schema is loaded. Expected
  on r2: the old refusal, no partial surface, "records no scan surface".
  Expected on q32: the refusal names the scan route; inspect_run lists
  steps 1-10 (step 10 at 2.325 A, -233.464021633484 Eh); point 10 binds
  with `source_normal_termination` false and
  `source_recorded_terminal_state` "timeout_terminated" read from the
  workspace's own run evidence; the woken session's repair_menu for
  timeout_terminated names bind_scan_point_geometry.
- G1's archived ledger and workspace record hash identically before and
  after the job.

## Replay 1 -- READ (CUHK Slurm 2154046, chpc-cn072, 3 min; code fccd4d89
verified on the node, digest b9392764...; G1's archive hashed identically
before and after)

- r2-c4 (G1's tree): all 42 archived turns served, every tool reply aligned;
  the replayed notice is byte-identical to the archived one, its event
  `content_sha256` 9d6af724... equal, budgets and decision record equal
  (ready ts-opt-freq, undecided); the session ended `waiting_for_approval`
  with the archived reason; `input_checks_probed` equal. The notice is
  reproduced. The park was not reached: the harness had left the archived
  cycle-4 approval store in place and the host refused to append a second
  session to it ("event store contains another session") -- a harness
  defect, not the host's. Cycle 3's recovery row also differed from the
  archive (no terminal states), because the stub executor said "" where the
  real one had said "completed".
- q32-c4 (fccd4d89): all 42 turns served, all replies aligned; the notice
  names select_execution_wave and continue_execution_reasoning (digest
  11b751da...), same session ending; the woken session's repair menu is the
  new one. Park: the same harness defect.
- r2-c3 (G1's tree, scripted at message 21): bind_reached_geometry refused
  with the archived message; inspect_run shows no partial surface;
  bind_scan_point_geometry refused "records no scan surface"; the wake's
  timeout_terminated route names bind_reached_geometry.
- q32-c3 (fccd4d89, scripted): the refusal names inspect_run and
  bind_scan_point_geometry; inspect_run lists steps 1-10, 4.5 -> 2.325 A,
  step 10 at -233.464021633484 Eh; point 10 binds with
  `source_normal_termination` false and `source_recorded_terminal_state`
  "timeout_terminated" read from the workspace's own run evidence, steps
  started 11, planned 13; the wake's timeout_terminated route names
  inspect_run and bind_scan_point_geometry.

## Replay 2 -- PRE-REGISTRATION (written before submission)

The same four replays with two harness corrections only: the approval
stores of the replayed cycle and later are cut with the ledger, and the stub
executor returns the analysis status the archived recovery row recorded.
Expectations are replay 1's, plus: r2-c4 writes the archived park row
(`execution_wave_decision_pending`, reason "the Agent made no
execution-boundary decision on workflow hexatriene-rclosure-r4") and the
archived `revision_admitted` checks; q32-c4 writes the same row with the
reason extended as pre-registered for replay 1; cycle 3's recovery row
equals the archived one on r2.

## Matched turns -- PRE-REGISTRATION (amends R-matched before any real turn)

Instrument: `tools/matched_turns.py` on CUHK (the replay above, a hybrid
transport serving the archived prefix, then real deepseek-v4-flash-0731
turns through alibaba-token-plan with the session's own lease; HOME fenced;
the driver stopped after the session). N amended from 12 to 6 per arm for
provider cost (each turn carries 180k-310k input tokens); probe turns at
most 3 per sample. A sample with zero real turns, a transport failure or a
`turn_deadline_exceeded` is infrastructure: reported, never counted, never
re-rolled.
- P (the notice): cycle 4, prefix through transcript message 116 (the
  session's first text close), base arm on G1's tree (the notice G1 saw),
  repaired arm on q32's tree. Outcome: select_execution_wave or
  continue_execution_reasoning succeeds after the notice. Prediction: base
  at most 2 of 6, repaired at least 5 of 6. FALSIFIED if repaired minus
  base is below 3.
- T (the route a stopped scan has): cycle 3, prefix through transcript
  message 21 (the two bind_reached_geometry calls on the timed-out scans,
  replayed verbatim), each arm's host answering them. Outcome: within the
  probe turns the session calls inspect_run or bind_scan_point_geometry on
  either scan result. Prediction: base at most 1 of 6, repaired at least 4
  of 6. FALSIFIED if repaired minus base is below 3. Also read, not scored:
  on the repaired arm, which point is bound (the ridge-side 2.325 A point
  of the cycle-2 scan, or another) and what the session says it is.

## Replay 2 -- READ (CUHK Slurm 2154049; G1's archive unchanged)

- q32-c4: all 42 turns served and aligned; the park row is written with the
  reason exactly as pre-registered ("the Agent made no execution-boundary
  decision on workflow hexatriene-rclosure-r4; the session was told once
  that the decision was pending and ended on text, calling neither
  select_execution_wave nor continue_execution_reasoning, and the host reads
  no decision from text"), ready ts-opt-freq, decision record equal to the
  archive's, `revision_admitted` checks equal.
- r2-c4: not faithful -- the stub executor still said "completed" for cycle
  3's run (the real one had failed), and on G1's tree that settled the goal
  `achieved` beside "no completion gate certified this delivery" before any
  cycle-4 turn. Found by this replay, it is the stub's word, not the
  archive's: the harness now returns the archived run's own status
  (`workflow_state` of its run_recorded row) with the archived analysis
  status. The q32-c4 recovery row likewise shows the stub's status.

## Replay 3 -- PRE-REGISTRATION (written before submission)

G1's cycle 4 on both trees with the stub executor returning the archived
run's status ("failed") and analysis status ("completed"). Expected on
r2: cycle 3's recovery row equals the archived one (terminal states
scan-bracket-r3 failed_nonconverged_scan_step), the notice digest
9d6af724..., and the archived park row. On q32: the same recovery row, the
notice naming both calls, and the park row with the extended reason. Then
one stub sample per matched arm (no provider call): each must end its
session with a terminal state, record its probe turns, and raise no error;
otherwise no real matched turn is taken.

## Replay 3 -- READ (CUHK Slurm 2154056, 4.5 min; G1's archive unchanged)

- r2-c4 (G1's tree, c0896a07): R-replay HOLDS. Cycle 3's recovery row
  equals the archived one field for field (analysis_status completed,
  terminal_states scan-bracket-r3 failed_nonconverged_scan_step); all 42
  turns served, all replies aligned; the notice is byte-identical
  (`content_sha256` 9d6af724...); the park row equals the archived one
  (reason "the Agent made no execution-boundary decision on workflow
  hexatriene-rclosure-r4", decision 63c26831..., ready ts-opt-freq) but
  for the approval and review paths, which name the replay's copy; the
  settlement reasons equal G1's.
- q32-c4 (fccd4d89): the same session, the notice naming both calls (digest
  11b751da...), and the park row with the reason extended exactly as
  pre-registered. Its recovery row carries the fields later integration
  added (`uncertified`, `undelivered_declared_observable_ids`) beside the
  same terminal states -- the host's evolution since c0896a07, not q32's.
- Stub pass of the matched instrument (no provider call): each of the four
  arms ended its session (P arms `waiting_for_approval` after the notice,
  T arms `blocked`), recorded its probe turn, raised nothing. The P probe is
  the turn that answers the notice (41 archived turns, the 41st being the
  text close that triggers it).

## Matched turns 1 -- READ (CUHK Slurm 2154062, COMPLETED 14:37 HKT after
1 h 23 min; code fccd4d89 verified on the node; G1's archive unchanged;
deepseek-v4-flash-0731 via alibaba-token-plan; 24 samples, all with real
turns, no transport error, no deadline: no infrastructure sample)

P (cycle 4, the turn that answers the notice):
- base (G1's tree, the notice G1 saw): 6 of 6 recorded
  select_execution_wave, each with [ts-opt-freq, ts-irc, ts-sp-dlpno] -- the
  wave G1 wrote as text. G1's prose answer did not recur in 6 draws of its
  own context.
- repaired: 6 of 6.
- Prediction (base at most 2, repaired at least 5; falsified if the
  difference is below 3): FALSIFIED, difference 0. For this model in this
  context the notice naming its calls changes nothing measurable; with the
  census (59 of 60) G1's prose is a rare draw, not a disposition.

T (cycle 3, three real turns after the two refused bind_reached_geometry
calls on the timed-out scans, each answered by its tree's host):
- base: 0 of 6 read or bound a scan point. Routes taken: a new bracket
  scan from the extended minimum (the archived cycle's own choice, whose
  first step never converged), or a transition-state seed made by
  stretching the product's ring bond (refused as a rigid ring edit, or
  because the atoms named were not bonded).
- repaired: 2 of 6 (samples 1 and 3) called inspect_run on the cycle-2
  scan, read steps 1-10 and bound point 10 (C1...C6 2.325 A,
  -233.464021633484 Eh) as the seed on the rising flank; sample 3 asked for
  step 11 first and was refused with "the steps that converged are 1-10".
  Of the other 4: sample 0 read the new route in the refusal and chose a
  def2-SVP rescan; samples 2 and 5 cited the scans' failed-result record
  ("inspectable evidence only; not admissible for quantity extraction or
  geometry handoff", live_session.py:408-411) as closing the route; sample 4
  quoted "a relaxed scan's structures are its points" and still went to the
  ring-bond stretch.
- Prediction (base at most 1, repaired at least 4; falsified if the
  difference is below 3): FALSIFIED, 2 - 0 = 2. The direction is the
  predicted one; 6 per arm cannot separate it from chance (Fisher, two-sided,
  p about 0.45).
- Model errors in the transcripts, not host words: repaired sample 1 said
  step 11 "failed to converge" (the clock killed it: timeout_terminated);
  repaired sample 3 called the thermally allowed 6-pi closure conrotatory
  (C2) and planned to break the seed's mirror symmetry -- a thermal 6-pi
  electrocyclisation is disrotatory, and Q20's O1e saddle is the
  mirror-symmetric one (torsions +32.9/-32.9 deg).

Milestone: C not earned (both behavioural predictions falsified as
pre-registered). A claimed for the partial scan: a relaxed scan that stops
early keeps its converged steps as constrained minima that are read,
listed, bound and routed, shown by witnesses red on the base, replays in
G1's own context, and the model's own use of the route in 2 of 6 real
samples where the base tree offered no route.

## Jobs issued

- 2026-09-25: replay 1, CUHK Slurm 2154046 (r10-q32-a), 4 cores, 2 h
  limit, pre-registration b5cd1a1bebf6, code fccd4d89 (digest b9392764...).
- 2026-09-25: replay 2, CUHK Slurm 2154049 (r10-q32-a), pre-registration
  fb0160375028, code fccd4d89.
- 2026-09-25: replay 3, CUHK Slurm 2154056 (r10-q32-a), pre-registration
  68959aed2d54, code fccd4d89.
- 2026-09-25: matched turns 1, CUHK Slurm 2154062 (r10-q32-a), 4 cores,
  6 h limit, pre-registration 4e71463ce825, code fccd4d89; tools
  matched_turns.py and replay_cycle.py in r10/q32/tools. COMPLETED
  14:37:27 HKT (1:22:32).

## Status

- 2026-09-25: base verified; brief, governance, lessons, charter topics
  (goal-grain-recovery-wake, producer-edges, settlement-and-terminal-records),
  Q16/Q22/Q26 merges and G1's cycle-4 records read; gate open; census
  pre-registered above.
- 2026-09-25: census read; four repairs committed (af4721ca, 451f5435,
  1b388d75, fccd4d89) each with a witness red on the tree before it;
  R-control read; replays 1-3 read (R-replay holds on G1's own tree).
  Gates on a pristine export of db5f5a72 (chemsmart/ = fccd4d89, merged with
  r10-integration df78d69d, which has not moved since): full suite 23
  failed = the round baseline (test_structures 19,
  test_pyscf_dispersion_conformance 2, test_PyscfSettings 1,
  test_aggregation 1), 4845 passed; tests/agent none failed; ruff, black
  and isort clean on every touched file. The exports are deleted.
- 2026-09-25 13:15 HKT: WAITING ON JOB 2154062 (matched turns 1; stub pass
  clean, real samples running, interleaved; ~1.5 h). On resume read, in
  order: (1) `r10/q32/matched1/samples.jsonl` (fetch it; read with
  tools/read_samples.py): per arm, infrastructure samples first (zero real
  turns, transport error, deadline), then the P outcome (a wave call
  succeeding after the notice) and the T outcome (inspect_run or
  bind_scan_point_geometry on a scan result within three real turns),
  against the pre-registered predictions and falsifiers; (2) on the T
  repaired arm, which point was bound and what the session said it was;
  (3) G1's archive hashes before and after. Then merge r10-integration if it
  moved, rerun the gates if anything merged, and write the final report.
