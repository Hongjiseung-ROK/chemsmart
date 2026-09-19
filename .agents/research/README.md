# Evidence graph

What this repository has learned, kept as links instead of prose. Nothing
under `chemsmart/` imports it.

| file | what it is |
|---|---|
| `graph.yaml` | the authored join: fundamentals, lessons pointing at the text that states them, negative results with their falsifiers, the commits that replaced what a sentence says, and per-rule annotations |
| `claims.yaml` | what the project may and may not yet claim, with the strongest counterexample and the missing experiment for each |
| `loop/graph.py` | the graph, derived on every call from the live registries (rules, gates, policies, guides, tests, charter sections and topics) and joined to `graph.yaml`; nothing is stored, so it cannot go stale |
| `loop/census.py` | what each instruction surface costs, measured from the live tree |
| `loop/replay.py` | what archived Agent runs did, recomputed from their hash-chained event streams |

```bash
PY=/opt/anaconda3/bin/python          # never pip install
$PY .agents/research/loop/graph.py find <word | rule id | commit>
$PY .agents/research/loop/graph.py why <node>
$PY .agents/research/loop/graph.py cost | orphans | stats | check
$PY .agents/research/loop/census.py
$PY .agents/research/loop/replay.py [ROOT ...]
```

A lesson or a result is added to `graph.yaml` with a pointer that `check` can
resolve; it is never restated in `AGENTS.md`.
