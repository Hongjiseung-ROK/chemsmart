from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from chemsmart.agent.evidence_artifact_manifest import (
    EvidenceArtifactManifestV1,
    build_evidence_artifact_manifest,
    build_evidence_artifact_manifest_v2,
    manifest_json_bytes,
    manifest_v2_json_bytes,
    verify_evidence_artifact_manifest,
    verify_evidence_artifact_manifest_v2,
)


def test_manifest_replays_exact_files_and_rejects_mutation(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "nested" / "b.txt").write_text("evidence\n", encoding="utf-8")

    manifest = build_evidence_artifact_manifest(
        tmp_path,
        manifest_id="campaign:test",
        scope="public",
        excluded_locators=("artifact-manifest.json",),
    )
    (tmp_path / "artifact-manifest.json").write_bytes(
        manifest_json_bytes(manifest)
    )
    verify_evidence_artifact_manifest(tmp_path, manifest)

    assert manifest.artifact_count == 2
    assert tuple(item.locator for item in manifest.artifacts) == (
        "a.json",
        "nested/b.txt",
    )
    assert json.loads(manifest_json_bytes(manifest))["manifest_sha256"] == (
        manifest.manifest_sha256
    )

    (tmp_path / "nested" / "b.txt").write_text("mutated\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not replay"):
        verify_evidence_artifact_manifest(tmp_path, manifest)


def test_manifest_contract_rejects_unsafe_or_inconsistent_records(tmp_path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    manifest = build_evidence_artifact_manifest(
        tmp_path,
        manifest_id="campaign:test",
        scope="private",
    )
    body = manifest.model_dump(mode="json")
    body["artifacts"][0]["locator"] = "../outside"

    with pytest.raises(ValidationError, match="safe and relative"):
        EvidenceArtifactManifestV1.model_validate(body)


def test_manifest_rejects_symbolic_links(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("target", encoding="utf-8")
    (tmp_path / "alias.txt").symlink_to(target)

    with pytest.raises(ValueError, match="symbolic links"):
        build_evidence_artifact_manifest(
            tmp_path,
            manifest_id="campaign:test",
            scope="public",
        )


def test_manifest_v2_replays_with_a_declared_final_envelope(tmp_path):
    (tmp_path / "campaign-run-receipt.json").write_text(
        "{}\n", encoding="utf-8"
    )
    manifest = build_evidence_artifact_manifest_v2(
        tmp_path,
        manifest_id="campaign:v2",
        scope="public",
        excluded_locators=(
            "artifact-manifest.json",
            "campaign-receipt.json",
        ),
    )
    (tmp_path / "artifact-manifest.json").write_bytes(
        manifest_v2_json_bytes(manifest)
    )
    (tmp_path / "campaign-receipt.json").write_text(
        json.dumps(
            {
                "manifest_sha256": manifest.manifest_sha256,
                "manifest_artifact_sha256": "envelope-owned",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    verify_evidence_artifact_manifest_v2(tmp_path, manifest)
    (tmp_path / "campaign-run-receipt.json").write_text(
        "{\"mutated\":true}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="does not replay"):
        verify_evidence_artifact_manifest_v2(tmp_path, manifest)
