"""Frozen source manifest for scientific-settings registry v1."""

from __future__ import annotations


FROZEN_EVIDENCE_CEILING_V1 = {
    "schema_version": "chemsmart.scientific-settings-evidence-ceiling.v1",
    "maximum_claim": "loader_renderer_verification_only",
    "safe_preview_executed": False,
    "engine_executed": False,
    "scientific_adequacy_verified": False,
    "setting_combination_verified": False,
}


FROZEN_MANIFEST_V1 = {
    "schema_version": "chemsmart.scientific-settings-registry.v1",
    "registry_id": "chemsmart.scientific-settings.source-snapshot-c793db6",
    "registry_version": "1.0.0",
    "chemsmart_version": "2.0.1",
    "source_revision": "c793db616d313ef783085f0584f83f0ceca83b73",
    "cli_schema_sha256": (
        "0cc218099762f0dd3f5bc0dabecbd29dab5c29666c8691dbc5d0f9b633850ebb"
    ),
    "basis_catalog_sha256": (
        "ed4ef918fb80e8ad3c2396c237d2120c31892cfaa2a61fb61af52965dc723c0b"
    ),
    "sources": (
        {
            "source_id": "bse-catalog-0.11",
            "source_kind": "basis_set_exchange_catalog",
            "locator": (
                "chemsmart/agent/harness/basis_sets/"
                "bse_basis_catalog.json"
            ),
            "artifact_sha256": (
                "ed4ef918fb80e8ad3c2396c237d2120c31892cfaa2a61fb61af52965dc723c0b"
            ),
            "source_revision": (
                "basis_set_exchange==0.11; all declared elements verified"
            ),
        },
        {
            "source_id": "cli-schema-2.0.1",
            "source_kind": "generated_cli_schema",
            "locator": (
                "chemsmart.agent.cli_schema:build_chemsmart_cli_schema"
            ),
            "artifact_sha256": (
                "0cc218099762f0dd3f5bc0dabecbd29dab5c29666c8691dbc5d0f9b633850ebb"
            ),
            "source_revision": (
                "ChemSmart 2.0.1@3bd8915e15795576d782ac005e79c0d16a3fc782"
            ),
        },
        {
            "source_id": "gaussian-settings-3bd8915",
            "source_kind": "checked_in_loader_renderer",
            "locator": "chemsmart/jobs/gaussian/settings.py",
            "artifact_sha256": (
                "26fee949b4825c8a6787caa7bd7580d7967c62958ddaedcf613ae84270f1cc72"
            ),
            "source_revision": "3bd8915e15795576d782ac005e79c0d16a3fc782",
        },
        {
            "source_id": "orca-references-3bd8915",
            "source_kind": "checked_in_reference",
            "locator": "chemsmart/io/orca/__init__.py",
            "artifact_sha256": (
                "e193a51e08fc0a6b0cdb710f0f29b80b7c9726ec2a217ee78f124487ceee79e5"
            ),
            "source_revision": "3bd8915e15795576d782ac005e79c0d16a3fc782",
        },
        {
            "source_id": "orca-settings-3bd8915",
            "source_kind": "checked_in_loader_renderer",
            "locator": "chemsmart/jobs/orca/settings.py",
            "artifact_sha256": (
                "fd912d9048c1769ee8fd497317531ac92a8816748f838b8a0e656aa47e98a49f"
            ),
            "source_revision": "3bd8915e15795576d782ac005e79c0d16a3fc782",
        },
        {
            "source_id": "project-protocol-c793db6",
            "source_kind": "checked_in_loader_renderer",
            "locator": "chemsmart/agent/project_protocol.py",
            "artifact_sha256": (
                "1d3ceb0229255fd2fe6380a54d5c481f416e4ab40b0ea37909293b580b93d418"
            ),
            "source_revision": "c793db616d313ef783085f0584f83f0ceca83b73",
        },
        {
            "source_id": "xtb-references-3bd8915",
            "source_kind": "checked_in_reference",
            "locator": "chemsmart/io/xtb/__init__.py",
            "artifact_sha256": (
                "f8e3b3ebd947096cb7e73aff4b1b9012c2f74ed60c62a7d4f2eb27075faa8649"
            ),
            "source_revision": "3bd8915e15795576d782ac005e79c0d16a3fc782",
        },
        {
            "source_id": "xtb-settings-3bd8915",
            "source_kind": "checked_in_loader_renderer",
            "locator": "chemsmart/settings/xtb.py",
            "artifact_sha256": (
                "521f69f5d02ded76a77155aadff0d546ff7efba9c22c7cf81024c4dedc091b42"
            ),
            "source_revision": "3bd8915e15795576d782ac005e79c0d16a3fc782",
        },
    ),
    "evidence_ceiling": FROZEN_EVIDENCE_CEILING_V1,
}


__all__ = ["FROZEN_EVIDENCE_CEILING_V1", "FROZEN_MANIFEST_V1"]
