"""Frozen minimal Gaussian, ORCA, and xTB setting overlays."""

from __future__ import annotations

from chemsmart.agent.harness.scientific_settings.manifest import (
    FROZEN_EVIDENCE_CEILING_V1,
)


FROZEN_OVERLAYS_V1 = (
    {
        "schema_version": "chemsmart.scientific-settings-overlay.v1",
        "overlay_id": "settings.gaussian.v1",
        "overlay_version": "1.0.0",
        "program": "gaussian",
        "source_ids": (
            "bse-catalog-0.11",
            "gaussian-settings-3bd8915",
            "project-protocol-c793db6",
        ),
        "capabilities": (
            {
                "capability_id": "gaussian.basis.def2-tzvp",
                "program": "gaussian",
                "setting_path": "method.basis",
                "canonical_value": "def2-TZVP",
                "aliases": ("def2 TZVP", "def2tzvp"),
                "applicable_job_kinds": ("*",),
                "source_ids": (
                    "bse-catalog-0.11",
                    "gaussian-settings-3bd8915",
                    "project-protocol-c793db6",
                ),
                "loader_observation": "accepted",
                "renderer_observation": "preserved",
                "observation_note": (
                    "The frozen BSE name and current Gaussian settings path "
                    "preserve this literal; no engine execution was performed."
                ),
                "engine_executed": False,
                "combination_verified": False,
            },
            {
                "capability_id": "gaussian.functional.b3lyp",
                "program": "gaussian",
                "setting_path": "method.functional",
                "canonical_value": "B3LYP",
                "aliases": ("b3-lyp",),
                "applicable_job_kinds": ("*",),
                "source_ids": (
                    "gaussian-settings-3bd8915",
                    "project-protocol-c793db6",
                ),
                "loader_observation": "accepted",
                "renderer_observation": "preserved",
                "observation_note": (
                    "The current Gaussian settings path accepts and preserves "
                    "the functional literal; no engine execution was performed."
                ),
                "engine_executed": False,
                "combination_verified": False,
            },
        ),
        "evidence_ceiling": FROZEN_EVIDENCE_CEILING_V1,
    },
    {
        "schema_version": "chemsmart.scientific-settings-overlay.v1",
        "overlay_id": "settings.orca.v1",
        "overlay_version": "1.0.0",
        "program": "orca",
        "source_ids": (
            "orca-references-3bd8915",
            "orca-settings-3bd8915",
            "project-protocol-c793db6",
        ),
        "capabilities": (
            {
                "capability_id": "orca.basis.ma-def2-tzvp",
                "program": "orca",
                "setting_path": "method.basis",
                "canonical_value": "ma-def2-TZVP",
                "aliases": ("ma def2 TZVP", "madef2tzvp"),
                "applicable_job_kinds": ("*",),
                "source_ids": (
                    "orca-settings-3bd8915",
                    "project-protocol-c793db6",
                ),
                "loader_observation": "accepted",
                "renderer_observation": "preserved",
                "observation_note": (
                    "The current ORCA settings route preserves the exact basis "
                    "literal; BSE membership and engine acceptance are not "
                    "claimed."
                ),
                "engine_executed": False,
                "combination_verified": False,
            },
            {
                "capability_id": "orca.dispersion.d3bj",
                "program": "orca",
                "setting_path": "method.dispersion",
                "canonical_value": "D3BJ",
                "aliases": ("d3 bj", "D3(BJ)", "D3-BJ"),
                "applicable_job_kinds": ("*",),
                "source_ids": (
                    "orca-references-3bd8915",
                    "orca-settings-3bd8915",
                    "project-protocol-c793db6",
                ),
                "loader_observation": "accepted",
                "renderer_observation": "preserved",
                "observation_note": (
                    "The current project compiler separates the ORCA D3BJ "
                    "keyword from the functional and preserves both through "
                    "the loader; no engine execution was performed."
                ),
                "engine_executed": False,
                "combination_verified": False,
            },
            {
                "capability_id": "orca.functional.b3lyp",
                "program": "orca",
                "setting_path": "method.functional",
                "canonical_value": "B3LYP",
                "aliases": ("b3-lyp",),
                "applicable_job_kinds": ("*",),
                "source_ids": (
                    "orca-settings-3bd8915",
                    "project-protocol-c793db6",
                ),
                "loader_observation": "accepted",
                "renderer_observation": "preserved",
                "observation_note": (
                    "The current ORCA settings route accepts and preserves the "
                    "functional literal; no engine execution was performed."
                ),
                "engine_executed": False,
                "combination_verified": False,
            },
        ),
        "evidence_ceiling": FROZEN_EVIDENCE_CEILING_V1,
    },
    {
        "schema_version": "chemsmart.scientific-settings-overlay.v1",
        "overlay_id": "settings.xtb.v1",
        "overlay_version": "1.0.0",
        "program": "xtb",
        "source_ids": (
            "project-protocol-c793db6",
            "xtb-references-3bd8915",
            "xtb-settings-3bd8915",
        ),
        "capabilities": (
            {
                "capability_id": "xtb.method.gfn2",
                "program": "xtb",
                "setting_path": "method.gfn_version",
                "canonical_value": "gfn2",
                "aliases": ("GFN2-xTB", "gfn2xtb"),
                "applicable_job_kinds": ("hess", "opt", "sp"),
                "source_ids": (
                    "project-protocol-c793db6",
                    "xtb-references-3bd8915",
                    "xtb-settings-3bd8915",
                ),
                "loader_observation": "accepted",
                "renderer_observation": "preserved",
                "observation_note": (
                    "The frozen xTB references and settings path preserve GFN2 "
                    "for the three current CLI leaves; no engine execution was "
                    "performed."
                ),
                "engine_executed": False,
                "combination_verified": False,
            },
        ),
        "evidence_ceiling": FROZEN_EVIDENCE_CEILING_V1,
    },
)


__all__ = ["FROZEN_OVERLAYS_V1"]
