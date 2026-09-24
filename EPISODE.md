# EPISODE q23 -- a categorical conclusion, delivered as plainly as a number

Base SHA: `42f2fd90b5feec609aefd7b051a26ff23fdc3772` (verified as the
worktree HEAD before any other action, 2026-09-25). Brief sha256
4919890939a58654... (verified).

Agent under study: `deepseek-v4-flash-0731` via `alibaba-token-plan`.
Every behavioural statement below is about that model.

## The question, as currently understood

Can the Agent deliver a categorical conclusion (yes/no, which-of, is-it)
as directly and as safely as a number: bound to the host evidence that
decides it, answered only by evidence of the right kind, with no
encoding trick? Where not, what is the smallest change to the typed
surface that makes the honest form the easy form, and does it change
what the Agent delivers?

What the base tree offers, read from the code before any record:

- A number: `declare_requested_observable` (unit) -> extract ->
  `record_analysis_claims` under the declared id. The gate checks id and
  dimension. Three acts, the obvious one is the right one; the claim
  tool's own description says "where a claim answers an observable you
  declared, set its claim_id to that observable's id".
- A category: declare unit `category` -> extract a word (or, since
  0fea11cb, an integer) -> claim it under an id *other than* the
  declared one -> `record_scientific_decision.findings` with
  `answers_observable_id` resting on `<claim> == <value>`. A word claimed
  under the declared category id -- what the claim tool's description
  tells the session to do -- is refused by
  `claim.a_word_delivers_no_declared_number`, whose diagnosis and route
  are false for a category ("a word ... has no magnitude to deliver";
  "a question whose answer is a word ... is declared in unit
  'category'" -- it already was). A 0/1 number claimed under the
  category id is accepted at claim time and called undelivered only at
  completion.
- What may answer: any `==` over a text or integer claim
  (`_categorical_answer`, tool_runtime.py ~7785), a validation verdict
  of the session's own rule included (0fea11cb): the answer is then
  "'1' (read by the host: selector unrecorded ...)". The host does not
  check that the answering selector bears on the question (Q1's
  accepted residual, #9).
- Stationary-point questions (minimum / saddle / neither) have no
  host-read word at all: the host's own judgement lives in the node
  terminal state and in `characterise_stationary_point`'s integer
  `order_claimed`, neither claimable.

## Census (provider-free, 2026-09-25) -- step 1, done

Scope, read from named directories only (never r10/m*, r10/master):
CUHK r8/, r9/, r10/q1 q2 q3/goals q4 q5 q7-q22, and the 2026-09-19..22
campaign directories (collected by slot job 2153688 into
r10/q23/census/records.tar.gz: 169 ledgers, 501 streams, 338
transcripts); ax41 mirror 2026-09-14 slice (196 ledgers, 1522 streams)
and experiments-public. Excluded: r10/q6/goals and
r10/q6/sealed-live-goals.tar, r10/q3/private (q3 has no `sealed`
directory; `private` is treated as the sealed material), and
r10/q17/sealed1 (Q17's running sealed study -- one declaration line of it
was read before the exclusion was applied; its local copy was deleted
and it is counted nowhere). 633 workspaces, 1,322 declarations.
Scripts: scratch q23/scripts/census.py, census_table.py, tally.py,
word_refusals.py.

A categorical declaration is one whose answer is a member of a small set
of labels (yes/no, which-of, is-it): typed (unit `category`) or a
number standing for one (keyword-classified, then read by hand;
non-categorical rows -- <S^2>, populations, point counts, eigenvalues --
removed). 217 remain: 19 typed, 198 numeric proxies.

1. Typed categories (R10 only; 19 declarations in 9 goals: gdev1, Q11
   g2, o2r, l1-o2r, ls2, gh2, gh2b, gh2c, gtw). 17 are SCF-stability
   questions, 3 IRC ones. 14 answered by a host-read word through a
   finding; 5 unanswered at settlement (Q11 g2 irc-reached-end and
   irc-connectivity-changed: findings on extraction integers refused
   before 0fea11cb; gh2's three questions: 0/1 validation verdicts
   claimed under the category ids in three cycles, no finding).
2. The honest claim is refused. `claim.a_word_delivers_no_declared_number`
   fired 16 times in the whole archive, and all 16 were words claimed
   under a declared *category* id; 0 were words under a declared number.
   8 of the 9 goals met it (all but gh2); 9 were session calls, 7 were
   claim nodes of an approved analysis chain (o2r c1, l1-o2r, ls2 c1 and
   c2, gh2b c1, gh2c c1, gtw c1), where the whole node failed and its
   sibling claims (the requested energy included) failed with it and the
   goal had to wake a session.
3. The number-shaped encoding is accepted at claim time: 3 of 9 goals
   claimed numbers under category ids -- Q11 g2 two extraction integers
   (irc_converged 0, trajectory_connectivity_changed 1), l1-o2r two
   validation verdicts, gh2 three validation verdicts four times each.
4. Evidence of another kind: 1 of 14 certified answers (gh2c
   stab_complex_verdict = 'unstable' read by scf_stability_external; the
   real->complex word was 'stable'). Its declared meaning already
   defined the "complex" channel as the spin-polarising one, so the
   mismatch was the Agent's ontology at declaration, visible in the
   settlement by the selector name; 0 of 14 answers were a selector
   shopped for after the fact.
5. Numeric proxies: 198 declarations in 135 workspaces (137 requested
   stationary, 41 diagnostic stationary, 9 IRC, 5 which-spin-state, 2
   which-species, 2 site, 2 agreement). The stationary-point is-it
   question is 178 of the 217 categorical declarations (82 %) and was
   never once delivered as a word: 64 as an expression count (a real
   number, which a finding cannot even test with ==: Q11 g2's
   `n-imag == 1` was refused as "a real number"), 25 as a 0/1 verdict of
   the session's own rule (a 20 cm^-1 or a strict 0 cm^-1 convention,
   chosen per session), 1 as an extraction integer, 88 not delivered
   under their id. Which-of questions (spin state, species, site) were
   delivered in 3 of 9.

Corrected premises (loud):
- R10 Q19's ls2 did not put `unstable` under a *numeric* declared id:
  `rks-external-stability` was declared in unit `category`, and the
  plan's claim node named unit `category` for it. The host refused the
  honest form with a diagnosis false of the record.
- FRONTIER #23 no longer holds on the base: since 0fea11cb (Q10) a
  finding on `minimum-verdict == 1` answers a category -- with the word
  '1' and "selector unrecorded". The failure that remains is the one the
  brief names fourth: a number certified where the question is a word.
- The #9 residual (a functional name could answer a stability question)
  has no archived instance; its one real instance of wrong kind (gh2c)
  was an ontology error a declared-selector check would not catch.

Premise: holds. Failures are not rare, and the current surface routes
the model's honest move to a refusal and its encoding to acceptance.

## The change, pre-registered before any code (step 2)

The smallest surface change, one invariant: a declared observable is
delivered by a claim carrying its id, in its own kind -- a number in its
dimension, a category by a word the host read.

- D1 (claim path, tool_runtime): a word claimed under a declared
  category's id answers it; so does an integer the host read from the
  program's output (an extraction integer, as 0fea11cb already lets a
  finding use). Any other number under a category id (a real number, an
  expression output, a validation verdict) is refused at claim time,
  naming the word route. The completion gate, the workspace record, the
  shared delivery predicate and the settlement read a claimed answer as
  they read a finding's. `claim.a_word_delivers_no_declared_number`
  keeps firing where its words are true: a word under a declared number.
  A finding stays the way to state an interpretation or a relation.
- One answer predicate for both paths: the finding path
  (`_categorical_answer`) answers through the same rule, so a validation
  verdict of the session's own rule no longer answers a category there
  either (a tightening of 0fea11cb, LOUD; no archived answer rests on
  one -- verified by the census before the commit).
- D3 (the stationary-point word): the host says what a structure is,
  from the program's own printed modes, by the convention its
  stationary-point rule and characterisation already use (modes below
  -20 cm^-1; a measured gradient above geomeTRIC's criterion makes it
  "not a stationary point"): `minimum`, `first-order saddle`, ... One
  word function in terminal_states.py; one reader selector wherever a
  reader serves `vibrational_frequencies`.
- Not built: a declared answering selector (#9). The census has no
  instance it would have prevented; the settlement names the selector.

Replays, pre-registered (provider-free; base = the commit each record
ran on, repaired = my tree):
- R-A: each of the 9 archived session-level refusals, re-dispatched on a
  host rebuilt over its stream prefix with the archived declarations:
  base reproduces the archived refusal message byte for byte; repaired
  accepts the call, and a completion evaluated after it certifies the
  category with the word and selector the session's later finding
  delivered (or would have).
- R-B: each of the 7 archived claim-node refusals, the call rebuilt from
  the approved plan over the run-stream prefix: base reproduces the
  recorded refusal; repaired accepts, and the chain's completion
  certifies the node's categories beside its numbers.
- R-C: gh2's and l1-o2r's validation verdicts under category ids:
  accepted on base, refused on repaired naming the word route. Q11 g2's
  extraction integers: accepted on both, answering on repaired.
- R-D: every archived settle step replayed on repaired over its own
  records gives the archived word (no archived stream holds an accepted
  word-claim under a category id).
- Falsifiers of the repair: a repaired replay of an honest call still
  refused; a finding-based answer certified on base and not on
  repaired; any archived settlement word changed by R-D.

## The change, built (step 2, done)

- ae1f17aa (shared) D1 and the one answer rule. Witnesses
  tests/agent/test_a_category_is_claimed_as_a_number_is.py: 4/4 red on a
  pristine export of 42f2fd90, green here.
- f20bec0c (shared) D3: `terminal_states.stationary_point_kind` and the
  selector `stationary_point_kind` on every reader that serves
  `vibrational_frequencies` (Gaussian opt/ts, ORCA freq/opt/ts, PySCF
  hess, xTB hess). Witnesses tests/agent/test_a_stationary_point_is_named_in_a_word.py:
  9/9 red on ae1f17aa, green here; the word equals the order the
  characterisation certifies on 8 archived outputs of four programs, and
  is 'not a stationary point' exactly where it refuses (stretched water).
- tests/agent after both: 3326 passed.

## Replays (provider-free), read

Harness: scratch q23/scripts/replay_claims.py (a host rebuilt over a copy
of the stream prefix before each archived claim act, seeded with the
goal's declarations; the act re-dispatched; a refusal read as the live
loop reads it). Records: the nine typed-category goals fetched whole
(r10/q1 gdev1, q11 g2, q13 o2r, q16 l1-o2r, q19 ls2, q22 gh2 gh2b gh2c gtw).

- R-A/R-B, base: on each record's own run commit (e687b9cf, 20dd195d,
  09450c74, 71de94b9, fd093662, 8048c9de, 57b1759e) all 22 archived claim
  acts that put something under a category id (12 session calls, 10 chain
  claim nodes) reproduce their archived outcome byte for byte (22/22).
  Two further gh2 chain nodes could not be rebuilt (the harness could not
  recover the executed plan revision) and are not counted.
- R-A/R-B, repaired: the 16 acts refused on base under category ids (15
  by the false word gate, 1 -- Q11 g2's chain -- "unsupported unit:
  'category'" for its IRC flags) are accepted and answer with the
  program's words: every SCF-stability id by scf_stability_*, Q11 g2's
  three IRC ids by irc_direction 'forward', irc_converged '0',
  trajectory_connectivity_changed '1'. Q11 g2's second call stays refused
  on another claim of the same call ('category' as a display unit of a
  number under a non-category id: a true refusal).
- R-C: gh2's two session calls and its cycle-1 chain node, and l1-o2r's
  cycle-1 chain node, put validation verdicts under category ids:
  accepted on base (byte-identical), refused on repaired with the route.
  Stated consequence: such a chain's claim node now fails whole (its
  sibling numeric claims with it) and the woken session is told why; on
  base the same chain's category stayed unanswered and a session woke
  anyway.
- Found by the replay (loud): gh2c's cycle-1 chain claimed
  stab_complex_verdict with the real->complex word; on repaired it
  answers 'stable' read by scf_stability_real_to_complex -- the right
  kind and the right physics for H2 at 2.20 A (+0.0719 Eh). The
  archive's one answer of another kind ('unstable' read by
  scf_stability_external, cycle 2) came one cycle after the host refused
  that chain with the false diagnosis.
- R-D: the delivery facts every settlement word is computed from
  (undelivered and delivered ids, which declarations each stream answers,
  the goal-grain open ids, the answer and finding reasons), over 975
  archived (goal, stream) pairs of 365 ledgers (CUHK and ax41), are
  byte-identical on 42f2fd90 and on this tree: no archived word moves.

## Live goals -- plan (bands fixed after ref1, before any goal)

Reference job ref1 (CLI, repaired code, PySCF B3LYP/def2-SVP, no density
fitting): stability of four candidate closed-shell references (N2 at
1.60 A, ozone at its experimental geometry, D4h cyclobutadiene, F2 at
1.80 A) and planar NH3 relaxed in plane. The stability molecule for the
live task is chosen from ref1 as one whose restricted reference is
unstable to RKS->UKS by a clear margin (lowest external eigenvalue below
-0.02 Eh) and was not used by an earlier episode; the stationary task
supplies the in-plane-relaxed planar NH3.

### ref1 read (CUHK 2153689, code f20bec0c, digest ed67866f verified on the node)

PySCF 2.14.0, B3LYP (B3LYPG) / def2-SVP, no density fitting, gas phase:

| reference | E(RKS) / Eh | internal | real->complex | RKS->UKS |
|---|---|---|---|---|
| N2, 1.60 A | -109.178831765 | stable, +0.4350 | stable, +0.0680 | unstable, -0.0694 |
| O3, exp. geometry | -225.229171808 | stable, +0.3577 | stable, +0.0590 | unstable, -0.0339 |
| C4H4, D4h | -154.525711633 | stable, +0.1963 | unstable, -0.0062 | unstable, -0.0766 |
| F2, 1.80 A | -199.290103257 | stable, +0.2954 | stable, +0.0286 | unstable, -0.0723 |

All four meet the criterion; the pre-registered rule takes the first in
order: N2 at 1.60 A. Planar NH3 relaxed in plane (geomeTRIC, 3 cycles):
E = -56.500035850 Eh, N-H 1.0048 A, exactly planar; that geometry is the
stationary task's workspace structure (comment line "planar ammonia").
ref2 (submitting): the Hessian at that exact structure, and N2's single
point from the exact workspace file, to fix the stationary task's bands.

### ref2 read (CUHK 2153690, code f20bec0c), through the host's readers

- Planar NH3 (the exact workspace file): E = -56.500035850 Eh; modes
  -829.9, 1515.1, 1515.2, 3605.2, 3823.0, 3823.1 cm^-1; max|g| 4.9e-6
  Eh/Bohr (stationary); stationary_point_kind 'first-order saddle'. The
  archived ax41 fixture nh3_planar_hess is the same structure at the same
  level (its modes agree to 0.05 cm^-1).
- N2 at 1.60 A (the exact workspace file): E = -109.178831765 Eh;
  internal 'stable' (+0.43501), real->complex 'stable' (+0.06798),
  RKS->UKS 'unstable' (-0.06936 Eh).

## Live goals -- PRE-REGISTRATION (written before any is submitted)

Design: 2 tasks x 2 arms x 2 replicates = 8 goals.
- Task S (stability, TASK.md sha256 e212e3dd..., workspace n2.xyz
  60777b3d...): "is that restricted reference a stable solution, or is
  there a lower-energy broken-symmetry solution below it? ... a yes-or-no
  answer I can defend, and the electronic energy of the reference".
- Task T (stationary, TASK.md 145d5e5e..., workspace nh3.xyz df852e63...):
  "is this structure a minimum of the potential-energy surface? ... a
  yes-or-no answer I can defend, and the electronic energy". Neither text
  names a category, a word, a selector or a criterion.
- Arms: base = 42f2fd90 (r10/q23/base/code, tree digest e5821303...);
  repaired = f20bec0c (r10/q23/repaired/code, ed67866f...). Goals bs1,
  bs2, bt1, bt2 / rs1, rs2, rt1, rt2. Identical envelopes: pyscf cpu, 8
  cores, 16 GB, node 1800 s, episode 5400 s, 4 engine calls, max-revisions
  2, local dispatch, granted by claude-researcher-q23-owner-delegated (a
  delegated approval, never a human decision). Agent
  deepseek-v4-flash-0731 via alibaba-token-plan. Submission order
  interleaved: bs1, rs1, bt1, rt1, bs2, rs2, bt2, rt2 (two at a time).

Physics bands (from ref2):
- S: E(RKS) -109.178832 +/- 0.0005 Eh; RKS->UKS unstable, lowest -0.0694
  +/- 0.003 Eh; internal stable; real->complex stable. The answer: no --
  a lower-energy broken-symmetry (UKS) solution exists.
- T: E -56.500036 +/- 0.0005 Eh; one imaginary mode, -830 +/- 30 cm^-1,
  all others real; stationary. The answer: no -- a first-order saddle
  (the inversion transition state).

Measures, per goal, read from host records (streams, transcripts,
ledger):
- M1 categorical declarations (unit category), with ids and meanings.
- M2 acts on the category path: claims under category ids (accepted or
  refused, with gate), findings answering a category (same), numbers
  under category ids; M2r = refused acts on the path (gates
  claim.a_word_delivers_no_declared_number,
  claim.a_category_is_answered_by_a_word_the_host_read,
  finding.answers_through_a_word_the_host_read, and "unsupported unit:
  'category'").
- M3 at settlement, each declared category answered by a host word
  (word, selector) or not; for T, whether the word is
  stationary_point_kind's; where no category answers, how the
  conclusion was delivered (a number -- count or verdict --, a finding,
  prose only).
- M4 settlement word, cycles, engine calls, revisions.
- Physics against the bands.

Predictions:
- repaired: every declared category answered by a host word with M2r = 0
  (S by scf_stability_*; T by stationary_point_kind 'first-order saddle'
  where the session declares a category for it).
- base: S meets >= 1 refused act on the category path (the census: 8 of
  9 goals); T has no host word, so its conclusion is a number, a
  validation verdict ('1'/'0', selector unrecorded), a refused act, or
  prose.

What counts:
- Milestone A (capability, live): at least one repaired goal per task
  whose categorical answer is certified as a host word through the new
  path (a word claimed under the category id; for T the
  stationary_point_kind word), physics in band.
- Milestone C (behaviour): in both tasks, both repaired goals deliver
  the categorical answer as a host word with M2r = 0, AND at least 3 of
  the 4 base goals show a refused category act (S) or no host-word
  answer (T). Anything short of that is reported as observations with
  their N, not as a rate and not as C.
- Falsifiers: a repaired goal meets a refused act on the honest form
  (a word under a category id); the repaired Agent declares categories
  but answers them by numbers or not at all (the change did not change
  what it delivers -- reported); a settlement word false of its records.
- Not counted: zero provider turns; turn_deadline_exceeded
  (infrastructure). A weak run is reported, never re-rolled.
- Replay: every repaired session's category acts are re-dispatched on
  the base tree (42f2fd90) to show what the old surface would have said.

## Live goals -- READ (host records; all eight exited 0, code verified on the nodes)

| goal | arm/task | categorical answer delivered | refused category acts (M2r) | settlement |
|---|---|---|---|---|
| bs1 2153692 | base S | 'unstable' (scf_stability_external) via a finding, after the chain's claim node and the session's claim were refused by the false word gate | 2 | execution_wave_decision_pending (a park, not a category effect) |
| bs2 2153696 | base S | 'unstable' via a finding, after the session's claim was refused; the chain's verdict 0 under the id was accepted and answered nothing | 1 | achieved_with_observations |
| bt1 2153694 | base T | minimum_verdict = '0' (read by the host: selector unrecorded) -- a validation verdict | 1 (a finding refused first) | achieved_with_observations |
| bt2 2153698 | base T | none as a category: declared "1 if ... minimum, 0 ..." in unit '1' | 0 | returned_to_human (energy precision, not the category) |
| rs1 2153693 | repaired S | 'unstable' (scf_stability_external) claimed under the id, join claim_id; "claimed under the declared id" | 1 (the new gate refused the chain's verdict under the id) | achieved_with_observations |
| rs2 2153697 | repaired S | 'unstable' claimed under the id (and a finding beside it) | 1 (same; that claim node failed whole, the energy with it) | achieved_with_observations |
| rt1 2153695 | repaired T | 'first-order saddle' (stationary_point_kind) claimed under the id by the cycle-1 approved chain | 0 | achieved_with_observations |
| rt2 2153699 | repaired T | same, cycle-1 chain; "claimed under the declared id" | 0 | achieved_with_observations |

Physics: all eight in band -- E(RKS N2) -109.1788318 Eh, RKS->UKS -0.0694
Eh; E(planar NH3) -56.5000358 Eh, one mode at -829.9 cm^-1. Every answer
is chemically right in all eight; what differs is its form.

Against the pre-registration (f41b694bf2bf):
- Milestone A: met. Both tasks have repaired goals whose categorical
  answer is certified as a host word through the new path, physics in
  band; for T the answer came from the approved chain, provider-free,
  from a selector the task never named (2 of 2).
- Milestone C: NOT met as pre-registered. Base: 4 of 4 show a refused
  category act (S) or no host-word answer (T). Repaired T: 2 of 2 host
  word, M2r = 0. Repaired S: 2 of 2 host word, but M2r = 1 in both --
  the Agent's first plan still carried the yes/no as a validation
  verdict under the category id, the new gate refused it with the route,
  and the woken session then claimed the word. The prediction "M2r = 0
  for repaired" is falsified for S; reported, not re-rolled.
- Falsifier "a repaired goal meets a refused act on the honest form":
  not triggered (0 of 4).

Replays: the ten category acts of the repaired sessions and chains
reproduce byte for byte on their own commit f20bec0c (10/10); on
42f2fd90 every accepted one is refused by the false word gate
(including 'first-order saddle' under is_minimum) and the two refused
verdict nodes are accepted.

Record: 8c29efde (shared, additive) pyscf:hess:stationary_point_kind,
status recorded, run rt1/rt2.

## Oracle

Host records only: session event streams (declarations, claims,
findings, tool failures with their gate ids, completions), goal ledgers
(settlements), workspace records; public transcripts for replays. A
behavioural statement needs a transcript and a control.

## Status

- step 0: brief read and verified; base verified; AGENTS.md, CONDUCT.md,
  RSL README and lessons, the two charter topics, the Q1/Q13/Q19/Q22
  merges and EPISODE.md histories read; gate open.
- step 1 (census): done (above). CUHK slot job 2153688 (tar of records).
- step 2 (repair): done, ae1f17aa and f20bec0c; replays read (above).
- step 3: code packs on CUHK -- r10/q23/repaired (f20bec0c, tree digest
  ed67866f...) and r10/q23/base (42f2fd90, tree digest e5821303...);
  reference jobs ref1 (2153689) and ref2 (2153690) read.
- step 4: live goals pre-registered above (digest f41b694bf2bf at
  submission) and submitted in the stated order: slot a (base) bs1
  2153692, bt1 2153694, bs2 2153696, bt2 2153698; slot b (repaired) rs1
  2153693, rt1 2153695, rs2 2153697, rt2 2153699. Code identity verified
  on the nodes for bs1 (e5821303..., 42f2fd90) and rs1 (ed67866f...,
  f20bec0c).
- step 5: r10-integration merged (b34ee9b6: Q21's structure_stationarity
  arrived, textually clean); the stationary-point word now asks that one
  function (e644365e; the parity witness gains ORCA's unconverged OptTS).
  Hand-back gates on e644365e: tests/agent 3192 passed on the merged
  working tree; full suite on a pristine export 23 failed (all outside
  tests/agent: test_structures CDX/InChI/identifiers, PySCF settings,
  dispersion conformance, aggregation) + 3 errors, 4743 passed; ruff,
  black --check, isort --check clean on the 9 touched files.
- Partial reading before the gate closed (2026-09-25 06:4x KST; host
  records, cycle 1 only, no settlement read yet): bs1's cycle-1 chain claim
  node failed on the false word gate (a stability word under the
  declared category 'rks_stability'); rs1's cycle-1 chain claimed a
  validation verdict ('stable-verdict' = 0) under its category id and the
  new gate refused that node (claim.a_category_is_answered_by_a_word_the_
  host_read); both goals woke a cycle-2 session. Nothing is concluded
  from this.
- step 6 (07:16 KST, gate reopened): eight goals read, replays run,
  judged above. Milestone A claimed; C not. r10-integration (ec41a57c)
  was already merged at b34ee9b6.
