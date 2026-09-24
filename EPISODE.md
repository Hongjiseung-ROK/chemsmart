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
  dimension. Three acts, the obvious one is the right one.
- A category: declare unit `category` -> extract a word (or, since
  0fea11cb, an integer) -> claim it under an id *other than* the
  declared one (a word under the declared id is refused,
  `claim.a_word_delivers_no_declared_number`, even when the declaration
  is the category) -> `record_scientific_decision.findings` with
  `answers_observable_id` resting on `<claim> == <value>`. Four acts; the
  obvious third act is refused, and the number-shaped mistake (a 0/1
  claim under the category id) is accepted at claim time and only
  called undelivered at completion.
- What may answer: any `==` over a text or integer claim
  (`_categorical_answer`, tool_runtime.py ~7785). The host does not
  check that the answering selector bears on the question (Q1's
  accepted residual, #9): `functional == 'B3LYP'`, `charge == 0` or a
  validation verdict `== 1` answer a stability question alike.
- Stationary-point questions (minimum / saddle / neither) have no
  host-read word at all: the host's own judgement lives in the node
  terminal state and in `characterise_stationary_point`'s integer
  `order_claimed`, neither claimable; the routes left are a model-authored
  validation rule whose verdict is an integer 0/1 (whose meaning depends
  on the rule's direction), or a count.

## Falsifiers of the premise (from the brief)

- A census of every categorical declaration in the archived goals
  (typed: unit `category`; proxy: a yes/no or which-of question declared
  as a number; encoded: a yes/no answer carried by a validation rule the
  session expected to fail) finds failures rare, or finds that every
  model misuse is already routed to the honest form by the current
  surface -> report and end.
- Any changed host word is replayed on the commit that produced its
  record; the base must reproduce the archived word byte for byte
  before a repaired word is believed.

## Oracle

Host records only: session event streams (declarations, claims,
findings, tool failures with their gate ids, completions), goal ledgers
(settlements), workspace records; public transcripts for replays. A
behavioural statement needs a transcript and a control.

## Census scope (named directories; nothing under r10/m*, r10/master,
r10/q6/goals, r10/q6/sealed-live-goals.tar, r10/q3/private)

CUHK /project/xlzhang/jiseung: r8/, r9/, r10/q1 q2 q3/goals q4 q5 q7-q22
(q17 is a running study, read-only, counted as archived-so-far), and the
2026-09-19..22 campaign directories at the top level. ax41 mirror:
~/developer/chemsmart-hetzner-mirror (2026-09-14 slice and the campaign
slice).

## Status

- step 0: brief read and verified; base verified; AGENTS.md, CONDUCT.md,
  RSL README and lessons, the two charter topics, the Q1/Q13/Q19/Q22
  merges and EPISODE.md histories read; gate open.
- step 1 (census): starting.
