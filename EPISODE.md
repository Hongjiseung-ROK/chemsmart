# R10 episode Q16 -- where goals are lost

Base SHA: 2c1050c74cc31c76d6f51970b9b03c4e37e7cf50 (verified with `git rev-parse HEAD` at start).
Brief: scratchpad/q16/BRIEF.md, sha256 9a94083b35c2a26c4420dab3355bf2dfb9135f5b176de0f859b7b5ad7a1b3ff7.
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

When a CHEMSMART goal ends short of `achieved`, what ended it -- the science,
the model, a program, infrastructure, or the host's own loop? For every
host-caused class: the mechanism, and whether the host can stop losing goals
that way without changing what an approval grants or what a settlement word
means.

## Census (provider-free, 2026-09-24)

Scope read: 95 CUHK goal ledgers (r8, r9, r10 except r10/q6 which is sealed;
the 2026-09-15..21 campaigns under /project/xlzhang/jiseung; r10/m* read) and
188 ax41 ledgers (`~/developer/chemsmart-hetzner-mirror/2026-09-14/campaign`,
claude/ excluded; 4 are byte-identical copies of one goal, so 184 goals).
880 planning-session streams, 10,228 provider turns.

Denominator: 279 goals; 145 settled achieved / achieved_with_observations;
134 ended short (57 CUHK, 77 ax41). First cause of each, read from ledgers,
streams, run streams and job logs (scratch q16/census/classification*.py):

| era | n | HOST | INFRA | MODEL | DELIB. | CAPAB. | SCIENCE | OPER. | PROGRAM | unres. |
|---|---|---|---|---|---|---|---|---|---|---|
| CUHK R8-R10 | 26 | 9 | 1 | 3 | 2 | 5 | 2 | 1 | 3 | 0 |
| CUHK pre-R8 | 31 | 6 | 11 | 2 | 5 | 2 | 2 | 3 | 0 | 0 |
| ax41 | 77 | 27 | 11 | 12 | 6 | 5 | 7 | 1 | 1 | 7 |
| all | 134 | 42 | 23 | 17 | 13 | 12 | 11 | 5 | 4 | 7 |

HOST is the largest single first cause (42/134). 33 of the 42 are in classes
repaired before this episode (cited per goal). Classes the base tree still
produces:

- H1 a partial analysis completion cannot terminate: the loop ends the session
  `planned` bound to the completion receipt; the event store admits `planned`
  only over the latest workflow draft (`planned termination requires the latest
  workflow draft`; before f913f5d7 the same loss read `a required completion
  gate is red`). o2r (R10 Q13), ino3-r11, e4p-cyclohexane-b1, c5-r1: 4 goals.
- H6 (found while replaying o2r) a planning session that raises is projected
  from the previous cycle's streams: the failed cycle's claims and findings
  never reach the workspace record, and the previous run is re-recorded under
  the failed cycle's label. o2r, e4p-cyclohexane-b1.
- H2 an output a delivered claim cites as its uncertainty is counted "computed
  and never rendered as a claim": r10/q3 g2 and r10/q9 g1 settled
  returned_to_human over passed completions; g5-methoxy in part; 8 more goals
  had a revision opened for it.
- H3 a hidden AppleDouble sidecar (`._x.xyz`) admitted as a molecule: the goal
  ends before any session (r10/m1 smoke1).
- H5 a molecule the human placed as SDF is never admitted (r9/xtb g2).
- H4 (Q15's radius, reported) an analysis-only plan resets the execution-wave
  decision, so an approved calculation workflow parks for ever (smoke1b,
  losartan-micropka-r2).

Premise falsified as stated: the brief's instances are not the only host
losses (H2, H5, H6 and H4 are further live classes), and the instances named
had earlier members (H1 x3).

## Replays (provider-free)

- o2r cycle 2, transcript replayed through `GoalDriver.resume` +
  `run_live_agent_session` with the provider transport replaced by the
  archived public transcript (scratch q16/tools/replay_goal.py). On the
  commit that ran it (09450c74): settles returned_to_human, reasons
  `["cycle 2, planning session: planned termination requires the latest
  workflow draft"]`, byte-identical to the ledger; 13/13 turns served, no
  receipt translated. With the H1 repair only: the session terminates
  `planned`, the driver records the session stream, admits the analysis-only
  revision and opens the one re-wake (the model's own criterion
  `external_no_spin_instability` failed, so its claims stand on a result the
  host reads as rejected).

## Status

- step 1 (census) done; step 2 (repairs H1, H6, H2, H3; H5 to decide) in progress.
