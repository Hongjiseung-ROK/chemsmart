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

To be completed in this file before any repair is committed.

## Falsifiers

- Premise falsified if every environment-dependent branch and every
  scratch/copy-back path either keeps its guarantee inside an allocation or
  is refused visibly, and no reader reads a file its own node did not
  produce. Premises 1-4 above already contradict this on archived records.
- A repair is falsified if, on the committed tree, a live goal inside an
  allocation records any ORCA probe `not_run` for the allocation reason, or
  if any node branch contains a file whose content another launch wrote.

## Pre-registration

(written before each job is issued; never edited after its result)

## Jobs issued

(none yet)

## Status

Census in progress (provider-free).
