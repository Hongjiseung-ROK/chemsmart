# P4 receipt — canonical unified-agent Chat

Date: 2026-07-19
Status: GREEN; automated gates and final read-only reviewer accepted
Baseline commit: `c79b6df8`
Branch distance before the phase commit: 4 ahead, 6 behind

## Outcome

P4 replaces the visual Chat placeholder with a native surface over the same
unified agent loop, session state, decision log, and runtime events used by the
maintained agent implementation. It does not add a real-compute, scheduler,
remote-diagnostics, or project-write boundary.

- `AgentSession.run_loop()` now accepts optional decision streaming and
  cooperative cancellation hooks. Both default to `None`, so existing CLI/TUI
  callers retain their prior behavior.
- A decision listener runs only after the canonical JSONL entry is written.
  Subscriber exceptions are contained and cannot change the durable agent
  outcome.
- The desktop registry is built from only read-only synthesis and project-YAML
  tools. `execute_chemsmart_command`, `repair_command`, `run_local`,
  `submit_hpc`, project-write, update, and wizard-write tools are absent and
  also fail closed at the approval boundary. The maintained CLI/TUI repair path
  remains unchanged.
- Chat constructs `AgentSession(stage_prompt="unified_agent.md",
  runtime_v2="active")`, supplies an explicit read-only `PermissionPolicy`, and
  presents bounded projections of canonical decisions. It creates no GUI-only
  transcript/event receipt store.
- Exact `chemsmart run ...` input uses a local deterministic pseudo-provider
  only to create the same canonical session receipts after real intent and
  semantic gates run. It never calls the configured AI provider and remains
  isolated from the next conversational session.

## Typed acceptance and handoff

An agent command becomes a `JobDraft` only when every independent condition is
true:

1. the synthesis payload has `ok: true`;
2. its status is exactly `ready`;
3. the intent gate accepts it;
4. the semantic gate accepts it; and
5. the current live Click schema parses the command into typed state.

The intent and semantic receipts remain separate in the result DTO and UI. A
not-ready, infeasible, rejected, or unparseable command is visible for diagnosis
but cannot be opened as an accepted draft. Accepted drafts carry
`AGENT_RECEIPT` provenance with the canonical session and tool receipt IDs.

Chat-to-Builder transfer passes the `JobDraft` object, not reverse-parsed display
text. Builder fields are recreated from the selected live-schema leaf before
values are applied, preventing stale prior values. A received agent draft must
complete a new P3 isolated safe preview before Builder-to-Chat handoff is
enabled. Conversely, Builder can attach a draft to Chat only after an accepted
safe-preview receipt, and any chemistry edit revokes that handoff immediately.
The provider context is a JSON argv list rendered from typed state; it is not GUI
shell state.

## Session, cancellation, and recovery evidence

- One in-memory provider and registry are reused for the selected AI session;
  a new session, provider change, deterministic command, or explicit resumed
  session establishes the appropriate separate boundary.
- Recent-session choices are bounded to ten current-schema session states. The
  selector does not scan or display full decision-log payloads. Explicit resume
  continues the canonical conversation and increments its turn index.
- Cancellation is checked before a provider call, after a provider response,
  and between queued tool requests. A synchronous provider/tool boundary is not
  falsely claimed to be interrupted; controls remain disabled while it drains,
  and a response completed after cancellation is discarded from the Chat UI.
  A tool that factually finished at that boundary remains `ok` in the durable
  log, while the terminal session summary, metadata, runtime, and GUI all agree
  that the turn ended `blocked` with reason `cancelled`.
- A 25-turn stress run remained one canonical session and created one session
  directory. Deterministic and later AI turns produced different session IDs.
- Missing configuration and provider construction failures expose only the
  exception class and a recovery action. They do not change or disable Job
  Builder. Raw provider turns are not enabled, and public stream projections
  never show raw tool/provider payloads.
- Approval UI is retained for future read-only tools, with explicit deny as the
  default, a bounded wait, cancellation/timeout denial, and recursive sensitive
  field redaction. Desktop execution/submission tools remain blocked regardless
  of a UI choice.
- Cancellation refreshes and selects the sealed canonical session. New session
  clears retry, ask-user, request, transcript, gate, command, and attached-draft
  presentation state. Resuming a different session likewise detaches the prior
  screen state before continuing the selected durable conversation, so one
  session's chemistry cannot be injected into another.
- Session separation starts synchronously before an AI/direct/provider boundary
  is dispatched, so a fast first event cannot briefly inherit another session's
  presentation. The canonical session ID then replaces that provisional UI
  boundary after the worker creates it.
- A cancellation that arrives from the durable decision listener immediately
  after an assistant turn is recorded is rechecked before success finalization.
  The late answer remains audit evidence but is removed from resumable provider
  history and cannot become a public successful result.
- Command semantics reject any `run`/`sub` route that does not resolve to a
  supported computational program before an evaluator or subprocess boundary.
  Direct desktop commands also pass the live typed `JobDraft` parser. Projection
  considers only the newest relevant tool outcome, so a failed repair cannot
  resurrect an older accepted draft.

## Visual and interaction evidence

Chat exposes provider/model setup, recent-session resume and New session,
read-only transcript, distinct intent/semantic gate labels, gated command
preview, typed Builder handoff, Retry, Send, Cancel, honest indeterminate
progress, ask-user continuation, and an AI privacy/safety disclosure. Gate rule
IDs and notices remain available through tooltips and accessibility descriptions
without overwhelming the compact visible state.

Fresh offscreen inspection retained all critical controls:

- 720 x 520 window: Chat body 556 x 478, transcript 524 x 80, both gates and
  composer visible, composer bottom 404/478;
- 1040 x 680 window: Chat body 612 x 638, transcript 580 x 253, composer bottom
  579/638;
- 1440 x 900 window: Chat body 1012 x 858, transcript 980 x 488, composer bottom
  799/858.

Computer Use remains an acceptance requirement. The Mac was locked during the
earlier P2/P3 attempts, so offscreen inspection is not promoted as real
keyboard/pointer acceptance. Real interaction is deferred to the final installed
app acceptance loop.

## Baseline repairs and retired failures

- The first complete GUI run had one macOS offscreen QtWebEngine renderer
  process exit (`-11`, lost GPU/Skia context) after the rest of the suite. The
  exact isolated 3Dmol resource test immediately passed, and the next complete
  GUI run passed. This is retained as a transient runner receipt, not hidden as
  a product pass or counted as a reproducible P4 defect.
- The first complete Agent run exposed only `slash_quit.svg`. Ten fresh captures
  produced one identical hash and matched the previously reviewed stable
  snapshot at `70075d64`; the checked-in snapshot had been overwritten at
  `cada8c50` with the pre-Markdown-reflow frame. The supported snapshot updater
  restored the stable fully reflowed frame. No visible text or TUI source changed,
  and the complete Agent suite then passed.
- Making every loop safety limit canonically blocked exposed an older TUI test
  fixture that sent five `harness_jobs` tools while the unified phase allowed
  only `synthesis`. All four attempted tools failed with
  `ToolExposureViolation`, but the old `blocked: false` result made the test call
  that turn successful. The fixture now exercises the allowed
  `synthesize_command` route and still verifies live tool/assistant cells and a
  successful footer. The safety gate was not relaxed to preserve the invalid
  success signal.

## Final validation receipts

- Focused streaming, cancellation, safety-profile, provider, session, typed
  handoff, minimum-window, command-semantic, and corrected TUI live-flow suite:
  `43 passed in 12.41s` in the independent review run.
- Complete Agent preservation suite: `1110 passed, 6 warnings in 51.97s`.
- Complete GUI suite: `211 passed in 85.12s`.
- Changed-Python Ruff, compileall, `git diff --check c79b6df8`, and feature
  contract YAML parsing are green.
- Final read-only reviewer verdict: GREEN, with no remaining Critical or High
  findings. The only Low documentation suggestion, explicitly listing the
  desktop-blocked `repair_command`, is incorporated above.

## Deferred boundaries

- Database assemble/select/extract/show/legacy, Grouper, Thermochemistry, DIAS,
  WBI, and optional PyMOL belong to P5/P6.
- Real OpenAI/Anthropic credential use was not required for P4 evidence; provider
  behavior uses offline deterministic fakes. No key was read or printed.
- Real Gaussian, ORCA, or xTB computation and scheduler submission remain
  unavailable in the desktop. Existing CLI/TUI backends are preserved.
- Finder launch, `.app`/`.dmg`, clean-machine interaction, upgrade/uninstall,
  signing/notarization, support bundle, and final Computer Use scenarios remain
  P7 gates.
