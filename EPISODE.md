# R10 episode Q10 -- is every word the host verifies true of the evidence?

Base SHA: c79c39a13174044fa208b2ac4ff12033f8b14f25 (verified with `git rev-parse HEAD` at start).
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

When the host signs a word -- a settlement and the reasons it quotes, a park
reason, a refusal verdict (`verified` + basis), a finding's standing, a
categorical answer -- is it true of the raw evidence (engine output,
receipts, streams)? The brief named five instances; its falsifier was a
census of every such word over the archived, unsealed goal ledgers.

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

- C1 achieved over a run that carried no analysis chain (6 settlements):
  r9/gaussian g1, g3 (4 of 6 declared IRC observables never claimed),
  r9/master infra-smoke (3 of 5), merged-smoke (2 of 3), r10/q2 g1-hono
  (only completion partial, two falsified expectations dropped), ax41
  E2-acetone (no completion ever passed).
- C4 refusal verified while the evidence holds the value (2 settlements, 3
  verdicts): r9/pyscf g2-stability (log prints the lowest stability
  eigenvalues, out:2595-2599), r8/orca goal-ts (host had read 'forward').
- C2 finding standing from one operand (1 standing + the reason quoting
  it): r10/q7 g2-scan-modred minimum-torsion-agreement.
- C3 park reason denies a decision (1 park): losartan-micropka-r2 cycle 4.

Host statement of absence contradicted by the evidence (outside the 397, in
receipts; found, left): every PySCF stability record names real->complex
"not determined"; PySCF's own log determines it (gdev1: "wavefunction has
an real -> complex instability", lowest eig -0.0383 Eh; r9 g2: stable).

FALSE, class repaired before this episode (historical): 11 ax41
standing-round achieved over completion limitations naming declared ids
(pre E4, 2026-09-03), h1b, 2 achieved over anomaly receipts, 48 unverified
refusal bases worded "the observable is reachable" (false at least where xTB
was absent or MP2 had no Hessian), 2 returned goals quoting an internal
ContractError in place of a delivery.

MISLEADING (literally true, attribution wrong): 4 unreachable_from_evidence
settlements whose reason read "the host verified each: <session statement>"
where the host checked only a blocked node (r9/gaussian g2 writer defect;
r9/orca g1, r9/xtb g1, g2 missing input).

Premise falsified: the five named instances are not the only false words.

## Repairs (committed)

1. 63d30456 finding standing over every operand (C2).
2. 51ff5466 chainless run settles on the goal's latest completion; "certified"
   only over a passed completion (C1).
3. c6216a9d park names the replaced wave selection (C3).
4. 204fe6fd `shared:` refusal verified only after reading the registered
   results; settlement attributes basis vs statement (C4).
5. cd711d3c reading line says what the reading read and recorded (instance 4).
6. 0fea11cb a category is answered by == over a host-read integer (instance 5).
7. a5cb66b7 `shared:` a refusal verified before the run is re-read against
   the run's results at settlement (found while pre-registering LG1: the
   likeliest Agent route -- refuse at planning, run, settle -- defeated 4).
8. f3fa7b92 served-selector basis says "a reading of the selector", not the
   observable; 6ec52fc9 `shared:` tool description names the settle-time read.

Each has a witness red before and green after, driving `run_goal_loop` or
the tool host's `dispatch`. Pristine export of f3fa7b92: tests/agent 2960
passed; full suite 23 failed, identical set to c79c39a1's (environmental:
test_structures x19, pyscf dispersion x2, PyscfSettings, aggregation).

## Provider-free replays on the archived records (scratch/q10/replay_*.py)

Base export of c79c39a1 reproduces each archived word exactly; the repaired
tree (0fea11cb) replays:
- r9/gaussian g1, g3, r9/master infra-smoke, merged-smoke, r10/q2 g1-hono:
  archived achieved/with_observations "certified" -> recovery_opened naming
  "cycle 2: the workflow ran without an analysis chain ... cycle 1's run,
  whose completion is partial" and the undelivered declared ids.
- r10/q7 g2 finding: archived on_the_request -> unrequested.
- losartan park: archived "the Agent made no execution-boundary decision" ->
  "the Agent selected c-neutral-opt on workflow losartan-micropka-rev4a; its
  later plan ... replaced that workflow ...".

## Pre-registration (written before any live goal)

LG1 -- a value the output holds but no reader serves (repair 4, live).
- Task: the electronic spatial extent <R**2> of water, Gaussian 16,
  HF/6-31G(d), gas phase, single point at the supplied geometry (r(OH) =
  0.9572 A, HOH = 104.52 deg). Every Gaussian population analysis prints
  "Electronic spatial extent (au): <R**2>= ..."; no reader serves it, and no
  served quantity composes it.
- Envelope: gaussian cpu only; 3 engine calls; 2 revisions; 1 h wall; 8
  cores, 16 GB. Granted by claude-researcher-q10-owner-delegated.
- Physics band for the printed value: 15 < <R**2> < 25 au (HF/DZP-quality
  water); energy -76.02 < E < -76.00 Eh.
- PASS (the host's word is true): the goal does not settle achieved or
  unreachable_from_evidence while the log prints <R**2>; a typed refusal,
  if recorded, is verified=false with a basis naming the Gaussian result
  and the printed "Electronic spatial extent" line.
- FAIL: unreachable_from_evidence (or achieved) over the printed value.
- Not counted: zero provider turns, turn_deadline_exceeded (infrastructure).
- Reported, not scored: whether the Agent refuses typed, the selector it
  names, what else it claims.
- Replay control: the recorded decision re-verified on c79c39a1 (expected:
  verified, "no program declares selector ...") and on the repaired tree.

## Jobs issued

none yet. CUHK gate closed at 2026-09-24 ~13:00 KST (after the census
copy); live part not run while closed.

## Status

- census, six repairs, replays done; tests/agent green (2959).
- next: LG1 when the gate reopens; merge r10-integration; hand back.
