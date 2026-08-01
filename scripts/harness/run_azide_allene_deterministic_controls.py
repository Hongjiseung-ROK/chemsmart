#!/usr/bin/env python3
"""Run deterministic controls derived from the live azide/allene pilot.

The positive control replays the typed command contract that DeepSeek V4
Flash successfully proposed.  The negative control changes exactly one field:
the SHA-256 bound to the input geometry.  No provider, chemistry engine, or
scheduler is called.  ChemSmart may generate ephemeral native input inside its
safe-preview temporary directory; it never writes a persistent native input
to the fixture workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from chemsmart.agent.command_workflow import CommandWorkflowCompiler
from chemsmart.agent.command_workflow_tools import synthesize_command
from chemsmart.agent.project_yaml import render_project_yaml
from chemsmart.agent.source_spans import (
    ImmutableSourceDocument,
    extract_project_protocol_spans,
    source_document_scope,
)
from chemsmart.agent.workspace_bindings import discover_workspace_bindings


PAPER_DOI = "10.3390/molecules26040928"
TARGET_TS = "1a+3a N1C1_N3C2 M08HX/pcseg-2"
PROJECT_NAME = "azide_allene_m08hx_pcseg2"
TAMPERED_SHA256 = "0" * 64


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _extract_target_xyz(si_text: str) -> str:
    start = si_text.index(TARGET_TS) + len(TARGET_TS)
    coordinates: list[str] = []
    started = False
    for line in si_text[start:].splitlines():
        match = re.fullmatch(
            r"\s*([A-Z][a-z]?)\s+"
            r"(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*",
            line,
        )
        if match is not None:
            started = True
            coordinates.append(
                f"{match.group(1):2s} {float(match.group(2)): .6f} "
                f"{float(match.group(3)): .6f} {float(match.group(4)): .6f}"
            )
            continue
        if started:
            break
    if len(coordinates) != 27:
        raise ValueError(
            f"expected 27 atoms for {TARGET_TS}, observed {len(coordinates)}"
        )
    return (
        f"{len(coordinates)}\n"
        f"{TARGET_TS}; SI Cartesian coordinates; angstrom\n"
        + "\n".join(coordinates)
        + "\n"
    )


def _paper_protocol_spans(article: str) -> tuple[dict[str, int], ...]:
    methods_start = article.index("3.4. Computational Methods")
    article_lines = article.split("\n")

    def line_of(marker: str) -> int:
        index = article.index(marker, methods_start)
        return article[:index].count("\n") + 1

    frequency_line = line_of("fully optimised and characterised")
    functional_line = line_of("M08-HX, a global meta-GGA")
    functional_column = article_lines[functional_line - 1].index("M08-HX") + 1
    return (
        {
            "start_line": line_of("(99,590) pruned integration grid"),
            "end_line": line_of("(99,590) pruned integration grid"),
        },
        {
            "start_line": functional_line,
            "end_line": functional_line,
            "start_column": functional_column,
            "end_column": functional_column + len("M08-HX") - 1,
        },
        {"start_line": frequency_line, "end_line": frequency_line + 2},
    )


def _prepare_workspace(run_root: Path, si_text: str) -> dict[str, Any]:
    workspace = run_root / "workspace"
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / "ts-1a-3a-n1c1-n3c2.xyz").write_text(
        _extract_target_xyz(si_text),
        encoding="utf-8",
    )
    rendered = render_project_yaml(
        {
            "project_name": PROJECT_NAME,
            "program": "gaussian",
            "method": {
                "functional": "m08hx",
                "basis": "pcseg-2",
                "freq": True,
                "integration_grid": "ultrafine",
            },
            "unsupported_yaml_features": [],
        },
        project_name=PROJECT_NAME,
        program="gaussian",
        profile="paper",
        required_job_kinds=("ts",),
    )
    yaml_text = rendered.get("yaml_text")
    if not rendered.get("ok") or not isinstance(yaml_text, str):
        raise RuntimeError("deterministic project rendering failed")
    project_dir = workspace / ".chemsmart" / "gaussian"
    project_dir.mkdir(parents=True)
    (project_dir / f"{PROJECT_NAME}.yaml").write_text(
        yaml_text,
        encoding="utf-8",
    )
    inventory = discover_workspace_bindings(workspace).public_inventory()
    geometry = inventory["geometry_artifacts"][0]
    project = inventory["project_artifacts"][0]
    return {
        "workspace": workspace,
        "geometry": geometry,
        "project": project,
        "project_yaml_sha256": project["sha256"],
    }


def _contracts(prepared: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    geometry = prepared["geometry"]
    project = prepared["project"]
    task = {
        "task_spec_id": "task:gaussian-ts:1a-3a-n1c1-n3c2",
        "molecule_id": "mol:1a-3a-n1c1-n3c2",
        "geometry": {
            "frame_id": "frame:ts-1a-3a-n1c1-n3c2",
            "artifact_id": geometry["artifact_id"],
            "sha256": geometry["sha256"],
            "ordered_geometry_sha256": geometry["ordered_geometry_sha256"],
        },
        "electronic_state": {"charge": 0, "multiplicity": 1},
        "requested_observable": (
            "transition-state optimization and harmonic-frequency preview "
            "under an engineering-only electronic-state assumption"
        ),
        "node_requirements": [
            {
                "node_id": "gaussian-ts",
                "program": "gaussian",
                "job_kind": "ts",
                "settings_source": "project",
                "method": "m08hx",
                "basis_or_ecp": "pcseg-2",
                "integration_grid": "ultrafine",
                "frequency_required": True,
            }
        ],
        "required_evidence": [
            "cli_schema",
            "command_workflow_receipt",
            "geometry_identity",
            "project_yaml",
            "safe_preview",
        ],
        "post_execution_validation_obligations": [
            "exactly_one_imaginary_frequency",
            "optimization_converged",
        ],
        "unresolved_facts": [],
    }
    workflow = {
        "workflow_id": "wf:gaussian-ts:1a-3a-n1c1-n3c2",
        "task_spec_id": task["task_spec_id"],
        "cli_schema_digest": CommandWorkflowCompiler().schema_digest,
        "nodes": [
            {
                "node_id": "gaussian-ts",
                "command_path": "run/gaussian/ts",
                "project_ref": {
                    "project_id": project["project_id"],
                    "sha256": project["sha256"],
                },
                "input_artifacts": [
                    {
                        "artifact_id": geometry["artifact_id"],
                        "sha256": geometry["sha256"],
                        "kind": "geometry.xyz",
                        "target_parameter": "filename",
                    }
                ],
                "charge": 0,
                "multiplicity": 1,
                "execution_intent": "preview",
                "dependencies": [],
                "expected_artifact_classes": [],
                "constraint_ids": [],
            }
        ],
    }
    return task, workflow


def _rule_ids(result: dict[str, Any]) -> list[str]:
    values = {str(item) for item in result.get("rule_ids") or ()}
    values.update(
        str(item.get("rule_id"))
        for item in result.get("counterexamples") or ()
        if item.get("rule_id")
    )
    return sorted(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article-text", type=Path, required=True)
    parser.add_argument("--si-text", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()

    run_root = args.run_root.resolve()
    run_root.mkdir(parents=True, exist_ok=False)
    article_bytes = args.article_text.read_bytes()
    si_bytes = args.si_text.read_bytes()
    article = article_bytes.decode("utf-8")
    prepared = _prepare_workspace(run_root, si_bytes.decode("utf-8"))
    task, positive_workflow = _contracts(prepared)

    article_document = ImmutableSourceDocument.from_text(
        "paper-main-text",
        article,
    )
    with source_document_scope([article_document]):
        protocol = extract_project_protocol_spans(
            source_id=article_document.source_id,
            source_sha256=article_document.sha256,
            spans=_paper_protocol_spans(article),
            project_name=PROJECT_NAME,
            program="gaussian",
            profile="paper",
        )

    original_cwd = Path.cwd()
    try:
        import os

        os.chdir(prepared["workspace"])
        positive = synthesize_command(task, positive_workflow)
        tampered_workflow = deepcopy(positive_workflow)
        tampered_workflow["nodes"][0]["input_artifacts"][0]["sha256"] = (
            TAMPERED_SHA256
        )
        negative = synthesize_command(task, tampered_workflow)
    finally:
        os.chdir(original_cwd)

    negative_rules = _rule_ids(negative)
    passed = (
        protocol.get("status") == "extracted"
        and (protocol.get("method") or {}).get("functional") == "m08hx"
        and (protocol.get("method") or {}).get("basis") == "pcseg-2"
        and (protocol.get("method") or {}).get("freq") is True
        and (protocol.get("method") or {}).get("integration_grid")
        == "ultrafine"
        and positive.get("status") == "previewed"
        and positive.get("cli_grounded") is True
        and negative.get("status") != "previewed"
        and "cmd.artifact.hash_mismatch" in negative_rules
    )
    receipt: dict[str, Any] = {
        "schema_version": "chemsmart.azide-allene-deterministic-control.v1",
        "paper": {
            "doi": PAPER_DOI,
            "target": TARGET_TS,
            "article_text_sha256": _sha256_bytes(article_bytes),
            "si_text_sha256": _sha256_bytes(si_bytes),
        },
        "source_span_control": {
            "status": protocol.get("status"),
            "method": protocol.get("method"),
            "source_evidence": protocol.get("source_evidence"),
            "model_authored_source_text_accepted": False,
        },
        "fixture_boundary": {
            "charge": 0,
            "multiplicity": 1,
            "source": "engineering_assumption_not_paper_evidence",
        },
        "positive": {
            "status": positive.get("status"),
            "cli_grounded": positive.get("cli_grounded"),
            "command": positive.get("command"),
            "task_spec_sha256": positive.get("task_spec_sha256"),
            "receipt_sha256": (positive.get("receipt") or {}).get(
                "receipt_sha256"
            ),
            "post_execution_validation_obligations": task[
                "post_execution_validation_obligations"
            ],
        },
        "single_factor_attack": {
            "mutated_field": (
                "workflow.nodes[0].input_artifacts[0].sha256"
            ),
            "changed_field_count": 1,
            "tampered_value_sha256": _sha256_bytes(
                TAMPERED_SHA256.encode("ascii")
            ),
            "status": negative.get("status"),
            "rule_ids": negative_rules,
            "expected_rule_id": "cmd.artifact.hash_mismatch",
        },
        "observable_actions": {
            "provider_requests": 0,
            "chemistry_engine_calls": 0,
            "scheduler_calls": 0,
            "persistent_native_input_writes": 0,
            "temporary_safe_preview_artifacts_generated": True,
        },
        "case_pass": passed,
    }
    receipt["receipt_sha256"] = _sha256_json(receipt)
    output = run_root / "public-receipt.json"
    output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "receipt": str(output),
                "receipt_sha256": receipt["receipt_sha256"],
                "case_pass": passed,
                "positive_status": receipt["positive"]["status"],
                "negative_status": receipt["single_factor_attack"]["status"],
                "negative_rule_ids": negative_rules,
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
