# Frontier Agent Foundation Receipt

## Isolation and preservation

The implementation branch was created in:

`/Users/hongjiseung/.codex/worktrees/chemsmart-frontier-agent-foundation/chemsmart`

from the exact remote object:

`fork/codex/v015-cli-schema@cf986251077b7ee65f8afa951ee76052146c7613`

The original development checkout remained on `feat/agent-xtb-harness` at
`fbb82316d13370940080a6b6981f9a047edb761b`. Before creating the worktree it
contained three tracked xTB runner-handoff edits and untracked GUI, frontend,
design, screenshot, and GUI-test artifacts. This foundation branch does not
read, stage, modify, or incorporate those artifacts.

After the final validation rerun, the original checkout was rechecked and had
the same branch plus the same three tracked and eleven untracked entries.

## Baseline and foundation checks

| Check | Result |
| --- | --- |
| Pinned focused CLI-schema/runtime/permission suite | 206 passed (4.80 s baseline; 4.19 s final rerun) |
| CLI schema dump | ChemSmart 2.0.1; 171 command nodes; digest `0cc218099762f0dd3f5bc0dabecbd29dab5c29666c8691dbc5d0f9b633850ebb` |
| Foundation evidence validator | passed |
| Project-local skill structural validation | 3 of 3 valid |
| Read-only clean-context skill forward tests | 3 representative cases completed; all withheld unsafe or unsupported success claims |
| Full agent suite after foundation additions | 1231 passed, 6 warnings in 65.56 s |

No live provider calls, real Gaussian/ORCA/xTB calculations, scheduler jobs,
dependency installations, or global-skill installations were performed.

## Source and supply-chain record

The scholarly BibTeX fields were retrieved through DOI content negotiation and
checked against Crossref metadata. Citation correction/retraction fields were
checked at retrieval time; unresolved entries fail the offline validator.

The project-local skills are clean-room documents. No third-party skill bundle
or executable code was imported. The OpenAI skill-installer catalog request was
attempted read-only but GitHub returned HTTP 403; this had no effect on the
repository or skill policy. The pinned-source decisions and exact license
statuses are in the [evidence ledger](frontier-agent-evidence-ledger.json).

## Forward-test outcome

The harness skill correctly distinguished the current OpenAI Chat Completions
history-based loop from a future Responses-style continuation capability. The
scientific-workflow skill refused to infer a TS-plus-frequency result from an
XYZ file or TS job kind alone, and the evidence-audit skill marked a
screenshot-only barrier statement as unresolved and blocked. These were
read-only checks; they did not run calculations or modify runtime behavior.
