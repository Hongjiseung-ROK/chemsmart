"""Stable bindings from knowledge rules to deterministic ChemSmart checks.

The manifest names existing host-side validators.  It does not expose an
approval, repair, execution, or native-input surface to a model.
"""

from __future__ import annotations

import hashlib
import json
from typing import Final


KNOWLEDGE_VALIDATOR_BINDINGS_V1: Final = (
    {
        "validator_id": "validator.project.loader.static.v1",
        "callable": (
            "chemsmart.agent.project_yaml_rules:static_project_yaml_issues"
        ),
        "contract": (
            "Reject project YAML settings that the selected program-specific "
            "loader contract cannot preserve."
        ),
    },
    {
        "validator_id": "validator.project.protocol-alignment.v1",
        "callable": (
            "chemsmart.agent.project_yaml_rules:protocol_alignment_issues"
        ),
        "contract": (
            "Compare the evidence-derived protocol with the rendered project "
            "settings without inventing missing values."
        ),
    },
    {
        "validator_id": "validator.scientific-settings.exact-program.v1",
        "callable": (
            "chemsmart.agent.harness.scientific_settings:"
            "resolve_scientific_setting"
        ),
        "contract": (
            "Admit only exact or verified program-scoped aliases; fuzzy and "
            "unknown values cannot become ready."
        ),
    },
    {
        "validator_id": "validator.xtb.method-solvent.static.v1",
        "callable": (
            "chemsmart.agent.project_yaml_rules:static_project_yaml_issues"
        ),
        "contract": (
            "Validate xTB GFN method, solvent pair, job block, and placement "
            "of molecular state in the command node."
        ),
    },
)


def knowledge_validator_registry_sha256() -> str:
    payload = json.dumps(
        KNOWLEDGE_VALIDATOR_BINDINGS_V1,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "KNOWLEDGE_VALIDATOR_BINDINGS_V1",
    "knowledge_validator_registry_sha256",
]
