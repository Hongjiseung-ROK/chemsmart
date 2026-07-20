# P8.1 design system and feedback primitives receipt

Date: 2026-07-20
Status: implementation and source gates green; independent review recorded below
Planned commit: `feat(ui): add modern design and feedback primitives`

## Scope

P8.1 creates the reusable visual and interaction vocabulary the later P8
surface phases adopt. It adds new modules only: no production screen, theme
stylesheet, chemistry, agent, database, analysis, packaging, or CLI/TUI file
changed. The serif "agent voice" retirement is a P8.2 change (it lives in
`theme.py`, which this phase does not touch); the user decision to retire it
is recorded in the approved plan.

## New modules

- `chemsmart/gui/design/tokens.py` — semantic role tokens (surfaces, text,
  accent, five state pairs, focus/selection/code/chart/viewport) in light,
  dark, and increased-contrast variants, plus the WCAG 2.1 contrast math the
  palettes are tuned against.
- `chemsmart/gui/design/typography.py` — sans-unified type scale derived from
  the live system size, spacing steps, control heights; monospace reserved for
  facts. Font resolution delegates to `theme.py` so old and new layers agree.
- `chemsmart/gui/design/icons.py` + `chemsmart/gui/assets/icons/lucide/` —
  26 Lucide-derived SVGs vendored offline with ISC/MIT notices (ADR 0002),
  SHA-256-pinned allowlist, fail-closed loader, `currentColor` token
  recoloring, DPR-aware pixmaps.
- `chemsmart/gui/design/motion.py` — 120–180 ms single easing family and the
  reduced-motion policy.
- `chemsmart/gui/widgets/_primitive_base.py` — `TokenConsumer` (in-place
  restyle on appearance change) and `PaintedSurface` (deterministic rounded
  background painting).
- `chemsmart/gui/widgets/actions.py` — Primary/Secondary/Destructive action
  buttons, `SegmentedModeControl` (disabled modes carry a visible reason),
  `LabeledToggle` (state written as text).
- `chemsmart/gui/widgets/status.py` — `StatusBadge`, `InlineMessage`
  (icon + label + accessible description; never color-only).
- `chemsmart/gui/widgets/feedback.py` — `TaskStrip` projecting the
  idle/validating/ready/running/awaiting_user/cancelling/succeeded/failed/
  cancelled/timed_out vocabulary with honest progress (determinate only with
  a real total), elapsed time, cooperative Cancel, terminal Retry; and
  `DecisionDialog`, the contrast-tested replacement for the native permission
  `QMessageBox` whose dark-mode text was invisible in the P8.0 baseline —
  safe choice holds default focus and Escape can never grant.
- `chemsmart/gui/widgets/fields.py` — `FieldMessage`, `ScientificValue`,
  `CommandSurface` (read-only exact-command evidence with exact copy).
- `chemsmart/gui/widgets/receipts.py` — `DisclosureSection` (a collapsed
  section can never hide a named blocker) and `ReceiptCard`.
- `chemsmart/gui/widgets/empty_state.py` — `EmptyState` with one primary and
  at most one secondary recovery action.
- `chemsmart/gui/diagnostics/component_gallery.py` — offscreen gallery
  rendering every primitive in light/dark/light-hc/dark-hc with SHA-256
  receipts; presentation fixture only, no task executed.

## Defects found and fixed inside this phase

1. Stylesheet backgrounds on `QWidget` subclasses were dropped — first
   deterministically (missing `WA_StyledBackground`, every pill/banner/panel
   rendered on the default window fill), then intermittently under widget
   churn even with the flag (observed dominant `#efefef` instead of the
   `#e2f2e5` tint in roughly two of three full-suite runs). Surface-owning
   primitives now paint their fill/outline directly (`PaintedSurface`);
   a dominant-color pixel regression guards the contract.
2. `StatusBadge` stretched to the full row width, destroying the pill shape;
   it now hugs its content (Maximum horizontal size policy, asserted).
3. The initial dark-high-contrast palette contained an invalid hex literal;
   the token tests fail on any non-`#rrggbb` value now because every token
   participates in measured contrast assertions.

## Evidence (measured this session)

- Focused design suite (tokens, icons, primitives, gallery): `159 passed`,
  five consecutive runs after the PaintedSurface fix (previously flaked
  ~2 in 3).
- Contrast matrix: text roles ≥ 4.5:1 on all four reading surfaces, state
  text ≥ 4.5:1 on its tint, state icons and focus ring ≥ 3:1 on plain
  surfaces, in all four palettes; increased-contrast variants are asserted
  never weaker than the defaults.
- Icon gates: manifest ↔ on-disk parity, tamper (hash-mismatch) fail-closed,
  unknown-name fail-closed, license notices present, nonblank render.
- Stress: 1,000 mixed task-state/badge/disclosure cycles across all four
  palettes with final-state assertions.
- Complete GUI suite: `566 passed, 1 skipped in 97.76s` (the accepted
  optional-dependency skip).
- Ruff, black, isort, compileall, `git diff --check`: green.
- Gallery evidence: 4 nonblank PNGs + `component_gallery.json` SHA-256
  receipt under `docs/design/evidence/p8_1/`; light and dark screenshots
  visually reviewed (pill tints, banner outline, task cards, receipt panel
  all render; dark PNG pixel-verified `#2a2a29` controls on `#1e1e1d`
  canvas).

## Boundaries and non-claims

- No production screen adopts the primitives yet; adoption starts at P8.2/8.3.
- `theme.py`, `app.py`, and all screens are unchanged in this phase.
- No packaging run, provider request, real calculation, or HPC action was
  performed; the frozen-build boundary is untouched.
- Offscreen rendering is layout/state evidence, not final macOS visual
  acceptance.

## Independent review

An independent read-only reviewer (senior Qt/accessibility focus) read every
new source/test file, ran the focused suite four times (no flakes), and
empirically verified the Qt-behavior claims. Initial verdict: Critical 0 /
High 1 / Medium 0 / Low 3. All four findings were fixed and regression-tested
before the phase commit:

- **H1** — The primary button's focus ring used `focus_ring`, which equals
  `accent` in all four palettes, so the ring was invisible (1:1) on the
  button's own accent fill — a WCAG 2.4.7 failure on the most consequential
  control, including DecisionDialog's primary choice. Fixed: the ring now
  uses `accent_on_fill` (contrast-verified ≥ 4.5:1 over accent). Regression:
  token-level contrast assertion for every palette plus a pixel test that a
  genuinely-unfocused vs focused primary render differ (the first version of
  that test was itself wrong — a lone top-level button takes focus on window
  activation, so both snapshots were focused; the test now clears focus and
  asserts focus state explicitly).
- **L2** — Qt QSS silently ignores `:first-child`/`:last-child`, so the
  segmented control's outer corners never rounded. Fixed with explicit
  `SegmentFirst`/`SegmentMiddle`/`SegmentLast`/`SegmentOnly` object-name
  selectors; regression asserts the unsupported selectors are gone and the
  names are assigned, including the single-segment case.
- **L3** — `reduce_motion()` probed a `QStyleHints.animationDuration`
  attribute that does not exist, so reduced motion could never be detected.
  Fixed: explicit app-level override plus a cached macOS
  `defaults read com.apple.universalaccess reduceMotion` probe that fails
  toward motion; covered by four new unit tests
  (`tests/gui/test_design_motion.py`).
- **L4** — The copy-confirmation `QTimer.singleShot` lambda could fire on a
  deleted button (e.g. `ReceiptCard.clear_facts()` within 1.2 s of a copy).
  Fixed with the receiver-context overload, which cancels the pending reset
  when the button is destroyed.

Post-fix evidence: focused design suite `165 passed`, five consecutive runs;
complete GUI suite `572 passed, 1 skipped in 90.37s`; ruff/black/compileall/
`git diff --check` green; gallery evidence regenerated. Post-fix verdict:
Critical 0 / High 0.
