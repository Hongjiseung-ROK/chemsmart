# R10 episode Q22 -- what the host tells the Agent when something went wrong

Base SHA: 111dc55e5d33d6a71ffd4e2a592a9c71851cb44d (verified with `git rev-parse HEAD` as the first action, 2026-09-25).
Brief: scratchpad/q22/BRIEF.md, sha256 97dbac34cf0ed4c78707c37afc0926bcdd2d97a022e9a2ba8d0515fdf5043e09.
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

When the host tells the Agent what went wrong and what it may do next --
a wake (its failure report, deliverables, repair menu and rule text), a
review refusal, a launch refusal, a park reason, a recovery row, and the
node terminal word all of them build on -- is each statement

- true of the records the host holds when it says it;
- specific: naming the node, the receipt, the criterion and the number,
  or the program's own line, that the statement is about;
- actionable: offering a route that exists for that ending?

Where one is not, can the host say what its records already hold, and does
saying it change what the Agent does next?

## Priors from the brief (verified in the base tree before the census)

P1 wake names failed verdicts by node/rule only; P2 wake.recovery_route
calls every failed criterion "a structure the host judged"; P3 the
not-achieved recovery row writes "verdicts": []; P4 planning path returns
on an unanswered verdict, run path recovers; P5 "every initial workflow
node requires a green preview" names no node; P6 a pre-SCF native death
of an opt is typed failed_nonconverged_geometry; P7 a goal whose last
workflow holds no calculation parks instead of reading its refusal; P8
the settlement reason does not name the completion's findings. All eight
were visible in 111dc55e as described.

## Falsifiers (armed before the census)

- F1 the census finds the defects are only P1-P8: repair those and end.
- F2 a message reproduces differently on its own run commit: the harness is
  wrong and nothing downstream of it is believed.
- F3 the Agent recovered equally well whatever the message said.
- F4 a repair that makes a message specific changes what a settlement word
  means: a `shared:` commit for the owner.

## Census (provider-free, 2026-09-25)

Scope. CUHK R8-R10, named directories only: r8/{gaussian,integration,orca,
pyscf,xtb}, r9/{gaussian,master,orca,pyscf,xtb}, r10/q1-q5, q7-q16, q18,
q19 goals -- 61 goal ledgers, 60 goal roots (excluded: r10/q6/goals,
r10/q3/private, r10/q17 (a running sealed study), r10/q20 (running),
r10/m*). ax41 mirror 2026-09-14 campaign + research: 195 goal ledgers.
Records fetched without engine binaries (scratch q22/cuhk, 195 MB).
Tools: scratch q22/tools (ledger_story, wakes, refusals, verdict_sessions,
completion_findings, replay_final (Q19's harness), settle_stream).

What each session was told is read from the goal block its public
transcript restates ("goal terms, restated for recency"), not recomposed.

| message class | archived | true | specific | actionable | still produced by 111dc55e |
|---|---|---|---|---|---|
| wake naming a failed criterion | 13 (CUHK 3, ax41 10) | framing false 4/13 (not a structure: o2r, L1, L-S2 stability; po3-r19 margin); 0/13 the host's judgement of the task | 0/13 name a receipt or the number | citation route needs a digest the wake withholds; inspect_run shows no chain receipts | yes (P1, P2) |
| ... what the woken session did | 13 | -- | -- | 0/13 cited the run-minted receipt; 3/3 CUHK re-evaluated their criteria to mint one (2, 4, 6 evaluations) | -- |
| recovery row when a criterion failed and the chain was partial | 2 (o2r c1, L-S2 c1) | "verdicts": [] false | names nothing | -- | yes, every such run since Q19 (P3) |
| node word on a death before any energy | 10 nodes (Q15 g2 ene-opt; r7m-h3 x3; ax41 po3-triazole-regio x6) | failed_nonconverged_geometry false 10/10; 14/14 real walks carry an energy | engine lines present | menu route "restart from the reached geometry" does not exist; both CUHK sessions said so | yes (P6) |
| node word on a finished run a host rule refused | 13 nodes (Q5 g1 x6, Q12 g1-hi x2, r9 xtb g3 x2, ax41 h2 x3) | failed_native false | -- | Q5 g1 took the route twice, same refusal | no (Q14 094df51c) |
| review refusal | 3 (Q15 g1, ax41 po3-r17, r9 gaussian g2) | true | 2/3 name no node | -- | yes (P5) |
| re-wake report (cycle_delivers_or_returns) | 6 | cost "no engine call" false of the plan ending | -- | route omits the executable-plan ending 6/6; mattered in 1 (Q15 g1), where the Agent took it anyway (F3) | yes |
| re-wake report (requirement_is_resolved) | 11 | true | names numbers | routes fit the state | -- |
| launch refusal | 3 (Q15 g1 x2, r9 orca g5) | Q15 g1's false (stale check; Q15 9cda6569) | r9 g5 names no producer (execution.py, outside radius) | -- | g1's reason: no |
| run-path settlement over unlaunched wave members | 1 (Q15 g1) | true | omits the refusal it held | -- | yes |
| park | 6 (R8 x5 ready calculations; Q15 g2) | true | -- | Q15 g2: no decision can resolve it; its stream held a verified refusal the base settles as unreachable_from_evidence | yes (P7) |
| "recorded analysis but the host completion gate did not pass" | 31 settlements | base replay: 25/25 still said; 24/25 streams hold no completion receipt at all | 1/25 drops the partial receipt's findings | -- | yes (P8) |

Found beyond P1-P8 (F1 falsified): the re-wake route/cost, the run-path
settlement over unlaunched members, and P8's truth (not only its
specificity).

## Repairs (one commit each; witness red on 111dc55e, green here)

- 6dd0c9f5 wake: a failed criterion is named with the number it read and
  the receipts that state it (P1, P2, P3, settlement reasons).
- 3c490a8b terminal_states: a death before the first energy is the
  program's own ending (P6).
- d7514215 tool_runtime: a review refused for a missing preview names each
  node and what it holds (P5).
- ca9c6377 driver: a re-wake's route names every ending its invariant
  admits, and its cost is true of each.
- 40449039 driver: a run whose wave member never launched settles quoting
  the executor's refusal.
- a4fb8a86 driver: a returned delivery says what its completion receipt
  holds, or that it holds none (P8).
- 1aef6143 driver: a park no decision can resolve settles on what the
  session's stream holds (P7; losartan's replaced-selection park kept).
- P4 left: whether the planning path should re-wake on an unanswered
  verdict decides when a goal returns (settlement semantics, owner).

Gates on 1aef6143: tests/agent on a pristine export, 3144 passed, 0 failed.

## Replays: every changed message, on the commit that produced it (provider-free)

Harnesses in scratch q22/tools; exports of chemsmart/ at each commit.
- W1 wake (replay_wake.py: ledger cut at the wake_composed row, record at
  earlier cycles, _wake_context, compared key by key with the goal block
  the transcript restates): o2r c2 on 09450c74, L1 c2 on 71de94b9, L-S2 c2
  on fd093662 -- every key byte-identical except previous_run_outcome,
  whose artifact reads need the cluster paths (deliverables, authority and
  trajectory identical). On 1aef6143 the same records name each verdict
  with its statement and the run's receipt: o2r df709b8b, L1 3cac78d8 (and
  its second), L-S2 fdcf92e6 ("read -0.058483161239773276 against
  minimum_greater_equal 0 hartree", minted_by goals/ls2/runs/cycle-1).
- W1 recovery row (replay_recovery.py): L-S2 c1 on fd093662 and o2r c1 on
  09450c74 reproduce "verdicts": [] byte for byte; 1aef6143 names the
  verdict (o2r also its three undelivered observables).
- W2 (derive_outcome.py / all_outcomes.py): Q15 g2 ene-opt on 8869a23e
  derives failed_nonconverged_geometry (archived), failed_native on
  1aef6143. Whole archive (1278 nodes, 8 streams with no run): base vs
  1aef6143 differ on 28 nodes, all failed_nonconverged_geometry ->
  failed_native, all energy-less sub-second deaths (Q15 g2 1, r7m-h3 3,
  po3-triazole-regio and its copies 24); the other 66 non-convergence
  words are unchanged.
- W3 (replay_review.py: the recorded plans and materializations through
  the runtime's own record converters, the host's plan pointer followed,
  _latest_bounded_materialization): Q15 g1 c1 on 943882de reproduces the
  bare refusal; 1aef6143 names bergman-scan (not materialized for the
  current plan). The session's 14:08 amendment restored plan a64ebd2a;
  the scan's last compile belonged to 5bb82f95, so the latest
  materialization of the current plan held only ene-optfreq. (A first
  replay that took the last recorded plan named ene-optfreq -- wrong: an
  amendment restoring a plan records no new plan event.)
- W4: Q15 g1's archived re-wake route and cost equal 943882de's
  constants character for character; 1aef6143 names the plan ending.
- W5 (replay_final.py run path, outcome derived): Q15 g1 c2 on 943882de
  reproduces "... pbnz-opt=not_launched, ts-search=not_launched"; on
  1aef6143 the reason quotes both refusals (ORCA's input-check lines on
  two Gaussian nodes -- the false refusal becomes visible to a reader).
- W6 (replay_final.py): the 31 settle steps on 111dc55e give the bare
  gate sentence 25/25 replayable; on 1aef6143 24 say "this stream holds
  no completion receipt, so nothing certifies it" and L1 names receipt
  bad4811a, partial, with its three claim_on_failed_criterion findings.
- W7 (replay_park.py: session rebuilt from the pending row and the
  stream): Q15 g2 c2 on 8869a23e parks with the archived reason; on
  1aef6143 it settles unreachable_from_evidence on the session's verified
  refusal, naming the unrun probe workflow.

## Reference job R1 -- PRE-REGISTRATION (written before submission)

CLI oracle, no Agent, code = this branch. PySCF RKS B3LYP/def2-SVP
single points with scf_stability (Q19's project file), 8 cores:
- S2 at 1.889 A (calibration, L-S2's system): E -796.1097378, external
  -0.0584831, real->complex -0.0288198 Eh, internal stable, each within
  1e-5 Eh of Q19's 2153508.
- ethylene twisted 90 deg (CH2 planes perpendicular; C-C 1.47, C-H 1.08
  A, H-C-H 118 deg): RKS->UKS unstable (lowest external eigenvalue below
  -0.01 Eh). Internal and real->complex: no prediction (at exact D2d the
  pi pair is degenerate, and either may be unstable).
- H2 at 2.20 A: RKS->UKS unstable (below -0.01 Eh); internal stable.
The reference fixes the live goals' physics bands, written here before
any goal is submitted. A system whose external eigenvalue is not negative
is dropped from the live set (its criterion would not fail).

### Reference job R1 -- READ (CUHK Slurm 2153624, code 8048c9de, digest 0ca781a4; prereg cef7ddb63259)

Read through the host's own extract_result_quantities from each result
and its sibling receipt (3/3 commands exit 0, receipts findings []):
- S2 1.889 A: E -796.1097377983; internal +2.5e-6 (stable); external
  -0.0584830627; real->complex -0.0288198792 Eh. Q19's 2153508 reproduced
  within 1.3e-6 Eh on every number: calibration PASS.
- ethylene 90 deg: E -78.3783953190; internal +0.4213 (stable); external
  -0.1033077562 (unstable); real->complex -0.0013451513 Eh (unstable,
  marginal). PySCF warns HOMO == LUMO (the degenerate pi pair).
- H2 2.20 A: E -0.9797177412; internal +1.873 (stable); external
  -0.1206681597 (unstable); real->complex +0.0718830061 Eh (stable).
Both live systems keep: external negative, so a stability criterion
fails on either.

### Physics bands (fixed here, before either goal is submitted)

- G-tw: E -78.3784 +/- 0.0005 Eh; external unstable, -0.1033 +/- 0.003;
  internal stable; real->complex -0.0013 +/- 0.003 Eh (sign negative,
  marginal). Answer: not a stable solution -- unstable to spin-symmetry
  breaking, marginally unstable to real->complex, stable to real internal
  rotations.
- G-h2: E -0.97972 +/- 0.0005 Eh; external unstable, -0.1207 +/- 0.003;
  internal stable; real->complex stable, +0.0719 +/- 0.003 Eh. Answer:
  not a stable solution -- unstable to spin-symmetry breaking, stable to
  internal and to real->complex rotations.

## Live goals G-tw, G-h2 -- PRE-REGISTRATION (bands above)

TASK.md sha256: gtw a4e4858e..., gh2 1cb3f5b4...; workspace geometries
gtw ethylene-perp.xyz fed26690..., gh2 h2.xyz b77375da... (the only
workspace files).

Tasks: L-S2's task with the molecule changed (twisted ethylene; H2 at
2.20 A): "is that restricted reference a stable solution ... yes-or-no
answer I can defend, stated for both kinds of orbital rotation, and the
electronic energy of the reference in hartree. Use PySCF." Nothing names
a criterion, a validation, an expectation or a receipt. Envelope as L-S2:
pyscf cpu, 8 cores, 16 GB, node 1800 s, episode 5400 s, 4 engine calls,
max-revisions 2, local dispatch, granted by
claude-researcher-q22-owner-delegated (a delegated approval, never a
human decision). Agent deepseek-v4-flash-0731 via alibaba-token-plan.

The recovery point is met when cycle 1's run holds a failed criterion no
decision cited. Then, read from host records:
- host (deterministic; the repair): R1 the recovery row names the
  verdict; R2 the cycle-2 goal block the session received names each
  verdict with its statement, every receipt of the run that states it,
  and minted_by the run; R3 it does not call the criterion a structure
  the host judged. FAIL: any of R1-R3 false, or the host refusing a
  citation of a receipt the wake named.
- behaviour (the Agent's; one observation per goal): B1 the woken
  session's decision cites at least one receipt the wake named; B2 it does
  not re-evaluate a named verdict's rule (no evaluate_scientific_validation
  on that node, no new validation node with that id). Control: the three
  archived sessions woken this way (o2r, L1, L-S2) cited 0 run-minted
  receipts and re-evaluated 3/3. Reported as observations with their N,
  never as a rate.
- the word: achieved_with_observations when the decision cites the verdict
  and the declared answers are delivered; otherwise the reason is read.
- replay: the cycle-2 wake recomposed on 111dc55e from the same records
  shows what the old message would have been.
Not counted either way: no failed criterion at cycle 1 (recovery point not
met: "not exercised"); zero provider turns or turn_deadline_exceeded
(infrastructure). A weak run is reported, never re-rolled.

### Live goals G-tw, G-h2 -- READ (CUHK 2153626, 2153627; code 8048c9de, digest 0ca781a4; prereg 8e24c763cd4e)

Both ran three cycles and settled returned_to_human (gtw 20 min, gh2 28
min wall). Physics, from the host's own extractions: G-tw E(RKS)
-78.3783953 Eh, external "unstable", internal "stable", real->complex
"unstable" (words the program printed), BS below RKS by 32.49 kcal/mol,
<S^2>(BS) 1.010 -- inside every band. G-h2 E(RKS) -0.9797177 Eh, external
-0.1206682, internal +1.8733, real->complex +0.0718830 Eh, BS below RKS by
0.0320598 Eh (20.12 kcal/mol), <S^2>(BS) 0.837 -- inside every band.

G-tw: recovery point not exercised (its run failed no criterion; the RKS
instability reached the record as an anomaly, scf.reference_unstable).
Its recovery row names what opened it (undelivered ids, unclaimed
conv-kcal, analysis_status partial -- the P3 repair, exercised). It then
settled on a precision requirement: cycle 3 re-claimed the energy with
basis "inferred" citing the energy's own extraction, the host judged it
not evidence-backed, and the word says "stands attested" (true; see
defects left).

G-h2: recovery point met (val-real-stab/real-stable failed on -0.1207 Eh,
receipt 80b40882, no decision cited it).
- R1 met: the recovery row carries "verdicts": ["val-real-stab/real-stable"].
- R2 met: the cycle-2 goal block names the verdict with its statement
  ("read -0.12066815968485223 against minimum_greater_equal 0 hartree"),
  receipt 80b40882, minted_by goals/gh2/runs/cycle-1.
- R3 met: no "structure the host judged". The same records recomposed on
  111dc55e (replay_wake.py) give "unanswered_failed_verdicts":
  ["val-real-stab/real-stable"] and "a structure the host judged not to be
  what the task required" -- the old message.
- B1 met (N=1): the cycle-2 decision cites 80b40882 (control: 0 of 3).
- B2 not met: cycle 2 evaluated val-real-stab once more (6135c9ad),
  beside two new criteria (bs-lower, complex-stable) whose verdicts it
  claimed as the answers to its three category questions -- a receipt to
  claim from, not one to cite (control: 3 of 3 re-evaluated, 2-6 times).

Cycle 3 (the goal's one re-wake) is where the host's words went false,
and the session acted on them:
- the wake named val-real-stab/real-stable unanswered with 6135c9ad
  (minted_by the cycle-2 session) and eleven numbers stale, the requested
  energy among them, while the settlement's goal-grain join calls it
  answered by 80b40882 (verdict_join.py: read alone unanswered, at goal
  grain answered). The session tried to cite 6135c9ad (refused: "no digest
  this host minted"), judged the rule twice more (43fb4807, 06498093),
  cited the second, and wrote "reproduced under the same node and rule ids
  on a fresh re-evaluation" -- the wake's own rule text, followed to the
  letter over a false premise.
- the diagnosis said the three category ids were "still undelivered by
  their id in any cycle" and that the cycle "rendered claims under other
  names instead: ..., verdict-bs, verdict-complex, verdict-real". Cycle 2
  had claimed all three under their ids (as 1/0 numbers); the three
  "other names" were those claims' quantity ids; the completion receipts
  the host held said what answers a category (a finding with
  answers_observable_id on a word the host read) and the report did not
  carry it. Cycle 3 claimed under the same ids as the same numbers and
  wrote five findings, none answering a declared id. The settlement said
  the three "have no claim carrying their id in any cycle" (false).

## Repairs found by the live goals (witness red on e8e8098e/962d7ad1, green after)

- 962d7ad1 driver: the wake and the re-wake read a verdict at the goal's
  grain, as the settlement does (W8; two witnesses).
- 7bba78f3 driver: an undelivered declared observable is named as carried
  or not, with what its completion receipt says it lacks. Census
  (id_carried.py over every rewake_opened row and every settlement reason
  saying an id has no claim): CUHK 3 statements, 0 false; ax41 11, 6
  checkable, 2 false (ino3-cont, ino3-r13a: 16 ids carried as quantity ids
  in another unit); live 2, 2 false (G-h2). 4 of 11 checkable.

Replays (both on an export of e8e8098e, whose chemsmart/ equals 8048c9de,
and on the repaired tree):
- gh2 cycle-3 wake (replay_wake.py): e8e8098e reproduces the archived
  deliverables byte for byte; repaired: unanswered_failed_verdicts [],
  stale_quantity_ids [].
- gh2 re-wake decision (replay_rewake.py, new: ledger cut at
  rewake_opened, a GoalDriver at the cycle-2 session's end, _rewake):
  e8e8098e reproduces diagnosis, route and cost byte for byte; repaired:
  "a claim carries each of these declared observables without answering
  its declaration: real-stability-stable, complex-stability-stable,
  bs-solution-lower; its completion receipt says: declared question ...
  (category) ... record a finding with answers_observable_id ...", other
  names only claims carrying no declared id; the route names how a
  category is answered.
- gh2 settlement (replay_final.py): e8e8098e reproduces it; repaired: same
  word, "a claim carries each of these declared observables without
  answering its declaration: ...".

Gates on 7bba78f3's tree: tests/agent 3148 passed, 0 failed.

## Live goals G-h2b, G-h2c -- PRE-REGISTRATION (written before submission)

Question: with the wake and the re-wake saying what the records hold (W1,
W8, W9), what does the Agent do at the points where G-h2's words were
false? Two replicate goals, submitted together; neither is re-rolled.

Code = 7bba78f3. Task, workspace and envelope byte-identical to G-h2's
(TASK.md 1cb3f5b4..., h2.xyz b77375da...; pyscf cpu, 8 cores, 16 GB,
node 1800 s, episode 5400 s, 4 engine calls, max-revisions 2, local),
granted by claude-researcher-q22-owner-delegated (a delegated approval,
never a human decision). Agent deepseek-v4-flash-0731 (alibaba-token-plan).
Physics bands: G-h2's, above.

Points, each read from host records with its own N (0, 1 or 2):
- P-verdict, met when cycle 1's run holds a failed criterion no decision
  cited: host R1-R3 as for G-h2; behaviour B1 the woken decision cites a
  receipt the wake named (G-h2: met), B2 no evaluate_scientific_validation
  on the named verdict's node (G-h2: not met).
- P-rewake, met when the goal is re-woken: host R4 every verdict the
  re-wake's deliverables call unanswered is unanswered at the goal grain
  (verdict_join.py), R5 the diagnosis calls each undelivered id carried or
  not in agreement with the goal's claims (id_carried.py) and quotes the
  stream's completion miss text where that receipt holds one. Behaviour B3
  the re-woken session evaluates no rule the goal has answered (G-h2: 2
  evaluations); B4 where a declared category id is carried but not
  answered, the re-woken session records a finding with
  answers_observable_id for at least one such id (G-h2: 0 of 3).
- the word: read, and each reason checked against the records.
Not counted: a point not met ("not exercised"); zero provider turns or
turn_deadline_exceeded (infrastructure). What the Agent chooses to declare
(categories or numbers) is its own; a goal that declares no category id
does not exercise B4.
Replays: each wake and re-wake these goals receive, recomposed on
111dc55e (and G-h2's code, e8e8098e) from their own records, shows what
the old words would have said.

### Live goals G-h2b, G-h2c -- READ (CUHK 2153672, 2153673; code 57b1759e = 7bba78f3's chemsmart/, digest 943cc270; prereg 2b8441ab02a9)

Physics, both inside every band: E(RKS) -0.9797177 Eh, external
-0.1206682 Eh ('unstable'), internal 'stable' (+1.873), real->complex
'stable' (+0.0719), BS below RKS by 0.0320598 Eh (20.12 kcal/mol),
<S^2>(BS) 0.837.

Points: neither run failed a criterion at cycle 1 (both reached cycle 2
through a recovery row naming undelivered ids and a partial chain) and
neither goal was re-woken. P-verdict and P-rewake: not exercised (N=0);
B1-B4 unobserved. What the Agent did instead:
- G-h2b: cycle 2 claimed the energy and the stability words, answered
  both declared category questions with findings bound to host-read words,
  and settled achieved_with_observations (two anomalies named) -- 2
  cycles, 0 revisions.
- G-h2c: cycle 2 did the same (both questions answered by host-read words,
  the energy claimed), and the goal returned to the human on "cycle 2,
  planning session: a required completion gate is red". A new host defect
  (W10, below): the completion passed over a partial extraction
  (reference_energy absent, 63ca261e); the loop asked only the
  completion's own word and asserted "complete"; terminate read the
  receipts beneath it and refused after the last turn; the typed-error
  path settled without reading the delivery. The same stream settled with
  the word the gate admits (settle_stream.py, blocked) gives
  achieved_with_observations -- G-h2b's word.
- the recovery rows both goals were woken with (analysis_status partial,
  undelivered ids) are the P3 repair's; their cycle-2 wakes recomposed on
  111dc55e differ only in the rule text and those trajectory fields.
Census of the word: 3 goals settled on "a required completion gate is red"
(ax41 e4p-cyclohexane-b1 and ino3-r11: the completion itself was partial,
the shape the loop's SUFFICIENCY-2 repair covers; G-h2c: a passed
completion over a red source, the shape it does not).

- 18180d00 loop: a session asks the terminate gate's own question before it
  calls itself complete, and a red gate names its receipt. Witness red on
  57b1759e (the stream left open, "cycle 1, planning session: a required
  completion gate is red"), green here (the session ends blocked naming
  "<receipt> (result_quantities_extracted, partial)", the goal settles
  achieved on its delivery).

## Defects found and left

- tool_runtime.py ~6956-6975 (record_scientific_decision's
  decision.receipt_is_one_the_host_minted): its route says "or one
  inspect_run shows on a recorded run of this goal", and inspect_run shows
  node outcomes and anomaly digests, never an analysis chain's receipts
  (L-S2 c2: "The analysis run itself is recorded but not readable"). A
  refusal naming a route that does not exist; the decision tool is outside
  this radius. W1 makes the wake carry the digests instead.
- execution.py:5954: the launch refusal "orca result is not a converged
  OPT or TS" names neither the producer node nor the result (r9 orca g5).
  Producer edges are Q20's.
- P4: the planning path returns an unanswered verdict to the human while
  the run path wakes a cycle for it. When a goal returns is settlement
  semantics (owner); the returned reason now names the verdict's number and
  receipt.
- H4 (a later analysis-only plan resets the wave decision; losartan's
  shape) still parks naming the replaced selection; wave selection is
  Q20's. W7 settles only when no selection was ever made.
- (Harness note, not a host defect: replay_recovery.py keeps the whole
  workspace record, so a replayed recovery row can read later cycles'
  deliveries -- L-S2 c1's undelivered ids replay as [] there; the wake
  harness cuts the record and names them.)
- executor.py _field: an analysis node's failure reason "host result does
  not carry any of ('receipt_sha256',); the executor and the tool contract
  have drifted apart" (G-tw cycle 2, node extract-bs, completion df89e137).
  The same session's direct extract_result_quantities of the same three
  quantities from the same artifact succeeded (92fcfdc2), so the words
  name a contract drift the records do not show, and whatever the handler
  returned is not recorded. The analysis-chain executor is outside this
  radius. Falsifier: replay the node over the archived h5 through the
  executor and read what the handler returned.
- G-tw's settlement "e-rks-hartree stands attested at 0.001 hartree"
  is true (the re-claim's basis "inferred" cited the energy's own
  extraction, which the host does not count as evidence for a magnitude),
  but it does not say why that citation did not back it. Precision and
  sufficiency are another radius.
- _settle (run path) still reads a run's verdicts from the run's stream
  alone. A run re-typing, over the same result, a verdict an earlier
  decision answered would be named unanswered there while the goal grain
  calls it answered. No instance in either archive; left, with that
  falsifier.
- G-h2c's session answered its "stab_complex_verdict" with the external
  (RKS->UKS) word, reading "complex" as the spin-symmetry-breaking channel;
  its finding says so explicitly. The Agent's naming, not a host defect;
  reported, not graded.

## Status

- step 0: brief read, base verified, CONDUCT/RSL/charter read, priors
  located.
- step 1 (census): done (above).
- step 2 (repairs): seven commits, witnesses red on base and green here.
- step 3: reference job R1 read; live goals G-tw, G-h2 read.
- step 4: two repairs the live goals found (962d7ad1, 7bba78f3), replayed.
- step 5: G-h2b, G-h2c run and read; P-verdict and P-rewake not exercised;
  G-h2c found W10 (18180d00, loop.py and runtime/event_store.py -- outside
  the listed radius, isolated in one commit for the master's call).
- gates on 18180d00: tests/agent 3149 passed, 0 failed (working tree).
- hand-back gates on a pristine export of d7ba72cd (code = 18180d00):
  full suite 23 failed, 4703 passed -- the failing set equals the round
  baseline, none under tests/agent; ruff, black --check and isort --check
  clean on every touched file; r10-integration merged (already up to
  date at 111dc55e).
