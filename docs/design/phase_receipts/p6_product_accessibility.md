# P6 Product and Accessibility Receipt

Date: 2026-07-19

Function commit: `83eb1707` (`feat(gui): complete product accessibility`)

Independent review: GREEN, Critical 0 / High 0 / Medium 0

## Outcome

P6 completes the native desktop product and accessibility contract without
changing ChemSmart's chemistry defaults, CLI/TUI behavior, or fake-run safety
boundary. The supported Job builder, Chat, Database, Analysis, Settings, and
structure-viewer surfaces now have responsive minimum-window layouts,
keyboard-order contracts, screen-reader labels, visible focus indicators,
light/dark/increased-contrast themes, help and recovery writing, and optional
local PyMOL rendering. The vendored offline 3Dmol viewer remains the default.

## Responsive and accessible product shell

- The complete nine-surface matrix was rendered at 720 x 520, 1040 x 680, and
  1440 x 900 in light, dark, and increased-contrast appearances: 81 rendered
  states in total.
- Every enabled focusable control on all nine surfaces has an accessible name,
  visible label, placeholder, or label buddy. Forward and reverse keyboard
  traversal are exercised for every screen and tab.
- The sidebar is a named primary-navigation region and is keyboard activatable.
- Focus styling covers inputs, spin boxes, item views, buttons, checkboxes, and
  tabs. A pixel-level test proves the primary action retains a visible focus
  border after its higher-specificity primary-button style is applied.
- Database and Analysis controls use independent vertical scroll regions while
  their scientific result tables remain pinned. At 18 pt and 720 x 520, the
  Database Build/Export and three Analysis control surfaces all have content
  width equal to their 502 px viewport and zero horizontal overflow.
- Thermochemistry compound settings and Grouper rule/threshold/count settings
  use independent semantic rows at large text sizes. Result tables retain their
  own horizontal scrolling where their scientific columns require it.
- Job builder reconstructs its explicit Tab chain after every dynamic schema,
  molecule-source, and Advanced-state change. Required chemistry fields precede
  command preview and output; all 25 tested advanced fields sit between the
  Advanced toggle and preview.
- Settings is vertically scrollable. Provider actions, workspace selection, and
  optional visualization selection remain reachable at the supported minimum
  size and at 18 pt with long recovery text.
- Help explains the safe Job builder workflow, optional Chat boundary,
  cancellation/retry/verified receipts, offline 3D, optional PyMOL, and the
  continuing prohibition on desktop real compute and HPC submission.

## Optional PyMOL boundary

The desktop may discover an exact `pymol` executable on PATH or persist one
explicit user-selected executable in `QSettings("ZhangLab", "ChemSmart")`.
Finder PATH failure has a visible recovery path through `Choose PyMOL…` and
`Use PATH`; a stale saved path falls back safely without hiding interactive 3D.

Rendering reuses `PyMOLVisualizationJobRunner` and the established Zhang Lab
style through a desktop adapter. It starts one exact executable without a shell,
uses an allowlisted environment that excludes provider credentials, creates an
isolated temporary job directory, and owns a separate process group. Cancel
sends TERM and then KILL if required. The controller imposes a 120-second
timeout. Only a regular, non-symlink PNG no larger than 64 MiB with a valid PNG
signature and successful Qt decode is accepted. The receipt includes SHA-256.

The viewer exposes honest indeterminate progress, Cancel, Retry, verified
success, and absent/error states. Starting a render clears any previous molecule
image. Failure, invalid Qt decode, source clearing, and service reconfiguration
also clear stale output. Reconfiguration during an active render requests
cancellation and asks the user to retry after the prior worker drains; it does
not synchronously wait on a Python Qt thread from the GUI thread.

## Review-driven corrections and self-improvement

The first independent review was RED and prevented a premature phase commit.
The following reproducible defects were converted into regression gates and
fixed:

- an always-failing `Path` call into the domain `quote_path` helper;
- a primary-button style that overrode the general focus indicator;
- no Finder-safe explicit PyMOL executable setting or restart persistence;
- stale PyMOL images remaining visible during a new request or decode failure;
- incomplete Help and accessibility smoke coverage;
- 18 pt Settings actions clipping at the minimum window;
- synchronous renderer replacement competing for the Python GIL while a Qt
  worker drained;
- hidden horizontal overflow in Database Build/Export and all three Analysis
  control panes at 18 pt and 720 x 520;
- Job builder's dynamically-created chemistry fields appearing after command
  preview and generated output in the real Tab order.

The final reviewer independently measured these five large-text surfaces:

| Surface | viewport / content / minimum hint | horizontal overflow |
|---|---:|---:|
| Database Build | 502 / 502 / 366 px | 0 px |
| Database Export | 502 / 502 / 491 px | 0 px |
| Thermochemistry | 502 / 502 / 451 px | 0 px |
| Grouper | 502 / 502 / 444 px | 0 px |
| DIAS / WBI | 502 / 502 / 445 px | 0 px |

All 68 visible buttons, spin boxes, combo boxes, and line edits remained inside
their content bounds. File, PubChem, Database, advanced-field, and reverse Job
builder focus sequences passed. The final finding count is Critical 0, High 0,
Medium 0.

## Validation receipts

- Complete GUI suite after the final corrections: `358 passed, 1 skipped in
  84.22s`.
- Complete Agent preservation suite: `1110 passed, 6 warnings in 50.20s`.
- Grouper, Thermochemistry, and structured Analysis service suites: `143 passed,
  7 skipped, 45 warnings in 22.52s`.
- Focused accessibility suite after final formatting: `25 passed in 1.71s`.
- Final review's expanded GUI/domain slice: `184 passed, 1 skipped`; its new
  large-text and focus-order gates: `11 passed`.
- Five repetitions of the minimum-layout, accessibility, and PyMOL-focused
  stress slice completed 140 checks before the final reviewer corrections; the
  final deterministic gates supersede the two missing cases the repetition did
  not originally cover.
- Changed-file Black, isort, Ruff, Python compilation, and `git diff --check`
  are GREEN.

The actual PyInstaller `.app` from authorized macOS run `29673363478` rendered a
nonblank water molecule through bundled QtWebEngine and vendored 3Dmol. Its
candidate archive SHA-256 is
`d7eaeeda8d0b83fcfb76e61ea21ee43524126ba879a66f7632311da652662a1b`.
This is real packaged-render evidence, not the temporary PyMOL state mock used
to review progress/error/success writing.

## Honest limitations and P7 handoff

- PyMOL is not installed on this development Mac. The exact subprocess and real
  ChemSmart PyMOL job-runner path were exercised with an executable test double,
  including a path containing spaces; a real PyMOL binary and real rendered
  chemistry image remain a P7 named-machine gate.
- The current P6 product commit has not yet been built into a Finder-launched
  distributable. The successful PyInstaller receipt proves the P1 packaging
  candidate and bundled 3Dmol boundary, not the final P6 tree.
- Developer ID signing, notarization, DMG installation, clean-machine use,
  long-path/unicode/restart acceptance, and SBOM/checksum release documentation
  remain P7.
- No provider credential, real Gaussian/ORCA/xTB calculation, scheduler, SSH, or
  HPC submission was exercised or enabled in P6.
