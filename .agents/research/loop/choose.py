"""Selection: Pareto fronts, expected information gain, and forecast scoring.

Three small pieces the generation protocol needs, and nothing else:

* ``pareto``  -- non-dominated candidates under hard constraints. Scientific
  quality is never collapsed into one number; only *cost* is, through weights
  that are themselves a loop parameter (``loop.yaml: select``).
* ``eig``     -- exact mutual information (bits) between a candidate's
  hypotheses and its possible outcomes, from the prior P(H) and the outcome
  model P(o|H) the slate entry states. An experiment whose outcome is already
  certain, or which cannot separate its hypotheses, is worth zero however
  interesting it sounds.
* ``score``   -- Brier and log scores for forecasts sealed before outcomes.

    python .agents/research/loop/choose.py slate     # rank slate.yaml
    python .agents/research/loop/choose.py score     # score sealed forecasts
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent

# TODO(owner): which objectives are lexicographic and how costs trade is a
# value judgement, not an engineering one. These defaults ship so the loop
# runs; edit them and the change is a `research_loop` mutation like any other.
HARD_CONSTRAINTS = {
    # a candidate violating any of these is removed before ranking
    "bypasses_hub": False,  # model-authored native input / shell / status
    "fabricates_evidence": False,  # invented execution state or result value
    "rewrites_raw_evidence": False,
    "outside_owner_envelope": False,
}
RISK_CLASSES = {
    "none": 0,
    "reversible": 1,  # one revertible commit, no outward effect
    "outward_facing": 2,  # spends provider/engine budget or writes to CUHK
    "touches_invariant": 3,  # needs an explicit, separate owner decision
}
COST_WEIGHTS = {  # -> one "cost unit" ~ one owner-dollar of attention
    "claude_tokens_k": 0.004,
    "provider_usd": 1.0,
    "engine_calls": 0.25,
    "wall_hours": 0.5,
    "owner_minutes": 1.0,
}


def admissible(candidate: dict) -> bool:
    flags = candidate.get("fundamentals", {})
    return all(
        bool(flags.get(name, False)) is allowed
        for name, allowed in HARD_CONSTRAINTS.items()
    )


def cost_units(cost: dict) -> float:
    return sum(COST_WEIGHTS.get(k, 0.0) * float(v) for k, v in cost.items())


def entropy(dist: dict) -> float:
    return -sum(p * math.log2(p) for p in dist.values() if p > 0)


def eig(prior: dict, likelihood: dict) -> float:
    """I(H; O) in bits. `likelihood[h][o]` = P(o | h)."""
    total = sum(prior.values())
    prior = {h: p / total for h, p in prior.items()}
    outcomes = {o for h in likelihood for o in likelihood[h]}
    p_o = {
        o: sum(prior[h] * likelihood[h].get(o, 0.0) for h in prior)
        for o in outcomes
    }
    expected_posterior = 0.0
    for o, po in p_o.items():
        if po <= 0:
            continue
        posterior = {h: prior[h] * likelihood[h].get(o, 0.0) / po for h in prior}
        expected_posterior += po * entropy(posterior)
    return max(0.0, entropy(prior) - expected_posterior)


def pareto(rows: list[dict], objectives: dict) -> list[dict]:
    """`objectives`: name -> 'max' | 'min'. Returns the non-dominated rows."""

    def better_or_equal(a, b, name, sense):
        return a[name] >= b[name] if sense == "max" else a[name] <= b[name]

    def strictly(a, b, name, sense):
        return a[name] > b[name] if sense == "max" else a[name] < b[name]

    front = []
    for a in rows:
        dominated = any(
            all(better_or_equal(b, a, n, s) for n, s in objectives.items())
            and any(strictly(b, a, n, s) for n, s in objectives.items())
            for b in rows
            if b is not a
        )
        if not dominated:
            front.append(a)
    return front


def rank_slate(slate: dict) -> dict:
    rows, excluded = [], []
    for cand in slate.get("candidates", []):
        if not admissible(cand):
            excluded.append(cand["id"])
            continue
        rows.append(
            {
                "id": cand["id"],
                "kind": cand["target_kind"],
                "eig_bits": round(eig(cand["prior"], cand["likelihood"]), 4),
                "cost_units": round(cost_units(cand.get("cost", {})), 3),
                "risk": RISK_CLASSES[cand.get("risk", "reversible")],
            }
        )
    front = pareto(
        rows, {"eig_bits": "max", "cost_units": "min", "risk": "min"}
    )
    for row in rows:
        row["on_front"] = row in front
        row["eig_per_cost"] = round(
            row["eig_bits"] / max(row["cost_units"], 1e-9), 4
        )
    rows.sort(key=lambda r: (-r["on_front"], -r["eig_per_cost"]))
    return {
        "ranked": rows,
        "excluded_by_fundamentals": excluded,
        "kinds_on_slate": sorted({r["kind"] for r in rows}),
    }


def score(forecasts: dict, outcomes: dict) -> dict:
    """`forecasts[by][event]` = P(event true); `outcomes[event]` = bool.

    Events with no outcome (void, not run) are left out of every forecaster's
    score alike, and counted, so a void experiment cannot flatter anyone.
    """
    resolved = [e for e, v in outcomes.items() if isinstance(v, bool)]
    out = {}
    for by, table in forecasts.items():
        brier, logs, n = 0.0, 0.0, 0
        for event in resolved:
            if event not in table:
                continue
            p = min(max(float(table[event]), 0.01), 0.99)
            y = 1.0 if outcomes[event] else 0.0
            brier += (p - y) ** 2
            logs += math.log2(p if y else 1 - p)
            n += 1
        out[by] = {
            "n": n,
            "brier": round(brier / n, 4) if n else None,
            "log2_score": round(logs / n, 4) if n else None,
        }
    return {"resolved_events": len(resolved), "by_forecaster": out}


def candidate_sources() -> list[dict]:
    """Every place a candidate can come from, enumerated rather than recalled.

    Four sources, all already on disk: an untested loop component's own
    falsifier, a paper claim's missing experiment, a rule annotation that was
    never validated, and a ledger observation that names what it implicates.
    The lead merges and words the slate; it does not get to forget a source.
    """
    import yaml

    sys.path.insert(0, str(HERE))
    from ledger import read

    out = []
    loop = yaml.safe_load((RESEARCH / "loop.yaml").read_text())
    for name, comp in loop["components"].items():
        if comp.get("status") != "promoted":
            out.append(
                {
                    "source": f"loop.{name}",
                    "kind": "research_loop",
                    "prompt": comp.get("falsifier", ""),
                }
            )
    claims = yaml.safe_load((RESEARCH / "claims.yaml").read_text())
    for claim in claims["claims"]:
        if claim.get("status") != "earned":
            out.append(
                {
                    "source": claim["id"],
                    "kind": "product|agent_context",
                    "prompt": claim.get("missing_experiment", ""),
                }
            )
    graph = yaml.safe_load((RESEARCH / "graph.yaml").read_text())
    for rule_id, note in (graph.get("annotations") or {}).items():
        if note.get("falsifier") and not note.get("last_validated"):
            out.append(
                {
                    "source": rule_id,
                    "kind": "agent_context",
                    "prompt": note["falsifier"],
                }
            )
    for row in read():
        if row["type"] == "observation" and row["loop_version"] == loop[
            "version"
        ]:
            out.append(
                {
                    "source": row["id"],
                    "kind": row["target_kind"],
                    "prompt": row["title"],
                }
            )
    return out


def main() -> int:
    import yaml

    mode = sys.argv[1] if len(sys.argv) > 1 else "slate"
    if mode == "candidates":
        for item in candidate_sources():
            print(f"{item['source']:<34} {item['kind']:<22} {item['prompt']}")
        return 0
    if mode == "slate":
        slate = yaml.safe_load((RESEARCH / "slate.yaml").read_text())
        print(json.dumps(rank_slate(slate), indent=1))
        return 0
    if mode == "score":
        sys.path.insert(0, str(HERE))
        from ledger import read

        forecasts, outcomes = {}, {}
        for row in read():
            if row["type"] == "forecast":
                forecasts.setdefault(row["by"], {}).update(row["p"])
            if row["type"] == "outcome":
                outcomes.update(row.get("events", {}))
        print(json.dumps(score(forecasts, outcomes), indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
