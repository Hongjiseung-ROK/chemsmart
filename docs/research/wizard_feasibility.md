# `/wizard` feasibility for server YAML autofill

- Date: 2026-05-10
- Scope: research only; no code changes
- Base considered for implementation: `fork/main` at `f37038e3`
- Verdict in one line: **feasible, deterministic-first, with LLM use kept to narrow ambiguity-resolution around human-formatted module output rather than scheduler/resource discovery.**

## 1. Topology decision tree

`/wizard` should not ask "are you on the cluster or on your laptop?" as its first question. It can derive the topology from runtime evidence plus any explicit SSH destination already present in the slash-command argument or active server context.

### Runtime decision tree

1. Parse the slash-command argument and active server context.
   - If the request already carries an SSH destination (`user@host`, SSH alias, or existing `SERVER.HOST`) and that destination is not local, select **Mode B**.
   - Else continue.
2. Run a local HPC-signature probe.
   - Check for scheduler evidence: `env | egrep '^(SLURM_|PBS_|LSB_|SGE_)'`, `command -v sinfo`, `command -v qstat`, `command -v bqueues`, `command -v qconf`.
   - Check for login-node evidence: `type module`, `hostname -f`, `command -v g16`, `command -v orca`, `command -v nciplot`.
   - Check that at least one scheduler read-only query actually works: `sinfo --json`, `qstat -Q -f`, `bqueues -l`, or `qconf -sql`.
3. If the local HPC-signature probe succeeds, select **Mode A**.
   - Probe locally.
   - Write `SERVER.HOST: localhost` (or `local`) explicitly so `chemsmart.agent.transport._is_local_host()` stays on the local-submit path instead of trying `ssh <yaml-filename-stem>`.
4. If the local HPC-signature probe fails but a remote destination is derivable from the request, SSH config alias, or existing server context, select **Mode B**.
   - Probe with `ssh -o BatchMode=yes "$HOST" '<command>'`.
   - Write `SERVER.HOST: <ssh-alias-or-user@host>`.
5. If neither local HPC evidence nor a remote destination is derivable, stop and ask only for the missing destination.
   - This is not a topology prompt.
   - It is a deterministic "no target host can be inferred" gate.

### Operational rule

- **Mode A** = chemsmart is already running on the HPC login node that will submit jobs.
- **Mode B** = chemsmart is running elsewhere and must probe/submit over SSH.
- The probe set is the same in both modes; only the transport changes.

## 2. Per-field source matrix

Mode B uses the same commands over SSH, e.g. `ssh -o BatchMode=yes "$HOST" '<probe>'`.

| Field | Probe command(s) | AI needed? | Deterministic fallback | User-prompt fallback |
|---|---|---|---|---|
| `SERVER.HOST` | Mode A: `hostname -f`; Mode B: request arg / active server / `ssh -G <alias> \| awk '/^hostname /{print $2}'` | N — the value is topology-derived, not interpretive | Mode A: write `localhost`; Mode B: use the exact alias or `user@host` token already supplied | Ask for SSH alias or confirm `localhost` |
| `SERVER.SCHEDULER` | `sinfo --json`; `qstat -Q -f -F json`; `bqueues -l` or `bqueues -o ... -json`; `qconf -sql` | N — scheduler family can be detected from command success plus parseable signatures | Leave unset and reject the run if no single family is confirmed | Ask for scheduler family only after ambiguity/failure is shown |
| `SERVER.QUEUE_NAME` | `scontrol show partition --oneliner`; `qstat -Q -f -F json`; `bqueues -l`; `qconf -sq <queue>` + `qstat -f` | N — default queue selection can follow fixed ranking rules | Choose scheduler-declared default; else enabled+started non-GPU queue with the shortest stable name; else leave placeholder | Ask user which queue/partition should be the default |
| `SERVER.NUM_HOURS` | Same queue/partition probes as above | N — use queue default if present, else a fixed safe default | Queue default if exposed; else `24`; never copy "infinite" max time | Ask for default walltime if site policy differs |
| `SERVER.MEM_GB` | SLURM: `scontrol show partition --oneliner`, `scontrol show nodes --oneliner`; PBS: `qstat -Q -f -F json`, `pbsnodes -av -F json`; LSF: `bqueues -l`, `bhosts -l -gpu`; SGE: `qhost -F` | N — resource values are numeric parses | Use queue default memory; else node memory; else conservative `64` | Ask for per-job memory default |
| `SERVER.NUM_CORES` | Same scheduler/node probes as `MEM_GB` | N — CPU counts are structured resource fields | Use queue default if exposed; else moderate shared-node default (`16` or `32`) rather than full node | Ask for default CPU count |
| `SERVER.NUM_GPUS` | SLURM `scontrol show nodes --oneliner`; PBS `pbsnodes -av -F json`; LSF `bhosts -l -gpu`; SGE `qhost -F` if GPU complex exists | N — GPU defaults should only come from explicit evidence | `0` unless the chosen queue is clearly GPU-scoped | Ask whether this server YAML should target a GPU queue |
| `SERVER.NUM_THREADS` | Same as `NUM_CORES`; optionally `lscpu` for Mode A | N — v1 can tie threads to cores | Set equal to `NUM_CORES` | Ask only if site needs a different OpenMP default |
| `SERVER.SUBMIT_COMMAND` | Derived from confirmed scheduler family | N — this is a fixed mapping | `SLURM→sbatch`, `PBS→qsub`, `LSF→bsub < `, `SGE→qsub` | None needed unless maintainer wants overrides |
| `SERVER.PROJECT` | No reliable portable read-only probe; optional weak hints from `sacctmgr`, `qmgr`, `groups`, or sample env vars if visible | N — account/project discovery is site-policy data, not something the tool should guess | Leave commented or null | Ask user for allocation/account/project string |
| `SERVER.SCRATCH_DIR` | `printf '%s\n' "$SCRATCH" "$WORK" "$TMPDIR"`; `test -d ~/scratch -a -w ~/scratch`; `getent passwd "$USER" \| cut -d: -f6`; `df -h` | N — path presence and writability are deterministic | Use the first writable stable user scratch root; else `null` | Ask for scratch root path |
| `SERVER.USE_HOSTS` | No probe required | N — current templates already standardize this | `true` | None |
| `SERVER.EXTRA_COMMANDS` | No reliable portable probe; optionally inspect `echo "$PATH"` and current shell init for comments only | N — safer to leave blank than invent activation logic | Keep comment-only block | Ask user for site-specific extra exports if needed |
| `GAUSSIAN.EXEFOLDER` | `command -v g16`; `readlink -f "$(command -v g16)"`; if missing, `module -t avail 2>&1 \| egrep 'gaussian|g16'`; `module show <candidate>` | Y — module-only installs often require interpreting site-local names before picking the right executable root | If `g16` is on `PATH`, use its parent dir; else leave placeholder | Ask for Gaussian install path or module name |
| `GAUSSIAN.LOCAL_RUN` | No probe required | N — existing scheduler templates agree on this default | `True` | None |
| `GAUSSIAN.SCRATCH` | Reuse scratch probe plus `test -w "$SCRATCH_DIR"` | N — this is a policy boolean driven by scratch availability | `True` only if a writable scratch root was confirmed; else `False` | Ask whether Gaussian should stage into scratch |
| `GAUSSIAN.CONDA_ENV` | `echo "$CONDA_PREFIX"`; `conda info --base 2>/dev/null`; `type conda` | N — only observed environments should be emitted | Leave blank if chemsmart env is not directly discoverable | Ask for activation snippet |
| `GAUSSIAN.MODULES` | `module -t avail 2>&1 \| egrep 'gaussian|g16'`; `module spider gaussian 2>&1`; `module show <candidate>` | Y — `module avail` output is noisy and selecting the minimal correct load-set is site-local | If `g16` is already on `PATH`, emit `module purge` only or leave blank | Ask for exact module load lines |
| `GAUSSIAN.SCRIPTS` | `find "$GAUSSIAN_EXEFOLDER" -path '*g16.login' -o -path '*bsd/g16.login' 2>/dev/null` | Y — deciding whether a found login script is required or redundant depends on site conventions | If `g16.login` is found under the chosen root, emit the exact `tcsh -c 'source ...'`; else blank | Ask whether Gaussian needs a login script |
| `GAUSSIAN.ENVARS` | Derive from `EXEFOLDER`; scratch probe; `env \| egrep '^GAUSS_EXEDIR=|^g16root=|^SCRATCH='` | N — these are direct path rewrites | Emit only observed/derived `SCRATCH`, `GAUSS_EXEDIR`, and `g16root`; else minimal/blank | Ask for missing Gaussian env vars |
| `ORCA.EXEFOLDER` | `command -v orca`; `readlink -f "$(command -v orca)"`; if missing, `module -t avail 2>&1 \| egrep '(^|/)orca'`; `module show <candidate>` | Y — many sites expose ORCA only through modulefiles with local naming | If `orca` is on `PATH`, use its parent dir; else placeholder | Ask for ORCA install path or module name |
| `ORCA.LOCAL_RUN` | No probe required | N — current scheduler templates agree on this default | `False` | None |
| `ORCA.SCRATCH` | Reuse scratch probe plus writability test | N — boolean from confirmed scratch availability | `True` only if scratch is confirmed; else `False` | Ask whether ORCA should stage into scratch |
| `ORCA.CONDA_ENV` | `echo "$CONDA_PREFIX"`; `conda info --base 2>/dev/null`; `type conda` | N — same rule as Gaussian | Leave blank if not directly observed | Ask for activation snippet |
| `ORCA.MODULES` | `module -t avail 2>&1 \| egrep '(^|/)orca|openmpi|intelmpi'`; `module spider orca 2>&1`; `module show <candidate>` | Y — choosing a compatible ORCA + MPI module pair is often site-specific | If `orca` is already on `PATH`, emit `module purge` only or blank | Ask for exact module load lines |
| `ORCA.ENVARS` | Scratch probe; `env \| egrep '^SCRATCH=|^PATH=|^LD_LIBRARY_PATH='` | N — only observed vars should be carried through | Emit only `SCRATCH` by default; avoid guessing MPI library exports | Ask for any required MPI/library exports |
| `NCIPLOT.EXEFOLDER` | `command -v nciplot`; `readlink -f "$(command -v nciplot)"`; if missing, `module -t avail 2>&1 \| egrep 'nciplot|nci'`; `module show <candidate>` | Y — if NCIPLOT is module-only, the naming can be site-local | If `nciplot` is on `PATH`, use its parent dir; else placeholder | Ask for NCIPLOT install path or module name |
| `NCIPLOT.LOCAL_RUN` | No probe required | N — current scheduler templates agree on this default | `False` | None |
| `NCIPLOT.SCRATCH` | Reuse scratch probe plus writability test | N — same as Gaussian/ORCA | `True` only if scratch is confirmed; else `False` | Ask whether NCIPLOT should stage into scratch |
| `NCIPLOT.CONDA_ENV` | `echo "$CONDA_PREFIX"`; `conda info --base 2>/dev/null`; `type conda` | N — observed-only | Leave blank | Ask for activation snippet |
| `NCIPLOT.MODULES` | `module -t avail 2>&1 \| egrep 'nciplot|nci'`; `module spider nciplot 2>&1`; `module show <candidate>` | Y — same free-form module-name problem as Gaussian/ORCA | If executable is already on `PATH`, emit `module purge` only or blank | Ask for exact module load lines |
| `NCIPLOT.ENVARS` | Scratch probe; derive `NCIPLOT_HOME` from `EXEFOLDER`; `env \| egrep '^SCRATCH=|^NCIPLOT_HOME='` | N — direct derivation only | Emit only observed/derived `SCRATCH` and `NCIPLOT_HOME`; else blank | Ask for missing NCIPLOT env vars |

## 3. AI-vs-deterministic verdict

### Bottom line

A viable v1 does **not** need an LLM for scheduler detection, queue parsing, node-resource discovery, SSH reachability checks, or YAML rendering. Those are better handled deterministically. The only place where LLM use is justified is **resolving human-formatted software-environment ambiguity after deterministic probes have already narrowed the candidate set**.

### Steps that should stay purely deterministic

1. **Mode A vs Mode B topology choice**
   - Derive from local scheduler evidence plus explicit/nonlocal `HOST` evidence.
2. **Scheduler detection**
   - `sinfo --json`, `qstat -Q -f -F json`, `bqueues`, `qconf -sql` are parser problems, not reasoning problems.
3. **Queue / partition choice**
   - Prefer scheduler-declared defaults; else apply fixed ranking rules.
4. **`NUM_HOURS` for unknown queues**
   - Use a hard fallback like `24`; this should not be model-generated.
5. **Node resource extraction**
   - CPU, memory, GPU counts are structured fields when available.
6. **Scratch discovery and writability gates**
   - `test -w`, env vars, and path existence checks are deterministic.
7. **YAML emission and validation**
   - Render from normalized facts and preserve placeholders when facts are missing.
8. **Node cache refresh**
   - Timestamped sidecar JSON and staleness checks are deterministic.

### Steps where LLM use is justified

1. **Interpreting noisy `module avail` / `module spider` output when multiple candidates survive regex filtering**
   - Example: ranking `gaussian/g16-c01`, `gaussian/16-C.01-avx2`, and `chem/gaussian16` after deterministic token matching.
2. **Choosing the least-surprising module stanza when the site exposes many valid-but-different stacks**
   - Especially ORCA+MPI combinations where several module pairs might work.
3. **Explaining ambiguity back to the user in one concise summary**
   - This is UX work, not control-plane logic.

### Steps where LLM use is optional but should not be required

1. **Mapping site-local module names like `gaussian/g16-c01` to chemsmart's program block**
   - Deterministic alias tables should run first (`gaussian`, `g16`, `g09`, `orca`, `nciplot`).
   - Use an LLM only as a tie-breaker when multiple candidates remain.
2. **Synthesizing human-readable comments in `EXTRA_COMMANDS` or blank blocks**
   - Nice to have, but the file should remain valid without it.

### Recommended control policy

- **Default path:** deterministic probe → deterministic normalization → YAML render.
- **LLM path:** only invoked on an explicit ambiguity object, never on raw scheduler output first.
- **If the LLM path fails:** keep the wizard running, preserve the best deterministic candidate, and fall back to warn-pause.

## 4. Auto-update nodes

### Recommendation

Use **on-demand refresh**, not a daemon.

### Why not a daemon

- Login nodes at NERSC/TACC/OLCF are the wrong place for an always-on watcher.
- Queue/node state is scheduler-owned and changes faster than a static YAML should.
- A daemon would add background SSH traffic, session management, and failure-recovery complexity for little gain.

### Storage model

Keep dynamic scheduler facts in a sidecar cache:

- `~/.chemsmart/server/<name>.cache.json`

Do **not** mutate the user's YAML after initial creation unless the user explicitly reruns `/wizard` or a future `/wizard refresh --write` equivalent.

### What belongs in the cache

- `host`
- `mode` (`local` or `ssh`)
- `scheduler`
- `probed_at`
- `source_commands`
- normalized partitions/queues
- node summaries (`cpu`, `mem_gb`, `gpu`, `state`, counts)
- discovered program candidates
- `status` (`fresh`, `stale`, `error`)
- `last_error` if refresh failed

### Refresh cadence

1. Refresh immediately after a successful `/wizard` run.
2. Refresh on demand when the user runs `/wizard` again for that server.
3. Refresh opportunistically before `validate_runtime` or `submit_hpc` **only if** the cache is older than 24 hours.
4. Never refresh more than once per session unless the user asks.

### Failure behavior

- If refresh fails and a previous cache exists:
  - keep the last good cache,
  - mark it `stale`,
  - warn but do not rewrite YAML.
- If refresh fails and no cache exists:
  - keep the static YAML,
  - mark dynamic node data unavailable,
  - warn-pause rather than inventing node facts.
- Cache misses or stale cache must never block local YAML loading.

## 5. Per-scheduler probe commands

Reused verbatim from `docs/research/setup_agent_feasibility.md` §5 because the probe plan is still correct for `/wizard`.

### Normalization policy before the table
Projected normalization rules:
- `SCHEDULER` comes from positive command family detection.
- `QUEUE_NAME` is the default partition/queue if the scheduler exposes one; else the shortest “normal/general/workq”-like queue that is enabled and started.
- `NUM_HOURS` should be conservative:
  - use queue default if present,
  - else use a bounded fallback such as 24,
  - never copy an “infinite” max walltime into the default.
- `MEM_GB` should prefer queue default memory if present; else a conservative node-level estimate.
- `NUM_CORES` should reflect a common per-job request size, not necessarily the full node size if the default queue is shared.
- `NUM_THREADS` should default to `NUM_CORES` unless a site-specific reason suggests otherwise.
- `NUM_GPUS` should default to `0` unless the chosen queue is clearly a GPU queue.
- `SUBMIT_COMMAND` is scheduler-family-specific.
- `SCRATCH_DIR` should come from discovered site scratch if stable, else remain `null`.
- `USE_HOSTS` should remain `true` unless future testing proves otherwise.
- `EXTRA_COMMANDS` should start empty except for comments / TODOs.
### Scheduler detection sequence
Projected sequence:
1. If `scheduler_hint` is provided, test that family first.
2. Else test:
   - SLURM,
   - PBS,
   - LSF,
   - SGE.
3. If multiple families appear present, prefer the family with the strongest parseable evidence.
4. If still ambiguous, return ambiguity instead of guessing.
### Command-to-field mapping table
| Scheduler | Command | Verified source | Parse target | YAML field(s) populated | Confidence class | Notes |
|---|---|---|---|---|---|---|
| SLURM | `sinfo --json` | Official Slurm docs confirm JSON output and that filtering still applies (https://slurm.schedmd.com/sinfo.html) | Partitions, partition states, max time, node counts | `SCHEDULER`, candidate `QUEUE_NAME`, candidate `NUM_HOURS` | High | Best first probe when available because it is machine-readable |
| SLURM | `scontrol show partition --oneliner` | Official Slurm docs confirm `--oneliner`; partition fields documented in `scontrol` page (https://slurm.schedmd.com/scontrol.html) | `Default`, `DefaultTime`, `MaxTime`, `DefMemPerCPU`, `DefMemPerNode`, `MaxMemPerCPU`, `Nodes`, `State` | `QUEUE_NAME`, `NUM_HOURS`, `MEM_GB`, queue notes | High | Prefer over ad hoc text formatting because `oneliner` reduces line-wrap ambiguity |
| SLURM | `scontrol show nodes --oneliner` | Command family documented; field use projected from normal Slurm output | `CPUTot`, `ThreadsPerCore`, `Gres`, `RealMemory` | `NUM_CORES`, `NUM_THREADS`, `NUM_GPUS`, `MEM_GB` fallback | Medium | This specific field mapping is projected because I did not fetch the node-field reference page in this pass |
| SLURM | `squeue -h -u $USER` | Requested by user flow; command presence is also used by local detection in code (`chemsmart/settings/server.py:360-365`) | Access sanity check, duplicate queue visibility, account hints | none directly; evidence only | Medium | Useful as a read-only “can this login node see the queue state?” check |
| PBS | `qstat -Q -f -F json` | Official PBS user guide documents queue long format and JSON mode for qstat (https://2019.help.altair.com/19.2/PBSProfessional/PBSUserGuide19.2.1.pdf) | Queue list, `enabled`, `started`, queue defaults, attributes | `SCHEDULER`, `QUEUE_NAME`, candidate `NUM_HOURS`, candidate `NUM_CORES`, candidate `MEM_GB` | High | Preferred when JSON is supported |
| PBS | `qstat -Q -f` | Official PBS guide shows exact text output format and attributes like `queue_type`, `enabled`, `started` (same PDF URL) | Same as above in text form | same fields as JSON fallback | High | Text fallback when JSON unavailable |
| PBS | `qstat -B -f` | Official PBS guide documents server long format (same PDF URL) | Server defaults, version, default queue | `QUEUE_NAME` fallback, informational notes | Medium | Helpful when queue default is omitted in per-queue output |
| PBS | `pbsnodes -av -F json` or `pbsnodes -av` | Projected, not fetched in this pass | Node memory, ncpus, GPU resources if site publishes them | `MEM_GB` fallback, `NUM_CORES`, `NUM_GPUS` | Medium | Needed because queue defaults often omit node hardware |
| LSF | `bqueues -l` | IBM docs describe queue long format and included scheduling/resource fields (https://www.ibm.com/docs/en/spectrum-lsf/10.1.0?topic=reference-bqueues) | Queue description, resource limits, open/active state | `SCHEDULER`, `QUEUE_NAME`, candidate `NUM_HOURS`, candidate `MEM_GB`, notes | High | Strongest queue-level probe for LSF |
| LSF | `bqueues -o ... -json` | IBM docs document customized JSON output (same URL) | Stable field extraction for queue names, status, limits | same fields as above | High | Better parser target than plain text when available |
| LSF | `bhosts -l -gpu` | IBM docs document `bhosts` and the `-gpu` family for host GPU info (https://www.ibm.com/docs/bg/spectrum-lsf/10.1.0?topic=reference-bhosts; search results also point to IBM GPU docs) | Host status, slots, GPU presence | `NUM_CORES`, `NUM_GPUS`, `MEM_GB` fallback | Medium | Hardware inference requires host-level aggregation |
| LSF | `lsid` | Projected common practice, not fetched in this pass | Cluster identity and version | none directly | Low | Useful only as additional evidence |
| SGE | `qconf -sql` | Grid Engine docs show this as the queue list command (https://manpages.debian.org/trixie/gridengine-client/qconf.1.en.html and Oracle/Sun docs surfaced in search) | Queue names | `SCHEDULER`, candidate `QUEUE_NAME` list | High | Best initial SGE queue enumeration |
| SGE | `qconf -sq <queue>` | Grid Engine admin/user docs surfaced in search show it for queue properties | Queue slots and queue configuration | `NUM_CORES`, `NUM_HOURS` candidate, notes | Medium | Exact field interpretation is site-dependent |
| SGE | `qhost -F` | qhost man page documents resource reporting with `-F` (https://manpages.ubuntu.com/manpages/trusty/man1/qhost.1.html) | Host/queue resource values | `MEM_GB`, `NUM_CORES`, possible `NUM_GPUS` if exported as complex | Medium | GPU detection depends on custom complexes |
| SGE | `qstat -f` | Common SGE usage docs show queue-instance listing; fetched docs support qstat family presence indirectly | Queue-instance state and slot usage | `QUEUE_NAME` accessibility check | Low/Medium | Less ideal than `qconf -sq` for durable parsing |
### YAML-field-specific population policy
#### `SCHEDULER`
Projected rule:
- `SLURM` if `sinfo`/`scontrol` parse successfully.
- `PBS` if `qstat -Q -f` or `-F json` returns queue structures.
- `LSF` if `bqueues` returns queue structures.
- `SGE` if `qconf -sql` and `qhost` behave as Grid Engine.
#### `QUEUE_NAME`
Projected rule:
- Prefer scheduler-declared default queue / partition.
- Else prefer the first enabled+started execution queue.
- Else require user confirmation.
#### `NUM_HOURS`
Projected rule:
- If scheduler exposes `DefaultTime`, use it.
- Else if queue max time is finite and modest (for example <= 24h), use that.
- Else fall back to `24`.
- Never infer from currently running user jobs.
#### `MEM_GB`
Projected rule:
- Prefer queue default memory.
- Else compute from node-level memory hints.
- If only per-CPU memory is available, multiply by chosen core count conservatively.
- If nothing trustworthy is available, use template-like conservative defaults rather than full-node memory.
#### `NUM_CORES`
Projected rule:
- Prefer queue default CPU count if one exists.
- Else derive a conservative count from node totals.
- For shared queues, do not assume “whole node”.
- If uncertainty remains large, choose a moderate default (for example 16 or 32) and note the assumption.
#### `NUM_THREADS`
Projected rule:
- Default to `NUM_CORES`.
- Do not attempt to model hyperthreading separately in v1.
- If `ThreadsPerCore > 1` is visible on SLURM, treat it as informational, not as a reason to inflate `NUM_THREADS` automatically.
#### `NUM_GPUS`
Projected rule:
- Set `0` unless the selected queue is clearly GPU-oriented or the probe returns queue-scoped GPU defaults.
- For GPU queues with obvious per-job defaults, set that count.
- Otherwise leave at `0` and let users opt in.
#### `SUBMIT_COMMAND`
Projected rule:
- Use scheduler-family constant:
  - `sbatch` for SLURM,
  - `qsub` for PBS,
  - `bsub < ` for LSF,
  - `qsub` for SGE.
This matches existing local defaults in `Server._get_submit_command()` (`chemsmart/settings/server.py:277-285`).
#### `SCRATCH_DIR`
Projected rule:
- Populate only if a stable path exists and is readable as a user-level convention.
- Do not set to transient scheduler-created directories unless the site documents them as persistent per-user scratch roots.
#### `USE_HOSTS`
Verified and projected mix:
- Templates set this to `true` in all scheduler examples (`chemsmart/settings/templates/.chemsmart/server/SLURM.yaml:13`; `chemsmart/settings/templates/.chemsmart/server/PBS.yaml:13`; `chemsmart/settings/templates/.chemsmart/server/small.yaml:13`).
- I found no runtime use in the current code beyond the accessor (`chemsmart/settings/server.py:247-255`).
- Therefore v1 should preserve template behavior and set `true`.
### Program-block probing plan
#### `GAUSSIAN.EXEFOLDER`
Projected strategy:
- First try `command -v g16`.
- Else probe module candidates.
- Else leave placeholder.
#### `ORCA.EXEFOLDER`
Projected strategy:
- First try `command -v orca`.
- Else probe module candidates.
- Else leave placeholder.
#### `NCIPLOT.EXEFOLDER`
Projected strategy:
- First try `command -v nciplot`.
- Else probe module candidates.
- Else leave placeholder.
#### `LOCAL_RUN`
Projected strategy:
- Keep template defaults unless a site-specific reason suggests otherwise:
  - Gaussian `true`,
  - ORCA `false`,
  - NCIPLOT `false`.
#### `CONDA_ENV`, `MODULES`, `SCRIPTS`, `ENVARS`
Projected strategy:
- If a module system is present and program modules are discovered:
  - emit a `module purge` + `module load ...` snippet.
- If PATH discovery finds executables without modules:
  - keep `MODULES` blank or `module purge` only.
- If scratch is found:
  - populate `ENVARS` with `export SCRATCH=...`.
- For Gaussian only:
  - if `g16.login` or similar is found, populate `SCRIPTS`; else leave blank with a comment.
### My recommended v1 probe ordering
1. SSH reachability and host-key state.
2. Scheduler family.
3. Queue / partition metadata.
4. Scratch environment.
5. Module system and program executables.
6. YAML render.
7. Validation.
8. Human approval.
9. Write.

## 6. Failure modes & deterministic gates

| Failure mode | Gate | Deterministic behavior |
|---|---|---|
| Unknown SSH host key (`StrictHostKeyChecking` would prompt) | Reject | Stop before the first remote probe; instruct user to trust the host out of band or rerun from a pre-established SSH session |
| TOFU/`accept-new` host key path already enabled in user SSH config | Warn-pause | Show that the first probe will mutate `known_hosts`; require explicit approval |
| SSH timeout / unreachable host | Reject | Abort probing; keep no partial YAML updates |
| MFA- or keyboard-interactive-gated SSH login | Reject | Non-interactive probe mode cannot satisfy MFA; instruct user to use ControlMaster, agent-backed auth, or run `/wizard` from the login node |
| Ambiguous scheduler (multiple families return plausible evidence) | Reject | Return the evidence set and require a narrower target or explicit scheduler hint |
| Missing `module` command | Warn-pause | Continue with PATH-based executable detection; leave module blocks blank/placeholder |
| `module avail` returns many plausible candidates | Warn-pause | Run deterministic alias filtering first; if ties remain, optionally invoke LLM ranking or ask user to choose |
| No `g16` / `orca` / `nciplot` found on `PATH` or modules | Warn-pause | Render placeholders for missing program blocks rather than inventing paths |
| Candidate scratch path exists but is not writable or appears sudo-only | Warn-pause | Leave `SERVER.SCRATCH_DIR: null`; set program `SCRATCH: False` unless the user provides a writable path |
| Queue metadata missing default walltime | Warn-pause | Use deterministic fallback `NUM_HOURS: 24` and record the assumption |
| Queue metadata missing memory/core defaults | Warn-pause | Use conservative defaults and record the assumption |
| Existing YAML already present and overwrite not requested | Reject | Refuse to replace user config silently |
| Rendered YAML fails schema/load validation | Reject | Do not write the file |

### Gate philosophy

- **Reject** when the probe path is untrusted, unreachable, or internally contradictory.
- **Warn-pause** when the probe path is valid but incomplete.
- Missing software paths or module names should degrade into placeholders, not hallucinations.

## 7. Implementation breakdown

1. **W3a — remote/local probe primitives**
   - Add one read-only probe wrapper that can run locally or over `ssh -o BatchMode=yes`, because every later step depends on the same transport contract.
2. **W3b — scheduler parsers and normalization**
   - Implement SLURM/PBS/LSF/SGE parsers plus queue/resource ranking first, because these are the most deterministic parts and define the `SERVER` block.
3. **W3c — software-environment probes**
   - Add `module`/`PATH`/scratch discovery separately, because program blocks are much noisier than scheduler facts and deserve isolated review.
4. **W3d — YAML render + validation**
   - Render a candidate server YAML and load-validate it before any UI integration, so the data model is reviewable on its own.
5. **W3e — `/wizard` setup intent + slash command**
   - Thread the new flow into the planner and TUI slash dispatcher only after probes and rendering already exist.
6. **W3f — HOST/topology finalization**
   - Add the explicit Mode A=`localhost` / Mode B=`<ssh target>` write policy so the existing transport layer behaves correctly.
7. **W3g — node-refresh sidecar cache**
   - Add cache refresh last, because it is an optimization on top of a working one-shot wizard rather than a prerequisite for first-use setup.

## 8. Open questions for maintainer (Hongjiseung-ROK)

1. Should Mode A server YAMLs always write `SERVER.HOST: localhost`, even when the file is named after the cluster (`perlmutter.yaml`, `bridges2.yaml`), so agent submission never falls into SSH-by-filename behavior?
2. Should `/wizard` preserve template defaults (`SCRATCH: True`) when scratch cannot be verified, or should safety win and force `SCRATCH: False` until a writable path is confirmed?
3. Do you want `PROJECT` in scope for v1 autofill at all, or should `/wizard` always leave it commented and prompt the user?
4. The templates are inconsistent (`SCRATCH_DIR` in scheduler templates vs `SCRATCH` in `local.yaml`); do you want that normalized before wizard implementation starts?
5. Should `/wizard` ever synthesize `EXTRA_COMMANDS` that export chemsmart paths, given that the README does not define one canonical chemsmart install location?
6. Is `/wizard` intended to be TUI-only at first, or should there also be a non-TUI CLI entry point for scripted setup and headless SSH use?
