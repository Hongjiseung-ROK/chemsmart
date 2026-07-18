# P2 receipt — secure desktop foundations

Date: 2026-07-19
Status: reviewer-green; complete on the phase commit containing this receipt
Baseline commit: `4e4afeade4acd48f7794fa03a97eccebe89c45c7`
Branch distance at receipt time: 2 ahead, 6 behind

## Outcome

P2 supplies the application contracts needed before any desktop action may run
a ChemSmart job or connect live Chat. It does not enable real computation, HPC
submission, or an unverified fake-run button.

- New provider credentials are stored behind unique, opaque staged Keychain
  references. YAML retains provider/model metadata and the reference, never a
  new literal key. A provider update stages and verifies the new credential,
  atomically commits YAML, then best-effort retires the prior reference; a
  failed commit deletes only the staged reference. Existing plaintext configs
  remain readable and move only through an explicit, lock-protected,
  read-back-verified migration with rollback.
- Configuration initialization merges missing packaged defaults, preserves
  unknown user fields, writes atomically with owner-only permissions, and never
  edits shell profiles or environment search paths.
- A typed `JobDraft` owns program, job kind, molecule source, project, charge,
  multiplicity, settings, resources, and provenance. Database sources carry a
  `.db` file plus exactly one record index, record ID, or global structure ID;
  an optional structure index may accompany a record selector. The unsupported
  molecule-ID job selector is rejected. The live Click schema remains
  authoritative for argv construction and validation.
- The source/frozen launcher resolves ChemSmart explicitly, allowlists the child
  environment, supplies cwd/timeout/cancellation, and rejects real execution,
  submission, xTB, and caller-supplied safety flags. Source mode fixes the
  currently loaded package root under Python isolated mode and ignores a shadow
  package in the job workspace. The UI action remains locked until P3 proves
  generated-artifact parity.
- One reusable Qt task controller owns honest indeterminate/determinate
  progress, cooperative cancellation, timeout, retry, stale-result suppression,
  bounded shutdown, and thread/worker cleanup.
- The native shell now has macOS menus and Settings, system semantic
  palette/fonts and point size, an adaptive sidebar/work surface/context
  inspector, label buddies, accessible status, and visible progress/cancel
  states. Provider Save is disabled until the exact current input has passed a
  connection test and its worker has drained.
- A pure read-only projection maps the existing reduced agent runtime state to
  session/activity/evidence/recovery text. It creates no second event store and
  never displays request text, commands, paths, hashes, tool arguments, raw
  failure reasons, or provider data.
- The selected Python 3.11.9/macOS 14/arm64 PyInstaller builder/runtime now has
  an exact lock derived from the retained P1 freeze receipt, with pinned
  pip/setuptools/wheel and Keyring transitives added for P2. Build isolation is
  disabled only after the reviewed build tools are installed; `pip check`,
  `freeze --all`, and a strict missing/mismatch/extra-distribution verifier are
  mandatory workflow gates.

## Stress and preservation evidence

- All 26 live Gaussian/ORCA leaves round-trip through typed drafts and the live
  schema adapter. High-risk TS, scan, modred, TD, DIAS/WBI, ORCA TS/NEB, aux-basis,
  duplicate option scopes, repeated/nargs fields, and tri-state flags are
  covered.
- Valid `.db` record selector plus structure-index pairs and global structure-ID
  selection round-trip for Gaussian/ORCA. Missing/ambiguous selectors,
  structure-index without record, non-`.db` selectors, and molecule-ID job
  selection are rejected before launch.
- Preview commands use shell-safe quoting for spaces. Incomplete edit states
  show bounded inline validation and cannot hand off or run a stale command.
- The task controller includes 40 repeated start/cancel cycles in addition to
  success, stale completion, timeout, retry, and shutdown contracts.
- Security/configuration focused gate: 69 passed.
- Safe launcher/frozen dispatch/task focused gate: 16 passed.
- Typed draft/schema/application focused gate: 33 passed.
- GUI namespace: 130 tests collected and the complete run returned green.
- Final combined preservation gate before final review: 248 passed in 8.76 seconds.
  It includes GUI, config, CLI schema/provider, secret, TUI foundation and
  synthesis regression coverage.
- Ruff, Python byte compilation, and `git diff --check`: green.
- No real calculation, provider request, scheduler/HPC operation, shell-profile
  mutation, package installation, or real Keychain write occurred.

## Render and interaction evidence

Offscreen Qt renders were inspected at 1040 × 680 and 800 × 600. The wider
layout retained the three-region shell and the narrow layout collapsed the
context inspector before the primary surface. Iterative inspection removed
clipped subtitles, duplicate structure viewers, clipped inspector controls, and
an overlong status line. Settings remained readable at the narrow size.

Computer Use was prepared against an ephemeral `/tmp` application wrapper, but
macOS reported that the machine was locked and automatic unlock failed. This is
not promoted as acceptance evidence. Offscreen render tests are green; real
keyboard/pointer acceptance remains mandatory after a packaged implementation
and an unlocked Mac are available.

## Deferred and invalid claims

- The real system Keychain is not exercised by automated tests; explicit user
  interaction owns that acceptance step.
- Settings labels the workspace as current rather than default because P2 does
  not persist it across restart. Draft/workspace persistence and optional PyMOL
  path configuration remain P5/P6 work and are not claimed complete here.
- The P2 source tree is not a newly packaged P1 artifact. The exact lock and
  source probes are green, while a refreshed Finder bundle belongs to a later
  isolated packaging gate.
- Job builder safe preview is intentionally disabled. P3 must prove direct CLI
  versus GUI fake-run artifact parity before enabling it.
- Session projection is a presentation foundation, not live Chat wiring,
  streaming, approval execution, or resume UI; those remain P4.
- PyInstaller remains selected from P1. The red pyside6-deploy fallback was not
  rerun and its invalid measurements were not reclassified.

## Reviewer loop

The pre-implementation audit identified plaintext YAML secrets, ambient-PATH
launching, destructive config overwrite, missing typed draft semantics,
unbounded direct QThreads, fixed-layout/native-menu gaps, and the absence of an
exact runtime lock. The first final-pass review then found valid database
selector composition, secret lifetime/update-rollback, noncooperative worker
drain, floating build tools, agent-extra Keyring support, font scaling, label
buddies, initial Save state, exact preview quoting, and incomplete-edit recovery
gaps. The implementation and regression tests above close those findings.
The final read-only rerun reported zero Critical, High, Medium, or Low findings
and an explicit GREEN/READY phase-commit verdict. It independently reproduced
248 passing combined tests and 130 GUI tests, confirmed the secret/Keychain,
database selector, launcher, Qt lifecycle, exact-lock, accessibility, and
runtime-projection findings were closed, and found no sensitive or packaged
artifact in the commit scope.
