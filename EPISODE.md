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

## Jobs issued

(none yet)

## Status

- 2026-09-25: base verified; brief, governance, lessons, charter topics
  (goal-grain-recovery-wake, producer-edges, settlement-and-terminal-records),
  Q16/Q22/Q26 merges and G1's cycle-4 records read; gate open; census
  pre-registered above.
