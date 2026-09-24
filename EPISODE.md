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
base tree's. Nothing else differs, measured (arm_digest.py, both switch
states): catalogue ed4699bd... (62 entries, the digest the dev sessions
recorded), tool definitions e4d128ee... (38), goal system prompt
e6d02186... (10,516 chars), selector lists 378e8123....

## Arms, pinned

| arm | code (commit; pack digest) | switch | what it is |
|---|---|---|---|
| S | 29adc265; b471fba5530e2e5f... | `CHEMSMART_AGENT_INSPECTION_VALUES=0` | today's product: the inspection reply names selectors |
| P | 29adc265; b471fba5530e2e5f... | `=1` | the lever: the reply also shows each selector's value |
| U | e77a0b47 on side branch `q17-arm-unserved` (parent ac3079bb, whose chemsmart/ is 29adc265's); 5d5265900b3a843e... | `=0` | the quantities R10 Q13 began to serve are not served |

U hides, per program, exactly the selectors merge 3a225067 added: PySCF
`scf_stability_real_to_complex` and the three
`scf_stability_*_lowest_eigenvalue`; Gaussian
`wavefunction_stability_lowest_eigenvalue`,
`wavefunction_stability_rotation_space`, `solvation_nonelectrostatic_energy`,
`solvation_model`, `solvent`, `molecular_volume`,
`electronic_spatial_extent`, `hirshfeld_atomic_spin_populations`; ORCA
`t1_diagnostic`, `mayer_bond_orders`, `mayer_free_valence`,
`hirshfeld_atomic_spin_populations` -- accessors, job-type declarations,
states, provenance and selector declarations, so every organ agrees they do
not exist. Parsing is untouched. Measured on U: catalogue 2e8875c4...,
tools 8082518f..., the same system prompt e6d02186...; the selector lists
shrink by exactly those names (Gaussian 72 -> 64, ORCA 87 -> 83, PySCF
76 -> 72). `tests/agent` on U: 4 failed, 3049 passed -- the word-list
witness (the new literal), my own inspection-values test, the capability
marker ladder and Gaussian's SMD-term witness, each because a hidden
selector is gone; no goal-loop or session test fails. U is never merged.

Packs: `pack_commit.py` (reproduces pack_code.sh: equal digest b471fba5 on
the clean checkout) -> CUHK /project/xlzhang/jiseung/r10/q17/code-29adc265
and code-e77a0b47, each verified there with verify_code.py (equal digests,
0 AppleDouble files).

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
  - dC-P-1: the same finding (the Hessian describes the inversion saddle;
    the ZPVE excludes the imaginary mode), with an independent ZPVE path.
- dB (Fe(III) aquo, ORCA M06-2X/def2-SVP opt of doublet, quartet, sextet;
  the doublet's <S^2> 1.705 against 0.75; the doublet and sextet stopped
  at the 50-cycle limit; "which spin state is the ground state, how far
  above lie the others").
  - dB-S-1 (switch off): unprompted, the planning session extracted
    `spin_square`, `converged` and the energy trajectory of all three
    results, and its uncertainties say "The doublet result shows
    significant spin contamination, <S^2> = 1.70 vs the ideal 0.75" and
    that the sextet and doublet carry converged = 0 (the doublet still
    drifting ~0.1 kcal/mol, negligible against a 75.8 kcal/mol gap).
    Sextet ground state; quartet +41.4, doublet +75.8 kcal/mol. Settled
    achieved_with_observations. This model asks for <S^2> and the
    convergence flag without being told: for these long-served
    diagnostics availability and attention are not the bottleneck here.
  - dB-P-1 (switch on): the same conclusion, a little sharper ("heavily
    spin-contaminated (S^2 = 1.70 vs 0.75, effective multiplicity 2.80)
    ... only qualitatively meaningful"); settled achieved. Planning cost
    1.09 M input tokens and 16 turns against S's 0.55 M and 11 (dA: 1.16 M
    against 0.67 M): the lever roughly doubled the planning session's
    input in both pairs, through more turns rather than larger replies.

- dD (converged water B3LYP/def2-SVP Hessian, PySCF; a control): S and P
  both extracted the frequencies and mode participation, no alarm; settled
  achieved both.
- dF (dA's question on Gaussian 16 logs: RHF -> UHF instability printed as
  a verdict word, served long before Q13): S extracted
  `wavefunction_stability_verdict` for both results and wrote that the gap
  "can carry only qualitative weight: the singlet restricted solution is
  externally unstable"; P extracted the verdict and the eigenvalue.
- dE (water CCSD(T)/cc-pVDZ, ORCA, T1 0.0059; a control): S and P both
  extracted T1 and called it benign ("confirms a securely single-reference"
  wavefunction, P); no alarm.

Development, read together (n = 1 per cell, 11 local goals and the 9 of
hc1; not evidence for the sealed question): where the base arm already
asks for the deciding quantity (dB's <S^2> and convergence flag; dC's
frequencies, which are the headline; dF's and hc1-dA's stability verdict
word), P changes little; where it asked for the wrong one of several
related questions (dA-S-1: `scf_stability_internal`, "stable", of the
three the result answered), P put the right one in front of it. The base
rate of S reading a long-served diagnostic unprompted is high on these
textbook systems, which is why the recently- versus long-served split is
reported. Cost over the 21 goals (12 local, 9 hc1): 1.06 M input tokens
and 507 s of provider time per goal (mean; max 1.81 M, 776 s); 17 of 21 had
a reading. The local batch ended 14:54 UTC with dE-P-1 (achieved); no
development process remains.

A second host-error instance: dF-P-1 settled returned_to_human on
"planned termination requires the latest workflow draft" after its
decision was recorded -- 3 of 20 finished goals so far (P 2 of 8, U 1 of
3, S 0 of 9).

## hc1 -- the harness on the cluster with the pinned arms (pre-registered before submission)

Purpose: run the exact harness the sealed run will use -- both code packs,
`run_sessions.py` (sha256 9c71634a...), the analysis envelope (b72e5e03...),
the job scripts (a ccd4e843..., b a19b4bbe...), the CUHK environment -- on
three of my own development tasks before any sealed material exists, so a
harness defect costs development sessions, not sealed ones. Run set
/project/xlzhang/jiseung/r10/q17/hc1: tasks dA (O2 PySCF), dB (Fe(III)
aquo doublet/quartet/sextet ORCA), dE (water CCSD(T)/cc-pVDZ ORCA, a T1
control); arms S, P, U, one goal each, 9 goals, plan sha256 1d431bd6...,
dealt to slots a (5) and b (4), one goal at a time per slot, 4 cores and
16 GB, 2 h each.

Mechanics, each pass/fail:
- both packs verify on the node (the job stops otherwise) and each arm
  imports chemsmart from its own pack;
- every goal ends with a `meta.json`, at least one provider turn, observed
  model deepseek-v4-flash-0731 and a settlement word;
- P's inspection replies carry `values`; S's and U's carry none;
- U's inspection reply on dA's singlet lists no
  `scf_stability_*_lowest_eigenvalue` and no `scf_stability_real_to_complex`,
  and on dE's result no `t1_diagnostic`; S's and P's list them;
- packets build from the run set with a mapping digest, and no packet
  carries an artifact id, a run id or a 64-hex digest.

Behaviour, reported and never scored (development): whether P's conclusion
on dA cites the singlet's instability, on dB the doublet's <S^2> or the
unconverged optimisations, and whether any arm raises an alarm over dE's
T1 of 0.006.

### hc1 read (CUHK 2152986 COMPLETED 0:42:51, 2152987 COMPLETED 0:35:02; records tar sha256 1cb6be27...)

Every pre-registered mechanic PASSED (check_hc1.py over the fetched
records):
- both jobs printed each arm's import from its own pack and the expected
  digests (b471fba5..., 5d526590...), and stopped on neither;
- 9 of 9 goals ended with `meta.json`, 8-31 provider turns, observed model
  deepseek-v4-flash-0731 only, and a settlement word; no infrastructure
  ending;
- P's 5 inspection replies carried `values`; S's 12 and U's 11 carried none;
- U's replies on dA listed no stability eigenvalue and no real -> complex
  selector, and on dE no `t1_diagnostic`; S's and P's listed them;
- 15 packets built (9 conclusion, 4 later reading, 2 duplicates), mapping
  digest printed, no artifact id, run id or 64-hex digest in any packet.

Two findings the check made, both before any sealed task:
- A packet-tool defect, mine, repaired: two goals (dA-o2gap-U1,
  dB-fe3spin-P1) wrote no `session_stream_recorded` ledger row, and the
  first packet builder found planning sessions only through that row, so
  their conclusion packets were empty. Sessions are now found on disk (see
  Packets).
- A host defect, found and left (Q13 found it; the goal loop's
  termination and the runtime event store are Q16's radius): those two
  goals settled `returned_to_human` with "cycle 1, planning session:
  planned termination requires the latest workflow draft" after their
  sessions had recorded claims and a decision; no reading turn follows
  such an ending. It struck S0/P1/U1 of 9 here. In the sealed run it
  removes readings, not conclusions; the settlement words per arm are
  reported from host records.

Development behaviour (one goal per cell, not evidence): dA -- S and U
both extracted the external stability word ("unstable": a long-served
verdict, not hidden by U) and tied the gap's weight to it; P extracted the
external eigenvalue and rotation space as well. dB -- S extracted
`converged`, `effective_multiplicity` and the energy trajectories; U,
before its reading, extracted neither <S^2> nor the effective
multiplicity, and its reading added the doublet's contamination. dE (T1
0.0059, a control) -- S and P extracted `t1_diagnostic` and called it
benign ("below the usual 0.02 single-reference warning threshold"); U,
which could not read it, called CCSD(T) "the gold-standard single-reference
method" from general knowledge; no arm raised an alarm (hc1 packets,
researcher's read).

## Pre-registration for the sealed tasks (written before any sealed task is seen)

### What is compared

Three arms (table above) and, inside every goal, the reading turn: every
sealed goal runs with `--reading-turn`, so each goal yields two paired
conditions -- the goal before its reading (everything recorded before
`reading_opened`, and the word it held) and the goal with its reading
(Q6's paired design). The reading turn's text and context are unchanged
from the base tree. A sealed task whose deciding quantity is not in U's
hidden list has U = S in what is served, and enters the S - U contrast as
long-served.

### Sessions and N

For every released task: S x3, P x3, U x1 goals -- 7 per task, N = 7T
goals for T released tasks (T = 12-16: 84-112 goals, fixed once T is known
and before the first sealed session). Each goal:
`chemsmart agent goal --reading-turn --max-revisions 0 --initial-decision
approve --dispatch local`, envelope gaussian/orca/pyscf/xtb cpu with
`max_engine_calls: 0` (analysis only; sha256 b72e5e03...), granted by
`claude-researcher-q17-owner-delegated` (a delegated approval, never a
human decision); the task's TASK.md verbatim, outside the workspace; the
workspace is exactly the task's released files (every file but TASK.md and
any rubric). Model deepseek-v4-flash-0731 via alibaba-token-plan (the
cluster's agent.yaml), on CUHK compute nodes inside r10-q17 slot jobs (4
cores, 16 GB), `CHEMSMART_CONFIG_DIR=/project/xlzhang/jiseung/r10/config`,
server CUHK, runner `run_sessions.py`. Order: `make_plan.py` shuffles the
7T rows with `random.Random(20260925)` over the sorted task folder names
and deals them alternately to slot a and slot b; each slot runs one goal at
a time (at most two of my sessions at once, a Slurm fact).

Infrastructure, never behaviour: a goal with zero provider turns, a
session whose last provider attempt ended on `turn_deadline_exceeded`, or a
goal the runner stopped at its 3600 s cap. It is re-issued once (label
`-retry`); a second failure leaves the cell missing and its task drops out
of the paired test that needs it. A goal a killed job interrupted has no
`meta.json`; it is kept as evidence and re-run. A goal that ran to its end
with provider turns is never re-run, however weak.

### Packets (blind), built before any grade exists

`build_packets.py` (sha256 acd91e4d...): per goal a *conclusion* packet
(the question; what the sessions before the reading read from the results,
with values; what they computed, claimed and recorded; their public words
in order) and, for S and P goals where a reading ran, a *later reading*
packet (the question, the answer already delivered, what the reading read,
claimed, recorded and said). U's readings are not packaged. The sessions
before the reading are every session stream in the goal's workspace except
the one `reading_recorded` names (not the ledger's
`session_stream_recorded` rows, which a goal settled on a host error does
not write). The host's settlement word is not in a packet: it is the
host's, and on a host error it says nothing about the recorded science; it
stays in the mapping. (Both changed after hc1, before any sealed task: the
first draft read planning sessions from `session_stream_recorded` and
printed the held word and reasons, which gave two hc1 goals empty
conclusion packets.)
Never in a packet: the system prompt, the context, reasoning, any tool
reply (inspection replies are what S and P differ by), searches, schema or
reference loads, digests, artifact or run ids (results are "result A/B/..."
in sorted id order), the arm. "reading turn" is redacted to "later
session". Six conclusion packets drawn with `random.Random(20260925)`
appear twice under new ids (self-agreement). Packet ids are random
(SystemRandom); the mapping's sha256 is committed before any packet
reaches a grader.

Leakage is measured before grading (`leak.py`) and never used to change a
packet: P-revealing phrases (values said to come from an inspection),
U-revealing phrases (a hidden selector said to be unavailable), a hidden
selector's name. The primary is repeated on the tasks whose P and S
conclusion packets carry no P-revealing phrase (sensitivity). A residual
leak no phrase list measures, stated now: a P session can cite a value it
saw on inspection and never extracted, so its words may carry numbers its
"read" section lacks; GRADER.md tells graders that a value missing from
the reads is not false for that reason, and graders are not told what the
arms are.

What U does not undo, stated now: U hides the selectors 3a225067 *added*.
Q13's parser repair that made Gaussian's long-served
`wavefunction_stability_verdict` read "RHF -> UHF instability" (a54aaadf)
is parsing and stays, so a Gaussian RHF -> UHF verdict word is served in
U; so are PySCF's three stability words other than real -> complex.

### Grading

Two independent graders the master commissions, with GRADER.md (sha256
709704be...) and the writer's rubrics. Per packet: Y 0/1/2 (soundness of
the conclusion with respect to the deciding quantity: 2 needs the rubric's
consequence tied to the deciding quantity or accepted equivalent evidence;
on controls 0 is a false alarm), F (false statements of fact about the
results; a value absent from the packet's reads is not false for that
reason), X (alarms raised on quantities the rubric shows benign, on any
task), H (headline computed correctly), one sentence of justification.
Grader 1 is primary; grader 2 gives agreement (exact, linear- and
quadratic-weighted kappa on Y) and its own direction. Task kind
(phenomenon or control) and each task's deciding selectors are taken from
the writer's rubrics after grading.

### Primary outcome and test

On phenomenon tasks, the session-level Y of P's and S's conclusion packets
(three each per task). Test: two-sided task-stratified permutation test --
statistic the sum over tasks of mean Y(P) minus mean Y(S); under the sharp
null that the arm changes no conclusion on these tasks, arm labels are
permuted within each task; 100,000 draws with `random.Random(20260925)`;
p = (hits + 1) / (draws + 1); alpha 0.05. Reported with the mean per-task
difference and the per-task sign counts (`analysis.py`, sha256 f055ef9f...). The inference is
about these sealed tasks; the task-level exact Wilcoxon signed-rank on the
per-task mean differences (zeros dropped, average ranks) is reported beside
it as the across-task generalisation, never as the primary.

Changed before any sealed task was seen (the first draft named the
task-level Wilcoxon primary): with 8 phenomenon tasks (a 12-task release)
and three replicates, simulated power for a lever moving a task's success
rate from 0.2-0.3 to 0.7-0.8 is 0.38-0.65 for the Wilcoxon and 0.71-0.84
for the stratified permutation test (power_sim2.py, 150 simulations per
cell); the Wilcoxon discards the within-task replicates the design pays
for.

### Milestone C -- all three

(a) the primary has p < 0.05 and a positive mean; (b) P has at most one
more false alarm (Y = 0) than S among the control conclusion packets; (c)
the phenomenon sound-and-bound rate (share of conclusion packets with
Y = 2) gains more under P than the control false-alarm rate under P.

### Harm -- any one fires, and the switch stays off

(h1) the primary's mean is negative with two-sided p < 0.2; (h2) P has two
or more false alarms more than S among the control conclusion packets;
(h3) false statements of fact summed over conclusion packets exceed S's by
3 or more; (h4) alarms on benign quantities (X) summed over conclusion
packets exceed S's by 3 or more. No "P below S on k tasks" rule: with three
noisy replicates per arm a null lever puts P below S on about half the
untied tasks.

### Secondary (reported; never a milestone on its own)

- Serving: S - U on the phenomenon tasks whose deciding quantity U hides
  (S's mean of three against U's one), exact Wilcoxon, descriptive.
- Where the lever acts: the primary's per-task differences split by
  whether the deciding selector is in U's hidden list (recently served) or
  not (long served), descriptive. Development already showed this model
  asking for <S^2> and the convergence flag unprompted (dB-S-1), so a
  long-served deciding quantity may leave little for P to add.
- Reading: a combined Y per goal = max(conclusion, reading) on phenomenon
  tasks and min(...) on controls (a false alarm in either counts); S+R vs
  S and P+R vs P over tasks, exact Wilcoxon; the reading's cost.
- Mechanism (`mechanism.py`, from typed events, never shown to graders),
  per session: was the result carrying the deciding quantity inspected;
  were values shown (P); was the deciding selector extracted.
- Cost per arm: provider requests, input tokens, wall seconds.

### Falsifiers, fixed now

- F1 (serving alone changes nothing unnamed): S - U mean <= 0 or p >= 0.2
  on the hidden-quantity phenomenon tasks, while the deciding selector was
  requestable in S's inspection replies.
- F2 (availability is not the bottleneck): the deciding selector extracted
  in <= 10 % of S's phenomenon planning sessions.
- Lever null: P - S mean <= 0 or p >= 0.2 while the deciding values were
  shown to >= 80 % of P's phenomenon planning sessions -- presentation does
  not move this model.
- Delivery failure (the lever untested, not a null): the deciding values
  shown to < 50 % of P's phenomenon planning sessions.

### Power, computed before the material (power_sim.py)

With 12 phenomenon tasks and a binary proxy of Y, the task-level Wilcoxon
reaches p < 0.05 with probability 0.77-0.93 at three replicates per arm
when the lever moves a task's success rate from 0.2-0.3 to 0.7-0.8,
0.53-0.81 at two replicates and 0.19-0.38 at one (Q6's C failed at one
replicate: McNemar p = 0.5); with 8 phenomenon tasks it falls to 0.34-0.62
at three replicates, which is why the primary is the stratified
permutation test (0.71-0.84 at 8 tasks; 0.89-0.98 at 12, where the
Wilcoxon gives 0.79-0.96). A moderate lever (0.2 -> 0.5) is detectable less
than half the time at 8 tasks (0.30-0.43) and about half at 12
(0.43-0.63): a null here says the lever is not large, not that it is
absent.

## Frozen for the sealed tasks

Nothing below changes after this section is committed and before every
sealed goal has settled.

- Arms: S and P = 29adc265 (switch 0 / 1), U = e77a0b47 (side branch
  `q17-arm-unserved`); packs verified on CUHK at r10/q17/code-29adc265
  (b471fba5...) and code-e77a0b47 (5d526590...).
- Harness and analysis (sha256 prefixes; durable copies in
  /project/xlzhang/jiseung/r10/q17/tools, identical): run_sessions.py
  9c71634a..., sessions_job.sh 4ca18cde..., render_job.py 1952b26a...,
  make_plan.py 2b512954..., stage_sealed.sh 8abbca83..., envelope
  b72e5e03..., build_packets.py acd91e4d..., leak.py 39663ad6...,
  mechanism.py 39284fcf..., analysis.py f055ef9f..., GRADER.md
  709704be..., fetch_runset.sh acfbf889..., pack_commit.py 96ba81cd....
- Run: one run set `sealed1`, staged by stage_sealed.sh from the released
  task folders (TASK.md and program outputs only), plan by make_plan.py
  (seed 20260925), two slot jobs (a, b), 4 cores / 16 GB / 12 h each.
- Expected cost (from the 20 development and hc1 goals): about 1.0 M input
  tokens and 8-9 min of provider time per goal, readings on about three
  goals in four. For T tasks: 7T goals and about 12.6T sessions -- 84
  goals, ~150 sessions, ~86 M input tokens, ~6.5 h per slot at T = 12; 112
  goals, ~200 sessions, ~115 M input tokens, ~8.5 h per slot at T = 16.
- Known host error that will recur (Q16's radius, found and left): about
  one goal in seven settles returned_to_human on "planned termination
  requires the latest workflow draft" after its decision is recorded; its
  conclusion is graded, it has no reading, and the settlement words per
  arm are reported.

## Re-pin (2026-09-25, on the master's word, before any sealed session)

Reason, in one sentence: r10-integration moved to a7bc02e0, whose Q16 H1
repairs the "planned termination requires the latest workflow draft" loss
that took 3 of my 20 development goals' readings, so the arms are rebuilt
on it and nothing else in the pre-registration changes.

| arm | commit | pack digest (verified on CUHK) | switch |
|---|---|---|---|
| S | 55729bc4 = merge of a7bc02e0 into this branch (chemsmart/ = a7bc02e0 + the lever, 121 lines of tool_runtime.py) | 0144da205957dd4a... (r10/q17/code-55729bc4) | 0 |
| P | 55729bc4 | 0144da205957dd4a... | 1 |
| U | 84223707 on `q17-arm-unserved` = merge of 55729bc4 into the side branch (chemsmart/ = 55729bc4 + the unserve block, 84 lines of result_readers.py) | 6b48ed8a785f570b... (r10/q17/code-84223707) | 0 |

Checks on the re-pinned trees: tests/agent on 55729bc4 3098 passed, 0
failed; on 84223707 5 failed, 3081 passed -- the four hidden-selector
failures recorded before plus one new test from Q16's merge
(test_a_partial_delivery_ends_its_session replays o2r's extraction of
`scf_stability_external_lowest_eigenvalue`, which U hides). Surface digests
are unchanged by the re-pin: S and P catalogue ed4699bd..., tools
e4d128ee..., prompt e6d02186... in both switch states; U catalogue
2e8875c4..., tools 8082518f..., prompt e6d02186...; U's reader serves none
of the hidden names.

Harness changes made with the re-pin, each on the master's word or forced
by the release, none changing an arm, a measure or a test:
- run_sessions.py (sha256 9ebfce01...): the master's stop rule -- after any
  goal in which an attempt was classed quota_exhausted, rate_limited or
  credential_invalid, or a session had zero provider turns, it writes
  <run set>/STOP and neither slot starts another goal (a running goal
  finishes); it records each goal's provider tokens and prints the running
  total; it copies a task's `workspace/` folder as the goal workspace (the
  release's layout). The pre-registered re-issue-once still applies to a
  turn-deadline death or a runner timeout. Stated now, from hc1's records:
  2 of 9 hc1 goals (both U) carried transient rate_limited attempts the
  transport retried inside a live session, so under this rule the sealed
  run may stop early; it stops, and I hand back.
- fetch_runset.sh (a1ffa8d0...) and stage_sealed.sh (1d694f87...): sealed
  content is staged and fetched only under the worktree's git-ignored
  sealed/ folder, never the session scratchpad.
- Job scripts: SHA_S = 55729bc4, SHA_U = 84223707, 12 h per slot.

## Sealed material (released 2026-09-25 after 9b039467; never committed)

- 11 task folders under the worktree's git-ignored `sealed/`, each
  TASK.md plus `workspace/` (the real CUHK outputs as ChemSmart left them);
  named here only by ordinal (t01..t11, sorted folder order). 335 files.
  My manifest of what runs (`find . -type f | LC_ALL=C sort | xargs
  shasum -a 256` inside the staged tasks folder), sha256 12079111a7be37f8...;
  the same digest recomputed on CUHK over the uploaded copy. The master's
  release record (7737012586236ae0) uses its own listing, so the two are
  not expected to agree.
- Nothing under chemsmart/ changed after the re-pin (cfe1fd66); the arms
  that run are the ones pinned before the material was copied in.
- Run set `sealed1` on CUHK (/project/xlzhang/jiseung/r10/q17/sealed1):
  N = 7 x 11 = 77 goals; plan by make_plan.py, seed 20260925, sha256
  f60980d1714a0346...; slot a 39 goals (S 17, P 16, U 6), slot b 38 (S 16,
  P 17, U 5); every task 7 goals; job scripts a a92e06b0..., b fc11b182...;
  envelope b72e5e03...; runner 9ebfce01....
- Smoke of the re-pinned tree and the new runner, local, on development
  task dE in the release layout (TASK.md + workspace/), arm P, from a
  `git archive` of 55729bc4 run from its own directory: exit 0, achieved,
  18 provider turns (planning 8, reading 10), 0.73 M input tokens, the
  inspection reply carried values, no stop condition. Not a sealed goal.

## Jobs issued

| job | slot | what | pre-registration | outcome |
|---|---|---|---|---|
| 2152986 | r10-q17-a | hc1 slot a (dA S/U, dB P, dE S/U) | a3eda4485329 | COMPLETED 0:42:51; 5 goals, mechanics pass |
| 2152987 | r10-q17-b | hc1 slot b (dA P, dB S/U, dE P) | a3eda4485329 | COMPLETED 0:35:02; 4 goals, mechanics pass |
| 2153435 | r10-q17-a | sealed1 plan slot a (39 goals) | 19b5352e3f59 | RUNNING (started 16:04 UTC); both arms' imports and digests verified on the node; tasks manifest 12079111... and plan f60980d1... re-computed equal |
| 2153436 | r10-q17-b | sealed1 plan slot b (38 goals) | 19b5352e3f59 | RUNNING (started 16:04 UTC) |

### The master's ruling on the stop rule (2026-09-25, recorded 16:15 UTC, 2 goals done, no STOP yet)

It applies from now and identically to every arm.
- Does not count: a `rate_limited` attempt the provider transport retried,
  inside a session that went on to finish with provider turns (the rule
  protects the owner's quota and keeps infrastructure out of the data; a
  recovered throttle threatens neither).
- Counts, and stops the run: `quota_exhausted` or `credential_invalid`; a
  session with zero provider turns; a session that ended on a provider
  error or `turn_deadline_exceeded`; three consecutive goals with throttled
  attempts. (This replaces the pre-registered re-issue-once for a
  turn-deadline ending: it now stops the run.)
- The running jobs (2153435, 2153436) are not touched: they run the
  literal rule (runner 9ebfce01), so a recovered throttle can write STOP.
  If STOP fires on a recovered throttle alone, I hand back when the jobs
  end; on resumption I delete STOP, record the event here, and submit the
  remaining goals in plan order with runner a7cc1679... (scratchpad
  tools/run_sessions.py), which implements the ruling -- three
  consecutive = the last three finished goals in order of ending across
  both slots; "ended on" = the session's last provider attempt carries an
  error class; nothing is re-issued. Checked on synthetic streams and on
  hc1's real records (under the ruling none of hc1's 9 goals would stop;
  its 2 throttled goals were recovered).

### Correction to the ruling (the master, 2026-09-25)

The ruling was not meant to replace the pre-registered rule, and a
pre-registered rule does not change mid-run: a session that ends on
`turn_deadline_exceeded` (or a goal the runner stops at its wall cap) is
re-issued once, as pre-registered. The run stops only on:
- a second deadline ending for the same goal (its re-issue ends on the
  deadline again);
- deadline endings on three consecutive goals;
- the other conditions as recorded: `quota_exhausted` or
  `credential_invalid`; a session with zero provider turns; a session that
  ended on a provider error other than the deadline; three consecutive
  goals with throttled attempts.
The line in the ruling above that reads "(This replaces the pre-registered
re-issue-once ...)" is withdrawn by this correction. Runner 9ebfce01 in the
running jobs already applies the pre-registered re-issue and is not
touched. The runner for any continuation now matches the correction:
sha256 eb77fd11bc000fb6... (replacing a7cc1679, never used), driven end to
end with a fake goal process through ten scenarios (tools/test_runner_v3.py,
fd0c60ce...): recovered throttles stop only at three in a row; a deadline
ending is re-issued once and stops on the second; an ending on any other
provider error, zero turns and quota each stop. A durable copy is on CUHK
(packs/q17-tools-v4.tar.gz, not unpacked).

First sealed goal done 16:12 UTC: 17 provider turns, 1.45 M input tokens,
456 s, no stop condition; it settled returned_to_human on a precision
requirement its own session declared (a behaviour ending, not a host
error). At ~7.6 min per goal the slots finish near 21:00 UTC. On resumption:
`after_run.sh` (scratchpad tools; sha256 recorded when it runs) fetches the
records into `sealed/q17-fetched/`, builds the packets into
`sealed/q17-packets/` (packets + GRADER.md) with the mapping in
`sealed/q17-private/` (mode 600, and a mode-600 copy on CUHK in
r10/q17/private/), measures leakage, and totals the provider tokens; the
mapping digest is committed before any packet leaves.

## Status

- 2026-09-24: brief read; base verified; read CONDUCT.md, the RSL README
  and its five lessons, Q3's, Q6's and Q13's merges and final EPISODE.md
  files, the four charter topics the brief names, and the reading
  surfaces in my radius (`_inspect_run`, `_inspect_result_selectors`,
  `_inspect_run_outcome`, their tool specs, the catalogue's reading
  entries, `_reading_context`, `wake.reading_turn`, `_system_prompt`).
  No provider session and no cluster job issued yet.
- 2026-09-24, later: the lever committed (29adc265), witness red on a
  2c1050c7 export (4 of 5) and green here; arm U built on the side branch
  (e77a0b47); development goals run locally (dA, dB, dC so far; dD, dE, dF
  queued), the later ones from a `git archive` export of 29adc265 so the
  worktree stays free; both code packs verified on CUHK; pre-registration
  committed; harness check hc1 running (2152986, 2152987).
- Gates at 0501decc (r10-integration merged; chemsmart/ equal to
  29adc265's): tests/agent 3065 passed, 0 failed (worktree); full suite
  from a pristine `git archive` export: 23 failed, 4619 passed, 25
  skipped, 3 xfailed -- the failing set is the round baseline
  (test_structures x19, pyscf dispersion conformance x2, aggregation x1,
  PyscfSettings x1); export deleted after the gate. ruff, black, isort
  clean on the two touched files.
- 2026-09-24, 23:41-23:55 KST: resumed after a provider session limit (not
  mine). Every development goal's run.log names the tree it imported: dA-S-1
  the worktree at 32e317ee (chemsmart/ = base), dA-P-1 the worktree at
  29adc265, dC-S/P-1 the worktree at d475fb4a (chemsmart/ = 29adc265), and
  every later goal the `git archive` export of 29adc265 run from its own
  directory (cwd = PYTHONPATH, so `python -m` cannot shadow it); switch
  values as labelled. hc1 read (all mechanics pass); packet builder
  repaired; the last local development goal (dE-P-1) finishing.
- ARMS FROZEN (this commit): the sealed tasks may be released.
