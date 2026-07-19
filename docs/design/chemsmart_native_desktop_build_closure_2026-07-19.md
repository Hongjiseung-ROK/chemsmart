# ChemSmart native desktop build closure and handoff

Date: 2026-07-19
Decision: stop after the current build; do not start another packaging run
Branch: `agent-codebase-simplification`
Current branch HEAD before the closure commit: `c53ced2372b69d1350fe82bc45ab0b1a8cc404ce`
Accepted binary source: `91f55b5972b57beb3e1ea39b45fcc04433c3e606`
Accepted packaging run: `29683902995`
Release level: ad-hoc-signed, arm64 macOS 14+ internal alpha

## 1. Closure verdict

The current work produced a real PyInstaller application, verified application
archive, HFS+ UDZO DMG, checksums, shipped-component inventory, CycloneDX SBOM,
release receipt, rotating diagnostics, support-bundle export, and lifecycle
guide. The downloaded DMG was independently mounted read-only and the app was
opened through macOS LaunchServices. PyInstaller is the only active packager.
The former pyside6-deploy/Nuitka comparison is retained only as historical P1
evidence and is not a fallback or release path.

This is a **build freeze**, not a claim that the full product goal is complete.
P0-P6 are phase-complete and reviewer-green. The P7 distribution slice is
artifact-green, but clean named-machine testing, the full packaged research
workflow matrix, stress acceptance, graceful packaged shutdown, Developer ID
signing, and notarization are not complete.

Three states must not be conflated:

| State | Exact meaning |
|---|---|
| Accepted binary | Run `29683902995`, source `91f55b…e606`; downloaded and independently reverified. |
| Current local source | Contains the accepted P7 implementation plus a post-artifact workspace-refresh/status fix. The fix passed local tests but was not rebuilt. |
| Public release | Does not exist. The current binary is ad-hoc signed and intentionally rejected by Gatekeeper as an unidentified public distribution. |

## 2. Phase progress

| Phase | State | Durable result | Remaining boundary |
|---|---|---|---|
| P0 contracts | Complete | Source/UI inventory, preservation manifest, feature contract, baseline tests and screenshots. | None inside P0. |
| P1 packaging spike | Complete | PyInstaller 6.21.0 `onedir` selected on macOS 14 arm64. | Nuitka evidence is historical only. |
| P2 foundations | Complete | Typed drafts, secure provider config/Keychain boundary, frozen dispatch, task controller, native shell. | Real Keychain mutation remains explicit user action. |
| P3 Job builder | Complete | 17 Gaussian, 9 ORCA, and 3 xTB leaves use live Click schema and isolated fake/no-scratch artifact parity. | No real compute or submission by design. |
| P4 Chat | Complete | Canonical unified agent loop, read-only desktop tool registry, distinct intent/semantic gates, cancellation/resume, typed handoff. | Live provider behavior was not exercised during packaging acceptance. |
| P5 Database/Analysis | Complete in source | Browse/build/export, Grouper, Thermochemistry, DIAS, and WBI use typed shared-domain services. | The complete fixture matrix was not exercised manually inside the packaged app. |
| P6 product/accessibility | Complete | Responsive PySide6 shell, system theme, focus/VoiceOver contracts, large-text matrix, offline 3Dmol, optional PyMOL boundary. | Real PyMOL on a named lab Mac remains unverified. |
| P7 release engineering | Build frozen, incomplete product acceptance | Signed app, verifier, DMG, checksum, SBOM, component inventory, logs, support bundle, install/remove guide. | See section 7. |

Authoritative per-phase receipts remain in
`docs/design/phase_receipts/p0_preserve_contracts.md` through
`docs/design/phase_receipts/p7_release_engineering.md`.

## 3. Implemented product surfaces

### Job builder

- Builds typed `JobDraft` state rather than treating the preview string as
  application state.
- Reads the maintained Click schema through
  `chemsmart/gui/services/cli_schema_service.py`.
- Accepts local files and the reviewed source selectors, validates required
  project/charge/multiplicity/job settings, and shows the exact command.
- Runs only an isolated `--fake --no-scratch` child through
  `chemsmart/gui/application/cli_launcher.py`.
- Captures every generated input plus route/state/dependency/hash receipts.
- Cancels, retries, rejects stale completion, and invalidates an accepted
  receipt whenever chemistry state changes.

### Chat

- Uses the canonical unified `AgentSession.run_loop()` and durable agent stores.
- Exposes only read-only synthesis/project inspection in the desktop registry.
- Excludes repair, real local execution, project writes, and HPC submission.
- Keeps intent, semantic, live-schema, and permission results distinct.
- Supports deterministic exact-command handling without an external provider.
- Transfers an accepted typed draft to Job builder; it does not execute it.

### Database and analysis

- Database browse is read-only and bounded.
- Database assembly and export are explicit create-new operations with private
  staging, integrity read-back, atomic no-overwrite publish, and a cancellation
  commit boundary.
- Grouper, Thermochemistry, DIAS, and WBI call shared domain APIs and return
  typed results; they do not parse terminal presentation text.
- Large, malformed, escaped, symlinked, missing, repeated, cancellation, and
  optional-dependency cases have source-level regression coverage.

### Visualization and settings

- Vendored, integrity-checked 3Dmol 2.5.5 is the offline default.
- PyMOL is optional, explicitly selected or discovered, runs without a shell,
  receives a bounded environment, and returns a verified bounded PNG.
- Provider credentials are stored through macOS Keychain references; provider
  setup is optional and never blocks the non-AI product.
- Native menus, Settings, responsive split layout, system palette/font roles,
  accessible names, focus order, and recovery text are implemented.

## 4. Accepted artifact receipt

Run: <https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29683902995>

| Item | Receipt |
|---|---|
| Source/workflow SHA | `91f55b5972b57beb3e1ea39b45fcc04433c3e606` |
| Runner | macOS 14.8.7 arm64, Python 3.11.9 |
| Whole job | 10 min 02 s |
| Dependency install | 1 min 09 s |
| Source preservation | 489 passed, 1 optional skip; 1 min 27 s |
| PyInstaller build | 2 min 50 s |
| Component inventory | 1 s |
| Nested-to-outer signing | 4 s |
| Application verifier | 18/18 mandatory flags; 1 min 14 s |
| DMG build and mounted verification | 2 min 53 s |
| App | 811,942,895 bytes; inventory SHA-256 `c8f29f29635249cb83fe16df795608f06ddfc1cbc328d134b96fb4fb956db123` |
| Bundle inventory | 10,633 files; 2,098 directories; 1,959 safe symlinks |
| Verified-bundle ZIP | 311,054,280 bytes; SHA-256 `80b6b1feb1f1a5151dc7c7b23fa5563575fadca17a8d15420b15a458dae4d7d9` |
| DMG | 338,317,126 bytes; SHA-256 `e287a6c6bda5bcc74fded295990debe3eb0903a5952cb7cd12a018b5988911b4` |
| Shipped distributions | 111; all 10 mandatory present; all 8 forbidden absent |
| Analysis TOC | `1f5d3fa71482022c51018a315d15242d457ee4fada58a8212e147c6fae9ff3d5` |
| PYZ TOC | `4a5917f675a62281c8c9e3973d194515574ceb3df8d6402126830a5df6affce6` |
| Evidence artifact | ID `8441538533`; 23,669,802 bytes; GitHub digest `cfbb12dc…a43e` |
| Verified-bundle artifact | ID `8441538903`; 311,054,679 bytes; GitHub digest `9fff7191…1d6` |
| Distribution artifact | ID `8441539284`; 338,374,019 bytes; GitHub digest `8e3b9161…fdd9` |

The downloaded DMG passed its image checksum, all entries in
`SHA256SUMS.txt`, strict/deep signature verification, bundle identifier
`org.zhanglab.chemsmart`, version `2.0.1`, declared minimum macOS 14.0, exact
README parity, `/Applications` shortcut, inventory parity, and unsafe-symlink
count zero. Gatekeeper return code 3 is the required result for the deliberately
ad-hoc-signed internal alpha. No application was copied into `/Applications`.

## 5. Build-time diagnosis

The accepted ten-minute workflow is not dominated by Python compilation alone.
Its time is split across four independently necessary trust boundaries:

1. dependency reconstruction and exact runtime-lock validation;
2. 489 source-preservation tests before freezing;
3. PyInstaller analysis/collection of Python, Qt, QtWebEngine, scientific, and
   provider dependencies into an approximately 812 MB app;
4. post-build signature, three fresh LaunchServices probes, offline CLI/3D
   verification, archive round-trip, DMG construction, read-only mount, and
   inventory/checksum parity.

The PyInstaller freeze itself took 2 min 50 s, while application verification
and DMG verification together took 4 min 07 s. Removing those gates would make
the workflow faster only by removing evidence. Earlier long compiler-based
activity is not part of the selected path; the final Nuitka comparison was
cancelled on user selection and is not a benchmark.

## 6. Computer Use evidence and findings

The downloaded run `29683902995` DMG was mounted read-only and the packaged app
was opened. The following were directly observed:

- native Job builder, Chat, Settings, Database, and Analysis navigation existed;
- a canonical methane XYZ loaded in Job builder;
- Gaussian `opt`, charge 0, multiplicity 1 produced the expected semantic
  preview;
- the offline interactive 3D viewer was present;
- absent PyMOL was shown as optional and did not disable the default viewer;
- Chat visibly disclosed optional provider setup, read-only tools, and the
  continuing real-compute/HPC prohibition;
- Settings exposed workspace and PyMOL recovery actions.

`Generate input` remained disabled in that interaction because the required
Project field had not been filled. This is valid fail-closed behavior, not a
packaging failure.

Two post-build UX observations were isolated in source:

1. changing the workspace after a draft existed did not immediately revalidate
   the Job builder; and
2. a process launched with `/` as its current directory displayed an empty
   workspace basename.

The local source now refreshes the existing builder from `set_workspace()` and
falls back to `/` for the root label. A regression test proves invalid-to-valid
workspace transitions and the root label. The change passed the complete local
GUI suite, but it is **not present in run `29683902995`** because the user ended
the build before a replacement artifact was made.

During final cleanup, Quit removed the window but left both the packaged main
process and its QtWebEngine renderer alive. The exact task-owned main PID was
sent `SIGTERM`; both processes exited, and the read-only DMG was detached. This
is an unresolved packaged lifecycle defect, not an accepted graceful-shutdown
result.

## 7. Residual issues and unpassed gates

### High

- **Packaged graceful quit is not reliable.** Reproduce from the accepted DMG,
  choose ChemSmart > Quit after opening QtWebEngine-backed content, and verify
  that both the main process and every `QtWebEngineProcess` terminate without
  an external signal. Add a frozen-app regression before any later release.

### Required before a supported internal rollout

- Rebuild the post-artifact workspace-refresh/root-label fix and repeat the
  complete 18-gate verifier.
- Run the artifact on named clean Zhang Lab Apple Silicon Macs, including the
  oldest supported macOS 14 target.
- Complete installed/manual flows for restart/session recovery, deterministic
  offline Chat, Gaussian/ORCA fake input generation, Database browse/build/export,
  Grouper, Thermochemistry, DIAS, WBI, and 3D visualization.
- Stress long and Unicode paths, a read-only workspace, missing optional
  dependencies, cancel/retry, repeated and concurrent launches, large bounded
  database inputs, support-bundle creation, upgrade, and removal.
- Verify a real optional PyMOL executable on a named machine if that renderer is
  to be advertised.

### Required before broad distribution

- Obtain Developer ID Application credentials.
- Enable and verify hardened runtime without weakening the required
  QtWebEngine entitlements.
- Notarize, staple, and verify Gatekeeper acceptance on a clean machine.
- Define support ownership, release retention, and user-facing privacy review.

### Intentionally untested or prohibited

- No real Gaussian, ORCA, or xTB calculation ran.
- No scheduler, SSH, remote node, or HPC submission ran.
- No provider key was read or disclosed and no live provider request was needed
  for packaging acceptance.
- No public release was published.

## 8. Current local verification

After the workspace-refresh fix:

- `tests/gui`: 372 passed, 1 optional skip in 93.46 s;
- focused workspace tests: 2 passed;
- Ruff: green for GUI, packaging, and GUI tests;
- `compileall`: green;
- `git diff --check`: green.

These local results validate the source tree, not the immutable accepted DMG.

## 9. Safe resumption order

If work resumes, do not reset, clean, rebase, stash untracked files, or switch
branches as preparation. First verify the dirty state and this closure receipt.
Do not touch `docs/design/p7_remediation_directive.md` unless the user explicitly
reassigns ownership.

Resume in this order:

1. reproduce and fix the packaged Quit/process leak with a source-level and
   frozen-app regression;
2. preserve the workspace-refresh/root-label fix;
3. run local GUI and preservation suites;
4. create one exact-source PyInstaller snapshot and repeat the workflow;
5. independently download and verify the new artifacts;
6. run the named clean-machine/stress/Computer Use matrix;
7. pursue Developer ID/notarization only with explicit credentials and scope.

The detailed file/function map and modification workflow are registered in the
global `chemsmart-app-gui-design` skill, reference
`references/chemsmart-app-gui-design.md`, for both Codex and Claude.
