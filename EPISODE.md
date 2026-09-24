# R10 episode Q10 -- is every word the host verifies true of the evidence?

Base SHA: c79c39a13174044fa208b2ac4ff12033f8b14f25 (verified with `git rev-parse HEAD` at start).
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

When the host signs a word -- a settlement and the reasons it quotes, a park
reason, a refusal verdict (`verified` + basis), a finding's standing -- is it
true of the raw evidence (engine output, receipts, streams)? The brief named
five instances; its falsifier was a census of every such word over the
archived, unsealed goal ledgers.

## Census (provider-free, 2026-09-24)

Scope read: 86 CUHK goal ledgers (r8, r9, r10/q1,q2,q4,q5,q7,q8 and the
2026-09-18..21 campaigns under /project/xlzhang/jiseung) and 188 ax41 mirror
ledgers (`~/developer/chemsmart-hetzner-mirror/2026-09-14/campaign`, claude/
and claude-analysis/ excluded); 187 + 652 session streams. Excluded as
sealed: r10/q6/goals, r10/q3; the master's r10/m* is refused by the round
guard, so smoke1b (instances 2 and 5) was not read.

Denominator: 397 host-signed words = 253 settlements (word + quoted
reasons), 6 execution-wave parks, 119 refusal verdicts, 19 finding
standings. (0 reading turns outside the sealed q6 goals.)

FALSE of the raw evidence, class still produced by the tree at c79c39a1
(14 words, 3.5%):

- C1 achieved over a run that carried no analysis chain (6 settlements).
  The run-path settlement reads only the last run's stream; with no
  completion receipt there, "no limitation list" reads as "nothing
  undelivered", and "workflow completed with its analysis chain; the host
  completion gate certified the delivery" is composed unconditionally.
  r9/gaussian/g1 and g3 (4 of 6 declared IRC observables never claimed in
  any cycle), r9/master/infra-smoke (3 of 5), r9/master/merged-smoke (2 of
  3), r10/q2/g1-hono (declared delivered in cycle 1, whose completion was
  partial and recorded two falsified expectations the word drops; nothing
  read the cycle-2 IRCs), ax41 E2-acetone (no completion ever passed).
- C4 refusal verified while the evidence holds the value (2 settlements, 3
  verdicts). r9/pyscf/g2-stability settled unreachable_from_evidence for the
  lowest stability-Hessian eigenvalues; its PySCF log prints them
  (dans-opt-geom_sp_gas_phase.out:2595-2599). r8/orca/goal-ts settled
  unreachable for irc-direction while the host's own extraction had read
  'forward'. Both verified by the session's own blocked_unsupported node.
- C2 finding standing from one operand (1 standing + the settlement reason
  quoting it): r10/q7/g2-scan-modred `minimum-torsion-agreement` recorded
  on_the_request; operand `lowest-coord` is undeclared.
- C3 park reason denies a decision (1 park): losartan-micropka-r2 cycle 4,
  "the Agent made no execution-boundary decision"; the session selected
  c-neutral-opt (status ready) on losartan-micropka-rev4a, then planned
  losartan-micropka-r4-settlement, which has no ready calculation.

Also a host statement of absence the evidence contradicts (outside the 397,
in receipts): every PySCF stability record says real->complex is "not
determined"; PySCF's log determines it (gdev1: "wavefunction has an real ->
complex instability", lowest eig -0.0383; r9 g2-stability: stable).

FALSE, class repaired before this episode (historical): 11 ax41
standing-round achieved over completion limitations naming declared ids
(pre E4, 2026-09-03), h1b, 2 achieved over anomaly receipts, 48 unverified
refusal bases worded "the observable is reachable" (pak-g3-ozone wording;
false at least where xTB was absent or MP2 had no Hessian), 2 returned
goals quoting an internal ContractError in place of a delivery.

MISLEADING (literally true, attribution wrong): 4 unreachable_from_evidence
settlements whose reason reads "the host verified each: <session statement>"
where the host checked only that the plan declared a node blocked, and the
cause was a writer defect (r9/gaussian/g2) or a missing input (r9/orca/g1,
r9/xtb/g1, r9/xtb/g2).

Premise falsified: the five named instances are not the only false words.
C1 is a sixth class, larger than any of the five; C4 has unsealed instances.

## Repairs (planned, one general commit each)

1. finding standing over every operand (C2).
2. run settlement judged at the goal grain; "certified" and "with its
   analysis chain" only over a completion receipt (C1).
3. park reason reads the session's own wave history (C3).
4. refusal verification reads the goal's evidence: served / absent-as-read
   / unread-by-any-reader / blocked-in-plan; the settlement says what the
   host checked (C4) -- `shared:`, it changes which refusals settle
   unreachable_from_evidence.
5. the reading turn's quoted word (instance 4).
6. a declared category answered through a host-read integer verdict
   (instance 5), if it stays inside Q1's accepted residual.

Each repair: a witness red on c79c39a1 and green after, driving the public
entry point over archived records.

## Pre-registration (written before any live goal)

(to be completed before the first slot_submit)

## Jobs issued

none yet.

## Status

- census done; repairs starting.
