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
  reference job ref1 submitting.
