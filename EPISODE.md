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
- D4 (mine): six archived ORCA opt+freq results for [Fe(H2O)4]n+,
  M06-2X/def2-SVP, Fe(II) S=0,1,2 and Fe(III) S=1/2,3/2,5/2
  (tests/data/ORCATests/outputs/fe*.out). Phenomenon task: the adiabatic
  IE of the low-spin pair (Fe(II) singlet -> Fe(III) doublet); unasked:
  neither state is the lowest of its charge at this level (final
  energies: Fe(II) quintet 0.118 Eh below the singlet, Fe(III) sextet
  0.121 Eh below the doublet). Control task: the high-spin pair (quintet
  -> sextet), the lowest of each charge; nothing of that kind to find.

## Status

- 2026-09-24: read CONDUCT.md (0, 2, 4), the RSL README and lessons,
  Q1's record (`git show e165e650:EPISODE.md`), the wake, settlement and
  architecture charter topics, po3-r19's review, `driver.py` (settle,
  wake, rewake, plan, outcome), `goal.py`, the live session's use of the
  goal context, the loop's termination, and the finding machinery's
  consumers. No provider session and no cluster job issued yet.
