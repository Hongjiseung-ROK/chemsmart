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

## Status

Phase 1 (provider-free and dev): arms under construction; the
pre-registration (N, grading, falsifiers) is written before the sealed
questions are copied in.
