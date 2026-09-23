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

## Status

- 2026-09-24: read CONDUCT.md (0, 2, 4), the RSL README and lessons,
  Q1's record (`git show e165e650:EPISODE.md`), the wake, settlement and
  architecture charter topics, po3-r19's review, `driver.py` (settle,
  wake, rewake, plan, outcome), `goal.py`, the live session's use of the
  goal context, the loop's termination, and the finding machinery's
  consumers. No provider session and no cluster job issued yet.
