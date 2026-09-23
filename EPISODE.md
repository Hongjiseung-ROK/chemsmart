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
- Batch dev1 on the cluster (D1 in C and B, D2 in C) validates the
  cluster runner; it is development, not the sealed test.

## Arms (what the model reads, measured, not asserted)

Initial request digests from `arm_digest.py` (host_search, empty context;
sha256 prefixes):

| arm | code | CHEMSMART_AGENT_SKILLS | catalogue | tools | system prompt |
|---|---|---|---|---|---|
| A false sentence, no access | 292b9bf3 | 1 | b233c12f (62) | 1295775e | 1fd85c2d (13,632 B) |
| B no sentence, no access | 292b9bf3 or the arm commit | 0 | b233c12f (62) | 1295775e | fda60dcd (10,969 B) |
| C honest sentence, real access | the arm commit | 1 | 584c866e (65) | 1295775e | 58f9f2e3 (12,826 B) |

B is byte-identical whichever commit serves it (same catalogue, tools and
prompt), so A-B is a contrast inside the base commit and B-C one inside
the arm commit; A differs from B only by the false sentence, C from B
only by the honest sentence and three deferred catalogue entries. (C's
row is at a270eca6; the sealed arm commit's row is recorded when it is
fixed.)

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
engine calls. Code: pristine packs of 292b9bf3 (A) and the arm commit (B,
C), digests verified in every job. Sessions run strictly one at a time;
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
mapping stays with me until grading is returned.

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

## Jobs issued

| job | slot | what | pre-registration | outcome |
|---|---|---|---|---|
| 2149579 | r10-q3-a | batch-dev1: D1 in C, B, A; D3 in C (dev, provider-only) | e7f1723f7b06 | running |

## Status

Phase 1 (provider-free and dev): pre-registration drafted; cluster dev
batch running; merge of r10-integration and the suite before hand-back.
