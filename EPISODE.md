# R10 episode Q25 -- no test writes into the developer's real home

- Base SHA: 05d556d75dafdc7a9a5d647734331e767242f9f5 (verified with
  `git rev-parse HEAD` as the first action, 2026-09-25).
- Brief: scratchpad/q25/BRIEF.md, sha256 d88a73a603d9e65d...
- Researcher model: claude-opus-5-5[1m]. No live goal, no cluster, no
  provider turn is planned: this episode is provider-free.

## The question (as currently understood)

1. Does a full-suite run on this Mac write into the developer's real
   home (`~/.chemsmart` first, the rest of `$HOME` too)? Shown by
   measurement around a run, not by reading code.
2. Where does the host bind a user path at import (a module constant, a
   class attribute, a default argument), so that a HOME fence a test sets
   later comes too late? Each binding is resolved at use or stated
   harmless.
3. With every binding resolved at use and HOME / `Path.home` fenced for
   every test, does the same measurement show nothing changed under the
   real home, with the full-suite failing set equal to the round baseline
   (23 known environmental failures)?

## State of the store before anything ran (2026-09-25, read-only)

`~/.chemsmart/agent/qualification.jsonl`: 740 rows, mtime
2026-09-25T07:47:46 local. 655 rows are a test's goal `g`
(`program_jobtype orca:cpu:sp`, node `sp-initial`, run
`goals/g/runs/cycle-1`), first 2026-09-15T12:48:43Z, last
2026-09-24T22:47:46Z (minutes before this episode began), 655 distinct
evidence tuples. 85 rows name archived goals (replays). Q24 counted 733
rows / 648 of `g`: seven more `g` rows arrived between Q24's census and
this one. The leak is not only historical: it is being written today.

## Falsifiers (armed before any suite run)

- F1 (premise): a full-suite run on a pristine export of the base with
  the real HOME changes nothing under `~/.chemsmart` and the audit hook
  records no write under the real home from the suite's process: the
  leak is historical; then find which runs wrote the rows and stop.
- F2 (repair incomplete): the same measurement on the repaired tree shows
  a change under `~/.chemsmart`, or the audit hook records a write under
  the real home attributable to the suite.
- F3 (baseline): the repaired tree's full-suite failing set differs from
  the base's measured failing set (and from the round's 23 known
  environmental failures): the fence broke a test that silently read the
  developer's home; each such test is named and repaired inside the
  radius, or the fence is not claimed.
- F4 (census): a user path bound at import that neither resolves at use
  nor is harmless survives the repair (the dynamic census finds a value
  derived from HOME in a module global, class attribute or default).

## Oracle (independent of the code under test)

- O1 filesystem snapshot of the real `~/.chemsmart`: relative path, type,
  size, mtime_ns, inode, mode, symlink target, and sha256 of contents,
  except credential files (`*.env`, names containing key/secret/token/
  credential, symlinks are never followed) whose contents are never read
  -- stat only. Diffed before/after each run.
- O2 CPython audit hook (`sys.addaudithook`, a pytest plugin loaded with
  `-p` from scratch, outside the tree) in the suite's process: every
  write-like event (open for write/append/create/truncate, mkdir, rename/
  replace, remove, rmdir, symlink, link, chmod, utime, truncate, shutil
  copy/move/rmtree, tempfile, sqlite3.connect) whose path lies under the
  real home (from the passwd database, not `$HOME`), attributed to the
  running test node id; every subprocess launch with the HOME it gives
  the child.
- O3 dynamic import census: import every `chemsmart` module in a child
  whose HOME is a unique sentinel directory; any module global, class
  attribute, function default or dataclass default whose value contains
  the sentinel is a user path bound at import. Run from an export under
  /private/tmp so the tree's own `__file__` paths are not under home.

Concurrency control: other episodes run suites on this Mac. A snapshot
change that O2 does not attribute to my process is reported as foreign
(with the concurrent processes seen), never counted for or against.

## Status

- step 0: brief read; base verified; AGENTS, CONDUCT, RSL README, lesson
  config-tests-fence-home and b78f5bec, Q24's EPISODE, capability
  registry, both conftests read; store profiled read-only.
