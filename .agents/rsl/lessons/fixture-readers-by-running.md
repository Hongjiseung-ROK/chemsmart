---
id: fixture-readers-by-running
paths:
  - "tests/data/**"
conditions: "R9 integration tree before the 2026-09-23 push; pytest on macOS; PySCF archived fixtures selected by directory listing and content identity"
evidence:
  - "file:tests/agent/test_every_archived_pyscf_result_reaches_its_verdict.py#The parametrisation is the directory listing"
  - "note:R9 push, 2026-09-23: a deletion of six fixtures that a by-name search called unreferenced turned this test red; the commit was dropped by rebase before the push, so no commit holds it"
repeat_cost: "a rebase of a 200-commit push series; the deletion had passed a by-name reference check"
falsifier: "wrong if every reader under tests/ names its fixture by literal path (no directory listing, glob or digest lookup); retire if a test fails whenever a fixture no test reads is present"
home: prose
supersedes: []
earned: 2026-09-23
last_verified: "2026-09-25 @ ef1eb516"
---
A fixture's readers are found by running the tests without it, never by searching for its name.
Tests here select fixtures by directory listing, glob and content digest, so "no test mentions this file" proves nothing.
Before deleting or renaming anything under tests/data, move it aside, run the full suite (or every test that reads its directory), and restore it if anything turns red.
Evidence: R9's by-name deletion of six "unreferenced" PySCF fixtures turned test_every_archived_pyscf_result_reaches_its_verdict red.
