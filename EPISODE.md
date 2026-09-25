# R10 episode q26 -- when the hub refuses to write an input, the model learns why

Base SHA: dc9ff937129cfb3c09d575113d0ce79c9529391f (verified with
`git rev-parse HEAD` as the first action, 2026-09-25). Model:
claude-opus-5-5[1m]. Episode id `q26`.

## The question (as currently understood)

When the hub refuses to write a program input, does the Agent learn why, in
the compile reply (`compile_command`, handler `_prepare_program_node`), the
frontier and the review it reads? Where the reason is lost, carry it through
one path, bounded, sanitised and true, so the three say the same words from
one function; then observe whether the Agent takes the route the refusal
names instead of guessing.

What decides whether a reason arrives is the phase in which the refusal
fires, not the refusal:
- project validation (`project_yaml` -> `validate_project_yaml`): the
  receipt keeps `error_class` and a bounded, path-scrubbed `diagnostic`;
- compile-time agent gates (`RoutedContractError`): the rejection carries
  the failure report;
- inside the safe preview's Click invocation (CLI settings construction and
  the writers): the base kept `type(result.exception).__name__` and a digest
  of the output only.

## Instruments (scratch, not committed)

- `drive.py` / `census_drive.py`: `run_live_agent_session` driven end to end
  with only the provider transport replaced by a script (HOME and the
  config dir fenced, placeholder key, no provider contacted). Every reply
  recorded is the reply a model would read. 3.3 s per session.
- `probe_reason.py`: the oracle -- the program's own `str(exc)` from the same
  project, geometry and state through `chemsmart run --fake --no-scratch`.
- `raise_sites.py` + `phase_trace.py`: every raise site in the Gaussian,
  ORCA, PySCF and xTB settings, writers and CLI builders, with the phase its
  function runs in, traced over a battery of valid nodes for every program
  and job type.
- `scan_compile.py` (cluster job 2153702): every compile-path refusal in the
  archived R10 session streams of the named episode directories.

## Established (provider-free, host records)

Census C2 (driven, base): 13 refusal cases. The program's own sentence
reached the model in 4 (Gaussian route refusals at project validation x2,
ORCA td manifold at validation, ORCA MDCI through its agent-layer copy); a
different gate's sentence in 1 (ORCA bp86, the vocabulary gate at
establish); only the class `ValueError` in 8: broken_symmetry on a triplet
in ORCA, Gaussian and PySCF (the sentence names both routes), ORCA without a
basis, reference rhf on a triplet, an invalid mdci_density, semiempirical
with a functional, ab initio with DFT. For those, the compile reply said
"inspect the generated-input validation findings" over findings restating
rule ids; the frontier called the node ready with next action
compile_and_preview; the review said "compiled, not previewed:
compile_command previews a node". The observation stated the refused
broken-symmetry translation. Gaussian's refused writer left a 0-byte `.com`
read back as five false semantic mismatches. On the repaired tree: 12 of 13
carry the program's own sentence (bp86 unchanged, refused earlier by the
vocabulary gate in its own words).

Census C1 (static + trace, base): 279 raise sites; by the phase their
function runs in -- Gaussian 23 validation / 12 preview-only / 25
unexercised, ORCA 24/26/28, PySCF 64/21/6, xTB 17/15/3, shared 8/0/7: 74
preview-only sites (58 ValueError, 10 UsageError, 3 FileNotFoundError, 2
BadParameter, 1 TypeError), plus validation-phase sites whose condition
reads compile-bound state (broken symmetry in PySCF). A sizing census: a
function first entered only in the preview in this battery may be entered
at validation when its input is set.

Archive A1 (job 2153702; 113 session streams, 3,969 tool rows): 240
compile_command calls -- 206 previewed, 3 preview_failed, 8 waiting, 4 needs
project validation, 2 needs clarification, 1 needs project, 1 needs
capability selection, the rest rejected; 53 invalid project validations and
49 compile-path rejections (reasons carried); 1 review refusal. The 3
preview failures are all R10 Q15: g2's is a validator finding with no
exception (the field named); g1's two raised AttributeError and were read
as 11 and 15 findings; the session next searched for ORCA's FlipSpin syntax
and wrote `additional_route_parameters: "FlipSpin 1,6"`.

Replay R1 (job 2153704): Q15 g1's recorded tree digest 85752dd3... is
`r10/q15/code-943882de`; on it both archived compiles reproduce
AttributeError, message `'NoneType' object has no attribute
'chemical_symbols'`, leaving a 22-byte `.inp` that is exactly the
`input_string` ("%scf\n FlipSpin 1,6\nend"): input_string replaced the whole
input and the fake runner found no molecule. Corrected premise: the archived
loss was a crash naming no route, not a routed refusal, and the findings the
session read were true of the written file. Same message on the control
tree (9297d6ba) and the repaired tree, which now carries it beside the
class. Route-taking count from the archive: 0 of 2 events could take a
named route (none was named); both were followed by a native-keyword guess
(one session).

## Repair (committed)

- 661c9c8e writers: a refused input leaves no file behind (failure path).
- d6de6c16 agent: the safe preview keeps `exception_message` (program's
  words, <= 800 chars, host paths replaced by role, others by `<path>`,
  key-shaped strings redacted); `preview_refusal` renders it; compile
  reply (`refusal`, `next_action`), frontier (`blocking_reason`) and review
  (held state) say that one sentence.
- 89243262 agent: compile_time_observations states the writer's refusal,
  not the refused broken-symmetry translation.
- Witness `tests/agent/test_a_refused_input_says_why.py`: red on a pristine
  export of the base (KeyError 'refusal'; the 0-byte artifact), each part
  red on the commit before its repair, green after.
- 6b5adf48 merged r10-integration (Q25) cleanly.

## Live goals G1, G2 -- PRE-REGISTRATION (written before submission)

Task (TASK.md sha256 6eedde20...): the vertical singlet-triplet gap of
p-benzyne at the given regular-hexagon geometry (R10 Q18 O0's), "at a DFT
level you can defend"; says nothing of broken symmetry, projects,
refusals or routes. Workspace: `pbenzyne.xyz` (sha256 e7626c65...).
Envelope: orca, gaussian, pyscf on cpu; 16 cores, 48 GB, node 1 h,
episode 3 h, 6 engine calls, 2 revisions; local dispatch; approval
`claude-researcher-q26-owner-delegated` (delegated, never a human
decision). G1 and G2 are two independent samples of the same task on the
repaired tree (6b5adf48 = r10-integration 9297d6ba + the three repair
commits; code digest dcdd750a..., in r10/q26/code-g1). goal.sh sha256:
G1 37768363..., G2 0543618f...; envelope.yaml G1 225c9b63..., G2
240ade12... (differ only in the scratch path). Agent:
deepseek-v4-flash-0731 via alibaba-token-plan. The control arm for the
behavioural question is the counterfactual experiment CF below, not a
live goal: natural exercise is rare (A1: 3 of 240 compiles), so a live
control would most likely not be exercised at all.

Why this task: at one geometry and one level the natural route is two
single points differing only in the bound state, so one project may serve
both; if it carries broken_symmetry the triplet node is refused in every
program. Q18 g1 (adiabatic, the same molecule) kept two projects, so
exercise is uncertain and is itself an outcome. Replays: each goal's
transcript is replayed call for call through the host on the control tree
(9297d6ba), which shows what the old reply said at the same call.

Outcomes, read from host records (streams, transcripts, ledger):
- X, exercised: a compile_command reply with status preview_failed and a
  non-empty exception_class. Not exercised in an arm -> no behavioural claim
  from that arm.
- For each exercised refusal, the session's next 8 tool calls classified:
  ROUTE (the next change applies a route the sentence names: for
  broken_symmetry on a non-singlet, the refused node's project no longer
  carries broken_symmetry or its multiplicity is 1; otherwise the named
  field changed as named), GUESS (another field, or native keywords in
  additional_route_parameters / input_string), RETRY (the same node
  compiled with no change between), ABANDON (node withdrawn or program
  changed without a named route), END.
- Predictions: an exercised refusal in G1 or G2 -> ROUTE. FALSIFIED (the
  behavioural claim for the live goals) if a goal is exercised and its
  first change is not ROUTE.
- Host words: the goals' compile reply, frontier and any review carry the
  sentence; the control-tree replay of the same calls carries the class
  only.
- Physics (never tuned after a result), against O1: a delivered gap is
  PASS if its sign is positive (singlet lower) and it lies within 1.5
  kcal/mol of O1 at B3LYP/def2-SVP (unprojected 2.56, projected 4.95), or
  within [0.5, 9] kcal/mol at another hybrid functional or basis; a
  restricted singlet (dE near -22 kcal/mol at B3LYP/def2-SVP) is the
  known trap and is recorded as that error whatever its number.

## Oracle O1 (local PySCF 2.14 triplet + Q18's broken-symmetry fixture)

Regular-hexagon geometry, B3LYP in Gaussian's VWN form (PySCF b3lypg,
ORCA B3LYP/G), def2-SVP. Triplet UKS (PySCF, grids level 5):
-230.700651808 Eh, <S**2> 2.0067. Broken-symmetry singlet (ORCA, Q18 O1
fixture): -230.704724039 Eh, <S**2> 0.970279 (Gaussian -230.704724145).
Restricted singlet (PySCF): -230.665089215 Eh, 24.87 kcal/mol above the BS
singlet, equal to Q18's printed 24.87 -- the two programs agree to the
digit here. dE = E(T) - E(S): unprojected +2.555 kcal/mol; Yamaguchi
projected +4.948 kcal/mol; against the restricted singlet -22.316
kcal/mol. (A PySCF broken-symmetry singlet from a GuessMix-like start
collapsed to the restricted solution, as Q18 recorded; that run is not
used.)

## Counterfactual refusal turn CF -- PRE-REGISTRATION

Question: given the same session up to a refused compile, does the reply's
content change what the model does next? Design: one scripted prefix
(make_prefix.py sha256 60ad88c2..., transcript 729ee62d...) on the G1 task
and workspace, in the provider's own exposure mode: inspect ORCA sp, bind
0/1 and 0/3 to pbenzyne.xyz, one ORCA project `orca-b3lyp-def2svp-bs`
({functional: b3lyp, basis: def2-svp, broken_symmetry: true}) for both a
singlet node and a triplet node, plan, finalise, compile both (singlet
previewed, triplet refused). cf_probe.py (fbf447f3...) replays those 7
assistant turns through each arm's host (host digests translated by
path), then hands up to 3 turns to the real provider
(deepseek-v4-flash-0731, alibaba-token-plan, the session's own lease; the
model's calls run on that arm's host, planning only). Arms: control =
r10/q26/code-g2 (9297d6ba, 812e923b...), repaired = r10/q26/code-g1
(dcdd750a...). The arms differ only in what the host said at the refused
compile, and anywhere later that the model reads it. N = 6 per arm,
interleaved; job cf.sh (3e320fe8...).

Outcome: the first change after the refusal, classified by cf_classify.py
(7d19d233...): RETRY, ROUTE (the triplet gets a project without
broken_symmetry), ROUTE_OVERBROAD (the shared project loses
broken_symmetry, so the singlet loses it too), MULT, NATIVE, GUESS,
ABANDON, READ_ONLY, END, INFRA. INFRA (no provider turn) is reported and
not counted. Each sample is also read by hand; a disagreement with the
mechanical class is reported beside it.

Predictions: repaired ROUTE >= 4 of 6; control ROUTE <= 2 of 6, with its
other samples spread over RETRY, GUESS, NATIVE or READ_ONLY. FALSIFIED (the
claim that the sentence changes the model's next move) if the repaired
arm's ROUTE count does not exceed the control arm's. A control arm that
takes the route as often as the repaired arm is reported as it is: the
model knew the route without being told.

## G1 -- READ (job 2153709, host records)

Code digest dcdd750a verified on the node. Settled
`achieved_with_observations` in one cycle (anomaly
spin.s2_deviation_ge_0.2 on the broken-symmetry singlet, as expected for
that state). NOT EXERCISED: 0 preview_failed; the model wrote one project
per state and method (broken-symmetry singlet, restricted singlet,
triplet, at B3LYP and CAM-B3LYP), so no refusal was met; 5 ORCA single
points, 5 engine calls, 123 s engine wall. Physics against O1, from the
engine outputs (ORCA B3LYP/G def2-TZVP defgrid2): BS singlet
-230.955634048 Eh (<S**2> 0.962), triplet -230.951313017 (2.007);
delivered `st_gap_vertical` +2.711 kcal/mol (singlet lower) -- PASS (O1
+2.56 at def2-SVP); the projected value (about +5.2) was not delivered.
Also delivered: `gap-rks-b3lyp` -20.75 (the restricted singlet, computed
and named as the comparison), and `gap-camb3lyp` -34.36 kcal/mol, whose
CAM-B3LYP singlet ran HFTyp RHF with no GuessMix: the restricted-singlet
trap, used as the "functional spread" uncertainty estimator. No host
sensor flagged it (no stability analysis ran on that singlet). Found and
left: outside this episode's radius.

## G2 -- READ (job 2153711, host records)

Settled `achieved_with_observations` (two spin.s2_deviation_ge_0.2
anomalies, one per broken-symmetry singlet); NOT EXERCISED (0
preview_failed in both session streams; one project per state and
method). ORCA def2-TZVP: B3LYP/G BS singlet and triplet equal G1's to every
printed digit; BHandHLYP BS singlet -230.809911554 Eh (<S**2> 1.035),
triplet -230.806455975 (2.009), +2.17 kcal/mol. Delivered
`st-gap-vertical` +2.711 kcal/mol -- PASS; no restricted-singlet claim.
Live-goal exercise over the episode: 0 of 2 goals (both kept separate
projects per state, as Q18 g1 did).

## CF-G -- READ (job 2153715, 12 of 12 samples, no INFRA)

Tree digests verified. ROUTE 6 of 6 in both arms; read by hand, the same
route in every sample. The control texts read the five false findings as
symptoms, not causes ("the generated native input is empty (0 bytes), so
basis/functional/broken_symmetry read as missing"), and diagnose by
difference (the singlet node on the same project previewed green). The
falsifier FIRED again: for this refusal the misleading findings did not
mislead deepseek-v4-flash-0731, and the sentence did not change its next
move. Over CF and CF-G: 24 matched samples, ROUTE 12 of 12 per arm; every
repaired-arm text restates the refusal's content.

## CF -- READ (job 2153710, 12 of 12 samples, no INFRA)

Both tree digests verified on the node (control 812e923b, repaired
dcdd750a). ROUTE 6 of 6 in the control arm, 6 of 6 in the repaired arm;
read by hand, every sample in both arms names broken_symmetry on the
triplet as the cause, establishes a second ORCA project without it (with
`reference: uhf` added in 3 of 6 control and 1 of 6 repaired samples), and
rebinds the triplet node (amend_scientific_workflow or a re-issued stage).
Repaired texts quote the sentence ("refused for exactly the reason
named"); control texts infer it ("almost certainly the project setting
itself ... meaningless for a requested triplet"), leaning on the base's own
observation that GuessMix runs "on the singlet (Ms = 0)". The
pre-registered falsifier FIRED: the repaired arm's ROUTE count (6) does not
exceed the control's (6). For this refusal, deepseek-v4-flash-0731's next
move did not depend on the sentence: the model knew the route from its own
project, the observation and chemistry. The sentence did reach it
(quoted in the repaired arm).

## CF-G -- PRE-REGISTRATION (Gaussian variant, before submission)

Same design, prefix built for Gaussian (make_prefix.py sha256 5e82afe1...,
now taking the program; transcript 5ad06fc5..., shared project
`gaussian-b3lyp-def2svp-bs`, {functional: b3lyp, basis: def2svp,
broken_symmetry: true}); configs cfg-control.json 7d48ea56...,
cfg-repaired.json 4bad7c1b...; job cf_g.sh de4d8076...; classifier
cf_classify.py 5eaf1dfe... (the same rules; the shared role is now an
argument). What differs from CF is the base reply: Gaussian's refused
writer leaves a 0-byte input, read back as five false findings
(functional, basis, charge, multiplicity, and `broken_symmetry expected
True observed False`); the repaired reply has the sentence and none of
them. Predictions: control ROUTE <= 4 of 6 with at least one GUESS or
NATIVE (re-spelled fields, or guess=mix as native words); repaired ROUTE >=
5 of 6. FALSIFIED if the repaired arm's ROUTE count does not exceed the
control's.

## Hand-back gates (pristine export of de7f6771)

- tests/agent: 3207 passed, 0 failed (chemsmart imported from the export).
- Full suite: 23 failed, 4762 passed; the failing set is the round
  baseline (test_structures x19, pyscf dispersion x2, PyscfSettings x1,
  aggregation x1), none under tests/agent.
- ruff, black --check, isort --check clean on the six touched files.

## Jobs issued

- 2026-09-25: archive scan, CUHK Slurm 2153702 (r10-q26-a), 1 core,
  pre-registration d0f3d7336465; COMPLETED (results above).
- 2026-09-25: replay R1, CUHK Slurm 2153704 (r10-q26-a), 2 cores,
  pre-registration d0f3d7336465; COMPLETED (results above).
- 2026-09-25: G1, CUHK Slurm 2153709 (r10-q26-a), 16 cores;
  CF, CUHK Slurm 2153710 (r10-q26-b), 4 cores;
  G2, CUHK Slurm 2153711 (r10-q26-b, queued behind CF);
  all three pre-registration e6226e5bbffd (commit 8c17ca95); all
  COMPLETED (reads above).
- 2026-09-25: CF-G, CUHK Slurm 2153715 (r10-q26-a), 4 cores,
  pre-registration f4ec218b845d (commit 1eb1b42b); COMPLETED.

## Status

- 2026-09-25: census, archive scan, replay R1 and the repair done; witness
  red on base, green here. tests/agent on the merged tree (6b5adf48, Q25's
  conftest fence): 3207 passed, 0 failed. (Before the merge one test was
  red only under my own scratch fence, which pinned Path.home and so
  overrode that test's HOME; the fence was corrected.) Next: submit G1 and
  CF, then G2.
- 2026-09-25: all jobs read. Reachability established (census 8 of 13
  lost -> 12 of 13 in the program's own words; witness; 12 of 12 live
  repaired-arm sessions carried and restated the sentence). Behavioural
  premise falsified for the refusal tested: 24 matched real-model samples
  took the route with or without the sentence; both live goals avoided the
  refusal. Milestone A claimed for reachability, with that result stated.
  Handing back; branch clean, r10-integration (9297d6ba) merged.
