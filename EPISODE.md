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

(none yet)

## Status

Repairs committed; O1 and G1 pre-registered; next: pack, upload, submit.
