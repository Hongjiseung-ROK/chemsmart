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

## Jobs issued

(none yet)

## Status

- 2026-09-25: base verified; brief, governance, lessons, charter topics
  (goal-grain-recovery-wake, producer-edges, settlement-and-terminal-records),
  Q16/Q22/Q26 merges and G1's cycle-4 records read; gate open; census
  pre-registered above.
