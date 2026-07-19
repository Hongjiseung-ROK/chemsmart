# P1 macOS packaging preflight receipt

Date: 2026-07-18
Status: Complete — PyInstaller selected; pyside6-deploy retained as red fallback
Baseline commit: `3f781642afc3`

## Scope and decision boundary

P1 compares the same real GUI entry point under:

- PyInstaller 6.21.0, onedir `.app`;
- PySide6 6.9.2 `pyside6-deploy` with its compatible Nuitka 2.7.11 path.

Both candidates were built on the same isolated target and subjected to the
same mandatory verifier. PyInstaller 6.21.0 is selected for the desktop release
path. The pyside6-deploy/Nuitka candidate remains documented as a fallback, but
its pinned macOS bundle layout is red under Apple's code/data placement and
signing rules and is not a distributable artifact.

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
66 passed

pytest -q tests/gui tests/test_config.py tests/agent/test_cli_schema.py
  tests/agent/test_provider_config.py tests/agent/test_provider_adapter.py
  tests/agent/tui/test_cli.py tests/agent/tui/test_track_a_foundation.py
  tests/agent/tui/test_synthesis_mode.py tests/agent/test_synthesis.py
173 passed in 9.99s

ruff check chemsmart/gui chemsmart/cli/config.py tests/gui tests/test_config.py
  packaging/macos
compileall chemsmart/gui chemsmart/cli/config.py packaging/macos
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

The first bounded-evidence rerun (`29635968258`) revealed a second duplicate:
the retained launch root also contained the archive-roundtrip extraction, so
its evidence artifact was still 3,985,597,066 bytes. The upload contract is now
narrowed again to receipt JSON, screenshots, fake Gaussian/ORCA inputs, metrics,
identity, and warnings. Archive extraction remains a mandatory in-run hash gate
but is never uploaded; a verified bundle remains available only through the
separate successful-bundle artifact.

The resulting 1,159,133-byte diagnostic artifact was downloaded and hashed.
Its metrics prove an 812,774,671-byte arm64 bundle with valid ad-hoc signing,
macOS 11.0 Mach-O minimum, macOS 14.0 plist minimum, intact symlinks and bundle,
successful archive round trip, and nonzero RSS. All three probes and the shell
process were observed for roughly 0.5 seconds (58,928–74,672 KiB peak RSS), but
LaunchServices returned without any app receipt. Because the Finder-style
bundle suppresses application stdout/stderr, the verifier now redirects both
streams to bounded diagnostic files for every launch.

The same metrics also showed that the generic `/Users/runner/` and
`/private/var/folders/` scan matched hundreds of compiled third-party wheel
objects rather than identifying a current ChemSmart source path. Those generic
signals remain recorded as provenance observations. The mandatory leak gate now
checks the exact current `GITHUB_WORKSPACE` and `RUNNER_TEMP` supplied by the
isolated builder, so an active build path still fails while unrelated upstream
wheel provenance cannot create a false packaging failure.

Run `29636430428` downloaded a 1,195,588-byte diagnostic artifact and exposed
the first application exception identically in all four launches. PyInstaller
started the app and measured 34,896–79,472 KiB RSS, but initial configuration
copying attempted to create relative `build/.../home/.chemsmart` from the
Finder-style `/` working directory and failed with read-only-filesystem error
30. A first resource-path hypothesis was tested in run `29636703894` and
rejected because the exception was unchanged.

The actual defect was in the verifier: `tempfile.mkdtemp(dir=relative_path)`
returned a relative launch root, while the receipt's expected field applied
`.resolve()` only when reporting it. The gate therefore displayed an absolute
HOME it had never supplied to the app. Launch evidence roots are now resolved
before HOME, TMPDIR, workspace, stdout, stderr, or receipt paths are constructed;
`_launch_once` rejects a non-absolute root, and a chdir regression proves that a
relative metrics argument still creates an absolute isolated environment. This
smaller fix preserves the existing `importlib.resources` behavior.

The first execution of that helper in run `29636976852` stopped before launch
because the caller retained the helper's former `rmdir()` responsibility and
removed the already-removed root a second time. The redundant caller cleanup is
deleted; the focused test continues to require that the helper return an
absolute, non-existent path ready for the verifier's create-once contract.

Run `29637140800` is the first fully green PyInstaller candidate. On the pinned
macOS 14.8.7 arm64/Python 3.11.9 builder, all 155 source contracts passed, the
app build took 3 minutes 31 seconds, and the mandatory verifier took 1 minute
21 seconds. The 812,774,671-byte app contains 10,612 files, 2,088 directories,
and 1,956 valid symlinks. Its main executable is arm64 with Mach-O minimum 11.0
and plist minimum 14.0; bundle identifier, ad-hoc signature, QtWebEngine helper,
3Dmol asset, exact-path leak gate, immutability, and archive round trip all
passed.

All three fresh-HOME launches passed with 10 required imports, absolute
self-dispatch, zero-returncode version/Gaussian/ORCA children, 313-byte Gaussian
and 274-byte ORCA fake inputs, and a real one-canvas/three-atom 3Dmol render.
The first full probe completed in 10.289 seconds and repeats completed in
6.654/5.873 seconds; matching app/helper/CLI process-tree peak RSS was
470,960–479,184 KiB. The normal shell workload, including navigation and
screenshot capture, passed in 3.089 seconds at 434,832 KiB process-tree RSS,
navigated and reused all five screens, retained a semantic
`chemsmart run gaussian opt` preview, and produced a nonblank 1040×680 capture.

The 1,273,686-byte evidence artifact and 310,936,342-byte bundle artifact were
downloaded. Local recomputation confirmed archive SHA-256
`16e08e1a4ea11c086b722aadd2fc8e316454f94db226f092b17db7e05f4e7407`
against both receipts, and `unzip -t` found no compressed-data error. The only
nonblocking stderr observation was Qt spending 58 ms substituting an available
monospace font for absent `SF Mono` on the runner. P2/P6 should use Qt's system
fixed-font family rather than relying on that named family; it is not a P1
packaging-integrity failure.

Run `29636435718` supplied the first complete pyside6-deploy/Nuitka comparison
receipt. Dependency installation and 153 source contracts passed, the generated
Nuitka command retained the package, CLI providers, QtWebEngine, and offline
resources, and native compilation completed successfully. The build step alone
took 1 hour 16 minutes 50 seconds; the whole job took 1 hour 20 minutes 10
seconds. Nuitka reported that no usable arm64 `ccache` was active, making the
first measurement a valid uncached build-cost baseline rather than an app
startup measurement.

The produced arm64 app was 2,472,314,601 bytes with 2,488 files and no symlinks.
Its three attempted full probes ran for 8.337/5.093/4.662 seconds at
594,592–599,312 KiB process-tree RSS, while the shell attempt ran for 5.018
seconds at 549,344 KiB. Those attempts are observations, not passing launch
receipts: the older verifier supplied relative HOME/TMPDIR paths, so the app
created one directory inside its bundle and the expected absolute receipt paths
remained empty. This independently reproduced the verifier defect already fixed
on the latest ref.

The same run exposed a candidate-specific defect that is not attributed to the
verifier. Strict recursive code-signature validation rejected an executable-mode
`qtwebengine_resources.pak` subcomponent, and Gatekeeper reported no usable
signature. The 12,113,898-byte failure-evidence artifact, including the complete
12,047,921-byte Nuitka report, was downloaded; the 2.47 GB invalid application
was intentionally not uploaded. The optimized retry normalizes execution bits
only on the exact `qtwebengine_resources*.pak` allowlist, records the path,
before/after modes, and unchanged content hash, reapplies an ad-hoc recursive
signature while preserving helper entitlements, and verifies it before running
the mandatory bundle gate.

The retry also follows Nuitka's documented macOS arm64 guidance by installing
Homebrew `ccache`, setting `NUITKA_CCACHE_BINARY`, persisting a bounded 2 GB
compiler cache, and retaining configuration/hit-rate receipts. This does not
relax the first uncached baseline or turn build time into a user-runtime metric;
it measures whether a repeated packaging iteration can avoid the observed
77-minute compiler bottleneck.

Inspection of the extracted PyInstaller artifact then found a stricter shared
boundary: `QtWebEngineProcess` had a valid file signature but exposed no signed
entitlements, while its bundled Qt template requires four Chromium/JIT values.
The earlier PyInstaller result therefore remains runtime-green under the first
gate but is not promoted to final P1 evidence. A common signer now applies the
template to each helper app, re-seals its containing QtWebEngine framework, and
finally re-seals the outer app. On the extracted 804 MB application this
nested-to-outer sequence passed strict deep verification and preserved all four
required entitlement values. The final remote gate independently verifies each
helper signature and compares its actual entitlement plist with the bundled
template.

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
not invented before measurements; candidate selection compares the same
retained probe workload, process-tree RSS, bundle size, and build cost.

## Final same-run evidence and decision

The user authorized the fork-only temporary branch, manual workflow runs, and
artifact downloads. The current local branch, HEAD, and index stayed unchanged
while ephemeral CI snapshots were fast-forwarded to
`codex/p1-macos-packaging-spike`; no PR, release, default-branch edit, provider
secret, or signing secret is involved.

Run `29641724327` at ephemeral snapshot `d51d878e4aa2` executed both candidates
together. Its PyInstaller job was fully green in 5 minutes 39 seconds: the build
took 2 minutes 50 seconds, nested-to-outer signing took 4 seconds, and the
mandatory verifier took 1 minute 12 seconds. All 166 source contracts on that
snapshot passed. The final 812,775,695-byte application passed all 18 mandatory
flags, including isolated LaunchServices execution, internal CLI self-dispatch,
Gaussian/ORCA fake inputs, an offline three-atom 3Dmol render, normal-window
navigation, bundle immutability, archive round trip, exact builder-path leak
checks, helper entitlements, and strict ad-hoc signature verification.

The three frozen probes completed in 7.534/5.673/5.690 seconds at
474,848–485,408 KiB process-tree peak RSS. The normal shell completed in 3.264
seconds at 421,056 KiB. The bundle contains 10,612 files, 2,088 directories, and
1,956 valid symlinks; its main executable is arm64 with Mach-O minimum macOS
11.0 and plist minimum macOS 14.0. The inner application archive SHA-256 is
`5fdf4c3b91d8ca8396f531b0097cbaaa56de9bf5583a0a3cbe88ccfdb2b7564a` and
matched both downloaded receipts. `unzip -t` passed.

The downloaded PyInstaller evidence artifact is ID `8428863685`, 1,280,063
bytes, GitHub artifact digest
`9e00c8254eeb3f904b2c8d21995f9965f382d67e64833a40a0c3aed0626fa68c`.
The verified bundle artifact is ID `8428864403`, 310,937,572 bytes, digest
`97396143a7538d1aa0ebe2d6467f39cde99adabdf569dcf32ce9184988920748`.
Gatekeeper rejection is retained as the expected observation for an ad-hoc,
unnotarized P1 artifact; Developer ID signing, hardened runtime, notarization,
and stapling remain P7 release gates.

The same run compiled the pyside6-deploy candidate successfully in 1 hour 21
minutes 7 seconds and passed 166 source contracts. Its exact hidden template
relocation preserved 13 files and four directories with identical before/after
tree SHA-256. All four discovered QtWebEngine helper paths and two containing
framework paths signed successfully, but the outer signature failed because
`Contents/MacOS/qtwebengine_resources.pak` was treated as unsigned nested code.
The mandatory verifier and bundle upload were therefore skipped. The downloaded
failure artifact is ID `8429504538`, 12,070,240 bytes, digest
`2b4516d974e3d36b204fc6fb8718fdfd52ae31d73dedb7cb6ce189313aa4b9b3`.

Apple's signing guidance reserves `Contents/MacOS` for code, while Qt documents
the Chromium `.pak`, ICU, V8 snapshot, and locale data under application
resources. A local minimum app reproduced the remote error with a nonexecutable
`.pak` under `Contents/MacOS` (`codesign` rc 1); moving the unchanged file to
`Contents/Resources` produced outer-sign and strict-verify rc 0. An exact,
preflighted relocation was therefore tested once more without relaxing any
signing gate.

The bounded pyside-only retry `29644567072` at snapshot `45d35f56ab1f` passed
172 source contracts and restored the compiler cache with 6,796/6,796 direct
hits and zero misses. Even with a 100% compiler hit rate, its build step took 51
minutes 17 seconds. Before mutating the bundle, the new stop guard discovered a
second unallowlisted data file directly in the code directory:
`Contents/MacOS/qt6.conf`. This proves the pinned Nuitka layout mixes code and
data structurally rather than exposing one isolated file-mode defect. Per the
reviewed stop condition, no reactive allowlist expansion or third long retry is
performed. The downloaded retry evidence artifact is ID `8430091014`,
12,061,648 bytes, digest
`5f2ca3d73627983f6c0915e92d68f323697cf8134a0690fabd14851c1cc46ff4`;
no invalid pyside application bundle was uploaded.

PyInstaller is selected because it alone passes the complete frozen runtime,
helper-entitlement, signature, archive, and researcher-shell gates; it also
builds in 2 minutes 50 seconds rather than 51–81 minutes and produces an
approximately 813 MB application rather than the 2.47 GB invalid pyside
baseline. The pyside measurements from invalid launch environments are not
promoted as performance results. pyside6-deploy remains a documented fallback
for future reevaluation after its macOS bundle layout changes upstream.

P1 establishes packaging feasibility and a reproducible candidate. It does not
claim that the P0 scaffold is the finished researcher UI. Progress reporting,
cancellation/recovery, accessible controls, researcher workflow depth, and
continued Apple-design refinement remain mandatory P2–P6 work.

## Fresh authorized confirmation — run 29668168830

On 2026-07-19 the user authorized pushing the already-existing temporary ref,
running the manual macOS workflow with `candidate=both`, and downloading both
candidate artifacts. The no-op fork push reported `Everything up-to-date`; run
`29668168830` executed exact SHA `45d35f56ab1f041131bbb5a0fe116647c9de6d9e`.

All three outer artifact ZIP SHA-256 values match GitHub's digests and pass
archive integrity checks. Both source suites report `172 passed`. The fresh
PyInstaller bundle archive SHA-256 is
`16c397ed0661007412392db9365afbd7505e7833d4e8a82fbc4574cadb10f7c0`,
matching both internal receipts. Its 812,775,791-byte app again passes all 18
mandatory gates: arm64/minimum-OS identity, exact bundle identifier, symlink and
inventory integrity, nested-to-outer signature, all four QtWebEngine helper
entitlements, three isolated LaunchServices probes, shell navigation,
Gaussian/ORCA fake inputs, self-dispatch, offline 3Dmol render, archive round
trip, and local strict/deep re-verification. Gatekeeper rc 3 remains expected
for an ad-hoc, unnotarized spike. The only Low observation is a 55 ms SF Mono
substitution.

pyside6-deploy again completed compilation, this time with 6,796/6,796 compiler
cache hits, but strict normalization stopped before mutation because the pinned
Nuitka bundle contains `Contents/MacOS/qt6.conf`. No pyside bundle, signature,
metrics, or launch artifact was accepted. This is the same deterministic
failure as the immediately preceding `45d35f56` attempt, not compiler
nondeterminism.

The bounded fallback fix is now specific: do not relocate `qt6.conf` blindly.
Permit it beside the executable only if it is a regular non-symlink,
non-executable file with the exact 19-byte `[Paths]\nPrefix = .\n` payload;
record path, mode, size, and SHA-256 unchanged. Missing, modified, executable,
symlinked, and additional direct-data cases must fail before mutation. A new
remote rerun requires new authorization and must still pass normalization,
signing, helper entitlements, three probes, shell, archive, and checksum gates.

The production recommendation is unchanged: PyInstaller is the release
baseline; pyside6-deploy remains an experimental, non-blocking fallback. The
temporary ad-hoc artifact itself is not a release. Current-product integration,
Developer ID, hardened runtime, notarization, maintained-builder, and
clean-machine acceptance remain P7 gates.
