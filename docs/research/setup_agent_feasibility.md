# HPC initial-setup agent feasibility study
Date: 2026-05-10
Author stance: OpenAI senior research scientist, research-only assessment.
Scope note:
- The requested `chemsmart/agent/*` files are absent from this checkout's `main` worktree.
- I verified the local filesystem state first.
- For the agent-loop files specifically, I read the latest in-repo implementation from branch `fix/agent-planner-advisory-mode` at commit `7d86fa59e183994a0bf1e352edda302103f9c1fc` via `git show`.
- All local-path citations below are still written as `file:line` for readability.
- When a citation points into `chemsmart/agent/*`, it refers to that branch snapshot, not the checked-out `main` tree.
Working definitions used in this report:
- **Verified by reading code** = directly observed in the repository files or in the agent branch snapshot above.
- **Verified by fetched web docs** = directly observed in URLs opened during this task.
- **Assumed / projected** = a design recommendation or scheduler-specific inference that is not directly encoded in current chemsmart code.
Summary verdict upfront:
- **Feasible with caveats.**
- The biggest caveats are not scheduler probing.
- They are configuration representation and trust boundaries.
- The current server YAML schema has no explicit `host`, `user`, `port`, or proxy fields.
- The current SSH submit transport derives the remote SSH destination from `server.name`, i.e. the YAML filename stem, and then runs bare `ssh <host>`.
- That means a first implementation can work if the setup agent writes filenames like `user@host.yaml` or relies on a pre-existing `~/.ssh/config` host alias.
- It does **not** cleanly represent richer SSH connection state without either schema growth or a strict alias-based convention.
## 1. Goal & User Flow
### Goal
The requested feature is an **initial-setup agent** that turns:
- host,
- login,
- optional scheduler hint,
into a first-pass `~/.chemsmart/server/<name>.yaml` matching chemsmart's existing schema.
### Intended user experience
1. User asks chemsmart to set up a new HPC target.
2. Agent collects an SSH destination or enough data to construct one.
3. Agent checks SSH reachability.
4. Agent probes the remote login node for scheduler, queues/partitions, scratch conventions, modules, and program executables.
5. Agent renders a candidate YAML.
6. Agent validates loadability.
7. Agent pauses for approval.
8. Agent writes the YAML.
### Success criteria
A useful v1 should reliably produce:
- correct scheduler family,
- one usable default queue/partition,
- conservative CPU/memory/time defaults,
- a plausible scratch setting,
- a valid submit command,
- and program blocks that are either concretely filled or clearly marked as placeholders.
### What makes this harder than scheduler detection
The work is really three coupled problems:
1. remote access representation,
2. scheduler/resource inference,
3. YAML population policy.
The main challenge is representation, because current chemsmart code does not model SSH host/user/port/proxy as first-class server settings.
### Recommended scope for v1
Constrain the first version to:
- key-based SSH only,
- no agent forwarding,
- login-node probes only,
- read-only remote commands,
- conservative defaults instead of “best possible” tuning,
- and human approval before writing config.
### Minimal v1 workflow
1. Normalize destination to either an SSH alias or `user@host`.
2. Probe scheduler.
3. Probe queues/partitions.
4. Probe scratch and modules.
5. Probe program executables.
6. Render YAML.
7. Validate YAML.
8. Write YAML after approval.
### Non-goals for v1
Out of scope for the first iteration:
- password capture,
- MFA flow management,
- package installation,
- remote file mutation beyond the local YAML write,
- automatic chemsmart installation on the cluster,
- and deep project/account allocation discovery.
## 2. Verified Architectural Findings — file:line refs only
### A. Local configuration location and server-file discovery
Verified by reading code:
- User config root is hard-coded as `~/.chemsmart` in `ChemsmartUserSettings.USER_CONFIG_DIR` (`chemsmart/settings/user.py:55-57`).
- Server YAMLs are expected under `~/.chemsmart/server` through `user_server_dir` (`chemsmart/settings/user.py:72-80`).
- Available server names are discovered by globbing `*.yaml` in that directory and removing the suffix (`chemsmart/settings/user.py:164-172`, `chemsmart/settings/user.py:227-238`).
Implication:
- The setup agent can write a new file into a single well-defined directory.
- It does not need repo-local state.
### B. The current server loader is filename-driven
Verified by reading code:
- `Server.from_servername(servername)` delegates to `_from_server_name(server_name)` (`chemsmart/settings/server.py:419-437`).
- `_from_server_name(...)` appends `.yaml` if needed, joins it under `user_settings.user_server_dir`, and creates a `ServerSettingsManager` for that path (`chemsmart/settings/server.py:440-467`).
- Missing files surface as a user-facing error that tells the user to place a new YAML under `~/.chemsmart/server` and points to bundled templates (`chemsmart/settings/server.py:472-479`).
Implication:
- The setup agent's natural end product is exactly one file in that directory.
- There is no separate registration step.
### C. Scheduler detection in current chemsmart is local-only, not remote
Verified by reading code:
- `Server.from_scheduler_type()` calls `detect_server_scheduler()` and maps the result to a server class or falls back to `local` (`chemsmart/settings/server.py:313-344`).
- `detect_server_scheduler()` checks **local** environment variables such as `SLURM_JOB_ID`, `PBS_JOBID`, and local command availability such as `squeue`, `qstat`, `bjobs`, `condor_q` via `subprocess.run(...)` (`chemsmart/settings/server.py:346-417`).
Implication:
- Existing scheduler detection is useful for “where am I running now?”
- It cannot configure a remote HPC login node by itself.
- A setup agent therefore needs separate remote probe tools.
### D. The `Server` object exposes only scheduler/resource settings
Verified by reading code:
- `Server.__init__` stores `name` and `kwargs`, and initializes only `NUM_HOURS` and `QUEUE_NAME` as first-class mutable fields (`chemsmart/settings/server.py:34-48`).
- First-class accessors exist for `scheduler`, `queue_name`, `num_hours`, `mem_gb`, `num_cores`, `num_gpus`, `num_threads`, `submit_command`, `scratch_dir`, `use_hosts`, and `extra_commands` (`chemsmart/settings/server.py:121-264`).
- Submission command defaults are derived only from scheduler family: `SLURM -> sbatch`, `PBS -> qsub`, `LSF -> bsub < `, `SGE -> qsub`, `HTCondor -> condor_q` (`chemsmart/settings/server.py:266-285`).
Implication:
- The current schema does not model SSH connection details as first-class server fields.
- The initial-setup agent must either encode SSH destination in the filename convention or propose schema growth.
### E. The current YAML-backed server loader reads only the `SERVER` block
Verified by reading code:
- `YamlServerSettings.from_yaml(filename)` loads the YAML and instantiates with `yaml_contents_dict["SERVER"]` only (`chemsmart/settings/server.py:655-668`).
- `ServerSettingsManager.create()` always returns `YamlServerSettings.from_yaml(...)` (`chemsmart/settings/server.py:754-768`).
Implication:
- `Server` loading validates the `SERVER` section only.
- That is insufficient to prove the full file is operational.
- Setup-time validation must also exercise the program-specific blocks.
### F. Scheduler-specific subclasses exist, but file loading still returns `YamlServerSettings`
Verified by reading code:
- The code defines `SLURMServer`, `PBSServer`, `LSFServer`, and `SGE_Server` subclasses (`chemsmart/settings/server.py:771-885`).
- However, `ServerSettingsManager.create()` instantiates `YamlServerSettings`, not the scheduler-specific subclasses (`chemsmart/settings/server.py:754-768`).
Implication:
- The setup agent does not need to target subclass construction.
- Writing a correct YAML file is the real compatibility boundary.
### G. The requested YAML schema is broader than the `SERVER` block
Verified by reading templates:
- The `SLURM`, `PBS`, `local`, and `small` templates all define a `SERVER` mapping plus `GAUSSIAN`, `ORCA`, and `NCIPLOT` mappings (`chemsmart/settings/templates/.chemsmart/server/SLURM.yaml:1-59`; `chemsmart/settings/templates/.chemsmart/server/PBS.yaml:1-59`; `chemsmart/settings/templates/.chemsmart/server/local.yaml:1-59`; `chemsmart/settings/templates/.chemsmart/server/small.yaml:1-62`).
- The `SERVER` block carries `SCHEDULER`, `QUEUE_NAME`, `NUM_HOURS`, `MEM_GB`, `NUM_CORES`, `NUM_GPUS`, `NUM_THREADS`, `SUBMIT_COMMAND`, `SCRATCH_DIR`, `USE_HOSTS`, and `EXTRA_COMMANDS` (`chemsmart/settings/templates/.chemsmart/server/SLURM.yaml:1-15`; `chemsmart/settings/templates/.chemsmart/server/PBS.yaml:1-15`; `chemsmart/settings/templates/.chemsmart/server/local.yaml:1-15`; `chemsmart/settings/templates/.chemsmart/server/small.yaml:1-15`).
- The program blocks carry `EXEFOLDER`, `LOCAL_RUN`, `SCRATCH`, `CONDA_ENV`, `MODULES`, optional `SCRIPTS`, and `ENVARS` (`chemsmart/settings/templates/.chemsmart/server/SLURM.yaml:16-59`; `chemsmart/settings/templates/.chemsmart/server/PBS.yaml:16-59`; `chemsmart/settings/templates/.chemsmart/server/local.yaml:16-59`; `chemsmart/settings/templates/.chemsmart/server/small.yaml:16-62`).
Implication:
- A scheduler-only setup is not enough.
- The setup agent either needs to populate program blocks or write explicit placeholders there.
### H. Program-specific blocks are actually used by runtime code
Verified by reading code:
- `Executable.from_servername(servername)` reads the server YAML from `user_settings.user_server_dir` (`chemsmart/settings/executable.py:57-81`).
- It then extracts `EXEFOLDER`, `LOCAL_RUN`, `CONDA_ENV`, `MODULES`, `SCRIPTS`, and `ENVARS` from the program-specific section keyed by `cls.PROGRAM` (`chemsmart/settings/executable.py:83-119`).
- `Executable.scratch_dir` derives a scratch path by parsing exported `SCRATCH` out of the program `ENVARS` block (`chemsmart/settings/executable.py:132-146`).
- `Executable.env` also parses exported environment variables from the program `ENVARS` block (`chemsmart/settings/executable.py:148-169`).
Implication:
- The setup agent cannot treat `GAUSSIAN` / `ORCA` / `NCIPLOT` as decorative.
- They influence actual runtime behavior.
### I. The current agent ToolRegistry is Pydantic-schema driven
Verified by reading code:
- `ToolSpec.openai_tool_def()` builds an OpenAI-style function definition from the Pydantic model JSON schema (`chemsmart/agent/registry.py:26-55`).
- `ToolRegistry.default()` currently registers ten tools: `build_molecule`, `recommend_method`, `build_gaussian_settings`, `build_orca_settings`, `build_job`, `dry_run_input`, `validate_runtime`, `run_local`, `extract_optimized_geometry`, and `submit_hpc` (`chemsmart/agent/registry.py:58-84`).
- `normalize_args(...)` validates and normalizes model arguments before planner output is used (`chemsmart/agent/registry.py:91-109`).
- `call(...)` validates inputs and returns structured `{"ok": false, "error": ...}` payloads on validation or runtime failure (`chemsmart/agent/registry.py:111-146`).
Implication:
- New setup tools fit the current architecture naturally.
- They should be small, typed, and independently testable.
### J. The agent loop is planner → deterministic pre-risk steps → critic → risky steps
Verified by reading code:
- `AgentSession.run(...)` creates a session, calls planner, stores `request_intent`, then delegates to `_continue_run(...)` (`chemsmart/agent/core.py:181-224`).
- `_continue_run(...)` executes all non-risky steps first until it reaches the first risky tool (`chemsmart/agent/core.py:267-285`).
- If the first risky step is `submit_hpc`, the session creates a preview result before critic evaluation (`chemsmart/agent/core.py:286-295`, `chemsmart/agent/core.py:675-705`).
- The critic verdict is then post-processed by deterministic gates (`chemsmart/agent/core.py:296-311`, `chemsmart/agent/core.py:912-979`).
- Blocking is decided by `_block_reason(...)` (`chemsmart/agent/core.py:313-333`, `chemsmart/agent/core.py:982-1012`).
- Only after that are risky steps executed (`chemsmart/agent/core.py:352-392`).
Implication:
- “setup” should be inserted as another planner path, not as a side-channel.
- Remote probing can participate in the same critic/pause pattern.
### K. Risk gating is currently hard-coded to two tools
Verified by reading code:
- `_RISKY_TOOLS = {"run_local", "submit_hpc"}` (`chemsmart/agent/core.py:28`).
- `_continue_run(...)` uses membership in `_RISKY_TOOLS` to determine where the pause boundary begins (`chemsmart/agent/core.py:273-276`).
- `pause_before_risky=True` returns `pending_approval` and names the next risky tool (`chemsmart/agent/core.py:334-350`).
Implication:
- A remote setup probe does not currently have a risk category.
- If the project wants a formal approval checkpoint before touching an unverified host, `remote_probe` should become a first-class risky tool category.
### L. Current intent classification has no “setup” concept
Verified by reading code:
- `_INTENT_PATTERNS` only recognizes chemistry intents such as `opt`, `ts`, `irc`, `sp`, `freq`, and `scan` (`chemsmart/agent/core.py:34-52`).
- `_classify_intent(...)` returns one of those labels, `composite`, or `unknown` (`chemsmart/agent/core.py:1063-1082`).
Implication:
- A setup workflow needs either:
  - a new intent label such as `setup`, or
  - a zero-step advisory mode that never reaches tools.
- The requested feature plainly needs tools, so a new intent is the cleaner fit.
### M. Current runtime validation treats remote facts as “unknown”, not probed
Verified by reading code:
- `validate_runtime(...)` returns local issues plus a `remote_unknown` list (`chemsmart/agent/tools.py:471-558`).
- When a server is absent, it immediately marks a set of server-related unknowns (`chemsmart/agent/tools.py:477-481`).
- Even when a server is present, queue, account, scratch, modules, and SSH are still treated as `remote_unknown` rather than positively verified (`chemsmart/agent/tools.py:488-558`).
- `_runtime_validation_result(...)` maps `local_issues -> fail`, `remote_unknown -> partial`, otherwise `ok` (`chemsmart/agent/tools.py:907-923`).
- Deterministic critic gating upgrades `validate_runtime == partial` to at least `warn` (`chemsmart/agent/core.py:924-935`).
- `_block_reason(...)` then blocks warn-level cases containing remote-unknown issues unless `allow_remote_unknown` is set (`chemsmart/agent/core.py:992-1012`).
Implication:
- A setup agent is valuable precisely because it can convert some of today's “remote unknowns” into observed facts.
### N. Submit transport already uses the system `ssh` client, not Paramiko
Verified by reading code:
- `SshQsubTransport.submit(...)` builds a command and executes it with `subprocess.run(...)` (`chemsmart/agent/transport.py:38-62`).
- `build_submit_invocation(...)` constructs either a local `[submit_command, script_path]` or remote `["ssh", host, remote_command]` invocation (`chemsmart/agent/transport.py:98-112`).
- The remote command is `cd <working_dir> && <submit_command> <script_path>` (`chemsmart/agent/transport.py:107-112`).
Implication:
- A remote probe tool implemented with subprocess `ssh` is consistent with the existing transport strategy.
- No new SSH dependency is needed for v1.
### O. Remote host selection is currently derived from the server filename stem
Verified by reading code:
- `_server_host(server)` reads `server.name`, takes the basename, strips the extension, and returns the result as the SSH destination (`chemsmart/agent/transport.py:115-120`).
- `_is_local_host(...)` only special-cases `localhost` and `local` (`chemsmart/agent/transport.py:123-124`).
Implication:
- If the setup agent writes `~/.chemsmart/server/bridges2.yaml`, the submit transport will SSH to `bridges2`.
- If it writes `~/.chemsmart/server/user@bridges2.example.edu.yaml`, the transport will SSH to `user@bridges2.example.edu`.
- This is the main reason the feature is feasible **without** an immediate schema migration.
- It is also a strong limitation for ports, proxies, and richer SSH metadata.
### P. There is no explicit password / credential handling surface in the current transport
Verified by reading code:
- The transport signature is just `submit(script_path, working_dir, server)` and wraps a shell command (`chemsmart/agent/transport.py:18-62`).
- There is no field for password, port, proxy, host key policy, or agent forwarding in the submit transport code (`chemsmart/agent/transport.py:38-120`).
Implication:
- The natural first implementation is key-based SSH using the user's existing SSH environment.
- Interactive password workflows do not fit the current architecture cleanly.
## 3. Required New Tools — JSON-schema sketches following ToolRegistry pattern
### Design rules for the new tool set
Verified architectural fit:
- Tool definitions should remain narrow and typed because `ToolRegistry` already expects small functions with Pydantic-friendly signatures (`chemsmart/agent/registry.py:26-55`, `chemsmart/agent/registry.py:149-196`).
Projected design rule:
- Do **not** make one monolithic `setup_hpc_server(...)` tool.
- Instead separate:
  - remote fact collection,
  - fact interpretation,
  - YAML rendering,
  - and YAML validation.
Reason:
- This gives the critic intermediate artifacts it can reason over.
- It also makes failure recovery much clearer.
### Proposed new tools
I would add the following tools:
1. `ssh_probe_scheduler`
2. `ssh_list_partitions`
3. `ssh_inspect_modules`
4. `ssh_detect_scratch`
5. `ssh_probe_programs`
6. `render_server_yaml`
7. `validate_server_yaml`
8. `write_server_yaml`
I would keep `render_server_yaml` and `write_server_yaml` separate.
That separation matters because:
- rendering is deterministic and critic-readable,
- writing is side-effectful,
- and only the write step needs the strongest approval barrier.
### Tool 1 — `ssh_probe_scheduler`
Purpose:
- Identify scheduler family on the remote login node.
- Return both positive evidence and ambiguity.
Projected schema sketch:
```json
{
  "type": "function",
  "function": {
    "name": "ssh_probe_scheduler",
    "description": "Connect to a remote login node over SSH and identify the scheduler family using read-only commands.",
    "parameters": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "destination": {
          "type": "string",
          "description": "SSH destination, preferably an alias or user@host."
        },
        "scheduler_hint": {
          "type": ["string", "null"],
          "enum": ["SLURM", "PBS", "LSF", "SGE", null],
          "description": "Optional hint to reduce probe fan-out."
        },
        "connect_timeout_s": {
          "type": "integer",
          "minimum": 1,
          "default": 10
        },
        "strict_host_key_mode": {
          "type": "string",
          "enum": ["require-known", "accept-new", "record-only"],
          "default": "require-known"
        }
      },
      "required": ["destination"]
    }
  }
}
```
Projected return payload:
```json
{
  "ok": true,
  "destination": "user@cluster.example.edu",
  "reachable": true,
  "scheduler": "SLURM",
  "confidence": 0.98,
  "evidence": [
    "sinfo present",
    "scontrol present",
    "sinfo --json parsed"
  ],
  "ambiguous_with": [],
  "hostkey_status": "known|accepted_new|unknown_unconfirmed",
  "raw": {
    "commands": ["..."],
    "stdout_samples": {"sinfo": "..."}
  }
}
```
Why this should be a standalone tool:
- It is the first trust boundary.
- It determines which later probes even make sense.
### Tool 2 — `ssh_list_partitions`
Purpose:
- Gather queue / partition defaults and capacity hints.
- Return normalized structures across scheduler families.
Projected schema sketch:
```json
{
  "type": "function",
  "function": {
    "name": "ssh_list_partitions",
    "description": "List scheduler partitions or queues and normalize them into a common structure.",
    "parameters": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "destination": {
          "type": "string"
        },
        "scheduler": {
          "type": "string",
          "enum": ["SLURM", "PBS", "LSF", "SGE"]
        },
        "connect_timeout_s": {
          "type": "integer",
          "minimum": 1,
          "default": 10
        }
      },
      "required": ["destination", "scheduler"]
    }
  }
}
```
Projected normalized queue record:
```json
{
  "name": "normal",
  "is_default": true,
  "state": "up",
  "max_walltime": "24:00:00",
  "default_walltime": "01:00:00",
  "default_mem_mb": null,
  "max_mem_mb": null,
  "default_cpus": 64,
  "gpu_hint": 0,
  "account_hint": null,
  "source_command": "scontrol show partition --oneliner",
  "raw": "PartitionName=normal Default=YES ..."
}
```
Why this should be separate from scheduler probing:
- Scheduler identity is one fact.
- Queue selection is a second fact.
- They fail differently.
### Tool 3 — `ssh_inspect_modules`
Purpose:
- Determine whether the site uses environment modules.
- Return candidate module load lines for Gaussian, ORCA, and NCIPLOT.
Projected schema sketch:
```json
{
  "type": "function",
  "function": {
    "name": "ssh_inspect_modules",
    "description": "Inspect whether environment modules are available and whether relevant chemistry software appears in the module tree.",
    "parameters": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "destination": { "type": "string" },
        "programs": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["GAUSSIAN", "ORCA", "NCIPLOT"]
          },
          "default": ["GAUSSIAN", "ORCA", "NCIPLOT"]
        },
        "login_shell": {
          "type": "string",
          "enum": ["bash", "zsh", "sh"],
          "default": "bash"
        }
      },
      "required": ["destination"]
    }
  }
}
```
Projected return payload:
```json
{
  "ok": true,
  "module_system": "environment-modules|lmod|none|unknown",
  "programs": {
    "GAUSSIAN": {
      "module_candidates": ["gaussian/g16", "g16"],
      "load_snippet": "module purge\nmodule load gaussian/g16",
      "confidence": 0.7
    },
    "ORCA": {
      "module_candidates": ["orca/6.0.0"],
      "load_snippet": "module purge\nmodule load orca/6.0.0",
      "confidence": 0.9
    },
    "NCIPLOT": {
      "module_candidates": [],
      "load_snippet": null,
      "confidence": 0.0
    }
  }
}
```
Why it matters:
- Current templates rely heavily on multiline `MODULES`, `CONDA_ENV`, `SCRIPTS`, and `ENVARS` blocks.
- The runtime executable loader actually consumes them (`chemsmart/settings/executable.py:83-119`).
### Tool 4 — `ssh_detect_scratch`
Purpose:
- Determine usable scratch conventions.
- Return both server-level scratch and program-level exported `SCRATCH` candidates.
Projected schema sketch:
```json
{
  "type": "function",
  "function": {
    "name": "ssh_detect_scratch",
    "description": "Probe common scratch-directory environment variables and common site conventions on the remote login node.",
    "parameters": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "destination": { "type": "string" },
        "candidates": {
          "type": "array",
          "items": { "type": "string" },
          "default": [
            "$SCRATCH",
            "$TMPDIR",
            "$LOCAL_SCRATCH",
            "$HOME/scratch",
            "/scratch/$USER",
            "/tmp/$USER"
          ]
        }
      },
      "required": ["destination"]
    }
  }
}
```
Projected return payload:
```json
{
  "ok": true,
  "server_scratch_dir": "/scratch/alice",
  "program_export_line": "export SCRATCH=/scratch/alice",
  "alternatives": ["/tmp/alice"],
  "source": "env+filesystem",
  "confidence": 0.85
}
```
Why it should be standalone:
- Scratch is frequently site-specific.
- It is also one of the current `remote_unknown` pain points in runtime validation (`chemsmart/agent/tools.py:548-558`).
### Tool 5 — `ssh_probe_programs`
Purpose:
- Detect actual executable paths when modules are absent or ambiguous.
Projected schema sketch:
```json
{
  "type": "function",
  "function": {
    "name": "ssh_probe_programs",
    "description": "Probe remote PATH and common install roots for Gaussian, ORCA, and NCIPLOT executables.",
    "parameters": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "destination": { "type": "string" },
        "programs": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["GAUSSIAN", "ORCA", "NCIPLOT"]
          }
        }
      },
      "required": ["destination", "programs"]
    }
  }
}
```
Projected return payload:
```json
{
  "ok": true,
  "programs": {
    "GAUSSIAN": {
      "binary": "/opt/apps/g16/g16",
      "exefolder": "/opt/apps/g16",
      "local_run": true,
      "confidence": 0.95
    },
    "ORCA": {
      "binary": "/opt/orca/6.0.1/orca",
      "exefolder": "/opt/orca/6.0.1",
      "local_run": false,
      "confidence": 0.95
    }
  }
}
```
Why it matters:
- `Executable.from_servername(...)` expects `EXEFOLDER`, not just a module name (`chemsmart/settings/executable.py:83-86`).
### Tool 6 — `render_server_yaml`
Purpose:
- Convert normalized probe facts into a candidate YAML document.
- This should be pure and deterministic.
Projected schema sketch:
```json
{
  "type": "function",
  "function": {
    "name": "render_server_yaml",
    "description": "Render a candidate chemsmart server YAML from normalized remote probe facts.",
    "parameters": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "server_name": { "type": "string" },
        "scheduler": { "type": "string", "enum": ["SLURM", "PBS", "LSF", "SGE"] },
        "default_queue": { "type": ["string", "null"] },
        "default_hours": { "type": ["integer", "null"] },
        "default_mem_gb": { "type": ["integer", "null"] },
        "default_cores": { "type": ["integer", "null"] },
        "default_gpus": { "type": ["integer", "null"] },
        "default_threads": { "type": ["integer", "null"] },
        "server_scratch_dir": { "type": ["string", "null"] },
        "module_facts": { "type": ["object", "null"] },
        "program_facts": { "type": ["object", "null"] },
        "notes": { "type": "array", "items": { "type": "string" }, "default": [] }
      },
      "required": ["server_name", "scheduler"]
    }
  }
}
```
Projected return payload:
```json
{
  "ok": true,
  "yaml_text": "SERVER:\n  SCHEDULER: SLURM\n  ...",
  "assumptions": [
    "NUM_THREADS copied from NUM_CORES",
    "Gaussian module not found; placeholder kept"
  ],
  "uncertainties": [
    "NCIPLOT not detected",
    "queue normal selected because partition marked Default=YES"
  ]
}
```
### Tool 7 — `validate_server_yaml`
Purpose:
- Validate both the `SERVER` block and the program blocks.
- This should go beyond `Server.from_servername(...)`.
Projected schema sketch:
```json
{
  "type": "function",
  "function": {
    "name": "validate_server_yaml",
    "description": "Validate a candidate chemsmart server YAML against the current runtime loaders.",
    "parameters": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "yaml_text": { "type": "string" },
        "server_name": { "type": "string" }
      },
      "required": ["yaml_text", "server_name"]
    }
  }
}
```
Projected validation steps:
- parse YAML syntax,
- verify top-level keys exist,
- verify `SERVER` contains required keys,
- verify `SCHEDULER` is one of known families,
- verify `Executable.from_servername(...)`-compatible program sections can be materialized,
- verify `EXEFOLDER` strings are at least present for enabled programs,
- emit warnings instead of failures for missing optional programs.
Projected return payload:
```json
{
  "ok": true,
  "errors": [],
  "warnings": [
    "NCIPLOT.EXEFOLDER is placeholder",
    "SCRATCH_DIR differs from exported SCRATCH"
  ]
}
```
### Tool 8 — `write_server_yaml`
Purpose:
- Perform the actual side effect.
- Keep it separate from rendering and validation.
Projected schema sketch:
```json
{
  "type": "function",
  "function": {
    "name": "write_server_yaml",
    "description": "Write a validated server YAML under ~/.chemsmart/server.",
    "parameters": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "server_name": { "type": "string" },
        "yaml_text": { "type": "string" },
        "overwrite": { "type": "boolean", "default": false },
        "backup_existing": { "type": "boolean", "default": true }
      },
      "required": ["server_name", "yaml_text"]
    }
  }
}
```
Projected return payload:
```json
{
  "ok": true,
  "path": "/home/alice/.chemsmart/server/user@cluster.example.edu.yaml",
  "created": true,
  "backup_path": null
}
```
### Why I would not add a single `setup_server_yaml` tool first
Projected rationale:
- It would entangle remote trust, scheduler inference, YAML rendering, and file writes.
- The critic would see only a coarse result instead of the evidence chain.
- Debugging a partial failure would be much harder.
## 4. SSH Strategy — paramiko vs subprocess ssh; agent forwarding; host-key trust on first probe; password vs key
### Short recommendation
Recommendation:
- **Use subprocess `ssh` for v1.**
- **Do not use agent forwarding.**
- **Support key-based auth only in v1.**
- **Treat unknown host keys as an explicit approval boundary, not a silent side effect.**
### Why subprocess `ssh` is the best initial fit
Verified by reading code:
- Current submit transport already uses subprocess `ssh` rather than Paramiko (`chemsmart/agent/transport.py:38-62`, `chemsmart/agent/transport.py:98-112`).
Verified by fetched web docs:
- Paramiko describes itself as an SSHv2 protocol library and explicitly says the client is responsible for password/private-key auth and for checking the server host key (https://docs.paramiko.org/en/stable/index.html).
- Fabric is a high-level remote-command library built on top of Paramiko and Invoke, not an alternative transport primitive (https://www.fabfile.org/index.html; https://pypi.org/project/fabric/).
- As of the fetched PyPI pages, Paramiko's latest stable release is `4.0.0` from **August 4, 2025** and Fabric's latest stable release is `3.2.3` from **April 6, 2026** (https://pypi.org/project/paramiko/; https://pypi.org/project/fabric/).
Projected interpretation:
- Paramiko is still healthy and current.
- Fabric is also current.
- But neither is a free win here because chemsmart already standardized on shelling out to `ssh`.
### Concrete comparison
| Option | Strengths | Weaknesses | Fit for chemsmart v1 |
|---|---|---|---|
| Subprocess `ssh` | Reuses user SSH config, SSH agent, ProxyJump, ControlMaster, host-key DB, campus-specific hardening | Harder to capture structured auth state; shell quoting must be careful | **Best** |
| Paramiko | Python-native API, structured exceptions, explicit host-key policy control | Diverges from user's working `ssh` setup; extra dependency; own proxy/hostkey behaviors to maintain | Medium |
| Fabric | Good task API for deployments | Mostly sugar over Paramiko; not useful for short read-only probes | Low |
### Strong argument from AiiDA experience
Verified by fetched web docs:
- AiiDA's current SSH transport uses Paramiko and explicitly has to manage policies like `load_system_host_keys` and `RejectPolicy` itself (https://aiida.readthedocs.io/projects/aiida-core/en/stable/_modules/aiida/transports/plugins/ssh.html).
- The same source also documents that Paramiko does **not** parse `ProxyJump` from SSH config for them, requiring extra handling (https://aiida.readthedocs.io/projects/aiida-core/en/stable/_modules/aiida/transports/plugins/ssh.html).
- AiiDA's SSH setup guide still recommends normal SSH keys and `ssh-agent` to users (https://aiida.readthedocs.io/projects/aiida-core/en/stable/howto/ssh.html).
Projected interpretation:
- Paramiko can be made to work.
- But mature HPC projects end up rebuilding pieces the system `ssh` client already solves.
- For chemsmart v1, that is unnecessary complexity.
### What the probe command should look like
Projected recommendation:
- Wrap every probe as a non-interactive call similar to:
  - `ssh -o BatchMode=yes -o ConnectTimeout=10 <destination> <remote-command>`
- Add `-o ClearAllForwardings=yes` explicitly for setup probes.
- Use a login shell remotely when module systems must be initialized:
  - `bash -lc '<probe>'`
Why:
- `BatchMode=yes` avoids hidden password prompts that will stall the agent.
- `ClearAllForwardings=yes` keeps forwarding off even if the user's SSH config enables it for some host.
- `bash -lc` is often necessary because `module` is a shell function rather than a standalone binary.
### Agent forwarding
Verified by fetched web docs:
- OpenSSH warns repeatedly that forwarded agents can be abused from compromised remote hosts; the agent-restriction page explains that a hostile host can forward use of the agent onward through other tooling (https://www.openssh.org/agent-restrict.html).
- OpenSSH's security page records `CVE-2023-38408`, where `ssh-agent` PKCS#11 support could be abused for remote code execution **if the agent was forwarded to an attacker-controlled system** (https://www.openssh.org/security.html; https://www.openssh.org/releasenotes.html).
- OpenSSH's security page also records a **2025** bug where `DisableForwarding` did not actually disable X11 or agent forwarding as documented in some versions (`CVE-2025-32728`) (https://www.openssh.org/security.html).
Projected policy recommendation:
- The setup agent should **never** request `-A` or otherwise rely on SSH agent forwarding.
- It may rely on the user's **local** ssh-agent to unlock a key for the initial outbound SSH connection.
- That is materially different from forwarding the agent to the remote HPC host.
### Host-key trust on first probe
Verified by fetched web docs:
- Paramiko explicitly pushes host-key verification responsibility to the caller (https://docs.paramiko.org/en/stable/index.html).
- OpenSSH supports `StrictHostKeyChecking=accept-new`, which auto-adds new host keys but rejects changed host keys (https://www.mankier.com/5/ssh_config).
- OpenSSH's agent-restriction guidance also emphasizes maintaining good `known_hosts` hygiene and leveraging learned hostkeys (`UpdateHostKeys`) (https://www.openssh.org/agent-restrict.html).
Projected recommendation:
- Do **not** use `StrictHostKeyChecking=no`.
- There are two acceptable v1 models:
  1. **Safer default**: require the host key to already be known; if not, stop and ask the user to perform a trusted first SSH login manually.
  2. **Convenience mode with warning**: allow `accept-new`, record that the connection was TOFU, and require a second explicit approval before writing config.
My recommendation is model 1 for the first shipped version.
Reason:
- The setup agent already has enough product risk in scheduler inference.
- It does not need to silently mutate trust anchors too.
### Password vs key
Verified by fetched web docs:
- AiiDA documents two user-facing modes: passwordless keys and passphrase-protected keys handled through local `ssh-agent` (https://aiida.readthedocs.io/projects/aiida-core/en/stable/howto/ssh.html).
Projected recommendation:
- v1 should support:
  - passwordless SSH keys,
  - passphrase-protected keys unlocked in the local `ssh-agent`,
  - and SSH aliases in `~/.ssh/config`.
- v1 should **not** support:
  - raw password prompts,
  - OTP capture,
  - Duo push flow management,
  - keyboard-interactive auth capture,
  - or password persistence.
Reason:
- Those flows are brittle in tool-driven agent loops.
- They also create logging and secret-handling problems.
### Connection representation under the current schema
Verified by reading code:
- The submit transport turns the server filename stem into the SSH destination (`chemsmart/agent/transport.py:115-120`).
Projected practical convention:
- If the user supplies `host` and `login`, the setup agent can write:
  - `~/.chemsmart/server/<login>@<host>.yaml`
- Then the transport will later use:
  - `ssh <login>@<host> ...`
Caveat:
- This does not cover custom ports, jump hosts, or enterprise proxy rules.
- For those, the recommended path is to require an SSH alias already defined in `~/.ssh/config`, and use that alias as the server name.
### Bottom-line SSH recommendation
Recommended first implementation:
- Prefer an existing SSH alias.
- Else derive destination as `user@host`.
- Use subprocess `ssh`.
- Use `BatchMode=yes`.
- Keep forwarding disabled.
- Require known host keys by default.
- Support local ssh-agent, but not forwarded agents.
- Reject password-only workflows in v1.
## 5. Probing Plan — table mapping scheduler command → YAML field populated (per SLURM/PBS/LSF/SGE)
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
## 6. Plan/Critic Integration — new intent "setup"; new risky-tool category "remote_probe"; how the critic gates an unverified host
### New intent
Verified current gap:
- Current intent classifier has no setup-oriented label (`chemsmart/agent/core.py:34-52`, `chemsmart/agent/core.py:1063-1082`).
Projected change:
- Add `setup` to `_INTENT_PATTERNS`.
- Suggested trigger patterns:
  - `\bset up\b.*\bserver\b`
  - `\bconfigure\b.*\bhpc\b`
  - `\binitial setup\b`
  - `\bnew cluster\b`
  - `\bssh\b.*\bprobe\b`
  - `\bwrite\b.*server yaml\b`
### New plan shape
Projected canonical plan for setup intent:
1. `ssh_probe_scheduler`
2. `ssh_list_partitions`
3. `ssh_detect_scratch`
4. `ssh_inspect_modules`
5. `ssh_probe_programs`
6. `render_server_yaml`
7. `validate_server_yaml`
8. `write_server_yaml`
### Why setup should still use the planner
Projected rationale:
- The planner should decide when some probe steps can be skipped.
- Example:
  - if the user passes `scheduler_hint="SLURM"`, the planner can avoid PBS/LSF/SGE fallback probes.
- Example:
  - if the user wants only a dry feasibility assessment, the planner can stop before `write_server_yaml`.
### New risky-tool category
Verified current state:
- Risk classification is currently hard-coded to `run_local` and `submit_hpc` (`chemsmart/agent/core.py:28`).
Projected change:
- Expand `_RISKY_TOOLS` to include either:
  - each side-effectful remote probe individually, or
  - a broader category represented by tool names such as `ssh_probe_scheduler`, `ssh_list_partitions`, etc.
My preference:
- Mark **all remote SSH probe tools** as risky in v1.
Reason:
- Even read-only probes contact external infrastructure.
- They can also mutate local trust state if host keys are auto-accepted.
### Better refinement of risk categories
Projected longer-term approach:
- Split risky behavior into:
  - `remote_probe`
  - `run_local`
  - `submit_hpc`
  - `write_user_config`
That would allow different UI copy and different critic rules.
### Critic gating for unverified hosts
Verified current pattern:
- Current critic blocking logic already distinguishes remote-unknown warnings from other warnings (`chemsmart/agent/core.py:992-1012`).
Projected extension:
- Introduce a specific warning vocabulary for setup probes:
  - `hostkey.tofu`
  - `hostkey.unknown`
  - `ssh.alias_required`
  - `scheduler.ambiguous`
  - `queue.default_missing`
  - `program.gaussian_not_found`
  - `program.orca_not_found`
  - `scratch.unverified`
Suggested block policy:
- Block on `hostkey.unknown` always.
- Warn-and-pause on `hostkey.tofu`.
- Block on `scheduler.ambiguous`.
- Warn on missing program blocks if the user only asked for cluster setup rather than immediate chemistry job submission.
### Critic inputs I would add
Projected addition:
- For setup intent, the critic should receive:
  - probe evidence,
  - normalized queue records,
  - candidate YAML text,
  - validation warnings,
  - and host-key state.
This is broader than today's critic, which sees only the plan and dry-run inputs (`chemsmart/agent/core.py:434-455`).
### Minimal implementation path without redesigning the critic prompt too much
Projected pragmatic path:
- Keep the LLM critic lightweight.
- Add deterministic setup gates analogous to `_apply_deterministic_gates(...)`.
- Let the deterministic layer enforce:
  - host trust,
  - scheduler ambiguity,
  - YAML validation failures,
  - and overwrite conflicts.
This is more reliable than asking the LLM critic to infer operational SSH safety from raw probe logs.
### Proposed deterministic gates for setup
Projected rules:
- If `ssh_probe_scheduler.reachable == false` -> reject.
- If `ssh_probe_scheduler.scheduler == null` -> reject.
- If `ssh_probe_scheduler.ambiguous_with` non-empty -> reject.
- If `validate_server_yaml.ok == false` -> reject.
- If `hostkey_status == unknown_unconfirmed` -> reject.
- If `hostkey_status == accepted_new` -> warn and require approval.
- If target file exists and `overwrite == false` -> reject.
### Approval pause point
Projected behavior:
- Setup plans should pause **before** `write_server_yaml`.
- If probe trust state is weaker than ideal, they should optionally also pause **before the first remote probe**.
Conservative v1 recommendation:
- Pause before first remote probe unless the user already asked explicitly to proceed.
- Pause again before file write if the rendered YAML contains assumptions or placeholders.
### How this fits current session artifacts
Verified current mechanics:
- The agent already logs `tool_call`, `tool_preview`, `tool_result`, `critic_verdict`, and `session_summary` artifacts (`chemsmart/agent/core.py:612-672`, `chemsmart/agent/core.py:684-705`, `chemsmart/agent/core.py:727-811`).
Projected benefit:
- Setup intent can reuse exactly that artifact structure.
- That would give a reproducible evidence trail for each inferred server YAML.
## 7. Failure Modes & Recovery — auth fail, timeout, partial config, ambiguous scheduler
### 1. Authentication failure
Failure mode:
- SSH cannot authenticate non-interactively.
Recovery:
- return `auth.unavailable_noninteractive`,
- do not fall back to password prompts,
- instruct the user to make `ssh <destination>` work manually or define a usable SSH alias.
Recommendation:
- hard block.
### 2. Timeout
Failure mode:
- SSH works, but a probe command hangs.
Recovery:
- keep per-command timeouts,
- report the exact failing command,
- retry with a lighter family-specific fallback (for example `scontrol show partition --oneliner` if `sinfo --json` stalls).
Recommendation:
- partial result if scheduler family is still inferable.
### 3. Ambiguous scheduler
Failure mode:
- multiple scheduler families appear present.
Recovery:
- prefer the family with the strongest structured evidence,
- otherwise require the user to supply a scheduler hint.
Recommendation:
- reject rather than guess.
### 4. Partial config
Failure mode:
- scheduler facts are known, but chemistry program blocks remain incomplete.
Recovery:
- write a scheduler-valid YAML,
- fill missing program blocks with placeholders and TODO comments,
- label the result as cluster-ready but program-incomplete.
Recommendation:
- acceptable warning for setup-only use; not acceptable for immediate chemistry execution.
### 5. Existing file collision
Failure mode:
- target YAML already exists.
Recovery:
- refuse overwrite by default,
- allow explicit backup-and-overwrite,
- or force the user to choose a new server name.
Recommendation:
- deterministic reject unless overwrite is explicit.
### 6. SSH destination is not representable for future submits
Failure mode:
- the probe works only because the user supplied connection details that later bare `ssh <stem>` transport cannot reproduce.
Recovery:
- require an SSH alias for nontrivial host/port/proxy setups.
Recommendation:
- surface this early; it is a schema/transport constraint, not a probe bug.
### 7. Weak host-key trust
Failure mode:
- first contact requires TOFU.
Recovery:
- record trust mode,
- warn explicitly,
- require confirmation before persisting config.
Recommendation:
- never use `StrictHostKeyChecking=no`.
### 8. Syntactically valid but operationally weak YAML
Failure mode:
- the file loads, but runtime behavior is likely poor.
Recovery:
- `validate_server_yaml` should emit operational warnings for missing `EXEFOLDER`, missing module snippets, scratch mismatch, and GPU ambiguity.
Recommendation:
- distinguish `valid` from `ready`.
## 8. Web Research Notes — cite URLs you actually fetched
### A. Paramiko vs Fabric current state (2025/2026)
Fetched URLs:
- https://docs.paramiko.org/en/stable/index.html
- https://www.fabfile.org/index.html
- https://pypi.org/project/paramiko/
- https://pypi.org/project/fabric/
Observed facts:
- Paramiko documents itself as the underlying SSHv2 protocol library and explicitly assigns host-key verification responsibility to the client code.
- Fabric documents itself as a high-level remote-command library built on top of Invoke and Paramiko.
- The fetched PyPI page for Paramiko shows stable release `4.0.0`, uploaded **August 4, 2025**.
- The fetched PyPI page for Fabric shows stable release `3.2.3`, released **April 6, 2026**.
Interpretation for chemsmart:
- Fabric is not a transport primitive the project currently lacks.
- It is mainly a higher-level task wrapper around Paramiko.
- Because chemsmart already shells out to `ssh`, neither Paramiko nor Fabric is a clear v1 win.
### B. SSH agent-forwarding security guidance + recent CVEs
Fetched URLs:
- https://www.openssh.org/security.html
- https://www.openssh.org/releasenotes.html
- https://www.openssh.org/agent-restrict.html
- https://www.mankier.com/5/ssh_config
- https://cert.europa.eu/publications/security-advisories/2023-051/
Observed facts:
- OpenSSH's security page records `CVE-2023-38408`, explicitly describing remote code execution through a forwarded agent socket under certain PKCS#11 conditions.
- OpenSSH release notes explain the same bug and note that later releases restrict remote PKCS#11 loading.
- OpenSSH's security page also records a **2025** logic error where `DisableForwarding` did not actually disable agent forwarding as documented in affected versions.
- The agent-restriction page explains that forwarded-agent use can be re-forwarded by hostile tooling from a compromised host.
- `ssh_config` documents `StrictHostKeyChecking=accept-new` as a safer TOFU mode than `no`.
Interpretation for chemsmart:
- The setup agent should avoid agent forwarding entirely.
- It should support local `ssh-agent` use only.
- Host-key handling needs an explicit trust policy.
### C. `sinfo --json` and `scontrol show partition --oneliner`
Fetched URLs:
- https://slurm.schedmd.com/sinfo.html
- https://slurm.schedmd.com/scontrol.html
Observed facts:
- Slurm documents `sinfo --json` as dumping information as JSON while ignoring formatting options but preserving most filters.
- Slurm documents `scontrol --oneliner` as printing one line per record.
- The `scontrol` partition field documentation includes operationally relevant fields like default time, max time, memory defaults, state, and nodes.
Interpretation for chemsmart:
- `sinfo --json` is the cleanest first parser target for SLURM.
- `scontrol show partition --oneliner` is the best text fallback.
### D. `qstat -Q -f` PBS output
Fetched URL:
- https://2019.help.altair.com/19.2/PBSProfessional/PBSUserGuide19.2.1.pdf
Observed facts:
- The PBS guide documents `qstat -Q -f [-F json|dsv ...]` for queue long format.
- The same guide shows queue attributes such as `queue_type`, `enabled`, `started`, and job-state counts.
- The guide also documents `-F json` output.
Interpretation for chemsmart:
- PBS is nearly as probe-friendly as SLURM if JSON output is available.
- Text fallback is still parseable because the long format is attribute-per-line.
### E. Prior art — MolSSI / QCArchive / QCEngine / ASE / AiiDA
Fetched URLs:
- https://docs.qcarchive.molssi.org/admin_guide/managers/index.html
- https://molssi.github.io/QCEngine/index.html
- https://aiida.readthedocs.io/projects/aiida-core/en/stable/howto/ssh.html
- https://aiida.readthedocs.io/projects/aiida-core/en/stable/_modules/aiida/transports/plugins/ssh.html
- https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/schedulers.html
- https://aiida.net/ecosystem/
- https://ase-lib.org/ase/calculators/calculators.html
- https://ase-lib.org/gettingstarted/external_calculators/ext_intro.html
Observed patterns:
- **QCFractalCompute** expects an explicit manager config naming scheduler type and fields such as `partition`, `account`, `walltime`, `workers_per_node`, etc.; it does not present HPC auto-probing as the normal setup path.
- **QCEngine** performs strong **local** environment detection (cores, memory, scratch, program binaries) but not remote scheduler setup.
- **AiiDA** explicitly supports schedulers over SSH and exposes a substantial transport/scheduler abstraction surface; its docs reveal that SSH configuration management is itself a significant subsystem.
- **ASE** relies on explicit config files and environment variables such as `ASE_CONFIG_PATH` and `ASE_VASP_COMMAND`; it does not appear to ship an HPC auto-detection flow analogous to the requested setup agent.
Interpretation for chemsmart:
- The proposed chemsmart setup agent is not copying a common off-the-shelf pattern.
- It would be comparatively more opinionated and automated than these reference projects.
- That is feasible, but it raises the bar for safety and explainability.
## 9. Open Questions for the User
### 1. What should the persistent server-name convention be?
Choices:
- SSH alias only,
- raw `user@host`,
- or human label plus future schema growth.
Why it matters:
- current transport uses the YAML filename stem as the SSH destination.
### 2. Is `~/.ssh/config` part of the supported setup contract?
If yes:
- nontrivial SSH setups can rely on aliases.
If no:
- chemsmart eventually needs explicit SSH fields.
### 3. Should v1 allow TOFU host-key acceptance?
Decision needed:
- strict known-hosts only,
- or `accept-new` with an explicit warning and approval step.
### 4. Is password-only SSH a required user story?
If yes:
- the current architecture needs a separate credential-handling design.
If no:
- key-based auth only is the cleanest v1 boundary.
### 5. What counts as “setup complete”?
Possible definitions:
- scheduler block complete,
- scheduler plus one chemistry program complete,
- or full Gaussian/ORCA/NCIPLOT completeness.
### 6. Are placeholder/TODO values acceptable in v1?
This single decision controls rollout speed.
If placeholders are acceptable, the first version can safely ship with conservative partial program discovery.
### 7. Should the setup flow be explicit?
My recommendation:
- yes, make it a dedicated `setup` intent or command before folding it into ordinary chemistry requests.
### 8. Is schema growth on the table?
The most valuable future additions would be fields for SSH destination, port, options, and host-key policy.
If schema growth is forbidden, SSH aliases become the long-term escape hatch.
## 10. Recommendation — verdict (feasible / feasible-with-caveats / not-recommended) + one-paragraph justification
**Verdict: feasible-with-caveats.**
The feature is technically feasible within chemsmart's current architecture because the project already has: a stable user config root under `~/.chemsmart`, filename-based server discovery, a Pydantic-driven tool registry, a planner/critic/execute loop with approval pause semantics, and an existing remote submit transport implemented with subprocess `ssh` rather than a Python SSH stack. The key caveat is representation, not probing: the current schema has no explicit host/user/port/proxy fields, and the current transport derives its SSH destination from the server YAML filename stem. That means a safe and useful v1 should restrict itself to SSH aliases or `user@host` filename conventions, key-based auth only, no agent forwarding, and an approval checkpoint before writing config. Within those limits, scheduler and resource probing are straightforward for SLURM and PBS, workable for LSF and SGE, and the resulting setup agent could materially reduce today's `remote_unknown` runtime warnings by converting them into explicit observed facts.
