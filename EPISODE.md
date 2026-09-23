# EPISODE q1 -- what the Agent may claim

Base SHA: `292b9bf3e7d14a3da112983d6152aecbf68059e3` (verified as the
worktree HEAD before any other action, 2026-09-24).

Agent under study: `deepseek-v4-flash-0731` via `alibaba-token-plan`.
Every behavioural statement below is about that model.

## The question, as currently understood

1. Standing. Can a conclusion the Agent reaches -- word-valued ("the
   reference is stable"), relational ("this saddle connects A and B",
   "these files are transposed"), or about something no task asked for --
   be recorded in a typed form that the completion gate, the settlement
   and the delivered report carry, bound to the receipts it rests on,
   while every value in it is still rendered by the host from a receipt
   and the Agent's own inference is marked as inference?
2. Discovery. Given that standing, does the Agent notice and claim a
   non-trivial phenomenon it was not asked about, and how often does it
   claim one where there is none (false-claim rate on matched controls)?

## Falsifiers of the premise (from the brief; each alone is enough)

- (a) A census of archived goal ledgers finds no settlement lost to a
  categorical deliverable.
- (b) Every categorical conclusion on record had a numeric proxy the
  Agent could have delivered -- then the fix is serving proxies.
- (c) With standing available, the Agent on sealed tasks still never
  notices, or cannot tell phenomena from controls -- then the bottleneck
  is the model or its knowledge.

## Census of archived ledgers (provider-free, 2026-09-24)

79 goal ledgers: 76 on CUHK under /project/xlzhang/jiseung (r8, r9 and
the 2026-09-19..22 campaigns; r10 excluded) and 3 in experiments-public.
68 settled: achieved 10, achieved_with_observations 18, exhausted 6,
returned_to_human 26, unreachable_from_evidence 8.

- (a) is NOT met. Two settlements were lost to a word-valued deliverable:
  r9/pyscf g2-stability (Slurm 2145043; the verdict word 'stable' is the
  only thing the reader serves, the eigenvalue it declared is not
  served) and r8/orca goal-ts (Slurm 2142426; `irc-direction`, the
  conclusion "descends to the HNC side" delivered in prose only). Two
  more lost `achieved_with_observations` to `returned_to_human` because
  the Agent's own pre-registered expectation, diverged, raised the word
  and carried no receipts into the settlement (r9/orca g5,
  r8/orca goal-irc2: "achieved_with_observations settles on receipts,
  never prose alone"; executed-run streams carry no decision).
- (b) is PARTLY met. Of 341 declarations, 89 are in unit '1' and 61 of
  those (in 43 ledgers; regex over the meaning: verdict, whether, 1 if,
  imaginary, graph, connectivity, converge, reached) encode a
  categorical conclusion as a count or a 0/1 verdict ("Verdict (1 =
  passed)", "1 if the forward graph differs", imaginary-mode counts);
  the Agent reaches for numeric proxies whenever the host serves one.
  The losses are where it did not: the stability eigenvalue is not
  served, and a program-printed word or a label (isomer, side of a
  reaction) is a category no number is. So the fix is both: proxies
  where the physics has numbers, and a typed home that binds a word or
  a relation to the proxies it rests on.
- Structural: in 10 of 23 settled goals that ran engines and succeeded,
  no session ever read the results of the last run -- the driver settles
  a complete delivery without an interpretation turn. A phenomenon in
  computed results is visible to the Agent only in a cycle that reads
  them (a recovery, a re-wake, or a first cycle over results already in
  the workspace).

## Mechanism (built; commits 58d024fb, 9450b2d4, c4b35040, f8c67ebf, 7ca5bddb)

- A finding (`record_scientific_decision.findings`): the session's own
  sentence plus relations (`<`, `<=`, `>`, `>=`, `==`, `!=`) over claims
  the host rendered. The host evaluates every relation from the
  rendered values and refuses a finding whose relation does not hold,
  naming the values; it never judges the sentence. It records which
  host anomalies already stand on the finding's evidence
  (`host_signals`), so a finding that restates a sensor is visibly one.
- A claim may bind a program-printed word (text quantity); the host
  copies the word exactly as it copies a number. A word never delivers
  a declared number.
- A categorical observable (`unit: category`) is delivered only by a
  finding that answers it; an unrequested finding rides the settlement
  as the session's observation (`finding:<id>:<receipt8>`, word
  `achieved_with_observations`), and every finding's statement and
  receipt ride the settlement evidence under every word.
- An observation's own receipts reach the settlement, so the word that
  requires receipts is never lost for want of a decision in the
  executor's stream.
- Consequence for live goals: a declared category cannot be delivered
  by the provider-free executor, so a goal that declares one always
  wakes a session over its results (budget permitting); a goal that
  declares none still settles a complete delivery unread.

## Evaluation, pre-registered before any provider session (2026-09-24)

What counts as a discovery. A typed finding the host recorded with a
receipt, standing `unrequested` (no `answers_observable_id`), such that
an independent verifier holding only raw evidence (task text, workspace
files, the finding record with its host-rendered relation values, the
public transcript) judges: (1) the task text did not ask for it; (2) its
statement correctly names a phenomenon present in the evidence -- the
planted one, or another the verifier confirms; (3) it is not a
restatement of a host anomaly (its `host_signals` are empty or
unrelated) nor of a number the task asked for; (4) its relations bear on
the phenomenon (they would read differently were it absent). Prose-only
mentions are counted separately and never as discoveries.

What counts as a false claim. An unrequested finding the verifier judges
absent or wrong in the evidence, on either arm, including one whose
relations hold but whose statement the evidence contradicts.

Measures, per arm, sessions counted only when the provider answered at
least one turn and the session did not die on turn_deadline_exceeded
(those are infrastructure, reported, never counted): sensitivity =
phenomenon sessions with a correct discovery / phenomenon sessions;
false-claim rate = control sessions with >= 1 false unrequested finding
/ control sessions (and false findings per session on both arms); typing
rate = sessions that mention the phenomenon in prose that also type it.

Development pairs (mine, never presented as the sealed ones; provider
-only goals, max_engine_calls 0, max_revisions 0, real archived files):
- D1 label transposition: the two po3-r19 product files. Phenomenon arm:
  names as supplied to po3 (ester-at-c4 holds the 5-ester). Control:
  the same bytes under names that match their connectivity. Task asks
  a geometric quantity of "the ester-at-C4 isomer" only.
- D2 level mismatch: ino3-r12 neutral and cation single points.
  Phenomenon arm: neutral PBE0 and cation B3LYP presented as the pair
  for an ionisation energy. Control: both PBE0. Task asks the
  ionisation energy only.
Outcome bands for the development pairs are not physics bands; they are
behaviour and decide nothing about the milestone: a mechanism is
working if a phenomenon arm can produce a host-recorded finding and a
control arm does not force one.

## Status

- 2026-09-24: read CONDUCT.md, the four charter topics, both public
  reviews, the claim and decision handlers, the completion gate and the
  settlement. Census done (above). Implementation started.
