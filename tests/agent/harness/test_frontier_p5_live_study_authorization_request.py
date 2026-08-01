"""Focused offline test for the nonbinding P5 authorization-request template."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REQUEST_PATH = (
    ROOT
    / "docs/program/frontier-agent/handoffs/"
    "p5-live-study-authorization-request-v1.json"
)
VALIDATOR_PATH = ROOT / "scripts/review/validate_frontier_p5_live_study_authorization_request.py"


def _load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "frontier_p5_live_study_authorization_request_validator",
        VALIDATOR_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p5_live_study_authorization_request_validates() -> None:
    strict_result = subprocess.run(
        [
            sys.executable,
            "scripts/review/validate_frontier_p5_live_study_authorization_request.py",
            "--repo",
            str(ROOT),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert strict_result.returncode == 0, strict_result.stdout + strict_result.stderr

    bootstrap_result = subprocess.run(
        [
            sys.executable,
            "scripts/review/validate_frontier_p5_live_study_authorization_request.py",
            "--repo",
            str(ROOT),
            "--bootstrap-empty-template",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert bootstrap_result.returncode == 1
    assert "P5 handoff bootstrap requires an empty phase-close log" in bootstrap_result.stdout


def test_p5_live_study_authorization_request_bootstrap_is_empty_document_only() -> None:
    request_document = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    request_document["phase_close_validation"]["invocations"] = []
    validator = _load_validator_module()

    strict_errors = validator.validate(ROOT, request_document=request_document)
    assert strict_errors == ["P5 handoff phase-close evidence is incomplete"]

    bootstrap_errors = validator.validate(
        ROOT,
        bootstrap_empty_template=True,
        request_document=request_document,
    )
    assert bootstrap_errors == []
