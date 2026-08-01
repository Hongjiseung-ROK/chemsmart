# ChemSmart CLI Ground Truth (legacy corpus supplement)

`chemsmart/agent/cli_schema.py` and the live Click parser are the authoritative
source. Regenerate and inspect the schema when command coverage matters; this
document is not an exhaustive command inventory. Trust the real parser and
semantic gate over any model output or prose.

For active frontier work, a model proposes typed CommandWorkflowSpec data, not
a free-form shell command or native-engine input. The deterministic compiler
resolves trusted project/artifact bindings and canonical long flags from the
live schema, then performs safe preview and independent intent observation.
This legacy corpus supplement may describe historical command rows but cannot
override the compiler, approval, or evidence contract in `AGENTS.md`.

## Command shape

```
chemsmart {run|sub} [group opts] {gaussian|orca|xtb} [-p PROJECT] -f FILE \
    -c CHARGE -m MULT <jobkind> [job-specific structural opts]
```
- `run` = local execution; `sub` = HPC submission. Server/cores/mem/time
  flags belong on the run/sub GROUP (before the engine), never after it.
- Test-mode injection (only when actually executing): `run` → add
  `--fake --no-scratch`; `sub` → add `--fake --test`.
- xTB is a primary calculation program. Its current leaf commands include
  `sp`, `opt`, and `hess`; inspect the generated schema and program help for
  exact options rather than copying Gaussian/ORCA assumptions.

## Historical Gaussian/ORCA corpus subset (not exhaustive CLI ground truth)

- gaussian: `com crest dias irc link modred nci opt qrc resp scan sp td
  traj ts userjob wbi` (TDDFT's CLI name is `td`, not `tddft`)
- orca: `inp irc modred neb opt qmmm qrc scan sp ts`
- `qmmm` is a NESTED child under selected Gaussian/ORCA parent job groups
  (`… opt qmmm`); inspect the live schema rather than assuming a static parent
  list.
- There is NO `freq` subcommand. Frequency on/off is project-YAML-owned.

## Runtime-owned fields — must NOT appear as CLI flags in trusted rows

functional, basis, ab initio method, aux basis, dispersion (D3/D3BJ),
solvent model/id, freq. These come from the workspace project YAML
(`./.chemsmart/<program>/<project>.yaml`). A command carrying
`--functional`, `--basis`, `-x`, `-b`, or freq smuggled into route params
(`-r '... freq ...'`, `--freq`, `freq=`) is a CANONICAL VIOLATION — the
exporter auto-skips it (`canonical_*` skip reasons); never hand-approve one.

## Structural options in legacy direct-string fixtures

These spellings describe historical direct-string fixtures, not the active
Frontier Runtime V2 model surface. The compiler maps typed canonical parameter
names to the current live schema. In a legacy fixture, structural data may
include `-f/--filename`, `-c/--charge`, `-m/--multiplicity`, `-p/--project`,
`-l/--label`, scan/modred coordinate lists, step size/count, TD states, DIAS
fragment indices, or a NEB end-file; validate each current scope before use.

## Project (`-p`) rule

For a legacy fixture, a workspace project default may be injected when a
direct string omits `-p`. In the active command-compiled path, the model
references a trusted project artifact and the compiler resolves the actual
project flag. A missing project becomes a project-workflow/approval issue, not
a model-invented name.

## Known model failure patterns (watch for these in WRONG rows)

- scan↔modred confusion (both take atom pairs; scan asks drive the bond,
  modred asks freeze it) — the single most common systematic WRONG.
- Router confusion: a plain job request answered by project-YAML authoring
  tools instead of `synthesize_command` (fix: command-hard framing).
- Invented option order: options after the jobkind that belong before it.
