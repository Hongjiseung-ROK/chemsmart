---
id: writer-and-reader-one-table
paths:
  - "chemsmart/analysis/result_readers.py"
  - "chemsmart/jobs/*/writer.py"
  - "chemsmart/jobs/pyscf/**"
  - "chemsmart/io/**"
conditions: "PySCF result contracts v4-v5 (2026-09-12/13) and the goal driver's stream records (2026-09-19); synthetic unit tests only, live goals on the ax41 host"
evidence:
  - "commit:8035bf0c"
  - "commit:f6ce5374"
  - "file:MAINTENANCE.md#A writer and a reader are two tables"
  - "test:tests/agent/test_a_cycle_settles_on_its_own_stream.py::test_a_live_session_result_names_its_stream"
repeat_cost: "twice: a declared PySCF selector was refused on every real Hessian while every synthetic test passed; four live goals wrote zero stream rows while their test stayed green"
falsifier: "wrong if a reader whose expectations are derived from the writer's own table, and tested on real archived artifacts, still disagrees with what the writer produced"
home: prose
supersedes: []
earned: 2026-09-19
last_verified: "2026-09-24 @ 6376f69c"
---
A reader's expectation of what a writer produced (units, names, shapes, fields) is derived from the writer's own table, never restated beside it.
A test that stands in for a live object uses the live type or a real archived artifact: a stand-in that supplies the attribute the code reads proves only that the code reads it.
Evidence: 8035bf0c (normal-mode units restated in the reader; a selector refused on every real Hessian) and f6ce5374 (session_id read as run_id; zero stream rows in four live goals).
