from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from chemsmart.agent.coordinate_import import (
    CoordinateAcquisitionMethod,
    CoordinateFormat,
    CoordinateImportError,
    CoordinateSourceAssessment,
    CoordinateSourceDecision,
    OfficialCoordinateProvenance,
    assess_coordinate_source,
    copy_private_preview_artifact,
    import_official_xyz,
    require_prp10_eligible_source,
)


_XYZ_BYTES = (
    b"3\r\n"
    b"publisher-deposited water geometry; units: angstrom\r\n"
    b"O 0.000000 0.000000 0.000000\r\n"
    b"H 0.758602 0.000000 0.504284\r\n"
    b"H -0.758602 0.000000 0.504284\r\n"
)
_APPROVAL_SHA = "a" * 64
_PROVENANCE_SHA = "b" * 64


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _import(
    tmp_path,
    content: bytes = _XYZ_BYTES,
    *,
    source_url: str = "https://official.example/data/structures.zip",
    archive_member: str | None = "structures/water.xyz",
):
    source = tmp_path / "retrieved-private.xyz"
    destination = tmp_path / "imported-private.xyz"
    source.write_bytes(content)
    receipt = import_official_xyz(
        source,
        destination,
        source_artifact_id="source:water-xyz",
        imported_artifact_id="geometry:water",
        source_url=source_url,
        expected_source_sha256=_sha256(content),
        archive_member=archive_member,
        coordinate_units="angstrom",
        identity_approval_id="approval:water-identity",
        identity_approval_sha256=_APPROVAL_SHA,
        license_id="CC-BY-4.0",
        provenance_kind=OfficialCoordinateProvenance.OFFICIAL_REPOSITORY,
        provenance_receipt_id="retrieval:water-xyz",
        provenance_receipt_sha256=_PROVENANCE_SHA,
    )
    return source, destination, receipt


def test_exact_official_xyz_import_is_byte_preserving_and_content_addressed(
    tmp_path,
) -> None:
    source, destination, receipt = _import(tmp_path)

    assert source.read_bytes() == destination.read_bytes() == _XYZ_BYTES
    assert receipt.source_sha256 == receipt.imported_sha256 == _sha256(_XYZ_BYTES)
    assert receipt.exact_byte_copy_verified is True
    assert receipt.prp10_eligible is True
    assert receipt.coordinate_units == "angstrom"
    assert receipt.atom_count == 3
    assert receipt.element_counts == (("H", 2), ("O", 1))
    assert receipt.identity_approval_sha256 == _APPROVAL_SHA
    assert receipt.provenance_receipt_sha256 == _PROVENANCE_SHA
    assert receipt.rule_ids == (
        "coordinate.prp10.exact_official_xyz_angstrom",
    )

    public = json.dumps(receipt.model_dump(mode="json"), sort_keys=True)
    assert str(source) not in public
    assert str(destination) not in public
    assert "0.758602" not in public
    assert "publisher-deposited" not in public

    # Re-importing identical bytes is idempotent and creates the same receipt.
    repeated = import_official_xyz(
        source,
        destination,
        source_artifact_id="source:water-xyz",
        imported_artifact_id="geometry:water",
        source_url="https://official.example/data/structures.zip",
        expected_source_sha256=_sha256(_XYZ_BYTES),
        archive_member="structures/water.xyz",
        coordinate_units="angstrom",
        identity_approval_id="approval:water-identity",
        identity_approval_sha256=_APPROVAL_SHA,
        license_id="CC-BY-4.0",
        provenance_kind="official_repository",
        provenance_receipt_id="retrieval:water-xyz",
        provenance_receipt_sha256=_PROVENANCE_SHA,
    )
    assert repeated == receipt


@pytest.mark.parametrize(
    ("method", "rule_id"),
    [
        (
            CoordinateAcquisitionMethod.COORDINATE_TABLE_REWRITE,
            "coordinate.source.coordinate_table_rewrite_forbidden",
        ),
        (CoordinateAcquisitionMethod.OCR, "coordinate.source.ocr_forbidden"),
        (
            CoordinateAcquisitionMethod.SMILES_TO_3D,
            "coordinate.source.smiles_to_3d_forbidden",
        ),
        (
            CoordinateAcquisitionMethod.MODEL_GENERATION,
            "coordinate.source.model_generation_forbidden",
        ),
    ],
)
def test_derived_or_generated_coordinates_are_rejected(method, rule_id) -> None:
    assessment = assess_coordinate_source(
        source_format="xyz",
        acquisition_method=method,
        coordinate_units="angstrom",
    )
    assert assessment.decision is CoordinateSourceDecision.REJECTED
    assert assessment.rule_ids == (rule_id,)

    with pytest.raises(CoordinateImportError) as captured:
        require_prp10_eligible_source(assessment)
    assert captured.value.rule_id == rule_id


@pytest.mark.parametrize("source_format", ["sdf", "mol", "pdb"])
def test_general_structure_formats_are_recorded_only_as_non_prp_references(
    source_format,
) -> None:
    assessment = assess_coordinate_source(
        source_format=source_format,
        acquisition_method="format_conversion",
        coordinate_units="angstrom",
    )

    assert assessment.source_format is CoordinateFormat(source_format)
    assert assessment.decision is CoordinateSourceDecision.NON_PRP_REFERENCE
    assert assessment.conversion_performed is False
    assert assessment.rule_ids == (
        "coordinate.prp10.converted_geometry_ineligible",
    )


def test_coordinate_source_assessment_cannot_forge_prp10_eligibility() -> None:
    with pytest.raises(ValidationError):
        CoordinateSourceAssessment(
            source_format="xyz",
            acquisition_method="model_generation",
            coordinate_units="angstrom",
            decision="prp10_eligible",
            rule_ids=("coordinate.prp10.exact_official_xyz_angstrom",),
        )


@pytest.mark.parametrize(
    ("content", "rule_id"),
    [
        (
            b"2\nmissing atom\nH 0 0 0\n",
            "coordinate.xyz.malformed",
        ),
        (
            b"1\nframe one\nH 0 0 0\n1\nframe two\nH 0 0 1\n",
            "coordinate.xyz.multiframe_forbidden",
        ),
        (
            b"1\nnon-finite\nH NaN 0 0\n",
            "coordinate.xyz.malformed",
        ),
    ],
)
def test_malformed_or_multiframe_xyz_is_rejected_without_import(
    tmp_path, content, rule_id
) -> None:
    source = tmp_path / "source.xyz"
    destination = tmp_path / "destination.xyz"
    source.write_bytes(content)

    with pytest.raises(CoordinateImportError) as captured:
        import_official_xyz(
            source,
            destination,
            source_artifact_id="source:bad",
            imported_artifact_id="geometry:bad",
            source_url="https://official.example/source.xyz",
            expected_source_sha256=_sha256(content),
            archive_member=None,
            coordinate_units="angstrom",
            identity_approval_id="approval:bad",
            identity_approval_sha256=_APPROVAL_SHA,
            license_id="CC0-1.0",
            provenance_kind="publisher_supplement",
            provenance_receipt_id="retrieval:bad",
            provenance_receipt_sha256=_PROVENANCE_SHA,
        )
    assert captured.value.rule_id == rule_id
    assert not destination.exists()


def test_wrong_units_or_source_hash_fail_closed_before_copy(tmp_path) -> None:
    source = tmp_path / "source.xyz"
    source.write_bytes(_XYZ_BYTES)

    for coordinate_units, digest, rule_id in (
        ("bohr", _sha256(_XYZ_BYTES), "coordinate.prp10.units_not_angstrom"),
        ("angstrom", "0" * 64, "coordinate.source.sha256_mismatch"),
    ):
        destination = tmp_path / f"destination-{coordinate_units}.xyz"
        with pytest.raises(CoordinateImportError) as captured:
            import_official_xyz(
                source,
                destination,
                source_artifact_id="source:water",
                imported_artifact_id="geometry:water",
                source_url="https://official.example/source.xyz",
                expected_source_sha256=digest,
                archive_member=None,
                coordinate_units=coordinate_units,
                identity_approval_id="approval:water",
                identity_approval_sha256=_APPROVAL_SHA,
                license_id="CC-BY-4.0",
                provenance_kind="official_repository",
                provenance_receipt_id="retrieval:water",
                provenance_receipt_sha256=_PROVENANCE_SHA,
            )
        assert captured.value.rule_id == rule_id
        assert not destination.exists()


def test_private_preview_copy_binds_source_project_and_command_without_content(
    tmp_path, caplog
) -> None:
    private_content = b"private generated preview bytes\x00not model-visible"
    source = tmp_path / "private-source.bin"
    destination = tmp_path / "private-preview.bin"
    source.write_bytes(private_content)
    digest = _sha256(private_content)

    receipt = copy_private_preview_artifact(
        source,
        destination,
        preview_artifact_id="preview:node-1",
        source_artifact_id="geometry:water",
        expected_source_sha256=digest,
        source_receipt_id="coordinate-import:receipt-1",
        source_receipt_sha256="c" * 64,
        project_id="project:orca-water",
        project_sha256="d" * 64,
        command_id="command:node-1",
        command_sha256="e" * 64,
    )

    assert destination.read_bytes() == private_content
    assert receipt.source_artifact_sha256 == receipt.copied_sha256 == digest
    assert receipt.project_sha256 == "d" * 64
    assert receipt.command_sha256 == "e" * 64
    serialized = json.dumps(receipt.model_dump(mode="json"), sort_keys=True)
    assert str(source) not in serialized
    assert str(destination) not in serialized
    assert "private generated preview bytes" not in serialized
    assert not caplog.records


def test_private_preview_hash_mismatch_creates_no_artifact(tmp_path) -> None:
    source = tmp_path / "private-source.bin"
    destination = tmp_path / "private-preview.bin"
    source.write_bytes(b"bounded private bytes")

    with pytest.raises(CoordinateImportError) as captured:
        copy_private_preview_artifact(
            source,
            destination,
            preview_artifact_id="preview:node-1",
            source_artifact_id="geometry:water",
            expected_source_sha256="0" * 64,
            source_receipt_id="coordinate-import:receipt-1",
            source_receipt_sha256="c" * 64,
            project_id="project:orca-water",
            project_sha256="d" * 64,
            command_id="command:node-1",
            command_sha256="e" * 64,
        )
    assert captured.value.rule_id == "preview.artifact.source_sha256_mismatch"
    assert not destination.exists()
