#!/usr/bin/env python3
"""Validate the append-only Frontier no-go evidence index offline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chemsmart.agent.harness.frontier_evidence_index import (  # noqa: E402
    load_frontier_evidence_index,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=_ROOT)
    parser.add_argument(
        "--index",
        type=Path,
        default=Path("docs/program/frontier-agent/paper/frontier-evidence-index-v1.json"),
    )
    args = parser.parse_args()
    root = args.repo.resolve()
    index_path = args.index if args.index.is_absolute() else root / args.index
    try:
        load_frontier_evidence_index(repo_root=root, index_path=index_path)
    except ValueError as exc:
        print(f"ERROR: {type(exc).__name__}")
        return 1
    print("Frontier no-go evidence index validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
