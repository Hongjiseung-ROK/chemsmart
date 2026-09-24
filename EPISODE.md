# R10 episode Q22 -- what the host tells the Agent when something went wrong

Base SHA: 111dc55e5d33d6a71ffd4e2a592a9c71851cb44d (verified with `git rev-parse HEAD` as the first action, 2026-09-25).
Brief: scratchpad/q22/BRIEF.md, sha256 97dbac34cf0ed4c78707c37afc0926bcdd2d97a022e9a2ba8d0515fdf5043e09.
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

When the host tells the Agent what went wrong and what it may do next --
a wake (its failure report, deliverables, repair menu and rule text), a
review refusal, a launch refusal, a park reason, a recovery row, and the
node terminal word all of them build on -- is each statement

- true of the records the host holds when it says it;
- specific: naming the node, the receipt, the criterion and the number,
  or the program's own line, that the statement is about;
- actionable: offering a route that exists for that ending?

Where one is not, can the host say what its records already hold, and does
saying it change what the Agent does next?

## Priors from the brief (to verify, not conclusions)

- P1 the wake names failed verdicts by `node/rule` only, no receipt digest
  and no number (driver.py `_deliverables_record`, "unanswered_failed_verdicts");
  L-S2 (CUHK 2153514) re-evaluated its rules in-session to mint receipts it
  could cite.
- P2 `wake.recovery_route` (rules.py) frames every failed verdict as "a
  structure the host judged not to be what the task required" and offers
  only structural repairs.
- P3 the analysis-partial recovery row writes `"verdicts": []` while a
  criterion failed (driver.py `_settle`, last recovery_opened).
- P4 the planning path returns an unanswered verdict to the human while the
  run path opens a recovery naming it.
- P5 the review refusal "every initial workflow node requires a green
  preview" names no node (tool_runtime.py `_latest_bounded_materialization`).
- P6 an undiagnosed native death of an opt before any SCF (Gaussian l301 at
  0.4 s) is typed `failed_nonconverged_geometry`, and its menu offers a
  restart from a reached geometry that does not exist (terminal_states.py
  `_classify_failure`).
- P7 a goal whose last workflow holds no calculation parks at
  `execution_wave_decision_pending` instead of reading its recorded refusal.
- P8 the settlement reason does not name the completion's findings.

## Falsifiers (armed before the census)

- F1 the census finds the defects are only P1-P8: repair those and end.
- F2 a message classified false/unspecific here reproduces differently on
  its own run commit: the harness is wrong and nothing downstream of it is
  believed.
- F3 the Agent recovered equally well whatever the message said (in the
  archive: the same recovery point met under a specific and an unspecific
  message, with the same next act): that is the result, reported.
- F4 a repair that makes a message specific changes what a settlement word
  means: it is a `shared:` commit for the owner, not mine to make silently.

## Oracle

Host records only: ledgers, run streams, session streams, public
transcripts, receipts and native output; every replay on the commit that
produced the record, base reproduced byte-for-byte before a repaired word
is believed.

## Status

- step 0: brief read, base verified, CONDUCT/RSL/charter topics read,
  priors located in the base tree (all eight visible as described).
- step 1 (census, provider-free): starting.
