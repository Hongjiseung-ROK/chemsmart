# CHEMSMART research loop

A dev-side research harness. Nothing under `chemsmart/` imports it, it grades
no chemistry inside the product, and it is not a second approval plane.

**Start a session:** read `BOOTSTRAP.md`, then `STATE.md`. Everything else is
retrieved when needed.

| file | what it is |
|---|---|
| `loop.yaml` | the loop itself, versioned: twelve mutable components, each with evidence and a falsifier |
| `ledger.jsonl` | append-only, hash-chained: observations, seals, forecasts, outcomes, decisions, each with `target_kind` and `loop_version` |
| `slate.yaml` | open candidate mutations across the three kinds, with priors and outcome models |
| `graph.yaml` | authored join between instructions and evidence; everything derivable is derived |
| `frontier.yaml` | evaluation cascade, task families, metric vectors, meta metrics |
| `claims.yaml` | paper claim map |
| `bootstrap/` | the owner's original prompt, verbatim (raw evidence) |

Three mutation kinds, never mixed in a commit or a ledger row: `product`,
`agent_context`, `research_loop`.

```bash
PY=/opt/anaconda3/bin/python          # never pip install
$PY .agents/research/loop/ledger.py        # verify the ledger chain
$PY .agents/research/loop/graph.py check   # every pointer still resolves (also: stats, why, cost, orphans, export)
$PY .agents/research/loop/census.py        # what each surface costs
$PY .agents/research/loop/replay.py [ROOT] # what archived runs did
$PY .agents/research/loop/arms.py check    # relocation loses no paragraph
$PY .agents/research/loop/choose.py slate  # EIG / cost / risk ranking
$PY .agents/research/loop/choose.py score  # score sealed forecasts
```

**Each generation** follows `loop.yaml: successor` (summarised in
`BOOTSTRAP.md`). Seals and answer keys live in
`~/.chemsmart-research-seals/`, never here.
