# R10 episode q11 -- does what one approval admits reach the programs?

Base SHA: 1dbc9984fc7585c8758b62bffc67d6624d245603 (verified with
`git rev-parse HEAD` as the first action, 2026-09-24).

## The question (as currently understood)

When one approval admits a multi-stage route -- producer and consumer,
with the artifacts that pass between them -- does execution match the
approval? Four checks: (1) every admitted input reaches the program in
the form the program reads; (2) every admitted consumer runs when its
producer completes; (3) a later step cannot erase an earlier node's
evidence; (4) the Agent is never told a route exists that the executor
cannot walk.

## Premise replay -- provider-free, host records only (DONE, base tree)

Archive: 1,810 run streams (the CUHK download Q4 made, excluding r10;
the Hetzner mirror; experiments-public; the master's smoke1b copy).
Scripts under the session scratchpad `q11/` (census*.py). 432 frozen
approvals carry at least one launch reservation.

(1) Admitted inputs on launched consumers. 176 structure roles
(`filename`) reached argv. 6 of 6 admitted Hessian roles
(`validated_final_orca_ts_hessian` / `hess_filename`) did NOT: Hetzner
h1 irc_a, h1b irc-a/irc-b, qualification irc-agent-path irc-fwd/irc-rev,
irc-agent-path-2 orca-irc-both; `auxiliary_input_bindings: []` on every
one. Q4 counted 7; I count 6 launched (the 7th binding, r8 goal-ts, was
bound and never launched -- see (2)).

(2) Admitted consumers under the approval that admitted them, per bound
data edge (the producer validated and the host bound the edge):

| window | consumer ran | consumer never ran |
|---|---|---|
| Hetzner 2026-08-14 .. 09-13 | 281 | 2 |
| CUHK 2026-09-15 .. 09-16 | 11 | 10 |
| CUHK 2026-09-17 .. 09-24 | 0 | 92 |

Since the wave barrier (0f19ce36 "a wave runs its own members and
stops", 2026-09-16; 6fa000c9 "require an explicit wave boundary",
09-17) no admitted consumer in any archived stream has run under the
approval that admitted it. `validate_wave` calls a consumer and its
producer in one wave `depends_on` (not dispatchable), the executor's
cohort frontier runs wave members only, and every goal cycle plans and
approves a new workflow -- so an in-approval producer edge is displayed,
approved, bound, and never consumed. Of 198 admitted consumers that
never launched, 95 had a producer that did not validate (correct) and
103 had a validated producer and a bound edge.

Premise NOT falsified. It is broader than the brief's instances: (2)
is not a few goals, it is every goal since 2026-09-17.

## Plan (checks -> layers), each repair shown red on the base first

- C2 the wave contract: a wave may name a consumer with its producer
  when the one owner (`producer_edge_selection_rule`) admits every edge
  into it; the executor runs it after its producer validates and hands
  on. The Agent still chooses: producer alone (read first) or the chain.
- C1 the Hessian edge: review argv, executor synthesis, the ORCA writer
  (a bound Hessian is the Hessian the job reads), runner staging.
- C3 a handoff refused after a validated run: the producer's state
  transitions are recorded before any handoff, and a refused handoff is
  the consumer's word, not the producer's.
- C4 guides: `about_relaxed_scans` and the Gaussian scan-point binding.
- Then the settings-section miss (opt -> modred) and the ORCA IRC
  endpoint edge if budget remains.

## Falsifiers (written before any change)

- C2 is falsified if the replayed archive shows an admitted consumer
  whose producer validated and whose edge was bound running under its
  approval after 2026-09-17 (it does not: 0 of 92).
- C1 is falsified if an executed ORCA IRC with a bound TS Hessian prints
  "Compute numerically" for its initial displacement Hessian on the
  repaired tree, or if ORCA refuses `InitHess Read` with the staged file.
- C3 is falsified if, on the repaired tree, a handoff refusal after a
  validated producer still records the producer as launch-refused.

## Jobs issued

(none yet)

## Status

- 2026-09-24: premise replay done on the base tree; plan written.
