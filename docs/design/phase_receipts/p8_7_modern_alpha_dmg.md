# P8.7 modern internal-alpha DMG receipt

> Superseded 2026-07-20 (same day) by the 3D-stage candidate below — the
> original `bc02f002` artifact remains historical evidence.
>
> **Accepted current artifact**: source
> `9b9360c093eae8853f420263cc32f0845fd47d8f` (adds the P8.3 gold slice:
> 3D molecule stage in the Job builder), run
> [`29723729765`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29723729765),
> `status: passed`. DMG SHA-256
> `3d669e8dbf3e856295938a7e16bac50896db9234598eddb24f9100a08385d5a8`
> (338,531,033 bytes). Independent local checks repeated: distributed
> checksums OK, `hdiutil verify` VALID, strict deep codesign OK, clean
> mount/detach. Delivered to
> `~/Desktop/ChemSmart-2.0.1-macos14-arm64-internal-alpha.dmg`
> (replacing the earlier build) with `SHA256SUMS.txt`.
> Complete GUI suite at that source: 580 passed, 1 skipped, three
> consecutive runs. Stage contracts: `tests/gui/test_molecule_stage.py`.

Date: 2026-07-20
Status: accepted exact-source PyInstaller candidate (ad-hoc internal alpha)
Source: `bc02f002550917b98d08aeec504fcc0e7723446c`
(branch `desktop-modern-experience` on `Hongjiseung-ROK/chemsmart`)
Run: [`29721549676`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29721549676)
— completed green in 9m40s on macOS 14 arm64, Python 3.11.9.

The packaging scope was explicitly reopened by the user on 2026-07-20
("p8을 최종 dmg build까지 진행하라"); the previous freeze no longer applies
to this candidate.

## What this artifact contains

The P8 modern experience line on top of the accepted P7R lifecycle
foundation:

- `dfed40f2` design tokens, hash-pinned Lucide icons, feedback primitives;
- `39d44a03` tokenized theme (serif retired), 84 px icon activity rail,
  ⌘⇧P command palette, 1280×800 default window;
- `bc02f002` width-bounded Job builder (860 px) and Chat (920 px) canvases.

## Workflow evidence (from the run's release receipt, `status: passed`)

- App: `ChemSmart.app`, 812,249,217 bytes; inventory 10,661 files, 2,100
  directories, 1,960 relative symlinks, zero broken/absolute/escaping;
  inventory SHA-256
  `2805752cb4ad6077bd681313916518589bb8d768bc37795843022ceb2e4c5359`.
- DMG: `ChemSmart-2.0.1-macos14-arm64-internal-alpha.dmg`,
  338,514,096 bytes; SHA-256
  `2dc092227852b15027ee2054fc26f103ac04662efa88c0d6eb19c57ac92e9c4f`.
- SBOM: 111 shipped components; runtime lock receipts recorded.
- Mounted verification inside CI: `hdiutil verify` rc 0, strict codesign
  rc 0, Applications link present, README matched, mounted inventory equal
  to the built app, Gatekeeper rejection rc 3 (expected for ad-hoc).
- Source-preservation and bundle gates ran on the exact pushed commit,
  including the committed P8 design/palette/rail/canvas test suites.

## Independent local verification (this machine, this session)

- `shasum -a 256 -c SHA256SUMS.txt`: all four distributed files OK.
- Local DMG SHA-256 matches the receipt (`2dc09222…c92e9c4f`).
- `hdiutil verify`: checksum VALID; read-only mount and clean detach.
- `codesign --verify --deep --strict ChemSmart.app`: OK.
- New design assets ship: all 26 pinned Lucide SVGs plus their ISC/MIT
  `LICENSE.txt` present under
  `Contents/Resources/chemsmart/gui/assets/icons/lucide/`.
- Delivered to `~/Desktop/ChemSmart-2.0.1-macos14-arm64-internal-alpha.dmg`
  with `SHA256SUMS.txt`.

## Boundaries and non-claims

- Ad-hoc signed internal alpha: Gatekeeper double-click is expected to be
  refused; install via right-click → Open per the bundled README.
  Developer ID, hardened runtime, notarization, and stapling remain open.
- Named clean-lab-Mac product acceptance and the full Computer Use
  scenario matrix are human/hardware steps not performed here.
- The deep P8.3–P8.5 gold slices (typed Chat cells, builder recomposition,
  Database/Analysis rework) remain open; this artifact ships the scoped
  canvas slice recorded in `p8_3_to_p8_6_canvas_and_polish.md`.
- The branch `agent-codebase-simplification` on the fork holds an unrelated
  agent-runtime line; the desktop line now lives on
  `desktop-modern-experience` to avoid clobbering it.
