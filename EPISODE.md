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

## Status

Phase 1 (provider-free): premise verified; design and pre-registration
in progress.
