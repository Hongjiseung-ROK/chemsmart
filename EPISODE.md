# R10 episode Q17 -- evidence the Agent is not told to look at

Base SHA: `2c1050c74cc31c76d6f51970b9b03c4e37e7cf50` (verified with
`git rev-parse HEAD` as the first action of the episode, 2026-09-24).
Brief: `scratchpad/q17/BRIEF.md`, sha256 `ea75c86e79a326da...` (verified).

Researcher model: claude-opus-5-5[1m]. Agent under study:
`deepseek-v4-flash-0731` through `alibaba-token-plan` (reasoning effort
xhigh, 1M context, the profile both the Mac and CUHK select). Every
behavioural statement below is about that model.

## The question, as I currently understand it

When the hub serves a quantity a program printed, and that quantity
decides whether a headline answer is sound, does the Agent use it to
reach a better-founded conclusion when the task does not name it? If
serving alone changes nothing unnamed, what does: how a completed result
presents what it holds when a session reads it, the reading turn, or
nothing within this model's reach?

Three things are mixed in that question and are kept apart:

1. Availability: whether the quantity can be read at all (served or not).
2. Attention: whether a session that could read it does read it, when the
   task names something else.
3. Use: whether a session that read it changes its conclusion, and does
   not raise an alarm on a benign value.

## Priors to verify (from the brief), not conclusions

- Q3 (25f158d0): reachable prose knowledge did not improve plans; the
  harm threshold fired (C-B 3 up / 7 down, p = 0.145).
- Q13 (3a225067): served stability eigenvalues changed conclusions on two
  byte-identical tasks that *named* stability (o2r, dans; one run each).
- Q6 (2e6b49e0): sessions that opened a per-root <S^2> selector found
  spin contamination; those that did not, missed it. The reading turn
  (`--reading-turn`, off by default) raised planted-phenomenon
  sensitivity 0/11 -> 2/11 (McNemar p = 0.5): D earned, C not.
- Q13 again: the Agent compared stability eigenvalues across the
  normalisations the declarations state, and read a curvature spread as
  kcal/mol.

## Falsifiers of the premise (from the brief)

- (F1) With the quantity served, the Agent concludes no differently than
  without it, the quantity demonstrably reachable. Reported with what the
  sessions did open.
- (F2) The Agent never requests the unnamed quantity in either arm: then
  availability is not the bottleneck, and a surface lever for attention is
  mine to design and test as a further arm, or I report that none moved
  this model.

## Status

- 2026-09-24: brief read; base verified; read CONDUCT.md, the RSL README
  and its five lessons, Q3's, Q6's and Q13's merges and final EPISODE.md
  files, the four charter topics the brief names, and the reading
  surfaces in my radius (`_inspect_run`, `_inspect_result_selectors`,
  `_inspect_run_outcome`, their tool specs, the catalogue's reading
  entries, `_reading_context`, `wake.reading_turn`, `_system_prompt`).
  No provider session and no cluster job issued yet.
