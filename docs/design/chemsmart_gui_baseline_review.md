# ChemSmart GUI Baseline Design Review

Date: 2026-07-18
Framework: PySide6/Qt 6 desktop
Target: macOS-first Zhang Lab scientific productivity app
Review method: source inspection plus offscreen rendering of Job builder, Chat,
and Onboarding at 1040 x 680 using the Codex-global `apple-design` skill.

## Summary

Rating: **Needs work; Critical functional issues**.

The scaffold has a sensible restrained direction: native controls, one accent,
a tool-first sidebar, a clear Dry run action, and an explicit AI-error notice.
It is not yet a valid product shell. The default Job builder represents the CLI
incorrectly, three enabled navigation destinations import missing modules, Chat
is a placeholder, and onboarding blocks non-AI use while persisting a key before
connection validation.

This review is a baseline, not a request to redesign the application from
scratch. Preserve the useful shell and correct it under
`chemsmart_native_desktop_master_plan.md`.

Observed runtime evidence:

```text
builder_default: database / assemble
builder_argv: chemsmart run database assemble --index : --output database.db
database navigation: ModuleNotFoundError (database_browser)
analysis navigation: ModuleNotFoundError (analysis)
settings navigation: ModuleNotFoundError (settings)
```

## Critical issues

### 1. Enabled navigation leads to missing screens

- **What:** Database, Analysis, and Settings appear as normal enabled navigation
  items, but their screen modules do not exist. Selecting them raises an import
  error rather than showing a recoverable state.
- **Why:** Design Guideline — Accessibility and Layout: actions must be intuitive,
  perceivable, and consistent; visible controls need a reliable result and clear
  recovery path.
- **Fix:** Until each screen exists, either provide an intentional “Coming in this
  build” placeholder with no destructive state change or disable the entry with
  an accessible explanation. Before internal alpha, every enabled destination
  needs a Qt navigation/error-recovery test.

### 2. The Job builder does not represent ChemSmart jobs

- **What:** Program defaults to `database`, not Gaussian/ORCA. The form reads only
  leaf options, omitting inherited `run` and program fields such as molecule
  source, project, charge, multiplicity, and method. The rendered database command
  visibly contains incomplete/default artifacts.
- **Why:** Design Guideline — Entering Data: request clear, necessary data, prefer
  choices, validate dynamically, and keep the primary action unavailable until
  required inputs are valid. A chemically incomplete form can produce plausible
  but wrong output.
- **Fix:** Restrict Job builder to Gaussian/ORCA, merge
  `run -> program -> leaf` schemas, bind typed widgets and validators, and render
  through a tested `JobDraft`. Database and Analysis belong to their own screens.

### 3. Provider onboarding is both blocking and prematurely persistent

- **What:** App launch is gated on an agent config even though Job builder can be
  useful without AI. “Test connection” writes the key before pinging, and Save
  accepts without a successful test. The current YAML secret file is mode 0644.
- **Why:** Design Guideline — Onboarding: onboarding should be fast and optional,
  and nonessential setup should be postponed. Design Guideline — Generative AI:
  the app should work when AI is unavailable when a non-AI path exists, and
  server-based processing requires clear privacy disclosure and user control.
- **Fix:** Launch into non-AI Job builder. Configure Chat contextually or from
  Settings. Ping an in-memory provider draft, persist only after success or an
  explicit override, and store the key in macOS Keychain with a 0600 legacy
  fallback/migration.

### 4. Muted small text failed minimum contrast

- **What:** The original `#888780` muted token rendered 10–11 px labels at
  3.334:1 on the main light surface and 3.134:1 on the sidebar surface, below
  the 4.5:1 requirement for small text. The dark token also fell below 4.5:1
  on elevated surfaces.
- **Why:** Design Guideline — Accessibility and Color: small text needs at least
  4.5:1 contrast, and color choices must work in light, dark, and increased
  contrast contexts.
- **P0 correction:** Light muted text is now `#686761` and dark muted text is
  `#9c9b94`; an executable contrast test covers both primary surfaces. P2/P6
  must still replace fixed tokens with semantic system palette behavior and
  validate increased contrast.

## High-priority improvements

### 5. Accessibility semantics are absent

- **What:** Labels are visual only; there are no explicit accessible names,
  descriptions, buddies, tested focus order, screen-reader announcements, or
  keyboard-only acceptance tests.
- **Why:** Design Guideline — Accessibility: desktop apps need keyboard access,
  appropriately labelled controls, more than color-only status, and controls
  sized for reliable clicking.
- **Fix:** Add Qt accessibility metadata and label buddies, define focus order,
  announce validation/loading/results, preserve textual status alongside color,
  and test Full Keyboard Access on every workflow.

### 6. Theme bypasses system palette and scalable typography

- **What:** QSS hard-codes hex colors, font family strings, and pixel text sizes.
  System accent, increased contrast, live appearance changes, and user font
  preferences are not represented.
- **Why:** Design Guideline — Color and Typography: prefer system semantic colors,
  verify light/dark/increased contrast, use legible system styles, and preserve
  hierarchy under text-size changes.
- **Fix:** Build tokens from `QPalette` and `QFontDatabase`, keep one optional
  ChemSmart accent, use point/system font metrics, and reapply on system palette
  change. Add light/dark/high-contrast screenshot gates.

### 7. Layout is fixed rather than adaptive

- **What:** Sidebar width is fixed, Job builder uses a rigid two-column ratio,
  important actions sit near the lower edge, and the blank Structure area consumes
  substantial space without an empty-state explanation.
- **Why:** Design Guideline — Layout: desktop windows must resize gracefully,
  group controls/content clearly, use progressive disclosure, and avoid critical
  controls at the bottom edge.
- **Fix:** Use splitters and minimum content widths, collapse the inspector first,
  make forms scrollable, keep actions near the active form/preview, and give the
  Structure panel a useful empty state with file/drop actions.

### 8. Standard macOS menu and settings conventions are missing

- **What:** Settings appears at the bottom of the sidebar; there is no application
  menu, `Command-,`, standard File/Edit/View/Window/Help behavior, or documented
  focus shortcuts.
- **Why:** Design Guideline — Settings and Keyboards: desktop Settings belongs in
  the App menu, opens with `Command-,`, and standard shortcuts should not be
  repurposed.
- **Fix:** Add native Qt actions/menus, open a separate Settings dialog/window,
  preserve standard copy/paste/undo/redo/open/save/close/help behavior, and add
  only a small set of frequent ChemSmart-specific shortcuts.

### 9. Chat has disclosure but no interaction states

- **What:** The AI-error notice is good, but the transcript has no assistant/user
  structure, loading, streaming, cancellation, retry, clarification, tool receipt,
  approval, or provider-error states.
- **Why:** Design Guideline — Generative AI: identify AI content, set capability
  expectations, keep people in control, handle latency, help improve blocked
  requests, and confirm consequential actions.
- **Fix:** Project the unified agent event stream into typed transcript cells;
  provide Stop, Retry, Edit in Job builder, and receipt details. Keep risky tools
  unavailable in v1 and make the non-AI workflow continuously usable.

## Positive notes

- Tool-first sidebar grouping matches a desktop productivity app.
- One blue accent and one primary action per surface are restrained and clear.
- Job builder distinguishes command/output surfaces with monospace styling.
- P0 now disables Dry run until a checkout-verified fake launcher exists; the
  AI-error notice also sets a useful safety expectation.
- Screens are imported lazily, which is appropriate for the heavy scientific
  dependency set.
- The shared Structure viewer concept is correct; it should become a contextual
  inspector rather than separate rendering logic per screen.

## Platform-specific notes

- Preserve native window chrome and use the macOS menu bar through Qt actions.
- Test Apple Silicon first, but do not infer Intel or older macOS compatibility
  from the current arm64/macOS 26 developer machine.
- Respect system appearance/accent/accessibility preferences instead of imitating
  another app's exact chrome. “Codex/Claude-level” should mean information
  hierarchy, interaction quality, safety, and polish, not visual cloning.
- Treat an unnotarized build as an internal alpha with explicit instructions, not
  as the final lab release.

## Implementation order

1. Fix functional contracts and dead navigation.
2. Make onboarding optional and secure secrets.
3. Add system palette/font/accessibility/menu foundations.
4. Complete one Gaussian/ORCA fake-run vertical slice.
5. Wire unified Chat and evidence.
6. Add Database/Analysis, then run a fresh full design review.
