# P8.3–P8.6 canvas adoption and polish receipt (scoped slice)

Date: 2026-07-20
Status: source gates green; scoped subset of the master-plan phases
Commits: `bc02f002` (canvas slice) on top of `39d44a03` (shell), `dfed40f2`
(primitives)

## What this slice is — and is not

The user directed the modernization to reach a final DMG in this pass. The
P8.3–P8.6 work here is therefore the **highest-visual-impact subset** of the
master plan, not the full per-phase gold slices. Implemented:

- Job builder working column width-bounded to 860 px and Chat to 920 px so
  MacBook full-screen layouts keep a scannable measure; leftover canvas
  stays quiet (P8.3/P8.4 canvas geometry).
- All surfaces inherit the P8.2 tokenized stylesheet: activity rail,
  quiet selection tint, sans-unified typography, evidence box styling,
  accent-bordered agent transcript (serif retired).
- Chat's safety disclosure promoted to a named attribute
  (`ChatScreen.disclosure`) with its test updated accordingly.

Explicitly NOT claimed (remains open for full P8.3–P8.5 gold slices):

- typed transcript cell model/delegates for Chat;
- Job builder Source/Chemistry/Method disclosure recomposition and
  TaskStrip adoption inside screens;
- Database model/view virtualization rework and Analysis workflow sidebar;
- Settings as a separate preferences window;
- workspace sidebar and global task drawer.

All chemistry, schema, gate, handoff, database, and analysis behavior is
unchanged; no preservation contract was relaxed.

## P8.6-scope evidence (measured this session)

- Complete GUI suite: `576 passed, 1 skipped in 98.29s`.
- Warm-navigation p95 with the new shell: **6.393 ms** (budget < 150 ms;
  pre-modernization measurement on this machine: 5.898 ms — within noise of
  the P8.0 receipt's 6.158 ms).
- Horizontal-overflow scan at 720×520, 900×600, 1040×680, and 1440×900
  across all four surfaces: zero visible horizontal scrollbars.
- 100 mixed navigation + light/dark stylesheet cycles: no failure, correct
  final surface.
- Full-screen (1440×860) light and dark renders of all four surfaces
  visually reviewed.

## Incident and restoration note

Re-running `experience_baseline` for the measurement above overwrote the
uncommitted P8.0 evidence PNGs/JSON (they share a fixed output directory).
The pre-modernization evidence was regenerated from the exact source commit
`151f6857` in a temporary worktree on the same machine and restored in
place. The P8.0 receipt's determinism claim (fresh-process hash
reproduction) applies to that regeneration path; the incident is recorded
here rather than silently repaired.
