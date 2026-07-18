# P1 macOS packaging preflight receipt

Date: 2026-07-18
Status: local preflight green; isolated candidate builds not yet executed
Baseline commit: `3f781642afc3`

## Scope and decision boundary

P1 compares the same real GUI entry point under:

- PyInstaller 6.21.0, onedir `.app`;
- PySide6 6.9.2 `pyside6-deploy` with its compatible Nuitka 2.7.11 path.

No packaging winner is selected in this preflight. The phase cannot be marked
complete or committed until both isolated builds run and their measured
receipts are reviewed.

The first target is a disposable `macos-14` arm64 GitHub-hosted runner with
Python 3.11. The choice matches the user's Apple Silicon target and builds on an
older macOS than the development machine. It is provisional because the runner
is approaching retirement; P7 must use a maintained equivalent or a named
dedicated oldest-supported builder.

## Official constraints used

- Qt recommends `pyside6-deploy` for optimized PySide deployment and documents
  that it wraps Nuitka and can install deployment dependencies into the active
  Python environment. Therefore it is restricted to the disposable builder:
  <https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html>
- Qt WebEngine requires its helper, resource packs, locales, and macOS helper
  signing/entitlements. Candidate verification requires a bundled
  `QtWebEngineProcess`, a working render, and a valid ad-hoc signature:
  <https://doc.qt.io/qt-6/qtwebengine-deploying.html>
- PyInstaller says compatibility with older macOS versions requires freezing on
  the oldest intended macOS. P1 therefore does not use the macOS 26 development
  machine as the builder:
  <https://pyinstaller.org/en/stable/usage.html#making-macos-apps-forward-compatible>
- Apple requires Developer ID signing, hardened runtime, secure timestamps, and
  notarization for direct broad distribution. P1 only verifies an ad-hoc signed
  feasibility artifact; P7 owns the release gate:
  <https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution>
- GitHub's runner-image table currently maps `macos-14` to the arm64 Sonoma
  image and its release notice records the 2026 retirement window. The workflow
  still asserts both OS major and architecture at runtime rather than trusting
  the label alone:
  <https://github.com/actions/runner-images>

## Implemented contracts

- A pinned offline 3Dmol.js 2.5.5 asset with BSD-3-Clause license, source
  manifest, and runtime SHA-256 verification.
- Script-context-safe base64 molecule embedding into a self-contained
  QtWebEngine document, including malicious `</script>` and Unicode separator
  regression coverage.
- Absolute-path source/frozen CLI self-dispatch; ambient `chemsmart` on PATH is
  never used.
- A single automated bundle probe covering numpy, scipy, matplotlib, ASE,
  RDKit, pymatgen, PySide6/QtWebEngine, OpenAI, and Anthropic imports.
- Fresh user-template creation without shell mutation.
- Offline Gaussian and ORCA `--fake --no-scratch` input generation using the
  existing Click/jobs/writer path.
- LaunchServices execution three times with fresh HOME/TMPDIR and minimal PATH;
  every receipt must prove the frozen executable, macOS 14 arm64, in-bundle CLI
  self-dispatch, config locality, and generated-input locality.
- A separate normal-window smoke navigating all five reusable screens, checking
  the schema preview, and retaining a nonblank screenshot.
- Bundle size, cold launch time, peak RSS, Mach-O architecture/minimum OS,
  QtWebEngine helper, code-signing, Gatekeeper observation, expanded
  builder-path scan, before/after bundle inventory, symlink validation, and zip
  round-trip comparison.
- Source CLI/TUI regression on the builder. Textual remains a separately
  supported source-install UI and is explicitly excluded from the Finder app;
  the app embeds the existing Click CLI self-dispatch contract only.
- A manual-only GitHub Actions workflow; it has no push trigger, provider
  secret, signing secret, release, or publication step.

## Local evidence

The current Mac was not modified with pip, conda, brew, PyInstaller, or Nuitka.
No packaging tool was found in the existing environments, so no local `.app`
claim is possible.

Green checks:

```text
pytest -q tests/gui
46 passed in 2.69s

pytest -q tests/gui tests/test_config.py tests/agent/test_cli_schema.py
  tests/agent/test_provider_config.py tests/agent/test_provider_adapter.py
  tests/agent/tui/test_cli.py tests/agent/tui/test_track_a_foundation.py
  tests/agent/tui/test_synthesis_mode.py tests/agent/test_synthesis.py
153 passed in 8.22s

ruff check chemsmart/gui tests/gui packaging/macos
compileall chemsmart/gui packaging/macos
git diff --check
all green
```

The source offline probe also produced a 313-byte Gaussian `.com` and a
274-byte ORCA `.inp` through self-dispatched fake CLI children with a minimal
PATH. It verified nine locally available mandatory imports and thirteen copied
configuration files. `pymatgen` is absent from this Mac's existing environment,
so its required import remains deliberately red until the isolated builder
installs the project dependency set.

## Bottleneck and self-improvement note

Remote run `29635409558` proved the macOS 14 arm64 runner and workflow-dispatch
path, then both matrix jobs failed at the shared resolver before any build. The
captured error was exact: PyInstaller 6.21.0 requires
`pyinstaller-hooks-contrib>=2026.6`, while the preflight had pinned 2026.5. The
pin is corrected to the compatible minimum 2026.6 in both the requirement and
constraint files, with a static pairing regression. No packaging gate was
relaxed, and the failed run is not counted as candidate evidence.

On rerun `29635500608`, both jobs resolved the pinned environment and passed all
153 source regression tests. The pyside6-deploy dry-run also generated the
expected Nuitka command, but its assertion step invoked `rg`, which is absent on
the stock macOS 14 arm64 image (`exit 127`). The workflow now uses the platform
`/usr/bin/grep -F` for the same exact flag assertions; it does not install an
extra search tool or weaken the dry-run gate. The PyInstaller job was allowed to
continue so its independent build evidence could be retained.

The PyInstaller build completed, but its mandatory bundle verifier stayed red:
four LaunchServices checks produced no passing receipts and the bundle scan
found builder-path material. Its failed evidence upload also exposed a workflow
bottleneck: the broad build-directory path captured the PyInstaller work tree
and expanded the diagnostic artifact to 4,163,486,644 bytes. That failed
artifact is not candidate evidence and is deliberately not downloaded to a
developer machine. The workflow now uploads only explicit identity, dependency,
launch, metrics, checksum, and warning receipts on every outcome; the zipped
application is a separate zero-recompression artifact emitted only after the
mandatory verifier passes. This keeps failure diagnosis small while preserving
the full successful candidate for checksum and extraction analysis.

The first real QtWebEngine test returned an empty Python value even though the
page loaded. A console-instrumented minimum reproduction showed that 3Dmol had
loaded, one canvas existed, and the molecule contained the expected atom.
The boundary was Qt's JavaScript-object marshalling, not WebGL or the vendored
asset. The probe now serializes its JavaScript result with `JSON.stringify` and
parses JSON in Python; a real QtWebEngine regression test prevents recurrence.

The first read-only P1 review also found that globally ignored `.spec` files,
source-only probe success, and screenshots without content checks could create
false remote confidence. The revised gate explicitly tracks both specs, installs
the test/TUI extras on the disposable builder, dry-runs the generated Nuitka
command, requires frozen runtime and workspace-local evidence, exercises the
normal window path, retains nonblank captures, and verifies bundle/archive
immutability. These are mandatory checks rather than documentation-only claims.

The follow-up reviewer rated the workflow **GREEN for remote execution** while
keeping **P1 completion RED/pending** until both real bundle receipts exist.
Its remaining observations were folded back into the gate: peak RSS must now be
nonzero on every probe and shell launch, timeout cleanup targets only processes
inside the candidate bundle, and the shell preview must have a semantic
`chemsmart run <gaussian|orca> ...` prefix. Absolute performance thresholds are
not invented before measurements; candidate selection compares the retained
cold-start, RSS, and bundle-size evidence.

## Red gate / required next authority

The workflow and P1 changes are only local. GitHub Actions cannot execute a
workflow that is not present on a remote ref, and `workflow_dispatch` requires
the workflow path to exist on the default branch. The fork already registers
`.github/workflows/main.yml`; the new P1 path is not registered yet. To avoid a
default-branch change or a premature phase commit, the remote test will use an
ephemeral commit that leaves the current branch/index untouched, contains the
reviewed P1 snapshot, and maps the P1 workflow content to the existing
`main.yml` path on that temporary ref only. Dispatching registered `main.yml`
with `--ref` then uses that ref's workflow version. The standing goal explicitly
withholds push/PR publication, so this requires permission to push the temporary
test branch, dispatch it, and download its two evidence artifacts. It does not
require a PR, release, default-branch edit, provider secret, or phase commit.
