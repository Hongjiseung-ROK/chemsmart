# R10 episode Q3 -- knowledge at the moment of decision

Base SHA: `292b9bf3e7d14a3da112983d6152aecbf68059e3` (verified with
`git rev-parse HEAD` as the first action of the episode).

Agent under study: `deepseek-v4-flash-0731` through the
`alibaba-token-plan` provider. Every behavioural statement below is a
statement about that model.

## The question, as I currently understand it

When method-adequacy and convention knowledge can be reached at the
typed moments it governs (choosing a level, comparing with experiment,
rendering a claim), does the Agent choose and qualify differently on open
questions; is the knowledge itself correct and current; and which
delivery works without routing on the human's words?

## Premise check (provider-free, on the base tree)

- The system prompt says "Domain-knowledge skills are advisory reading
  carried in this prompt" and tells every session to consult them; only
  a one-line index per skill is rendered
  (`chemsmart/agent/live_session.py`, `_system_prompt`).
- The planning catalogue holds 62 entries in every exposure mode and none
  of them is a skill; `consult_domain_skill` has a handler in
  `TOOL_HANDLERS` and no definition anywhere, so a call by name is a
  `CapabilityNotInCatalogueError`.
- `chemsmart agent capabilities --kind skill` reports all three skills
  `advertised` from the constant string "system prompt skill index",
  while the same ladder reports `tool:consult_domain_skill` as `wired`
  (unadvertised): two organs answering one question.
- The opener was `open_guide`, deleted by the commit this branch knows
  as `a1367535` ("the stem-and-guide tree is deleted", 2026-09-20); the
  brief's `1c2f4158` is the pre-rewrite id of the same change and is not
  an ancestor of the base.
- Before the deletion, 7 of the 9 archived session streams in
  `experiments-public/` consulted `method-adequacy` through `open_guide`
  -- but those ran `qwen3.8-max`, not the model under study.

## Commits so far (repair, then content)

- f21ae5e7 knowledge entries in the catalogue, index read off it,
  sentence registered (`stem.knowledge_is_reference_text`); witness red
  on base, green after.
- 391c9ff9 the ladder's advertised rung for skills is computed.
- f963a434, 35b2292e, a270eca6 content corrections and additions.

## Development observations (not evidence for the sealed question)

- Local pilot, pull-only delivery (391c9ff9), dev question D1 (para-nitro
  effect on the gas-phase deprotonation enthalpy of phenol): the session
  searched "method adequacy ... error cancellation ... semiempirical
  uncertainty" and loaded `about_method_adequacy` in its second turn,
  before its first `project_yaml` -- pull worked once.
- The same session shows why the sealed sessions cannot run on this Mac:
  locally only xTB is environment-ready (PySCF 2.13 fails the 2.14 guard,
  ORCA and Gaussian are absent), so the model planned GFN2-xTB and named
  DFT as "the scientifically preferred but unmaterialized alternative".
  Method choice would measure the laptop, not the knowledge. Planning
  sessions therefore run on the cluster under the R10 CUHK profile
  (Gaussian 16, ORCA 6.1.1, PySCF 2.14, xTB), inside slot jobs, one
  session at a time.
- Batch dev1 on the cluster (Slurm 2149579; D1 in C, B and A, D3 in C;
  code a270eca6 and 292b9bf3, digests verified in the job) -- development,
  not the sealed test:
  - dev1-D1-C (550 s, 15 provider turns): searched "about_method_adequacy
    method basis dispersion solvation adequacy effect size" and loaded it
    before its first project; planned ORCA B3LYP-D3BJ/def2-TZVPD opt+freq
    with omegaB97X-D4/def2-TZVPD single points as a measured
    functional-spread estimator, and wrote that def2-TZVPD is deliberate
    because a basis without diffuse functions biases the anions in a known
    direction.
  - dev1-D1-B (333 s): no knowledge; ORCA B3LYP/def2-TZVPD opt+freq, no
    dispersion, no second level; its text already says diffuse functions
    are essential on the anionic oxygen and that errors cancel between the
    two acids. The model's priors cover this common case.
  - dev1-D1-A (432 s): no knowledge reached, no call of an advisory
    document's name; searched once for "optimal method for gas phase
    acidity anions diffuse basis"; Gaussian omegaB97X-D/6-31+G(d,p).
  - dev1-D3-C, control (327 s): loaded about_method_adequacy before its
    project; B3LYP-D3BJ/def2-TZVP opt+freq, one engine call, no escalation.
    Its text attributes "0.005 A" to about_method_adequacy, which contains
    no number: an attribution that over-reaches the source (noted for the
    F flag).
  - All three knowledge-arm sessions on either host loaded
    about_method_adequacy by the model's own search before the first
    level-fixing act (4 of 4 with the local pilots): pull is the delivery
    under test. Cluster sessions take 5.5-9 min and 1.5-2.0 M input
    tokens each.

## Arms (what the model reads, measured, not asserted)

Initial request digests from `arm_digest.py` (host_search, empty context;
sha256 prefixes):

| arm | code | CHEMSMART_AGENT_SKILLS | catalogue | tools | system prompt |
|---|---|---|---|---|---|
| A false sentence, no access | 292b9bf3 | 1 | b233c12f (62) | 1295775e | 1fd85c2d (13,632 B) |
| B no sentence, no access | 292b9bf3 or 64fc0ca1 | 0 | b233c12f (62) | 1295775e | fda60dcd (10,969 B) |
| C honest sentence, real access | 64fc0ca1 | 1 | f730d227 (65) | 1295775e | 58f9f2e3 (12,826 B) |

**Arm commit for the sealed run: 64fc0ca1** (code tree digest
cdfd90c9..., packed as `code-64fc0ca1` on the cluster; base packed as
`code-292b9bf3`, digest d3652db7...). B is byte-identical whichever
commit serves it (same catalogue, tools and prompt), so A-B is a contrast
inside the base commit and B-C one inside the arm commit; A differs from
B only by the false sentence, C from B only by the honest sentence and
three deferred catalogue entries. 64fc0ca1 carries the r10-integration
merge, whose only code-tree change is one release.json record, read by
the capability ladder and by no session.

## Pre-registration for the sealed questions (written before they are seen)

**Delivery under test (arm C).** Pull only: the honest index sentence and
three deferred catalogue entries, reached by the model's own search or by
exact name. Nothing is pushed by the host and nothing reads the task
text. Chosen because pull worked in both local dev sessions that could
show it (D1, D2: each searched for adequacy knowledge by name and loaded
it before its first project); the sealed run measures the pull rate
instead of assuming it.

**Sessions.** N = 16 questions x 3 arms x 1 session = 48 provider-only
`chemsmart agent plan` sessions. Model `deepseek-v4-flash-0731` via
`alibaba-token-plan` (cluster agent.yaml: reasoning_effort xhigh, 1M
context), exposure mode host_search (the provider's own). Controller:
CUHK compute node inside an r10-q3 slot job, CHEMSMART_CONFIG_DIR =
/project/xlzhang/jiseung/r10/config, server CUHK (Gaussian 16 C.02, ORCA
6.1.1, PySCF 2.14, xTB). Envelope `plans/envelope.yaml`: gaussian, orca,
pyscf, xtb on cpu; 32 cores, 120 GB, 6 h per node, 10 h episode, 12
engine calls. Code: pristine packs of 292b9bf3 (A) and 64fc0ca1 (B, C),
digests verified in every job. One slot job (4 cores, 16 GB, 11 h) runs
all 48; if it is killed, a continuation job skips every label that has a
meta.json. Expected cost from dev: 5.5-9 min and about 1.8 M input tokens
per session. Sessions run strictly one at a time;
order: questions shuffled with `random.Random(20260924)`, and within each
question the three arms in a permutation drawn from the same generator.
Each session gets a fresh copy of its question's workspace, which holds
one RDKit ETKDG/MMFF starting geometry per species the question names
(hand-built where RDKit cannot place a metal), and nothing else.

**Infrastructure.** A session with zero provider turns, or that ends on
turn_deadline_exceeded or a provider error before any scientific tool
call, is infrastructure, not behaviour: it is re-issued once; a second
failure leaves its cell missing and the question drops out of the paired
tests. A session that ran is never re-run, however weak.

**Packets (blind).** `build_packets.py`: per session, the question, a
mechanically extracted plan (identities, project settings, calculation
and analysis stages, declared observables, terminal state), the Agent's
public text in order, its scientific calls with arguments and a result
status, host notices, and the final text. Never the system prompt, the
context block, reasoning, search calls, schema loads or reference reads.
Every `about_*` name, advisory-document id and the words skill /
advisory knowledge / knowledge entry are replaced by `[reference]` in
every arm. Packet ids are random; the packet-to-arm mapping file's
sha256 is committed here before any packet reaches a grader, and the
mapping stays with me until grading is returned. Four sessions, drawn
with the seed, appear twice under different ids, so the grader's
agreement with itself is measured rather than assumed; only the first
copy of each enters the tests.

**Grading (by the grader the master commissions; nothing in the product
grades).** Per packet, against its question's sealed rubric:
- M, method adequacy of the planned route: 2 adequate; 1 defensible with
  one consequential rubric item missing; 0 a rubric-listed inadequate
  choice or its equivalent.
- S, adequacy statement: 2 says whether the method resolves the effect
  asked about and names the dominant limitation with its direction, as
  the rubric's honest statement does; 1 a generic or partial caveat; 0
  none, or confidence the method cannot support.
- On a control question (a routine method is fully adequate): M = 2 for a
  routine adequate route; S = 2 when it says why the routine method
  suffices, 0 for a false alarm or a refusal; an unjustified escalation
  is flagged O.
- F flags a false statement of fact (invented provenance, a claimed
  result that does not exist).

**Tests (fixed now).** Primary: per question Q = M + S (0-4); paired
difference C - B over questions with both cells; Wilcoxon signed-rank
statistic (zero differences dropped, average ranks for ties) with its
exact null by enumerating every sign assignment, two-sided, alpha 0.05;
reported with the median and mean difference and the sign counts. Secondary: A - B on Q;
M and S separately; O flags on controls, C against B; F flags. Mechanism
(computed by me from events, never shown to the grader): per C session,
which knowledge entries arrived, how (search / exact name), and whether
`about_method_adequacy` arrived before the first accepted
`project_yaml` establish or render; per A session, calls of names the
host cannot serve and searches for the documents.

**Falsifiers.**
- Premise falsified: C - B median <= 0 with Wilcoxon p >= 0.2, while
  `about_method_adequacy` arrived before the first level-fixing act in
  >= 12 of 16 C sessions.
- Delivery falsified, premise untested: that arrival in < 12 of 16 C
  sessions.
- Harm: more O flags on controls in C than in B plus one, or C's M below
  B's on >= 3 questions.
- Success: C - B > 0 with p < 0.05 and no harm.

**Live goals (at most three; bands fixed before submission).** Chosen by
a rule fixed now: among sealed questions whose rubric gives a reference
value and whose adequate plan fits 12 engine calls and 10 h on 32 cores,
the one where the B and C planning sessions differ in a rubric-relevant
method setting (read mechanically from the plans, before grading); it
runs once as a goal in arm B and once in arm C, and a third goal may run
arm C on a control. Each goal's delivered value is graded on physics
against the rubric's reference, with the band and the arm's expected
failure written here, committed, before its `slot_submit`.

## Oracle

Planning sessions: the sealed rubric of each question, applied blind by
the independent grader the master commissions (`GRADER.md` instructions,
kept with the tools). Live goals: the rubric's reference value and the
physics of the delivered number (geometry, arithmetic, constants
registry), never a product verdict alone. Mechanism measures are mine and
come only from typed events and transcripts.

Tools (durable copies on the cluster, /project/xlzhang/jiseung/r10/q3/tools):
run_plans.py (session runner), build_packets.py (blind packets),
mechanism.py, signed_rank.py, make_sealed_plan.py, pack_commit.py
(packs a commit exactly as pack_code.sh packs a checkout; digest checked
equal on a270eca6).

## Sealed material (arrived after 2015c2f3; never committed)

- 16 question folders, 52 files (TASK.md and .xyz files), in the
  worktree's `sealed-questions/` (excluded from git). The master's manifest
  digest is `e5e7585050d13e68`; recomputed here and equal, as the sha256
  of `cd sealed-questions && find . -type f | LC_ALL=C sort | xargs
  shasum -a 256`. Questions are named here only by ordinal (q01-q16).
- All 16 run as written: every folder has its TASK.md and the geometries
  it names. Clarification of the pre-registration, not a change: the
  questions arrived with their own starting geometries, so the RDKit build
  step is not used; each session's workspace is exactly its question's
  .xyz files, copied unchanged (a verification step in the job checks all
  52 files against the manifest and stops the job on any mismatch or
  extra file).
- Seeded order (input: sorted folder names; `random.Random(20260924)`):
  q10, q05, q02, q06, q04, q08, q12, q07, q16, q13, q03, q15, q09, q11,
  q14, q01, each question's three arms in the drawn permutation; the
  48-row plan's sha256 prefix is 06ac75152061672a.
- Nothing under `chemsmart/` changed after 2015c2f3: the arms are the
  ones pinned before the questions were copied in.

## Jobs issued

| job | slot | what | pre-registration | outcome |
|---|---|---|---|---|
| 2149579 | r10-q3-a | batch-dev1: D1 in C, B, A; D3 in C (dev, provider-only) | e7f1723f7b06 | COMPLETED; 4 sessions, exit 0, waiting_for_approval each |
| (next) | slot | live goal g1 = q03 in arm C (64fc0ca1, knowledge on); g2 = q03 in arm B (64fc0ca1, CHEMSMART_AGENT_SKILLS=0); g3 = q02 in arm C (control). make_goal.py: gaussian, orca, pyscf, xtb on cpu; 32 cores, 120 GB (+8 controller), node 6 h, episode 10 h, 12 engine calls, 0 excursions, 2 revisions; granted by claude-researcher-q3-owner-delegated (a delegated approval, not a human decision); each goal's TASK.md and workspace are its sealed question's own files; bands sealed at af4569be... | -- | submitted g1 first, g2 staggered after g1's planning, g3 when a slot frees |
| 2149677 | r10-q3-a | sealed1: the 48 sealed sessions (provider-only), plan 06ac7515 | 34a1e57ab05a | COMPLETED 0:0, 8:13:53 (04:02-12:15 HKT); the job verified both code digests (d3652db7 = 292b9bf3, cdfd90c9 = 64fc0ca1), all 52 sealed files and the plan digest before the first session; 48 of 48 sessions exit 0 |

## Sealed run: host records (read before any grading)

**Infrastructure accounting (pre-registered rule).** 48 of 48 sessions ran
and ended `waiting_for_approval` with a review prepared; provider turns
11-28 per session; observed model `deepseek-v4-flash-0731` throughout.
822 provider attempts succeeded and two failed transiently inside
sessions that continued: one connect timeout in q05-B (13 provider turns
in all) and one rate-limited attempt in q12-C (14), each retried by the
transport. Neither session had zero provider turns or ended on the error,
so neither is infrastructure: nothing was re-issued and no cell is
missing. Input tokens: A 25.9 M, B 39.3 M, C 36.3 M, 101.5 M in all, 18 %
above the 86 M estimate; wall time 8 h 14 min against the 6-7 h estimate.

**Mechanism (from typed events and transcripts; never shown to a grader).**
- C: 16 of 16 sessions loaded advisory knowledge, every load by the
  model's own search (none by exact name, none pushed).
  `about_method_adequacy` arrived in 15 of 16, every time before the
  first accepted `project_yaml` establish or render (arrival at
  transcript messages 6-22, level act at 20-38); the exception, q12,
  loaded conventions and never adequacy. `about_scientific_conventions`
  16 of 16, `about_typed_analysis_contract` 11 of 16. The pre-registered
  delivery falsifier (fewer than 12 of 16) is not met, so the premise is
  tested by the grading.
- A: 0 calls of an advisory-document name the host cannot serve, 0
  searches for the documents: the false sentence cost no tool call; any
  cost it has is in the science, which A - B measures.
- B: 0 knowledge loads, as designed.
- Refused calls summed per arm: A 10, B 15, C 29.

## Packets (built before any grading)

- 52 packets = 48 sessions + 4 duplicates drawn with
  `random.Random(20260924).sample` over the run order; random ids
  (SystemRandom). Location: `sealed/q3-packets/packets/*.md` in this
  worktree, with `sealed/q3-packets/GRADER.md`; `sealed/` is in the shared
  git exclude and nothing there is committed.
- **Packet-to-arm mapping sha256:
  `1da36c5b82f182df87ca1c5ab71389a71e426db1a352c91778030586e04cc8fb`.**
  The mapping is kept by me only (scratchpad, and a mode-600 copy in
  /project/xlzhang/jiseung/r10/q3/private/); it never leaves me before
  grading is returned.
- Built with the redaction as fixed. One presentational line was added,
  identical in every arm: each packet names its question id, so the grader
  can match the rubric (GRADER.md asks for it).
- **Residual leakage, measured.** The fixed redaction replaces reference
  names and document ids in their catalogue spellings; a session's own
  paraphrase survives it. Five phrases only a knowledge-arm session writes
  -- regexes `method[\s_-]adequacy`, `analysis[\s_-]contract`,
  `scientific[\s_-]conventions`, `conventions? (reference|document|entry|text)`
  and the word `advisory`, case-insensitive -- occur in 7 of the 16 C
  packets and in no A or B packet. The redaction token `[reference]`
  itself occurs in 12 of 16 C, 5 of 18 A and 1 of 18 B packets. The packet
  set is not changed after this measurement; instead:
- **Sensitivity analysis, added now, before any grade exists.** The
  primary test (C - B on Q, exact signed-rank) is repeated on the
  questions whose C packet contains none of the five phrases (9
  questions). A primary result that the sensitivity test contradicts is
  reported as leak-dependent. Recommendation to the master: graders are
  not told what the arms are.

## Grades received; live goals selected before any grade was read

- Grades locked by the master: grader 1 (primary) scores.csv sha256
  8da4f147...04ea2, grader 2 (reliability) 8828c38e...9b2af; both recomputed
  equal here, and the mapping's sha256 recomputed equal to 1da36c5b... .
- Live-goal selection and physics bands were written before any grade file
  was opened, into the git-excluded `sealed/q3-live/bands.md` (it names
  sealed content), **sha256 af4569beb62e63bb746e86d0f8de06d4134df4b58039e396210f19cd5b9d7ad1**.
  Outcome: q03 runs as a goal in arm B and in arm C; q02 runs in arm C as
  the control. The file records how the pre-registered rule was applied
  without the rubrics (only questions whose own task states a reference
  value; "rubric-relevant" read as a difference in the level of the energy
  entering the observable), the tie-break it needed (the seeded run order,
  fixed there, not pre-registered), each band, each arm's expected
  failure, and what counts as the effect surviving execution.

## Unblinded result (grader 1 primary; the analysis as pre-registered)

Mapping sha256 recomputed equal to 1da36c5b...; the 48 primary packets
(duplicates excluded) unblinded. Controls, as both graders' rubrics name
them: q02, q05, q09, q13.

Grader 1, per question M/S (A | B | C): q01 2/2|2/2|2/2; q02 2/2|2/2|2/2;
q03 2/1|1/1|2/1; q04 2/2|2/2|2/2; q05 2/2|2/1|2/2; q06 1/1|2/2|1/1;
q07 2/1|1/2|0/0; q08 0/1|0/1|1/1; q09 2/2|2/2|2/1; q10 0/1|1/1|1/0;
q11 2/2|2/2|2/1; q12 2/2|2/2|0/1; q13 2/2|2/2|2/2; q14 1/1|2/2|2/1;
q15 1/1|0/0|0/0; q16 2/0|2/1|2/1. Means (M, S, Q): A 1.56, 1.44, 3.00;
B 1.56, 1.56, 3.13; C 1.44, 1.13, 2.56.

- **Primary, C - B on Q:** 3 up, 7 down, 6 tied; median 0, mean -0.56;
  exact two-sided signed-rank W+ = 12 (n = 10), p = 0.145.
- C - B on M: 2 up, 3 down, p = 0.75. C - B on S: 1 up, 7 down, p = 0.0625.
- **A - B on Q** (the false sentence): 3 up, 4 down, mean -0.13, p = 0.77.
- O flags: none in any arm, by either grader. F flags (false statements of
  fact, all misremembered literature values): grader 1 A 3, B 2, C 3;
  grader 2 A 1, B 0, C 1.
- **Sensitivity** (the 9 questions whose C packet carries none of the five
  arm-revealing phrases): C - B mean -0.56, 3 up, 4 down, p = 0.44 -- the
  same direction; the primary result is not leak-dependent.
- **Reliability**, grader 2 against grader 1 on the 48 primary packets: M
  exact agreement 0.917, linear-weighted kappa 0.881 (quadratic 0.920); S
  exact 0.875, kappa 0.823 (0.867); Q exact 0.812; O 1.000; F 0.875.
  Grader 2's own C - B on Q: mean -0.38, p = 0.27, same direction. Both
  graders scored all four duplicate pairs identically, which they report
  recognising as byte-identical bodies: it cannot distinguish consistency
  from recognition.

**Falsifiers, applied as written.**
- Success (C - B > 0, p < 0.05, no harm): not met.
- Premise falsified (median <= 0 AND p >= 0.2 AND adequacy read before the
  level act in >= 12 of 16): median 0 and 15 of 16 hold, p = 0.145 does
  not, so it does not fire by its letter -- because the data lean past the
  null toward harm, which that falsifier was not written for.
- Delivery falsified (< 12 of 16): not fired (15 of 16).
- **Harm: fired.** C's M is below B's on 3 questions (q06, q07, q12), the
  registered threshold; O flags on controls 0 against 0.

**Reading.** With the knowledge demonstrably read before the level was
chosen in 15 of 16 sessions, reachable method-adequacy and convention
knowledge did not improve the method choice or the adequacy statement of
`deepseek-v4-flash-0731` on these open questions; the point estimate is
negative, carried by the adequacy statement, and the registered harm
threshold was met. The master's premise (that reachability would change
choices and qualifications for the better) is not supported; the false
sentence itself cost nothing measurable.

## Status

Phase 3: tests done (above). Next: the three pre-registered live goals
(q03 in B and in C, q02 in C), bands sealed at af4569be... before any
grade was read; then the r10-integration merge, the gates, the report.
