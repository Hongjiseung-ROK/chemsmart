# P3 receipt — safe native Job builder

Date: 2026-07-19
Status: reviewer GREEN; complete on the containing P3 phase commit
Baseline commit: `3356aa08`
Branch distance before the phase commit: 3 ahead, 6 behind

## Outcome

P3 turns the typed P2 foundation into a usable native input-generation surface
without opening a real-compute or scheduler boundary.

- The live Click schema drives program, leaf, common, and advanced fields. All
  17 Gaussian, 9 ORCA, and 3 xTB leaves round-trip through `JobDraft` and the
  strict parser. The schema-node snapshot makes additions fail closed until a
  desktop mapping is reviewed.
- Local file, PubChem, and ChemSmart database source modes remain explicit for
  Gaussian/ORCA. PubChem is honestly unavailable in offline preview. xTB enables
  local files only; unsupported source choices are disabled instead of failing
  after launch.
- Generate input is enabled only for a complete local draft. The user sees the
  exact command, inline validation, honest indeterminate progress, Cancel,
  Retry, and every generated input through an artifact selector with per-input
  route, charge/multiplicity, size, and full hash evidence. A chemistry edit
  immediately invalidates and clears an accepted receipt; a completion from an
  older draft is discarded rather than promoted.
- The launcher injects `--fake --no-scratch`, uses explicit source/frozen
  self-dispatch, absolutizes existing source arguments, starts an owned POSIX
  process group, mirrors only the selected bounded workspace project/defaults
  YAML into the isolated cwd, bounds output/artifacts/dependencies before any
  payload read, excludes provider secrets from the child environment, and
  removes its hidden isolated workspace in every completion, failure,
  cancellation, and timeout path.
- GUI and agent callers share strict preflight plus the same post-runtime
  semantic and generated-invariant assessment. The GUI does not duplicate
  route chemistry.

## Artifact-parity and backend evidence

- Gaussian: all 17 live leaves have GUI-versus-direct-CLI byte parity. The
  high-risk set includes TS, scan, modred, TD, DIAS, WBI, CREST, QRC, trajectory,
  and custom route generation, including multi-artifact jobs.
- ORCA: all 9 live leaves have byte parity. The high-risk set includes TS,
  scan, modred, NEB, auxiliary basis, QRC, and direct `.inp` conversion.
- ORCA NEB exposed a real backend defect: the writer emitted an endpoint
  basename without staging an absolute endpoint into the run directory. The
  runner now stages endpoint/intermediate/restart dependencies in both scratch
  and no-scratch paths. It rejects different sources that share one basename,
  and invariants require every active directive, staged file, and source/staged
  SHA-256 match. Restart mode is mutually exclusive with endpoint/TS-guess
  mode; NEB method, image count, and pre-optimization are also preserved.
- ORCA `inp` exposed a runner-propagation defect: it constructed a new real
  scratch runner instead of preserving the parent fake/no-scratch runner. The
  parent runner is now passed into the imported job.
- xTB lineage `/Users/hongjiseung/bin/chemsmart@1494fc18` passed its original
  10 CLI tests and Ruff audit. Its opt/sp/hess CLI, settings, job, real/fake
  runner, executable, submit-test, and templates were selectively adapted to
  the current architecture. All three leaves have desktop/direct byte parity.
  xTB receipts read the fake runner's actual rendered `--chrg`/`--uhf` program
  call, rather than trusting the requested command, before checking state and
  electron-count parity. Project YAML cannot redirect one leaf into another,
  unknown/typo settings are rejected, project charge/spin survive omitted CLI
  overrides, and solvent model/identifier are an atomic pair checked again
  against the rendered program call.

## Stress and lifecycle evidence

- Cancellation and timeout terminate, bounded-wait, then kill only the owned
  child process group; isolated preview directories are removed.
- Process output retains a bounded 64 KiB tail. Generated inputs and staged
  dependencies have separate per-file, aggregate-byte, and count ceilings.
  Stat checks precede bounded reads, and a generated xTB `.xyz` is never
  double-counted as a dependency.
- Direct fake xTB and CLI submission `--test` remain available; desktop requests
  cannot supply `--no-fake`, real execution, or submission.
- Repeated Qt windows exposed retained QtWebEngine ownership at interpreter
  shutdown. Top-level windows now delete on accepted close, the close contract
  verifies the deferred deletion, and the 3D viewer is created only after a
  molecule is selected. The live 3Dmol gate runs in its own application process,
  matching the packaged probe boundary instead of reusing an exited shell-smoke
  `QApplication`. This reduces startup work and renderer lifetime while
  preserving interactive preview.
- Advanced forms live in a dedicated scroll region, while command, actions,
  progress, artifact selector, and output remain reachable. ORCA TS stress at
  720 × 520 and 1040 × 680 preserves nonzero row geometry and Tab traversal
  through the scroll range.
- Structure evidence is cleared immediately when a source/path becomes stale.
  File/database mode changes clear their incompatible payloads, and files over
  8 MiB skip synchronous 3D parsing without blocking safe CLI input generation.
- The final combined GUI/backend/agent/CLI preservation gate passed 464 tests
  in one invocation after every reviewer finding was closed.
- Ruff, compileall, `git diff --check`, and offscreen visual inspection are
  required green at the phase boundary.

## Visual and interaction evidence

Offscreen renders were inspected with xTB optimization and the worst-case ORCA
TS advanced form. They retained clear program/job/source hierarchy,
local-file wording, promoted project/file/charge/multiplicity fields, the exact
command, primary Generate input action, disabled Chat handoff, and reachable
artifact/output regions. Independent Qt stress confirmed the advanced scroll
and keyboard focus path at the 720 × 520 minimum and 1040 × 680 default sizes.

Computer Use remains an acceptance requirement, but the Mac was locked during
P2/P3 attempts. No simulated offscreen render is promoted as keyboard/pointer
acceptance. The real interaction scenarios must be rerun when the Mac is
unlocked and again against the packaged app.

## Final validation receipts

- Primary combined phase gate: `464 passed in 86.89s` with process exit code 0.
  It ran `tests/gui`, `tests/agent/harness`, the model-command parser, xTB,
  ORCA, Gaussian, config, runner, server, and YAML preservation suites in one
  invocation.
- Independent reviewer GUI gate: `186 passed in 76.38s`.
- Independent reviewer parity/safety gate: `162 passed in 91.15s`.
- Independent Qt stress: the real offscreen window and WebEngine viewer were
  both released; Tab traversal reached 51 unique fields with automatic scroll
  at 720 × 520 and 1040 × 680.
- Final reviewer verdict: Critical 0 / High 0 / Medium 0 / Low 0 — **GREEN**.
- Changed-Python Ruff, compileall, and `git diff --check 3356aa08` are green.

## Deferred boundaries

- Chat handoff, unified-agent streaming, approvals, cancellation/resume, and
  typed agent-to-builder drafts belong to P4.
- Saving drafts, database browsing, analysis, optional PyMOL rendering, and real
  Computer Use workflows belong to later phases.
- Real Gaussian, ORCA, or xTB calculation and scheduler submission remain
  unavailable in the desktop. Existing CLI/TUI backends are preserved.
- Full historical xTB output post-processing is not claimed by this selective
  job-generation port; P3 completion is the three-leaf CLI/fake/desktop input
  contract.
