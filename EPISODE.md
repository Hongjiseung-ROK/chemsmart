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
| 2149677 | r10-q3-a | sealed1: the 48 sealed sessions (provider-only), plan 06ac7515 | 34a1e57ab05a | running; the job verified both code digests (d3652db7 = 292b9bf3, cdfd90c9 = 64fc0ca1), all 52 sealed files and the plan digest before the first session |

## Status

Phase 2: waiting on job 2149677 (the sealed run, plans/sealed1, 48
sessions, strictly sequential; about 6-7 h). Then: infrastructure check of
every session (zero provider turns or a provider error before any
scientific call is re-issued once in a continuation job), packets, the
mapping digest committed here, hand-back "packets ready". Grading is the
master's.
