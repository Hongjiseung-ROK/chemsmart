# P7 macOS release-engineering receipt

Date: 2026-07-19
Status: In progress — PyInstaller selected; current P6 product build pending
Baseline commit: `760e0406`

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
- `chemsmart/gui/frozen_dispatch.py`
- `chemsmart/gui/packaging_probe.py`

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

- The previously authorized PyInstaller artifact passed all 18 P1 verifier
  flags, three isolated LaunchServices probes, a normal-window navigation smoke,
  offline 3Dmol rendering, Gaussian/ORCA fake input generation, archive
  round-trip, strict ad-hoc signing, and QtWebEngine helper entitlements.
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

Pending — no completion claim:

- Build the exact current P6 product tree on the isolated PyInstaller builder.
- Verify three fresh launches, Finder launch, clean preferences, restart/session
  recovery, database/analysis fixtures, and packaged 3Dmol against that artifact.
- Produce DMG, checksum, SBOM/dependency receipt, install/remove/upgrade guides,
  crash/log/support bundle, and explicit internal-alpha labeling.
- Run long/unicode path, read-only workspace, missing optional dependency,
  cancellation/retry, multi-launch, and database build/export stress tests.
- Obtain independent P7 release review and Computer Use acceptance.
- Developer ID/notarization remains pending external credentials and Apple
  service; it must never be inferred from an ad-hoc signature.

## Next gate

Run only the PyInstaller workflow against the exact current P6/P7 source tree.
Download both the evidence and verified bundle artifacts and independently
recompute archive integrity, signature, architecture/minimum-OS, launch, and
functional receipts before beginning DMG work.
