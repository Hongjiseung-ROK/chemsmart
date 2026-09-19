# CHEMSMART research loop

A dev-side research harness. Nothing under `chemsmart/` imports it, it grades
no chemistry inside the product, and it is not a second approval plane.

**Start a session:** read `BOOTSTRAP.md`, then `STATE.md`. Everything else is
retrieved when needed.

| file | what it is |
|---|---|
| `loop.yaml` | the loop itself, versioned (`g0`, `g1`, ...): twelve mutable components, each with its evidence and falsifier |
| `ledger.jsonl` | append-only, hash-chained record of observations, seals, forecasts, outcomes, decisions; every row names its `target_kind` and `loop_version` |
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
$PY .agents/research/loop/graphcheck.py    # every pointer still resolves
$PY .agents/research/loop/census.py        # what each surface costs
$PY .agents/research/loop/replay.py [ROOT] # what archived runs did
$PY .agents/research/loop/arms.py check    # relocation loses no paragraph
$PY .agents/research/loop/choose.py slate  # EIG / cost / risk ranking
$PY .agents/research/loop/choose.py score  # score sealed forecasts
```

**Each generation:** score the previous generation's forecasts; attribute
outcomes to loop components; build a slate of at least five candidates across
all three kinds from this generation's evidence; forecast before running;
select by information gain, cost, risk and the two fundamentals; execute inside
the owner's envelope; promote one kind per commit; render `STATE.md`; verify
it with a fresh session. No target is named in advance. Seals and answer keys
live in `~/.chemsmart-research-seals/`, never here.
