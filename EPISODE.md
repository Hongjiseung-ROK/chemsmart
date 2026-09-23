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
- (b) is PARTLY met. 62 declared observables in unit '1' encode
  categorical conclusions as counts or 0/1 verdicts ("Verdict (1 =
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

## Mechanism under construction

- A finding (`record_scientific_decision.findings`): the session's own
  sentence plus relations (`<`, `<=`, `>`, `>=`, `==`, `!=`) over claims
  the host rendered. The host evaluates every relation from the
  rendered values and refuses a finding whose relation does not hold,
  naming the values; it never judges the sentence. It records which
  host anomalies already stand on the finding's evidence, so a finding
  that restates a sensor is visibly one.
- A claim may bind a program-printed word (text quantity); the host
  copies the word exactly as it copies a number. A word never delivers
  a declared number.
- A categorical observable (`unit: category`) is delivered only by a
  finding that answers it; an unrequested finding rides the settlement
  as an observation attributed to the session.
- An observation's own receipts reach the settlement, so the word that
  requires receipts is never lost for want of a decision in the
  executor's stream.

## Status

- 2026-09-24: read CONDUCT.md, the four charter topics, both public
  reviews, the claim and decision handlers, the completion gate and the
  settlement. Census done (above). Implementation started.
