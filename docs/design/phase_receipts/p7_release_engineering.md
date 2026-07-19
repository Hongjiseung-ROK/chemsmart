# P7 macOS release-engineering receipt

Date: 2026-07-19
Status: Build frozen by user — exact-source PyInstaller internal-alpha
distribution verified; product acceptance incomplete
Baseline commit: `760e0406`
Packaging-selection commit: `c53ced23`

## Final packaging decision

PyInstaller 6.21.0 `onedir` is the sole active macOS packaging and release path.
The decision is backed by retained P1 macOS 14 arm64 receipts and was finalized
by the user on 2026-07-19. Active workflow inputs, build dependencies, runtime
dispatch, and the feature contract expose no second packager.

The retired compiler-based comparison remains historical evidence only in
`p1_packaging_preflight.md`. Its last authorized run, `29678977207`, was
cancelled after 22 minutes 23 seconds when the final selection was made. It
produced no signed, verified, or downloadable candidate bundle and is not a
performance or failure result.

## Active owned files

- `.github/workflows/macos-packaging-spike.yml`
- `packaging/macos/ChemSmart.pyinstaller.spec`
- `packaging/macos/build-requirements.txt`
- `packaging/macos/constraints.txt`
- `packaging/macos/runtime-lock-py311-macos14-arm64.txt`
- `packaging/macos/adhoc_sign_bundle.py`
- `packaging/macos/verify_bundle.py`
- `packaging/macos/build_internal_alpha.py`
- `packaging/macos/inventory_pyinstaller_components.py`
- `chemsmart/gui/frozen_dispatch.py`
- `chemsmart/gui/packaging_probe.py`
- `chemsmart/gui/application/desktop_logging.py`
- `chemsmart/gui/application/support_bundle.py`
- `docs/release/macos_internal_alpha.md`

## Preservation and safety boundary

- The selected app retains the existing Click CLI through absolute-path frozen
  self-dispatch; it does not resolve an ambient `chemsmart` executable.
- The Textual TUI remains source-install supported and regression-tested. It is
  not embedded in the Finder app and is not deleted or simplified for packaging.
- QtWebEngine, offline integrity-checked 3Dmol, provider SDK imports, scientific
  dependencies, configuration templates, and Gaussian/ORCA fake-input probes
  remain mandatory bundle gates.
- No provider request, secret, real Gaussian/ORCA/xTB calculation, or HPC
  submission is part of packaging verification.
- Ad-hoc signing is internal-alpha evidence only. Developer ID, hardened
  runtime, notarization, and stapling remain separate release gates.

## Current receipts

Green:

- The PyInstaller-only workflow parses as YAML and remains manual-only, with no
  push or pull-request trigger and no secret reference.
- Focused packaging/feature-contract/frozen-dispatch tests: 14 passed.
- Complete GUI regression after retiring the inactive packager: 345 passed,
  one optional-dependency skip.
- Packaging-aligned CLI/TUI/provider regression: 118 passed.
- Ruff, compileall, and `git diff --check`: green.
- Independent read-only release review: GREEN, Critical 0, High 0, Medium 0.
  Its two Low observations were closed by pinning every GitHub Action to an
  immutable commit SHA and narrowing signing/verification to the exact selected
  PyInstaller output path.
- Post-review packaging/signing/verifier focused regression: 28 passed; reviewer
  follow-up GREEN with Critical 0, High 0, Medium 0, Low 0.

### Exact current-product build

Authorized manual run
[`29680091104`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29680091104)
built exact source/workflow SHA `fea2b50f8f1b9167abe4af6c047354df0b59f4d5`
on the temporary fork branch only. That snapshot contains the current P6 product
tree and final PyInstaller-only release path. The current feature branch was not
pushed or modified by the run.

The `macOS 14.8.7 arm64`/Python 3.11.9 job completed green in 6 minutes 30
seconds. Its PyInstaller build step took 2 minutes 39 seconds, nested-to-outer
ad-hoc signing took 3 seconds, and bundle verification took 1 minute 11
seconds. The isolated builder ran the combined source preservation suite first:
463 passed and one optional-dependency test skipped. Runtime-lock verification
found all 134 expected distributions at the required versions; the only 135th
distribution was the explicitly allowed unlocked local `chemsmart` source.

All 18 mandatory bundle flags passed. The resulting application is
812,618,651 bytes with 10,633 regular files, 2,098 contained directories, and
1,959 relative, nonescaping, nonbroken symlinks. Its main executable is arm64,
its Mach-O minimum is macOS 11.0, its declared application minimum is macOS
14.0, and its bundle identifier is `org.zhanglab.chemsmart`. The app retained
the offline 3Dmol 2.5.5 asset and one QtWebEngine process helper exposed through
three framework paths. The helper and containing framework were signed before
the outer app, all four required Chromium/JIT entitlements were present, and
strict deep code-signature verification passed.

Three independent fresh-HOME/TMPDIR/minimal-PATH LaunchServices probes passed in
7.456, 5.597, and 5.877 seconds at 468,224–474,960 KiB peak process-tree RSS.
Every run proved frozen arm64 execution, in-bundle absolute self-dispatch,
configuration and generated-file locality, zero-returncode version/Gaussian/
ORCA CLI children, 313-byte Gaussian and 274-byte ORCA fake inputs, and a real
offline three-atom/one-canvas 3Dmol render. The normal product shell passed in
3.016 seconds at 272,512 KiB peak RSS, reused and navigated Job builder, Chat,
Database, Analysis, and Settings, and retained the semantic
`chemsmart run gaussian opt` preview. All four application stderr receipts were
empty. Screenshot inspection confirmed both the rendered water molecule and
the current 1040 x 680 P6 product shell rather than a packaging-only placeholder.

The verifier hashed the application before and after launch to the same
inventory digest
`ee61aa7987bdd9bcf33c0993154e6bc4172854720e7130b46e1d65b248e5a9eb`.
Its zip round-trip restored the same files, directories, symlinks, and digest.
The inner application archive is 311,728,518 bytes with SHA-256
`fd328266eee022f470fdd07612ae1219d3df23055a826d09e74fbb90357ca379`;
that value matches the checksum in both downloaded artifacts and `unzip -t`
reported no compressed-data errors.

The downloaded evidence artifact is ID `8440321981`, 1,307,481 bytes, with
GitHub digest
`17cc30042a528aa30d264fafba7b886d15f174acd76d56c3249f7913657ae51a`.
The verified-bundle artifact is ID `8440322450`, 311,728,917 bytes, with GitHub
digest `75e065e07de58678b15325848fb15c4a8707b236ab69b464b9f0e9beb5ef049c`.
These are outer artifact digests and are deliberately distinguished from the
inner application-archive checksum above.

Independent extraction on the development Mac revalidated 10,633 files, 1,959
symlinks, zero broken links, arm64 identity, the two minimum-OS values, the
bundle identifier, all four helper entitlements, zero occurrences of the exact
CI workspace path, and strict/deep signature validity. No package was installed
on the development Mac. Gatekeeper rejection remains an expected, retained red
boundary for this ad-hoc-signed internal-alpha candidate; it is not represented
as Developer ID or notarized software.

### P7 distribution and support implementation

The PyInstaller-only workflow now builds an explicitly labeled HFS+ UDZO
internal-alpha DMG only after the signed application passes the complete bundle
verifier. The release builder copies rather than edits the signed app, rejects
an output path inside or enclosing the input app, mounts the resulting image
read-only, and requires exact inventory parity, the Applications shortcut,
unchanged release notice, strict/deep signature validity, and the expected
ad-hoc Gatekeeper rejection. It atomically publishes a new release directory
with the DMG, `SHA256SUMS.txt`, a release receipt, an internal-alpha README, and
a CycloneDX SBOM. The content contract is reproducible; raw HFS+/`hdiutil` DMG
bytes are explicitly not claimed reproducible because filesystem-image metadata
is not normalized.

The SBOM boundary was tightened during independent review. It now derives
shipped distributions from PyInstaller's binary/data `Analysis-00.toc` plus
its pure-Python `PYZ-00.toc`, hashes both graphs, maps their modules to the exact
134-item runtime lock, requires the scientific/provider/Qt runtime set, and
fails if excluded builder/test/TUI distributions appear. Build-environment tools
are recorded separately as SBOM tool metadata, with each scope stating whether
that tool also appears in the shipped inventory. Three earlier local DMG
integration attempts used the complete builder lock as their SBOM component
list; their DMG-mount and inventory results remain diagnostic only, while their
SBOMs and release receipts are retired and are not accepted as P7 evidence.

The application now writes bounded rotating diagnostics to an owner-only log
directory without following a log-file symlink. Failure to configure diagnostic
logging cannot block Finder launch. Help > Create Support Bundle creates a new,
owner-only ZIP on explicit request, loses concurrent filename races without
overwriting the winning file, exports only complete bounded log lines, redacts
home paths and common secret forms, and excludes configuration, projects,
provider payloads, sessions, and Keychain data. About ChemSmart reports the
exact application version. The lifecycle guide covers checksum verification,
install, upgrade, application removal, optional removal of configuration,
preferences and logs, Keychain review, and support-bundle review.

Fresh focused regression after the review fixes is green: 57 tests passed;
Ruff, compileall, and `git diff --check` are green. This was the local
source-level gate before the exact-source remote sequence below.

Exact-source run
[`29681783918`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29681783918)
then exposed a workflow-path defect without producing release evidence. The
486-test source gate passed and the PyInstaller app build completed in 2 minutes
44 seconds, but the new component-inventory step looked under
`work/ChemSmart/Analysis-00.toc`. PyInstaller names this spec work directory
`work/ChemSmart.pyinstaller`, so the receipt path did not exist. Signing,
bundle verification, and DMG creation correctly did not run. The workflow now
uses the exact spec-derived directory for both `Analysis-00.toc` and the warning
file. This run is retained as a failed gate-path diagnostic, not an application
or distribution result.

Follow-up run
[`29682007885`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29682007885)
proved that the corrected path resolves, then failed the component boundary
honestly with 35 observed distributions and four missing mandatory pure-Python
packages: `anthropic`, `ase`, `keyring`, and `openai`. The cause is not missing
application functionality: `Analysis-00.toc` describes the binary/data side of
the freeze, while PyInstaller records pure modules in `PYZ-00.toc`. The
inventory now merges and separately hashes both graphs rather than weakening
the mandatory set or reverting to the inaccurate full builder lock. Signing,
bundle verification, and DMG creation again correctly did not run, so this is a
second failed-gate diagnostic rather than release evidence.

Run
[`29682308206`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29682308206)
preserved both raw TOCs and showed why the first two-graph parser still reported
the same 35 distributions: PyInstaller records optimized pure modules with TOC
types such as `PYMODULE-1`, while the parser accepted only the unsuffixed
`PYMODULE` type. Direct inspection confirmed the supposedly missing packages
inside the downloaded 1.7 MiB `PYZ-00.toc`. The parser now normalizes the
optimization suffix before applying the allowlist and has a regression fixture
using the observed format. This is again a failed parser-gate diagnostic; no
signed bundle or DMG from the run is accepted.

Reanalysis of those downloaded graphs with the corrected parser found all ten
mandatory distributions and one real excluded distribution, `pytest`. One
confirmed import chain was `collect_submodules("keyring")` →
`keyring.testing.backend` → `pytest`; both modules were present in the raw PYZ
graph. The spec excluded only `keyring.testing*` while retaining the macOS
Keychain backend and all other keyring modules.

Exact-source run
[`29682672351`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29682672351)
confirmed all mandatory distributions but still found `pytest` after
`keyring.testing` was removed, proving that the first chain was real but not the
only optional diagnostic edge. Product code does not use pytest. The selected
spec therefore excludes `pytest`, `_pytest`, `coverage`, `pip`, and
`PyInstaller` from application analysis explicitly; the subsequent full frozen
runtime verifier must prove that this boundary removes no required behavior.
Future evidence artifacts also retain PyInstaller's import cross-reference for
direct diagnosis. No signed bundle or DMG from this run is accepted.

Run
[`29682893760`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29682893760)
confirmed that `pytest` and `_pytest` were gone, but retained the independent
top-level compatibility shim `py`, whose installed distribution is still
pytest. The component gate correctly attributed that single shipped module and
remained red. The spec now excludes `py` as well. The run also exposed the
spec-derived report filenames `xref-ChemSmart.pyinstaller.html` and
`warn-ChemSmart.pyinstaller.txt`; the evidence upload now uses those exact
names. No signing, bundle verification, or DMG result from this run is accepted.

### Exact-source internal-alpha distribution

Run
[`29683113974`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29683113974)
was the first end-to-end green P7 distribution. Independent review then found a
Low metadata ambiguity: `setuptools` and `wheel` appeared correctly in the
shipped component list but the tool metadata called all five build tools
builder-only. The app, DMG, checksums, and shipped list remain valid diagnostic
evidence, but that distribution was superseded rather than promoted. The SBOM
generator now distinguishes builder-only tools from build tools also present in
the shipped inventory; its regression and reviewer follow-up are green with
Critical 0, High 0, Medium 0, and Low 0.

Authorized manual run
[`29683902995`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29683902995)
is the accepted P7 internal-alpha distribution receipt. It built exact source
and workflow SHA `91f55b5972b57beb3e1ea39b45fcc04433c3e606` on the
temporary fork branch only. The `macOS 14.8.7 arm64` job completed green in 10
minutes 2 seconds. Dependency installation took 1 minute 9 seconds, the combined
source gate took 1 minute 27 seconds, the PyInstaller build took 2 minutes 50
seconds, component inventory took one second, nested-to-outer ad-hoc signing
took four seconds, the 18-gate application verifier took 1 minute 14 seconds,
and DMG construction plus mounted verification took 2 minutes 53 seconds. The
source gate reported 489 passed and one optional-dependency skip.

All 18 mandatory frozen-application flags passed again. Three fresh
LaunchServices probes completed in 8.474, 5.843, and 6.021 seconds with peak
process-tree RSS of 484,144, 481,872, and 481,200 KiB. The normal product shell
completed in 3.070 seconds at 274,272 KiB peak RSS. The signed app contains
10,633 files, 2,098 directories, and 1,959 relative, nonbroken, nonescaping
symlinks; it is 811,942,895 bytes and hashes to the exact inventory digest
`c8f29f29635249cb83fe16df795608f06ddfc1cbc328d134b96fb4fb956db123`.
The 311,054,280-byte verified-bundle ZIP has SHA-256
`80b6b1feb1f1a5151dc7c7b23fa5563575fadca17a8d15420b15a458dae4d7d9`;
the downloaded copy matches its receipt and `unzip -t` reports no compressed
data error.

The PyInstaller `Analysis-00.toc` and `PYZ-00.toc` hashes are respectively
`1f5d3fa71482022c51018a315d15242d457ee4fada58a8212e147c6fae9ff3d5`
and `4a5917f675a62281c8c9e3973d194515574ceb3df8d6402126830a5df6affce6`.
Their component receipt maps 111 shipped distributions, includes all ten
mandatory scientific/provider/Qt distributions, and contains none of the eight
forbidden builder/test/TUI distributions. The CycloneDX 1.5 SBOM repeats those
111 shipped components and records `pip`, `pyinstaller`,
`pyinstaller-hooks-contrib`, `setuptools`, and `wheel` separately as build
tools. `setuptools` and `wheel` also occur in the shipped inventory; the other
three are builder-only. Its embedded source SHA and inventory digest match the
run and app.

The published HFS+ UDZO image is 338,317,126 bytes with SHA-256
`e287a6c6bda5bcc74fded295990debe3eb0903a5952cb7cd12a018b5988911b4`.
Every entry in the downloaded `SHA256SUMS.txt` passed. Independent read-only
mounting on the development Mac then reconfirmed a valid image checksum,
strict/deep signature validity, `org.zhanglab.chemsmart`, version `2.0.1`,
declared minimum macOS 14.0, the `/Applications` shortcut, exact README content,
zero unsafe symlinks, and the same app inventory digest. Gatekeeper returned the
required code 3 rejection for the deliberately ad-hoc-signed internal alpha. No
package was installed on the development Mac.

The downloaded evidence artifact is ID `8441538533`, 23,669,802 bytes, with
GitHub digest
`cfbb12dcbdc5cdec10c96c7037143ec8bde5dfe3267b2d6c42429f491a5da43e`.
The verified-bundle artifact is ID `8441538903`, 311,054,679 bytes, with digest
`9fff7191c1fee1cc5a845b04ab93b1a08b87decfadb24b266a03ca9de15bd1d6`.
The internal-alpha distribution artifact is ID `8441539284`, 338,374,019 bytes,
with digest
`8e3b916123774f82069d8efd74e4e041b55f35950e0a8823852f72eb738dfdd9`.
These GitHub artifact digests describe the outer transport archives and remain
distinct from the inner ZIP, DMG, SBOM, README, and receipt checksums.

### Build-stop addendum

The user ended the build after run `29683902995`; no replacement packaging run
is authorized by this receipt. Computer Use opened the downloaded read-only DMG,
loaded a canonical methane structure in Job builder, rendered the semantic
Gaussian optimization preview and offline 3D surface, confirmed optional PyMOL
and provider disclosure states, and inspected Settings and Chat. Generate input
correctly remained disabled because the required Project field was empty.

That interaction exposed two source-level workspace presentation/state issues:
an existing draft was not revalidated immediately after changing workspace, and
the root workspace `/` rendered with an empty basename. The local source fixes
both and adds a regression for invalid-to-valid workspace changes and the root
label. The complete local GUI suite then passed 372 tests with one optional
skip; Ruff, compileall, and `git diff --check` are green. These changes are not
inside the immutable accepted artifact and must not be attributed to it.

Final cleanup exposed an unresolved packaged lifecycle defect: ChemSmart > Quit
removed the window but left the main process and its QtWebEngine renderer alive.
The exact task-owned process was terminated with `SIGTERM`, both processes
exited, and the read-only DMG was detached. A future build must reproduce and
fix this leak, then prove graceful main/helper shutdown from the frozen app.

The complete frozen-state handoff is
`docs/design/chemsmart_native_desktop_build_closure_2026-07-19.md`.

Pending — no completion claim:

- Verify restart/session recovery and packaged database/analysis fixtures.
- Test the installer on clean, named Zhang Lab Macs rather than treating the
  disposable builder as the final supported-machine matrix.
- Run long/unicode path, read-only workspace, missing optional dependency,
  cancellation/retry, multi-launch, and database build/export stress tests.
- Rebuild the post-artifact workspace fix and fix/prove graceful packaged Quit.
- Complete, rather than partially sample, Computer Use acceptance.
- Developer ID/notarization remains pending external credentials and Apple
  service; it must never be inferred from an ad-hoc signature.

## Next gate

No next build is authorized by this frozen receipt. If the user resumes work,
begin with the packaged Quit leak and the unbuilt workspace-refresh fix, then
create a new exact-source PyInstaller artifact before named clean-machine and
stress acceptance. Retain the verified content contract without claiming
byte-reproducible HFS+ DMG images.
