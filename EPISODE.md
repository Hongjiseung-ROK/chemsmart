# R10 episode Q19 -- when the Agent's own expectation fails

Base SHA: a7bc02e031a703c24a7b9fcf38d8301211f12ed4 (verified with `git rev-parse HEAD` at start).
Brief: scratchpad/q19/BRIEF.md, sha256 521ce13e577ca48d7fd730a50a3affc1d0cbfacc0e46b15861fb5da78c40729e.
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

When a plan's own acceptance criterion (a `scientific_validation` rule the
Agent planned) fails, is that a finding the goal can deliver -- the failed
receipt and the Agent's recorded reading of it standing in the delivery --
or a delivery the goal has failed? Three host organs answer it today:

- the session's toolchain completion (`_claims_on_a_failed_criterion`)
  names every claim that descends from a failed criterion and never reads a
  decision, so the completion is partial and the goal returns;
- the executor's completion of an approved chain
  (`evaluate_approved_toolchain_completion`) never looks at criteria, so it
  passes the same shape;
- the settlement (`_analysis_delivery`) counts a verdict answered when a
  recorded decision cites that exact receipt, and an answered verdict then
  settles plain `achieved`, which names nothing.

Working hypothesis (to be tested against the archive, not assumed): one
function over the records -- each failed rule verdict and whether a
recorded decision cites a receipt carrying that same verdict -- can serve
all three; an answered failed criterion is a certified delivery that
carries the failure as an observation (`achieved_with_observations`, the
charter's word for "a pre-registered expectation the physics left"), and an
unanswered one is a delivery not made (returned / recovery), named in the
reason.

## Falsifiers (armed before the census)

- The organs never disagree on a real record apart from L1, o2r, ino3-r11:
  then repair those and end.
- Unifying certifies a goal whose failed criterion no recorded decision
  answered: that is the result, reported.
- The answered-verdict rule needs a settlement word to change meaning:
  owner's decision, reported with the evidence.
- The base replay of any archived word differs on its own run commit: the
  harness is wrong and nothing downstream of it is believed.

## Census scope

CUHK: every events.jsonl under /project/xlzhang/jiseung except r10/m*,
r10/q6, r10/q3/{sealed,private}, r10/q17, r10/q18 (running episodes), any
`sealed`/`private`/`oracle*` directory, and code trees. ax41: the mirror's
2026-09-14 and 2026-09-15 campaign trees, claude/ excluded.

## Status

- step 0: brief read, base verified, charter/lessons/CONDUCT read.
- step 1 (census, provider-free): in progress.
