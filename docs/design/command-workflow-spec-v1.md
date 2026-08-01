# CommandWorkflowSpec v1: Command-Compiled Scientific Boundary

## Status

This is the active M2 contract. It supports deterministic command compilation
and isolated safe preview only. It does not authorize an engine run, scheduler
submission, training, or an SOTA claim. A successful new workflow is
`previewed`; an unavailable downstream artifact remains `planned`; a red gate
is `blocked` or `needs_clarification`.

## Separation of authority

`ScientificTaskSpec v1` is the scientific source of truth. It binds a stable
molecule ID, a single-frame XYZ geometry artifact and its raw/ordered hashes,
coordinate units, charge, multiplicity, requested observable, node-specific
method settings, constraints, and unresolved facts. `CommandWorkflowSpec v1`
is the operational source of truth. It binds a workflow ID, task-spec ID, live
CLI-schema digest, and an ordered command DAG.

The model may propose those two typed objects through an API tool call. It
does not provide a native Gaussian/ORCA/xTB input, raw shell command, arbitrary
path, flag alias/order, project name, or quote escaping. The deterministic
compiler resolves all of those values from the current Click schema and
host-owned workspace bindings.

## M2 supported scientific slice

| Program | Previewable jobs | Method authority |
| --- | --- | --- |
| Gaussian | `opt`, `ts`, `sp`, `td` | content-addressed project YAML; loader and route observation must agree |
| ORCA | `opt`, `ts`, `sp` | content-addressed project YAML; loader and route observation must agree |
| xTB | `opt`, `sp`, `hess` | typed `gfn_version`; `solvent_model`/`solvent_id` are an all-or-none pair |

M2 accepts only a single-frame XYZ artifact in Angstrom. QMMM, NEB, scans,
modred, multi-frame geometries, arbitrary route text, custom/ECP layering that
the existing project summary cannot verify, and native-input artifacts as
calculation geometry are not previewable yet. They terminate with structured
clarification or block evidence; no fallback input is created.

## Compilation and preview order

```text
ScientificTaskSpec validation
  → workspace artifact/project discovery
  → CommandWorkflowSpec DAG and live Click-schema compilation
  → project-loader/method/geometry/electronic-state comparison
  → canonical long-flag argv + shlex display rendering
  → isolated run --fake --no-scratch or sub --test --fake preview
  → independent parser and intent projection comparison
  → generated-input charge/multiplicity/ordered-geometry validation
  → path-free CommandWorkflowReceipt
```

Every computational root node must reference the task's exact geometry ID and
SHA-256. A downstream node must reference both a declared producer node and an
actual producer receipt; until that artifact exists it is planned. Project
program and content hashes are verified before settings are read. The compiler
rejects native input/output artifacts, shell operators, redirects, environment
substitution, runtime controls, stale schema/project/artifact hashes, and
project-owned Gaussian/ORCA method fields on the CLI.

Gaussian and ORCA previews parse the ChemSmart-generated native input.
xTB previews parse the fake-preview geometry named by the xTB program-call
record only when it remains inside the isolated preview workspace. All three
paths bind charge, multiplicity, and the ordered geometry hash; the xTB record
also retains element counts. None of those checks represents an engine run.

## Receipt and repair

`CommandWorkflowReceipt v1` contains only stable IDs, hashes, Click paths,
safe-preview verdicts, parser/intention observations, and generated-input
hashes. It includes the full `ScientificTaskSpec` hash, but never paths, raw
argv, native input text, stdout/stderr, provider payloads, credentials, or
hidden reasoning.

Repair accepts a prior workflow, candidate workflow, one structured
`CommandCounterexample`, the predecessor task-spec and receipt digests, and an
attempt number. The active lifecycle verifies that those digests bind the
immediately preceding typed preview. At most two repairs are allowed. Only the
named parameter of the named node may change. Changing a workflow/task/schema
ID, command path, project, input artifact, charge, multiplicity, execution
intent, dependency, expected artifact class, or constraint is rejected. A
repeated rule ID, rejected repair, or exhausted budget is `blocked`; it cannot
be ignored by reusing an earlier green preview.

## Runtime and approval boundary

The active Runtime V2 profile exposes `inspect_command_schema`,
`inspect_command_workflow`, `synthesize_command`, and `repair_command`, along
with read-only workspace/project operations. It hides and fail-closes native
builders, job builders, direct raw-command inspection, `run_local`,
`submit_hpc`, and `execute_chemsmart_command`. A future M3 executor must bind a
one-shot approval to the invocation, task, command, project, artifact,
environment, and receipt hashes; this contract implements none of that
execution authority. The active typed profile may reach its successful terminal
state only after a receipt reports `previewed`; a model tool result, a rendered
string, or an unconsumed repair proposal cannot satisfy that completion gate.

## Baseline comparison record

M2 records a path-free A0/A1 observation for a fixed fixture: an already
captured direct-command trace and the typed receipt are projected into the same
schema/parser/preview/intent/repair/failure fields. The record is deliberately
`experimental_not_adopted`; it does not include live provider identity, cost,
prompt, trial order, or repeated outcomes, so M5's frozen paired study is the
only place where an efficacy decision can be made.
