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

## Instruments validated (red state first)

- v0: two agent test files on a pristine export of 05d556d7 with HOME
  moved (outside the process) to a sentinel directory that the audit also
  watched: 4 write events under the sentinel (mkdir .chemsmart,
  .chemsmart/agent; append agent/qualification.jsonl) from
  test_an_analysis_only_settlement_qualifies_the_cycle_that_ran; the row
  written is exactly the store's shape (goal g, orca:cpu:sp, sp-initial,
  goals/g/runs/cycle-1). Real ~/.chemsmart unchanged. O2 sees a write.

## Measurements (full suite, pristine exports, scratch q25/runs/*)

| run | tree | HOME | failed / passed | real ~/.chemsmart | audit: writes under real home | children given real HOME |
|---|---|---|---|---|---|---|
| E0 | 05d556d7 | real | 23 / 4746 | 1 row appended (ours, line 741) | 2 (one test) | 188 of 188 |
| E1 | 05d556d7 | empty dir, set before python | 90 / 4679 | 1 row appended -- FOREIGN (see below) | 0 | 0 |
| E1t | 05d556d7 | fresh copy of the repo template | 23 / 4746 (same set as E0) | unchanged | 0 | 0 |

- E0 is the leak, measured: the store row is appended at
  2026-09-24T23:03:17.003110Z (evidence hashes dcdbc702..., 4db91c78...,
  8a07a682...), by record_host_qualification <-
  driver._record_goal_qualification <- _write_delivery_settlement inside
  test_an_analysis_only_settlement_qualifies_the_cycle_that_ran. Nothing
  else under ~/.chemsmart changed (the snapshot covers children too). The
  pytest process inspected 18,139 write-mode opens and 22,748 path events.
  F1 does not fire: the leak is live. My own measurement added that one
  row; it stays for the owner (item #21) with the others.
- E1 is the read dependence, measured: 67 tests pass only because this
  Mac's ~/.chemsmart is configured (no server local.yaml, KeyError ORCA /
  GAUSSIAN, "Default file settings does not exist"). The row that appeared
  in the real store during E1 (2026-09-24T23:06:52.875772Z, goal g) is not
  E1's: its audit recorded 0 writes under the real home, and a foreign
  `python -m pytest -q -p no:cacheprovider -rf tests` (pid 4484, started
  about 08:05:18 local, gone by 08:10) was running; the leaking test
  fires ~96 s into a full run (E0), which puts that run's row at 08:06:5x.
  Independent confirmation that other sessions write the store today.
- E1t: the repository's own template (what the config command installs)
  is enough configuration for every one of those 67 tests.

## Census of user paths bound at import (O3, base 05d556d7)

Values holding the sentinel HOME after importing all 282 modules:
capability_registry.HOST_QUALIFICATION_STORE and the defaults of
load_host_qualifications / record_host_qualification /
build_capability_registry; CHEMSMARTUserSettings.USER_CONFIG_DIR; the
module-level user_settings instances of settings/{server, orca, gaussian,
executable, submitters} and jobs/runner (config_dir, yaml and data fixed
at import; server/project lists memoised at first use). None bound to the
real home any other way (pwd, literals). Import-time file events under the
sentinel by chemsmart's own code: 7 reads of usersettings.yaml and the
server glob/scan of live_session's module-level _PYSCF_INTERPRETER (user
configuration read at import; its value holds no home path, so only the
audit sees it). Third-party at import: ASE reads ~/.config/ase/config.ini;
matplotlib creates ~/.matplotlib and writes its font cache when absent.

Resolved at use (commits 0b356517, 365d452f, 6e679fd1); the census on the
repaired tree finds 0 values and 0 chemsmart touches. Already resolved at
use (stated harmless): api_access keys path, provider_config agent.yaml
path, skills overlay root ("~" expanded at use), every path in
cli/config.py, jobs/runner scratch, utils conda candidates. Third-party
residue (not the host's; imported by conftest before any fixture):
matplotlib's config dir and ASE's config file -- no write under the real
home from either in any measured run on this Mac (the font cache exists).

## Witness

tests/test_a_user_path_is_resolved_where_it_is_used.py: red on a pristine
export of 05d556d7 (11 values bound + 9 home touches at import, run with
HOME fenced from outside), green on 851cff1d.

## Status

- step 0: brief read; base verified; AGENTS, CONDUCT, RSL README, lesson
  config-tests-fence-home and b78f5bec, Q24's EPISODE, capability
  registry, both conftests read; store profiled read-only.
- step 1: instruments built and validated; E0, E1, E1t measured; census.
- step 2: commits df2c48f4 (fence, shared), 0b356517 (store), 365d452f
  (user settings, shared), 6e679fd1 (PySCF interpreter, shared), 851cff1d
  (witness).
- step 3: E2 (full suite on 851cff1d, real HOME) running; then merge
  r10-integration (Q24 landed; no file overlaps) and E3 on the merge.
