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
- step 2 (repair): pre-registered above; starting.
