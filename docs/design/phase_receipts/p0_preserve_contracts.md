# P0 receipt — preserve and establish contracts

Date: 2026-07-18
Status: complete on the phase commit containing this receipt
Phase: P0

## Provenance and ownership

- Branch at start: `agent-codebase-simplification`
- HEAD at start: `cada8c505ad298dd3735c497c56b668be61cb236`
- Upstream after a fresh fetch: `fork/agent-codebase-simplification@8d68d790`
- Distance: 0 ahead, 6 behind
- The six upstream commits touch runtime/harness/Windows-portability files only;
  they do not overlap the current GUI, `pyproject.toml`, or CLI config changes.
- Tracked user changes at start: `chemsmart/cli/config.py`, `pyproject.toml`.
- Untracked user work at start: the complete `chemsmart/gui/` scaffold and the
  three canonical design documents.
- Original GUI file identities are recorded in
  `evidence/p0/gui_scaffold_before_codex.sha256`; no reset, clean, stash, branch
  switch, or history rewrite was used. The phase commit containing this receipt
  makes the corrected working files recoverable.
- The SHA-256 manifest is provenance evidence only. It is not a byte archive and
  cannot reconstruct the original untracked scaffold; mismatches against the
  corrected files are expected and no original-byte recovery claim is made.

Reconciliation plan: keep the working tree on its current branch through P0.
Do not pull or switch while the GUI is untracked. After the P0 phase commit has
captured the work, inspect the six non-overlapping upstream changes again and
integrate them without rebasing or rewriting the phase history before agent
runtime integration requires them.

## Fresh baseline evidence

Before P0 corrections:

- Ruff: green for `chemsmart/gui` and `chemsmart/cli/config.py`.
- Existing config/provider/schema slice: 64 passed.
- Job builder programs: database, gaussian, grouper, iterate, mol, nciplot,
  orca, thermochemistry.
- Default preview: `chemsmart run database assemble --index : --output database.db`.
- Database, Analysis, and Settings navigation: three reproducible
  `ModuleNotFoundError` failures.
- Six new P0 contract tests failed before implementation.

## P0 changes

- Added an optional GUI test namespace that skips cleanly when PySide6 is not
  installed.
- Restricted the Job builder to the 17 Gaussian and 9 ORCA leaf commands.
- Merged run, program, and leaf option layers and preserved their Click argv
  placement.
- Added scoped field identifiers for same-name options at different Click
  levels, preventing silent overwrites.
- Corrected boolean flag polarity for true-default flags such as
  `skip_completed`.
- Added a checked-in path-level schema snapshot and made unknown draft fields a
  hard error, so backend option additions cannot be silently ignored.
- Forced GUI-owned fake/scratch safety flags out of the editable form.
- Disabled Dry run until an explicit checkout-verified launcher enforces fake
  flags, cwd, timeout, and cancellation without ambient `PATH`.
- Added recoverable P0 placeholders for Database, Analysis, and Settings.
- Made application startup independent of AI-provider setup.
- Extracted config-tree creation that cannot mutate shell or registry state.
- Changed provider connection testing to use an in-memory draft and prevented
  saving values that have not passed the current connection test.
- Set the initial workflow to Gaussian optimization.

## Stress and preservation checks

- Every one of the 26 top-level Gaussian/ORCA desktop command paths passes the
  same deterministic Click-schema validator used by synthesis; an invented leaf
  option is rejected. This is a path/schema gate, not a fake-runtime claim.
- Duplicate option names receive unique scoped identifiers and retain correct
  program-versus-leaf placement.
- One hundred navigation cycles across five destinations reuse exactly five
  lazy screen instances.
- The feature contract contains 6 unique policies and 16 unique surfaces. All
  declared source paths exist, and the source-less xTB surface is explicitly
  classified as a missing backend instead of being silently omitted.
- The xTB lineage candidate was located read-only at
  `/Users/hongjiseung/bin/chemsmart@feat/xtb-submit-jobs`, with implementation
  commits `14f800a1` and `1494fc18`; it is not yet assumed compatible or copied.
- Final integrated P0 regression slice after reviewer corrections: 133 passed
  in 6.17 s (26 GUI + 64 config/provider/schema + 43 TUI/synthesis).
- Python byte compilation and Ruff checks are green.
- No real calculation or scheduler submission was executed.

## Render evidence

- `evidence/p0/job_builder_minimum.png` — 760 × 520
- `evidence/p0/job_builder_default.png` — 1040 × 680
- `evidence/p0/job_builder_wide.png` — 1440 × 900
- `evidence/p0/database_placeholder.png` — recoverable unavailable state

The images confirm the corrected Gaussian/opt default, disabled unsafe Dry run,
and working placeholders. They also preserve known later-phase work: the fixed
sidebar, empty Options box, hard-coded theme structure, and large blank molecule
panel are not claimed complete in P0.

## Reproduction commands

```text
ruff check chemsmart/gui chemsmart/cli/config.py tests/gui
python -m compileall -q chemsmart/gui
pytest -q tests/gui
pytest -q tests/test_config.py tests/agent/test_cli_schema.py tests/agent/test_provider_config.py tests/agent/test_provider_adapter.py
pytest -q tests/agent/tui/test_cli.py tests/agent/tui/test_track_a_foundation.py tests/agent/tui/test_synthesis_mode.py tests/agent/test_synthesis.py
```

## P0 exit gate

- Original provenance recorded: green; corrected files are captured by this
  phase commit.
- Feature contract reviewed and machine checked: green.
- Reproducible GUI contract namespace: green.
- Upstream reconciliation plan: green; integration intentionally not performed
  while the phase work was untracked.
- Packaging/runtime completeness claim: none; P1 remains mandatory.
- Reviewer feedback: green after the second read-only review.
- Final focused/regression receipts: green.
- Phase commit: the commit containing this receipt.

## Reviewer feedback loop

The first read-only review returned red gates for undisclosed third-party
provider routing, ambient-PATH Dry run, nonrecoverable hash wording,
NO-SILENT-DROP enforcement, shallow parser evidence, missing xTB tracking, and
small-text contrast. P0 now:

- pins built-in provider tests and saved configs to the reviewed first-party
  OpenAI/Anthropic endpoints and discloses the destination;
- disables Dry run until the explicit safe launcher exists;
- describes the original hash manifest only as identity/provenance evidence;
- rejects unknown fields and snapshots every relevant Click node;
- uses the synthesis schema validator and narrows the receipt claim;
- records xTB as a missing backend with a verified lineage candidate;
- raises muted-token contrast above 4.5:1 and tests both palettes.

Second reviewer verdict: green, with no remaining Critical, High, or Medium
findings. The reviewer verified endpoint persistence, disabled Dry run, receipt
wording, schema drift enforcement, deterministic validation, xTB tracking, and
contrast coverage before authorizing the final regression rerun and phase
commit.
