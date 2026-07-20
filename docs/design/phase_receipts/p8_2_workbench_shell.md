# P8.2 workbench shell receipt

Date: 2026-07-20
Status: source gates green
Commit: `feat(ui): introduce evidence-first workbench shell`

## Scope

The shell adopts the P8 design tokens and the workbench navigation model
while preserving every existing MainWindow contract (navigation keys,
`_nav_buttons`, menu roles, two-phase close, runtime projection, workspace
refresh). The user-approved deviations from the original 2026-07-18 plan are
applied here: the serif agent voice is retired and the ⌘⇧P command palette is
included.

## Changes

- `chemsmart/gui/theme.py` — now derives its `Palette` from
  `chemsmart.gui.design.tokens` (single color source; light accent moved
  `#185fa5` → `#0f62c0`, dark accent `#378add` → `#5ba3f0`). The serif
  `AgentText` rule is removed — agent text renders in the system sans with a
  quiet accent border; `serif_font_family()` remains only as a deprecated
  compatibility shim. Rail (`QToolButton#NavItem`), evidence summary,
  splitter handle, and progress styling added. System-palette
  (increased-contrast) derivation is preserved.
- `chemsmart/gui/app.py` — the text sidebar becomes an 84 px activity rail:
  icon-over-label `QToolButton`s using the hash-pinned icon set
  (flask-conical / message-square / database / chart-column), recolored on
  appearance change and selection, with a fail-open fallback to the text
  label if an icon asset is rejected. Default window size 1280×800.
  `View → Command Palette…` (⌘⇧P) and `menu_actions["command_palette"]`
  added.
- `chemsmart/gui/workbench/command_palette.py` — searchable palette over
  contract-authorized actions only: navigation, Settings, inspector toggle,
  Help, Support bundle, About, and Run Safe Preview only while its menu
  action is enabled. Disabled actions are excluded, so the palette can never
  offer what the shell refuses. Keyboard: type-ahead, Up/Down, Enter, Esc.

## Evidence (measured this session)

- Shell/accessibility/theme focused tests: `64 passed`.
- New palette/rail contracts (`tests/gui/test_command_palette.py`):
  `4 passed` — enabled-state gating, filter+run navigation, menu/shortcut
  wiring, rail icons + accessible names.
- Complete GUI suite: `576 passed, 1 skipped in 99.29s`.
- Light and dark 1440×860 shell renders visually reviewed (rail selection
  tint, panel separation, status strip, inspector evidence box).
- Ruff green; `test_theme.py` updated to reference `theme.LIGHT.accent`
  instead of a hard-coded hex so the token move is contract-checked.

## Deferred inside P8.2

- Settings remains a navigable screen (its dedicated preferences window is
  deferred; ⌘, continues to work).
- Contextual workspace sidebar and the global task drawer are deferred to
  the screen-adoption phases; the status strip continues to carry task
  state.
- Job builder form width/geometry refinement is P8.3 (the full-screen render
  shows over-wide fields — a canvas concern, not a shell concern).
