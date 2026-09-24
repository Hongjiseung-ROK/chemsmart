# R10 Q9 -- does the production path keep the design's promises?

Base SHA: d2c192af15bfbb2a3d6a0e6b7a4e7c0dfca792db (verified `git rev-parse HEAD` at start)
Episode id: q9
Branch: worktree-agent-a1f57265e43e4603b

## Question (as currently understood)

When a goal runs where production goals run -- the controller inside a
Slurm allocation, engines writing to cluster scratch -- does it keep every
check and every provenance guarantee the design promises, and does each
node's evidence belong to that node alone (Fundamental 1: CHEMSMART owns
execution contracts, provenance and reproducible configuration)?

The provenance guarantee is read strictly: a node's recorded result is a
function of the inputs its record names. A file in its branch that another
calculation wrote, or a file another calculation left where this one's
engine reads, breaks it -- whether or not the numbers happen to agree.

## Premises checked from host records before any change

All read-only from `/project/xlzhang/jiseung/r10/q6/goals/pair3-b`
(Slurm 2150179, code commit 6f902802). Q6's scientific content is not used.

1. CONFIRMED. Every ORCA probe in pair3-b is `not_run` with reason
   "inside a scheduler allocation; the probe runs on the controller only"
   (events.jsonl, 8 `input_check_probed` events across 3 runs). The
   controller runs inside the slot allocation (`goal.sh`, `--dispatch local`).
2. CONFIRMED, and the brief's placement of the error is checked: in
   `cycle-3/rad-sp-cc-r3/radical-opt-geom_sp_sp_gas_phase.out` ORCA 6.1.1
   prints `INPUT ERROR / UNRECOGNIZED OR DUPLICATED KEYWORD(S) IN SIMPLE
   INPUT LINE / MAXCORE 1800` *before* its `INPUT FILE` banner and exits.
   So the probe, had it run, would have ended `aborted` with these lines
   (it stops at the banner; this error precedes it).
3. CONFIRMED and WIDER than the brief. `rad-sp-cc-r3` (died at the input
   check, its own .out 13 KB) holds cycle 2's `.gbw`, `.property.txt`,
   `.densities`, `.qro/.uno/.unso/.loc` and ~5 GB of `.tmp.N` integrals.
   Mechanism read from the tree: `ORCAJobRunner._set_up_variables_in_scratch`
   keys scratch by `job.label` (= input stem + jobtype + solvent, no node,
   cycle, method, charge or multiplicity), the base runner deletes scratch
   only after a *complete* job, and `_postrun` copies back every
   `{label}*`. The `.tmp` filter is `file.endswith((".tmp", ".tmp.*"))`,
   whose second member is a literal string, so ORCA's numbered
   temporaries are copied into /project.
4. NEW (not in the brief): the stale files are also the engine's input.
   `cycle-1/h-sp-dft` (wB97X-D3BJ on the H atom) ran in the scratch that
   `cycle-1/h-sp` (DLPNO-CCSD(T) on the same file, died in MDCI) left, and
   ORCA's AutoStart read h-sp's `.gbw` as its guess ("GBW file was renamed
   to GES file ... Guess is set to MORead"; the `.ges` in h-sp-dft is
   988988 bytes, h-sp's `.gbw` size). Its branch also holds h-sp's
   `.loc/.qro/.uno/.unso` (DLPNO/UHF artifacts a DFT run does not write),
   bound by `_execution_output_artifacts` as h-sp-dft's own outputs. The
   same key is shared by concurrent members of a scheduler wave.
5. CONFIRMED: `MaxCore 1800` rode `additional_route_parameters` onto the
   `!` line; nothing refused it before ORCA; the preview verifier accepts
   it because the tokens appear in the written route.

## Census (provider-free; the goal path's environment branches and scratch paths)

Read from the base tree (`grep -rn "SLURM_\|PBS_\|os.environ\|tempfile\|scratch"`
over `chemsmart/agent`, `chemsmart/jobs`, `chemsmart/settings`), each item
judged by whether its guarantee holds with the controller inside an
allocation and engines on cluster scratch.

Environment-dependent branches:

| # | where | inside an allocation | verdict |
|---|---|---|---|
| E1 | `tool_runtime._probe_input_check`: `SLURM_JOB_ID`/`PBS_JOBID` -> `not_run` | the check never runs; the launch refusal it feeds (`executor._refuse_launch_the_program_already_refused`) has no input, so an input ORCA rejects is launched and charged | DEFECT (premise 1) |
| E2 | `settings/probe/detect.detect_scheduler` (wizard) | answers SLURM from the job's own variables -- correct | keeps |
| E3 | `settings/server.Server.detect_server_scheduler`/`current()` | not reached on the goal path: every node names `--server <execution-server.yaml>` | not on path |
| E4 | `tool_runtime._launch_reserver` | diagnosis string only; liveness is the lease | keeps |
| E5 | `live_session._allocated_execution_resources` | reads the dispatch receipt; under `--dispatch local` inside an allocation the envelope is taken as the grant with no check against the cgroup the process actually has (`sched_getaffinity`) | owner's ruling territory (hardware); noted, not repaired |
| E6 | `live_session.local_orca_input_check` / `Executable.resolved_env` | resolves the same ORCA and ENVARS the engine gets | keeps |

Scratch, staging and copy-back paths:

| # | where | verdict |
|---|---|---|
| S1 | ORCA runner: scratch `<scratch_root>/<label>`, reused, deleted only after a complete job; copy-back of every `{label}*` | DEFECT: a later run of the label inherits and delivers an earlier failed run's files and ORCA reads its `.gbw` (premises 3, 4); concurrent wave members share the directory |
| S2 | ORCA `_postrun` `.tmp` filter: `endswith((".tmp", ".tmp.*"))` | DEFECT: the second member is a literal; numbered temporaries (GBs of PNO integrals) are copied to /project and hashed as outputs |
| S3 | Gaussian runner: same `<scratch_root>/<label>` keying and `{label}*` copy-back | same defect class as S1 (a stale `.chk` is delivered; Gaussian reads it only if asked) |
| S4 | PySCF runner: same keying when `SCRATCH: true` | the agent profile sets `SCRATCH: false`; a stale `.h5` would fail the run-nonce provenance check visibly; keyed the same way for humans |
| S5 | NCIPLOT, thermochemistry runners: same keying | off the Agent execution surface; same class |
| S6 | xTB runner: `mkdtemp` per run under `.chemsmart-xtb-runs`, stale-artifact refusal | keeps (the pattern the others lack) |
| S7 | input-check probe work dir: `tempfile.mkdtemp()` | unique and removed; would write under the compute node's `/tmp` once E1 is repaired, outside the scratch the server profile names |
| S8 | `GAUSS_SCRDIR = <scratch_root>` for every Gaussian node | PID-named `Gau-*` files, unique per host; two array elements on two hosts could share a PID -- noted, not repaired |
| S9 | PySCF engine temporaries (`lib.param.TMPDIR`) | node-local `/tmp` whatever the profile says; unique names -- noted |
| S10 | `_prepare_execution_node_workspace` | refuses a non-empty branch before launch -- the promise S1 breaks after launch |
| S11 | `_execution_output_artifacts` | binds every file in the branch as the node's output: the consumer that turns S1/S2 into false provenance, correct once its producer is |

Resource ownership:

| # | where | verdict |
|---|---|---|
| R1 | ORCA `additional_route_parameters` -> `!` line, no resource refusal; the tool sentence ("CPU count and memory belong to the ChemSmart run/server layer") did not hold on deepseek-v4-flash (pair3-b cycle 3) | DEFECT (premise 5) |
| R2 | ORCA writer `%maxcore = 0.75 x MEM_GB x 1000 / NUM_CORES`, `%pal nprocs NUM_CORES` | host-owned, one number; no typed lever trades ranks for memory per core within a grant (pair3-b cycle 2: triples needed 1416.5 MB > 1044.7 MB available at %maxcore 1500) | frontier, not repaired here |

## Falsifiers

- Premise falsified if every environment-dependent branch and every
  scratch/copy-back path either keeps its guarantee inside an allocation or
  is refused visibly, and no reader reads a file its own node did not
  produce. Premises 1-4 above already contradict this on archived records.
- A repair is falsified if, on the committed tree, a live goal inside an
  allocation records any ORCA probe `not_run` for the allocation reason, or
  if any node branch contains a file whose content another launch wrote.

## Repairs (committed before any job)

- e68c1bc3 jobs: every engine run writes in a scratch directory no earlier run left (S1, S3-S5)
- d2b3e6ca jobs: ORCA's numbered temporaries stay in scratch (S2)
- 0cb2bf09 agent: ORCA's input check runs where the controller runs, inside an allocation too (E1, S7)
- 364bf2fd jobs: an ORCA project cannot state cores or memory; the refusal names the grant (R1)

Each has a witness red on its parent and green on it. Full suite at 5965fe61
from a `git archive` export: 23 failed / 4433 passed -- the round's 23
environmental failures (InChI, CDX, PySCF dispersion probe); none in a file
this episode touched.

## Pre-registration

(written before each job is issued; never edited after its result)

### O1 -- oracle, provider-free, real ORCA 6.1.1, one slot job (8 tasks, 24 GB, 1 h)

`/project/xlzhang/jiseung/r10/q9/oracle1/{job.sh,oracle.py}`; two packed trees,
`code-base` = d2c192af (the round's base) and `code-repaired` = this branch's
code (digest ad888d1d... at 5965fe61; chemsmart/ unchanged since). Inputs are
pair3-b's archived files copied read-only into `oracle1/inputs/` (sha256 in
the job's own listing): cycle-3's `.inp` with `MaxCore 1800`, cycle-2's
valid DLPNO `.inp`, cycle-1's `geom-h-atom.xyz`, `prj-h-sp-cc.yaml`
(UHF DLPNO-CCSD(T)/def2-TZVP), `prj-h-sp-dft.yaml` (UHF wB97X-D3BJ/def2-TZVP),
cycle-3's `proj-radical-cc-r3b.yaml`. TMPDIR is set to the q9 scratch.

Expected, per part (a miss on the repaired tree falsifies that repair on real
ORCA; a miss on the base tree falsifies my reading of the archived loss):

- A (the probe function, both trees): `maxcore-cycle3.inp` -> `aborted`, engine
  lines contain `UNRECOGNIZED OR DUPLICATED KEYWORD(S) IN SIMPLE INPUT LINE`
  and `MAXCORE 1800`, wall < 5 s; `dlpno-cycle2.inp` -> `passed`, wall < 20 s.
  Repaired: the work root is empty afterwards. No ORCA process left after
  either tree.
- B (the host's `_probe_input_check` under this job's SLURM_JOB_ID): base ->
  both `not_run`, reason "inside a scheduler allocation ..."; repaired ->
  rad-sp-cc-r3 `aborted` with ORCA's lines and a review line starting
  `input-check probe: aborted`, radical-sp-cc `passed`; the envelope's scratch
  root holds nothing afterwards.
- C (the executor's command line on geom-h-atom.xyz, same label twice: node-a =
  h-sp's project, node-b = h-sp-dft's project, one shared scratch root; control
  = h-sp-dft's project alone in its own root). Both trees: node-a exits nonzero
  (MDCI error, as h-sp did); node-b and control terminate normally.
  Base: node-b's output shows `GBW file was renamed to GES file`; node-b holds
  names the control does not (at least `.ges`); node-a holds >= 1 `.tmp` file.
  Repaired: no AutoStart line in node-b; node-b's names are a subset of the
  control's; node-a holds no `.tmp` file; the shared scratch root holds exactly
  one directory afterwards (node-a's `<label>-<hex>`, kept because it failed).
  Physics: E(node-b) = E(control) within 1e-6 Eh in each tree, both equal to
  the archived h-sp-dft value -0.505034793652 Eh within 1e-6 Eh (the same
  input on the same ORCA; an H-atom UHF-DFT solution is unique, so AutoStart
  is not expected to move the number -- the defect is provenance, not value).
- D (the ORCA project loader on cycle-3's project): base loads it with
  `MaxCore 1800`; repaired refuses it with the message naming the grant.

### G1 -- live Agent goal on the repaired tree (the milestone run)

`goals/g1`: methanol O-H BDE, task text in the shape of Q6's pair3 (level of
theory the model's choice), ORCA the only program the envelope allows;
8 cores / 16 GB, node 1800 s, episode 7200 s, 12 engine calls, 2 revisions;
allocation 8 tasks / 24 GB / 2:20:00; delegated approval
(`claude-researcher-q9-owner-delegated`, never a human decision); model
deepseek-v4-flash-0731 via alibaba-token-plan.

Infrastructure expectations (the question; read from events, ledger, branches
and scratch):
1. Every `input_check_probed` event for an ORCA node has status `passed` or
   `aborted` with wall < 20 s; none is `not_run` for the allocation reason.
   Any `not_run` for another reason is reported with its reason. FAIL if any
   allocation-reason `not_run` appears.
2. No ORCA output in any branch contains `GBW file was renamed to GES file`;
   no branch holds a `.ges` or a `.tmp` file; every file an engine wrote in a
   branch carries that branch's own job label; the scratch root holds one
   `<label>-<hex>` directory per failed launch and none for completed ones.
3. If a node fails and a later node of the same label runs (pair3-b's pattern:
   a DLPNO step on the H atom dies in MDCI and the atom is recomputed), the
   later branch holds only its own run's files (checked as in O1-C). If no
   such pair occurs, expectation 3 is not tested by G1 and rests on O1-C;
   that is reported, not re-rolled.
4. If the session writes a resource token into a route, the project is refused
   naming the grant before any engine call (not expected; reported if seen).

Physics (sanity, recorded not scored): a delivered BDE(298 K) of methanol's
O-H in 100-110 kcal/mol (Blanksby & Ellison 2003 list 105.2 +/- 0.7 kcal/mol --
recalled, not read this session, so only a band); an H-atom energy, if one is
computed, within [-0.51, -0.49] Eh.

Agent-side facts (method, failures, repairs, claims) are recorded as
deepseek-v4-flash behaviour and are not what G1 tests. A session with zero
provider turns or a `turn_deadline_exceeded` death is infrastructure.

### G2 -- conditional, pre-registered now

Issued only if G1 shows no failed-then-same-label pair (expectation 3
untested) AND O1-C passes: the same shape of goal on the hydrogen atom alone,
"What is the energy of the hydrogen atom at the DLPNO-CCSD(T)/def2-TZVP
level?", same envelope numbers. Expectation: ORCA's MDCI refuses DLPNO on one
electron (as h-sp did), and whatever the session computes next on the same
geometry file runs in its own scratch and its branch holds only its own
files (expectations 1-3 of G1). Physics band: an H-atom energy delivered at a
one-electron-exact wavefunction method with def2-TZVP within
-0.49981 +/- 0.00002 Eh (the archived UHF/def2-TZVP reference energy of h-sp,
-0.49980983 Eh).

## Jobs issued

| job | slot | what | code | pre-registration digest |
|---|---|---|---|---|
| 2150437 | r10-q9-a | O1 oracle (base d2c192af + repaired 55e4424a) | trees verified in-job | ace1a6ecdd8d |
| 2150438 | r10-q9-b | G1 methanol O-H BDE goal | 55e4424a, digest ad888d1d | ace1a6ecdd8d |
| 2150471 | r10-q9-a | O2 probe leftovers, before 55e4424a / after 279b11cb (digest 7b2fb624) | verified in-job | 780f83311007 |

## O1 read (Slurm 2150437, chpc-cn071, 10:39-10:41 CST; both code digests verified in-job)

Reports: `/project/xlzhang/jiseung/r10/q9/oracle1/{base,repaired}/report.json`.

| part | base d2c192af | repaired 55e4424a | pre-registered |
|---|---|---|---|
| A probe fn, MaxCore input | aborted, 1.43 s, ORCA's lines incl. `UNRECOGNIZED OR DUPLICATED KEYWORD(S) IN SIMPLE INPUT LINE`, `MAXCORE 1800` | aborted, 0.11 s, same lines | met |
| A probe fn, valid DLPNO input | passed, 0.45 s | passed, 0.12 s | met |
| A work root afterwards | empty (TMPDIR) | empty (granted scratch) | met |
| B host path under SLURM_JOB_ID, rad-sp-cc-r3 | `not_run` "inside a scheduler allocation" | `aborted` 0.11 s; review line `input-check probe: aborted ...` + ORCA's lines | met |
| B host path, radical-sp-cc | `not_run` | `passed` 0.24 s | met |
| C node-a (h-sp's DLPNO on H) | exit 1 (MDCI) | exit 1 (MDCI) | met |
| C node-b AutoStart from node-a | yes (`GBW file was renamed to GES file`) | no | met |
| C node-b names not in control | `.ges .loc .qro .uno .unso` (4 byte-identical to node-a's) | none | met |
| C node-a `.tmp` files | `cpscfdata.tmp.0`, `propint.tmp.0` | none | met |
| C shared scratch afterwards | `<label>` (node-a's, reused by node-b) | one `<label>-ea87dbbf` (node-a's) | met |
| C E(node-b) vs E(control) | **-0.505034793652 vs -0.505029107556** | -0.505029107556 = -0.505029107556 | **base FALSIFIED my physics expectation** |
| D cycle-3 project | loads, `MaxCore 1800` | refused, the grant message | met |

Corrected premise (mine, pre-registered wrong): "an H-atom UHF-DFT solution is
unique, so AutoStart is not expected to move the number". It moved it. The
contaminated node-b converged in 7 cycles to -0.50503479 Eh with its virtual
p shell split (1.463959, 1.463959, 1.464080 Eh); every clean run (base
control, repaired node-b, repaired control) converged in 8 cycles to
-0.50502911 Eh with the p shell threefold degenerate (1.463386 x 3) and the
same occupied 1s (-0.432978). The stale guess -- the failed DLPNO run's
orbitals -- led the SCF to a slightly symmetry-broken one-electron solution
5.7 microEh lower (self-interaction rewards a polarised density). The archived
Q6 pair3-b h-sp-dft value, -0.505034793652, equals the contaminated run to
every printed digit: that recorded number is not reproducible from its own
recorded command in a clean scratch. The defect is value as well as
provenance (negligible in kcal/mol here, 0.0036; an atom's broken degeneracy
is the fingerprint).

Not measured: "no ORCA process left" -- `pgrep -u $USER` counted 66 ORCA
processes before and after on a node shared with another R10 job of the same
account (q4's 64-core goal 2149497 on chpc-cn071); the instrument cannot
attribute them. The probe's own directories were empty afterwards.

## After the issue (not in the packed tree G1 runs; off the Agent path)

- f65dab8b jobs: ORCA reads the geometry files an input names from the input it
  was given -- a regression e68c1bc3 introduced in `orca inp` with scratch
  (first run FileNotFoundError), found by reading the tree after the O1 issue;
  red at 364bf2fd's runner, green here, green on d2c192af too.
- ba1dd2e7 shared: the ORCA inp job no longer pre-stages its input at
  `<scratch>/<label>` (chemsmart/jobs/orca/job.py, outside the radius).
Neither touches an Agent node (every Agent branch is empty before launch, so
the runner never takes the supplied-input path); G1's tree 55e4424a stands for
the Agent path.

## Integration check

Merged r10-integration (c79c39a1, Q6's reading turn) at 95c4349e, no
conflict. Full suite from a `git archive` export of 95c4349e: 23 failed /
4439 passed, the failing set identical to the pre-merge run (all in
test_structures, test_PyscfSettings, test_aggregation,
test_pyscf_dispersion_conformance; none in tests/agent). ruff, black, isort
clean on every file this episode touched.

## G1 so far (host records, read-only)

The first three ORCA compiles of the live session (opt-ch3oh, opt-ch3o,
sp-h) each carry an `input_check_probed` event with status `passed`, wall
0.35 / 0.13 / 0.12 s, inside Slurm 2150438 -- the first ORCA input checks to
run inside an allocation in R10 (every earlier one was `not_run`).

## A defect of my own change, seen live in G1, repaired (9774ed01)

G1's granted scratch holds an empty `chemsmart-input-check-s1d5dfb2`
(created 11:11:23.5 HKT, last touched 11:11:24.0; the sp-h-ccsd probe event
is 03:11:24.02 UTC; still there 30 s later); the three earlier probes and
O1's four left nothing. Inferred mechanism: past its banner ORCA starts a
module in children of its own; `_stop` waited for the leader only, so the
probe could rmtree while a child held its files open, and on NFS an open
unlinked file survives as a placeholder. 9774ed01 waits on the process group
and retries the removal; its witness (a child ignoring SIGTERM) is red on
936f04fe, green on 9774ed01.

### O2 -- pre-registered before issue: the probe's leftovers on real ORCA + NFS

`oracle2/{job.sh,oracle2.py}`, one slot job (8 tasks, 16 GB, 40 min).
Input: G1's retained sp-h-ccsd input (sha256 0449bd9d...; CCSD(T)/def2-QZVPPD
AutoAux, UHF, `%pal nprocs 8`), the one whose probe left the directory. Thirty
probes per tree into `/scratch/.../q9/oracle2/<tree>`: before = 55e4424a
(oracle1/code-repaired), after = 9774ed01's code. After each return: my
processes whose cwd lies in the work root, and the root's entries, at return
and 3 s later.
- after: 30/30 `passed`; 0 probes with a process inside the root at return;
  0 entries at return; root empty at the end. Any miss falsifies 9774ed01.
- before: the race is timing-dependent; I expect >= 1 of 30 probes with a
  process inside the root at return or an entry left. If 0/30 on both, the
  mechanism is not reproduced and stays inferred (reported as such; the
  repair stands on its witness and on "after" being clean, not on this).

### O2 read (Slurm 2150471, chpc-cn071, 11:16-11:19 HKT; both digests verified in-job)

| | before (55e4424a) | after (279b11cb, contains 9774ed01) | pre-registered |
|---|---|---|---|
| status | 30/30 passed, wall <= 0.54 s | 30/30 passed, wall <= 0.57 s | met |
| probes with a process of mine inside the work dir at return | **10/30**, every one `mpirun -np 8 .../orca_startup_mpi` | 0/30 | met (before: mechanism reproduced) |
| probes with entries in the root at return | 21/30 | 0/30 | met |
| directories left at the end | 10 | 0 | met |

The mechanism is no longer inferred: ORCA 6.1.1 launches `mpirun -np 8
orca_startup_mpi` past its INPUT FILE banner inside the probe's 0.1 s poll;
the old `_stop` returned with mpirun alive, and NFS kept the directory. No
process was still inside 3 s later in either tree. **Corrected premise
(mine, stated as fact in 0cb2bf09): the probe does start MPI ranks; it is
safe inside an allocation because it now waits on its whole group on the
allocation's cores** (424776df corrects the docstring).

## G1, partial (host records read before the gate closed ~11:30 HKT)

- cycle-1: opt-ch3oh, opt-ch3o, sp-h (wB97X-D3BJ/def2-TZVPPD on the H atom,
  UHF); every ORCA input check `passed` inside the allocation (0.35, 0.13,
  0.12 s).
- cycle-2: sp-h-ccsd (canonical CCSD(T)/def2-QZVPPD AutoAux on the same H
  geometry file -- the same job label as sp-h), check `passed` (0.43 s); the
  engine died in MDCI: "Number of processes (8) in parallel calculation
  exceeds number of pairs (0)", reference energy -0.499983298 Eh (UHF near
  its limit, -0.5 exact). Its branch holds only its own run's files and no
  `.tmp`; its failed scratch is its own `geometry-h-atom_sp_sp_gas_phase-dcaea49d`.
  The same-label predecessor (sp-h) had completed, so this is not yet a
  failed-then-same-label pair; expectation 3 is tested only if a later node
  reruns the atom on that file.
- the empty probe directory of the sp-h-ccsd check (expected on 55e4424a,
  per O2; repaired by 9774ed01, not in G1's tree).

Settlement not read: the SSH gate closed (hpc --check: GATE CLOSED at 12:31
KST = 11:31 HKT) while the job was running (elapsed 42 min at 11:21 HKT; its
limit is 2:20). The waiter's "no longer in the queue" line is an artefact of
the closed gate (an empty squeue answer), not a job state.

## Status

O1, O2 read. **Waiting on job 2150438 (G1) and on the gate** to read its
settlement and branches; G2 is decided from that reading.
