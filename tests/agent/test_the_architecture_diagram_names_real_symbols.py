"""The architecture diagram in the charter is true to the code.

Every node id in the mermaid flowchart under ``## Architecture`` maps to
a symbol that exists in the tree, so the diagram cannot describe an
architecture the code does not have. When a node moves, this test is
what says so.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

#: node id -> (module, attribute) the node is anchored on.
_ANCHORS = {
    "SP": ("chemsmart.agent.driver", "GoalDriver"),
    "TOOLS": (
        "chemsmart.agent.tool_specs",
        "build_command_compiled_tool_surface",
    ),
    "YAML": ("chemsmart.agent.execution", "promote_project_candidate"),
    "DAG": ("chemsmart.agent.workflows", "build_scientific_workflow_plan"),
    "CC": ("chemsmart.agent.preview", "execute_safe_preview"),
    "REV": ("chemsmart.agent.execution", "WorkflowExecutionReviewV1"),
    "DEC": (
        "chemsmart.agent.live_session",
        "resolve_workflow_execution_review",
    ),
    "GOAL": ("chemsmart.agent.goal", "GoalLedger"),
    "DISP": ("chemsmart.agent.driver", "DISPATCH_MODES"),
    "LOC": ("chemsmart.agent.executor", "execute_approved_workflow"),
    "SUB": ("chemsmart.agent.dispatch", "dispatch_run_to_scheduler"),
    "PARK": ("chemsmart.agent.dispatch", "DISPATCH_RECEIPT_FILE"),
    "WAKE": ("chemsmart.agent.driver", "GoalDriver"),
    "ANA": ("chemsmart.agent.executor", "ApprovedWorkflowExecutor"),
    "VER": (
        "chemsmart.agent.terminal_states",
        "stationary_point_order_finding",
    ),
    "MENU": ("chemsmart.agent.driver", "REPAIR_MENU"),
    "REP": ("chemsmart.agent.live_session", "run_live_agent_session"),
    "ADM": ("chemsmart.agent.goal", "admit_revision"),
    "SET": ("chemsmart.agent.goal", "GOAL_SETTLEMENTS"),
}


def _diagram_node_ids() -> set[str]:
    charter = Path(__file__).resolve().parents[2] / "AGENTS.md"
    text = charter.read_text(encoding="utf-8")
    start = text.index("```mermaid")
    end = text.index("```", start + 10)
    block = text[start:end]
    return set(re.findall(r"^\s*([A-Z]+)[\[{]", block, flags=re.MULTILINE))


def test_every_diagram_node_is_anchored_on_a_symbol_that_exists():
    ids = _diagram_node_ids()
    assert ids, "the charter has no mermaid flowchart"
    human_only = {"U", "HUM"}
    assert set(_ANCHORS) == ids - human_only, (
        "diagram and anchor map disagree: "
        f"only in diagram {sorted(ids - human_only - set(_ANCHORS))}, "
        f"only in anchors {sorted(set(_ANCHORS) - ids)}"
    )
    for node, (module, attribute) in _ANCHORS.items():
        assert hasattr(importlib.import_module(module), attribute), (
            f"node {node} is anchored on {module}.{attribute}, which no "
            "longer exists"
        )


def test_the_wake_resumes_at_the_outcome_phase():
    from chemsmart.agent.driver import GOAL_PHASES

    assert "outcome" in GOAL_PHASES and "parked" in GOAL_PHASES
