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

## Development sessions (provider-only, local, deepseek-v4-flash-0731)

- dev-d1-phen (code 08dfddb5): settled achieved_with_observations. VOID
  as a probe of noticing: the session's artifact list names each
  workspace geometry by its content id (`geometry-<sha16>`), atom count
  and symbols -- never by file name or comment line -- so the two arms
  of D1 are identical to the Agent and a label carried only by a file
  name is invisible to it. The Agent assigned the isomers by
  connectivity (N1 = the benzyl nitrogen) and answered for the true
  ester-at-C4 structure. It typed its requested distance as a finding
  resting on its own declared claim, and the word said it had observed
  something nobody asked for: that is the defect repaired in 2ff0d160
  (standing is computed from the evidence). D1 is replaced by D1',
  whose task names each file with its SMILES as po3-r19's did, so the
  label is in the text the Agent reads.
- dev-d2-phen (code ba750e57; neutral PBE0 + cation B3LYP): the Agent
  delivered the requested difference (-14.88 eV) and, unasked, recorded
  a finding that the two single points use different functionals so the
  number is not an ionisation energy. The finding's relations rest only
  on the requested claim (IE < 0, IE < -10): the symptom, not the cause
  (the functional words were never claimed), so the host classified it
  on_the_request. It did not doubt its own delivered claim; the goal
  settled achieved_with_observations on its falsified IE band alone.
- dev-d2-ctrl (both PBE0): IE 4.51 eV (ino3-r12's PBE0 couple, -0.4727 V
  vs Fc with Fc at 4.988 V absolute, implies about 4.52 eV: consistent);
  one on_the_request finding restating it; no unrequested finding.
- dev-d1p-phen (task names each file with its SMILES, labels transposed
  as po3-r19's were): the Agent matched each SMILES to its file by
  connectivity and never tested the label against the SMILES under
  IUPAC numbering; it reported 3.30 A for the file labelled ester-at-C4,
  which holds the 5-ester (the true 4-ester reads 3.219 A, as dev-d1-phen
  found). Missed. It recorded one unrequested finding -- "the requested
  pair distinguishes the two isomers", on the other file's distance --
  true, trivial, and it moved the word to achieved_with_observations.
  Trivial unrequested findings moving the host's word is a defect of the
  mechanism, repaired next: a finding never moves the word.
- dev-d1p-ctrl (labels consistent): 3.219 A for the true 4-ester
  (correct); the same trivial "the pair distinguishes the isomers"
  finding as the phenomenon arm -- no false claim, same noise. Repaired
  in e687b9cf: findings never move the word.
- dev-d3 (code e687b9cf; the archived PySCF 2.14.0 run
  o2_singlet_sp_stability, B3LYP/def2-SVP at 1.2075 A; the task asks
  whether the RKS reference is stable for both rotations): the Agent
  declared two questions in unit 'category', claimed the verdict words
  as read ('stable', 'unstable'), answered each with a finding resting
  on == relations, and the goal settled `achieved` -- the shape r9
  g2-stability lost to unreachable_from_evidence. Its stated
  uncertainties name the two-configurational character of 1-Delta-g.

## Protocol for the sealed material (frozen with the mechanism)

- Code: the hand-back commit, packed with pack_code.sh; every live goal
  and every archived session runs that tree and prints its digest.
- Live tasks: one goal each on CUHK through make_goal.py and slot_submit
  (episode q1, concurrency 2), task text verbatim, granted by
  claude-researcher-q1-owner-delegated, max_revisions 2 unless the
  sealed material says otherwise, envelope sized to the chemistry and
  written into this file before submission with the physics bands the
  master's verification fixes.
- Archived set: one provider-only goal per item, run locally and
  sequentially (the key is shared), max_engine_calls 0, max_revisions
  0, task text verbatim, workspace = the item's files only (no earlier
  streams or transcripts).
- The verifier receives, per session: the task text, the workspace input
  files, the public transcript, the session event stream (claims,
  findings with their host-rendered relation values and standing,
  host_signals), and the goal ledger's settlement. Never this file's
  interpretation or a report.
- Labels (phenomenon or control) are read only after every session of
  the set has settled; a session is never re-run.
- Known limits the sealed material meets, stated before it is opened:
  (1) a workspace file's name never reaches the session -- artifacts
  are listed by content id, atom count and symbols -- so a phenomenon
  carried only by a file name or an xyz comment line is invisible unless
  the task text restates it; (2) a live goal whose approved chain
  delivers every declared number settles without any session reading
  the results (10 of 23 archived successful engine goals), so a
  phenomenon only in computed results is visible to the Agent only if
  the goal wakes a session (a declared category the executor cannot
  deliver does; a recovery does).

## Live goal gdev1, pre-registered before submission (development, mine)

Task: is the closed-shell RKS reference of singlet O2 at
B3LYP/def2-SVP, 1.2075 A, gas phase, stable for both kinds of orbital
rotation, and its electronic energy (PySCF, one engine call expected).
Reference: the archived PySCF 2.14.0 run at exactly this level and
geometry (tests/data/PySCFTests/outputs/o2_singlet_sp_stability):
E = -150.141807 Eh, internal 'stable', external 'unstable'
(RHF/RKS -> UHF/UKS).
- Success (standing, live): the settlement is achieved or
  achieved_with_observations; each stability question the Agent
  declares as a category is delivered by a finding resting on the verdict
  words the host read from the new run; E within 0.001 Eh of the
  reference; verdicts equal the reference's.
- Failure: the goal ends unreachable_from_evidence or returned_to_human
  over the categorical question, or the verdicts or energy fall outside
  the reference.
- Premise falsified for the live path: the Agent is offered the category
  and the finding and still delivers the verdict only in prose, or a
  category it declared cannot be delivered after the run because no
  session reads the results (the executor cannot deliver a category, so
  the goal must wake one; if it does not, that is the defect).

## gdev1 result (CUHK Slurm 2149848, code e687b9cf, digest ded5d770)

Settled `achieved_with_observations`, 2 cycles, 1 engine call (PySCF sp,
12.4 s, 8 cores). E = -150.14180681 Eh (reference -150.141807: inside
the band). Verdicts read by the woken session in one extraction
receipt: internal 'stable', external 'unstable', rotation space
'RHF/RKS -> UHF/UKS' (equal to the reference). The executor could not
deliver the declared category, the goal woke a session over the result
(recovery_opened, analysis_status partial), the session first tried to
claim the word under the declared id, met
claim.a_word_delivers_no_declared_number, claimed it under its own id,
and answered `rks-stability-verdict` with a finding on external ==
'unstable'; the internal verdict is stated in the sentence only. The
host's own sensor scf.reference_unstable fired on the run; the finding
recorded host_signals [] -- the run outcome had dropped the flagged
result's digest on the way to the ledger (repaired in 9d74f399). Every
pre-registered success condition holds: milestone A's live path is
exercised. Three stability selectors are recorded in release.json
(920345ea).

## Acceptance hold (master's boundary probe on 0adf6c27) and its repair

The probe declared `reference-stability` (unit category), claimed the
verdict word and the po3 distance, and recorded one answering finding:
- A. rests on verdict == 'stable_under_considered_perturbations': passed.
  Correct.
- B. rests only on distance < 1.6, says "stable": passed. A stability
  verdict was delivered on a bond distance.
- C. rests on verdict == 'stable...', says "UNSTABLE": passed. The
  delivered answer contradicted the relation the host checked.
In B and C "the host completion gate certified the delivery" was false.

Rule now (relation layer, the smallest owning one): a declared category
is answered only through an `==` relation that holds over a word the
program printed (a text claim). The finding verifier refuses any other
answer with `finding.answers_through_a_word_the_host_read`; the finding
receipt carries `answer` -- the host's words, each with its claim,
extraction selector and receipt -- and nothing else delivers the
category (completion gate, shared predicate, workspace record, goal
grain). The completion event names what it certified
(`declared_categorical_answers`), and the settlement states
"<id> = '<word>' (read by the host: <selector> on <receipt8>)" before
the session's sentence, which is labelled its interpretation. A finding
recorded before this rule, answering without words, answers nothing.

Witnesses (public path: host tools over real archived files, then
completion and run_goal_loop): probe B and probe C, both red on
0adf6c27 and green on the repair.

gdev1 replay (provider-free, the woken session's recorded calls
re-dispatched in order through a host seeded as run_live_agent_session
seeds one, over the fetched result and sibling receipts, digests verified
17fa1c94.../ac5abff5...): every call's outcome equals the recording --
the word under the declared id refused by
claim.a_word_delivers_no_declared_number, the first decision refused by
the functional-convention gate, the second accepted -- and the completion
passes with no limitation: rks-stability-verdict = 'unstable', read by
scf_stability_external via claim rks-stab-external-word. The rule is a
strict tightening that gdev1 passes; no re-run.

Residual, stated: the host checks that the answer is a word it read and
names the selector; it does not judge whether that selector's word is
the right kind of answer to the question (as it does not judge which
energy answers a declared energy beyond dimension). A declaration that
names its answering selectors would close that at the cost of a new
required declaration field; gdev1's declaration names none and would
not have passed.

Doubt link from a finding (dev-d2-phen): left. The typed route exists
(`doubt:<receipt>` in the decision's evidence), the session did not use
it, and a second route that lets a finding move the completion status
has no evidence behind it yet.

## Status

- 2026-09-24: read CONDUCT.md, the four charter topics, both public
  reviews, the claim and decision handlers, the completion gate and the
  settlement. Census done (above). Mechanism built (58d024fb ..
  ba750e57); tests/agent green at 7ca5bddb. PySCF stability words now
  extract as words (ba750e57): the r9 g2-stability loss had a second
  cause below the claim, an untyped ValueError in extraction.
- 2026-09-24, later: six development sessions and one live development
  goal (gdev1). Two repairs the live goal showed: a run outcome keeps
  its sensor's flagged results (9d74f399), and a finding is the goal's,
  carried by the workspace record to the settlement a later run ends in
  (8228a286; also carries a planning session's claims, the ino3-r12
  section 0.4 omission). Merged r10-integration (0fd69b89, clean).
  tests/agent green (2804 passed); full-suite failing set identical to
  r10-integration's (23 failed + 3 errors, environmental).
- FROZEN for the sealed material: mechanism at code commit 8228a286;
  what counts as a discovery and a false claim, the measures, the
  protocol, and what the verifier receives are the sections above.
  Nothing in the finding or claim surface changes before the sealed
  sessions have settled. Status: ready for sealed tasks.
