# The RSL: CHEMSMART's research-and-development doctrine

The RSL is a small, curated, evidence-backed body of knowledge that keeps
the laboratory from paying twice for the same mistake. It is canonical
enough to guide the next researcher and never sacred enough to escape
revision. It is subordinate to the two Fundamentals (`AGENTS.md`) and to
current evidence, and it does not grow by default: a smaller and more
accurate RSL is better than a larger one.

It no longer observes the repository, ranks topics or selects research.
The automatic loop (utility u1, slate generations, forecasts) is retired
and kept, untouched, as evidence.

## Five layers

1. **Kernel** -- `AGENTS.md`, always loaded: the Fundamentals and the
   doctrines that hold in every session. Capability state is never
   narrated there; it is computed (`chemsmart agent capabilities`).
2. **Lessons** -- `lessons/<id>.md`, one small file each, read when the
   surface it scopes is in play. The body *is* the lesson; the
   frontmatter is metadata. Claude Code delivers a lesson by itself: the
   tracked link `.claude/rules/rsl` makes the store a rules folder, and a
   session that reads a file the lesson's `paths` match receives its body
   (observed 2026-09-24 in the main checkout and inside a worktree
   subagent; without the tracked link a worktree received nothing).
   Other agents search with `rsl.py find`.
3. **Procedures** -- skills, loaded when invoked (the CUHK campaign recipe
   lives in the site skill, not here).
4. **Enforcement** -- wherever a rule can be checked: tests, hooks,
   registries, typed contracts, host invariants. A lesson whose rule
   becomes mechanical is retired to a one-line comment beside the
   mechanism.
5. **Evidence** -- outside the rules and never deleted: git history,
   `chemsmart/agent/qualification/release.json`, cluster goal records,
   `experiments-public/`, the charter topics, `MAINTENANCE.md`,
   `.agents/research/graph.yaml` and `claims.yaml`. A lesson points into
   evidence; evidence never instructs.

## A lesson

```yaml
---
id: kebab-case-id                # equals the file name
paths:                           # the scope; mandatory -- an unscoped lesson belongs in the kernel or nowhere
  - "chemsmart/io/**"
conditions: "model, host, versions and tree it was learned on"
evidence:                        # at least one pointer that resolves
  - "commit:<sha>"
  - "file:<path>#<verbatim text in that file>"
  - "test:<path>::<test or class name>"
  - "note:<what no pointer can hold, e.g. a history that was rebased away>"
repeat_cost: "the loss it was paid for: at least twice, or once expensively"
falsifier: "what would show it wrong, or make it unnecessary"
home: prose                      # prose | test | hook | registry | invariant | skill
supersedes: []
earned: YYYY-MM-DD
last_verified: "YYYY-MM-DD @ <sha>"
---
The statement, once. The guidance. A last line naming the evidence.
```

Claude Code reads only `paths` from a rule's frontmatter and strips the
rest, so everything a reader needs is in the body.

## Admission

A lesson is admitted only with a demonstrated repeat cost and only when
no mechanical home exists; a rule that can become a test, hook, registry
entry or invariant is admitted *as that*. Every addition competes against
adding nothing, deleting or narrowing an existing entry, replacing it, or
keeping the observation only as evidence. A one-molecule anecdote, a
trick that worked once, and a fact the host can compute are not lessons.

Specialists propose candidates in their episode report (the RSL
reflection); "no new RSL fact is warranted" is a good answer. Only the
master admits, narrows, replaces, merges, moves or retires, and only the
master edits this directory.

## Budget -- current, revisable by evidence

About 150 kernel lines, about 25 lessons, about 1.2 KB and six lines per
lesson body. These numbers are the current curation budget, not a
Fundamental. Durable, evidence-backed knowledge is admitted even when that
means revising them; the revision is itself a curation decision recorded
with its evidence (`rsl: BUDGET ...`). What governs is the principle --
compact, current, high-value, aggressively pruned.

## Curation record

A decision that changes the store is one commit whose subject is
`rsl: <ADMIT|NARROW|REPLACE|MERGE|MOVE|RETIRE|BUDGET> <id>`, with the
candidate, the comparison against existing entries and code, and the
reason in the body. A decision that changes nothing (reject; keep as
evidence) is a line of the same form in the body of the merge commit that
judged it. `git log --grep '^rsl:'` is the whole decision log.

## Old facts re-earn their place

When an episode returns, every lesson whose scope it touched is re-checked
against the tree it produced: still true (bump `last_verified`), narrowed,
or retired. A lesson not re-verified for a whole round is reviewed for
retirement when the round closes.

## Tools

```
python .agents/rsl/rsl.py find <path | word> ...   # lessons in scope, then lesson and evidence text
python .agents/rsl/rsl.py check                    # structure, scopes, pointers; budget prompts
```

`check` fails on a frontmatter that does not parse (Claude Code would load
the file unscoped), a missing field, an id that is not its file name, a
scope that matches no tracked file, and an evidence pointer that does not
resolve. It reports a budget overrun as a prompt for an explicit decision.
It cannot prove that a lesson is true -- a pointer that resolves is not a
statement that holds; re-verification is what keeps a lesson true.
