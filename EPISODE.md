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

## Premise check on the base tree (provider-free)

- `inspect_run` with a program and an artifact returns selector *names*
  (available, requestable), each selector's structural state and
  electronic provenance, atom metadata and the level. It returns no
  value. `ResultReaderV1.available_selectors` reads every accessor to
  learn what resolves and discards what it read.
- A workspace result (the form every sealed task takes: finished outputs
  plus a question) carries no run sensor: the anomalies an executed run
  raises (`scf.reference_unstable`, `spin.s2_deviation_ge_0.2`,
  `stationary_point.*`) are computed only for runs the goal executed. A
  session learns a diagnostic's value only by extracting it.

## The lever under test (P), and how it is switched

Commit 29adc265: with `CHEMSMART_AGENT_INSPECTION_VALUES` on (off by
default), `inspect_run(program, artifact_id)` also returns `values`:
every requestable selector's value and unit as `extract_result_quantities`
returns it, read through the same function, floats to ten significant
digits, a vector past 64 numbers by its ends and a matrix past 64 cells by
its shape (each cut labelled). It mints no receipt. Off, the reply is the
base tree's. Nothing else differs: the tool surface, the catalogue and the
system prompt are byte-identical in both switch states (to be verified by
digest before freezing).

## Development (local, my own tasks from archived real outputs; never sealed)

Workspace = the task's finished outputs only; `chemsmart agent goal
--reading-turn`, envelope gaussian/orca/pyscf/xtb cpu with
`max_engine_calls: 0`, `--max-revisions 0`, granted by
claude-researcher-q17-owner-delegated. Model deepseek-v4-flash-0731.

- dA (O2 at 1.2075 A, PySCF B3LYP/def2-SVP closed-shell singlet and UKS
  triplet single points; "what vertical singlet-triplet gap, does it
  reproduce 0.98 eV, how much weight can it carry"). The singlet's own
  record: internal stable (+2e-6 Eh), external RKS->UKS unstable
  (-0.0926 Eh), real->complex unstable (-0.0383 Eh).
  - dA-S-1 (base behaviour, switch off; 29adc265's parent tree): planning
    0.67 M input tokens, 324 s; reading 0.29 M, 197 s. It inspected both
    results, extracted `scf_stability_internal` ("stable") for both and
    wrote "Both SCF solutions are stable" (transcript msg 19) -- false of
    the singlet's record. Delivered 1.71 eV, attributed the 0.73 eV excess
    to static correlation from general knowledge. The reading extracted
    14 selectors per result, none of them stability, and added "the gap
    carries no spin-contamination error". Settled achieved.
  - dA-P-1 (switch on, 29adc265): the dominant uncertainty became "the
    singlet is an unstable restricted closed-shell determinant ...
    Evidence: scf_stability_external = unstable with lowest eigenvalue
    -0.0926 Eh", and the finding names "the unstable restricted
    closed-shell representation". One run each: an observation, not a
    rate.
- dC (planar NH3 B3LYP/def2-SVP Hessian, PySCF, one imaginary mode at
  -829.9 cm-1; "what ZPVE and N-H stretches for NH3").
  - dC-S-1: the frequencies are the requested quantity, so the imaginary
    mode sits inside the headline extraction; the session named it
    (umbrella/inversion, all H in phase) and stated that the Hessian is not
    at the C3v minimum; its reading added the zero dipole as corroboration.
    A deciding quantity inside the headline read is not unnamed in effect:
    such a task cannot separate S from P.

## Status

- 2026-09-24: brief read; base verified; read CONDUCT.md, the RSL README
  and its five lessons, Q3's, Q6's and Q13's merges and final EPISODE.md
  files, the four charter topics the brief names, and the reading
  surfaces in my radius (`_inspect_run`, `_inspect_result_selectors`,
  `_inspect_run_outcome`, their tool specs, the catalogue's reading
  entries, `_reading_context`, `wake.reading_turn`, `_system_prompt`).
  No provider session and no cluster job issued yet.
