"""Deterministic coordinate provenance and private-preview receipts.

PRP-10 accepts only an exact official, single-frame XYZ artifact whose units
are explicitly bound as Angstrom.  This module never reconstructs coordinates
from tables, OCR, line notation, or a model, and it never converts a general
structure format into PRP evidence.  SDF, MOL, and PDB sources can be recorded
as non-PRP references so a future reviewed converter can handle them without
silently promoting derived coordinates.

The copy helpers preserve exact bytes.  Returned receipts contain only stable
identifiers, hashes, counts, and provenance bindings: neither filesystem paths
nor coordinate/native-input content are included or logged.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.geometry_identity import xyz_text_geometry_manifest


COORDINATE_IMPORT_SCHEMA_VERSION = "chemsmart.coordinate-import-receipt.v1"
COORDINATE_SOURCE_ASSESSMENT_SCHEMA_VERSION = (
    "chemsmart.coordinate-source-assessment.v1"
)
PRIVATE_PREVIEW_ARTIFACT_SCHEMA_VERSION = (
    "chemsmart.private-preview-artifact-receipt.v1"
)

MAX_COORDINATE_ARTIFACT_BYTES = 32 * 1024 * 1024

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_SHA256 = r"^[0-9a-f]{64}$"
_ELEMENT = re.compile(r"^[A-Z][a-z]?$|^X$")

RULE_PRP10_ELIGIBLE = "coordinate.prp10.exact_official_xyz_angstrom"
RULE_NON_XYZ = "coordinate.prp10.non_xyz_reference"
RULE_CONVERSION = "coordinate.prp10.converted_geometry_ineligible"
RULE_UNITS = "coordinate.prp10.units_not_angstrom"
RULE_TABLE_REWRITE = "coordinate.source.coordinate_table_rewrite_forbidden"
RULE_OCR = "coordinate.source.ocr_forbidden"
RULE_SMILES_3D = "coordinate.source.smiles_to_3d_forbidden"
RULE_MODEL_GENERATION = "coordinate.source.model_generation_forbidden"
RULE_SOURCE_HASH = "coordinate.source.sha256_mismatch"
RULE_XYZ_UTF8 = "coordinate.xyz.not_utf8"
RULE_XYZ_MALFORMED = "coordinate.xyz.malformed"
RULE_XYZ_MULTI_FRAME = "coordinate.xyz.multiframe_forbidden"
RULE_DESTINATION_CONFLICT = "coordinate.import.destination_conflict"
RULE_PREVIEW_SOURCE_HASH = "preview.artifact.source_sha256_mismatch"


class CoordinateImportError(ValueError):
    """Fail-closed coordinate or exact-copy error with a stable rule ID."""

    def __init__(self, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id


class CoordinateFormat(str, Enum):
    XYZ = "xyz"
    SDF = "sdf"
    MOL = "mol"
    PDB = "pdb"


class CoordinateAcquisitionMethod(str, Enum):
    EXACT_OFFICIAL_FILE = "exact_official_file"
    FORMAT_CONVERSION = "format_conversion"
    COORDINATE_TABLE_REWRITE = "coordinate_table_rewrite"
    OCR = "ocr"
    SMILES_TO_3D = "smiles_to_3d"
    MODEL_GENERATION = "model_generation"


class CoordinateSourceDecision(str, Enum):
    PRP10_ELIGIBLE = "prp10_eligible"
    NON_PRP_REFERENCE = "non_prp_reference"
    REJECTED = "rejected"


class OfficialCoordinateProvenance(str, Enum):
    PUBLISHER_SUPPLEMENT = "publisher_supplement"
    OFFICIAL_REPOSITORY = "official_repository"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class CoordinateSourceAssessment(_Contract):
    """Policy result without claiming that a conversion or import occurred."""

    schema_version: str = Field(
        default=COORDINATE_SOURCE_ASSESSMENT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.coordinate-source-assessment\.v1$",
    )
    source_format: CoordinateFormat
    acquisition_method: CoordinateAcquisitionMethod
    coordinate_units: str = Field(min_length=1, max_length=32)
    decision: CoordinateSourceDecision
    rule_ids: tuple[str, ...]
    conversion_performed: Literal[False] = False

    @model_validator(mode="after")
    def _validate_policy_result(self) -> "CoordinateSourceAssessment":
        expected_decision, expected_rules = _coordinate_source_policy(
            source_format=self.source_format,
            acquisition_method=self.acquisition_method,
            coordinate_units=self.coordinate_units,
        )
        if self.decision is not expected_decision or self.rule_ids != expected_rules:
            raise ValueError("coordinate source assessment contradicts policy")
        return self


class CoordinateImportReceipt(_Contract):
    """Path-free receipt for an exact official XYZ import."""

    schema_version: str = Field(
        default=COORDINATE_IMPORT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.coordinate-import-receipt\.v1$",
    )
    receipt_id: str = Field(pattern=_IDENTIFIER)
    receipt_sha256: str = Field(pattern=_SHA256)
    source_artifact_id: str = Field(pattern=_IDENTIFIER)
    imported_artifact_id: str = Field(pattern=_IDENTIFIER)
    source_url: str = Field(min_length=1, max_length=2048)
    archive_member: str | None = Field(default=None, max_length=1024)
    source_sha256: str = Field(pattern=_SHA256)
    imported_sha256: str = Field(pattern=_SHA256)
    size_bytes: int = Field(ge=1, le=MAX_COORDINATE_ARTIFACT_BYTES)
    source_format: Literal["xyz"] = "xyz"
    coordinate_units: Literal["angstrom"] = "angstrom"
    atom_count: int = Field(ge=1)
    element_counts: tuple[tuple[str, int], ...]
    atom_order_sha256: str = Field(pattern=_SHA256)
    ordered_geometry_sha256: str = Field(pattern=_SHA256)
    identity_approval_id: str = Field(pattern=_IDENTIFIER)
    identity_approval_sha256: str = Field(pattern=_SHA256)
    license_id: str = Field(min_length=1, max_length=160)
    provenance_kind: OfficialCoordinateProvenance
    provenance_receipt_id: str = Field(pattern=_IDENTIFIER)
    provenance_receipt_sha256: str = Field(pattern=_SHA256)
    exact_byte_copy_verified: Literal[True] = True
    prp10_eligible: Literal[True] = True
    rule_ids: tuple[Literal["coordinate.prp10.exact_official_xyz_angstrom"], ...]

    @field_validator("source_url")
    @classmethod
    def _official_https_url(cls, value: str) -> str:
        _validate_source_url(value)
        return value

    @field_validator("archive_member")
    @classmethod
    def _safe_archive_member(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_archive_member(value)
        return value

    @model_validator(mode="after")
    def _validate_binding(self) -> "CoordinateImportReceipt":
        if self.source_sha256 != self.imported_sha256:
            raise ValueError("exact import hashes must match")
        if self.rule_ids != (RULE_PRP10_ELIGIBLE,):
            raise ValueError("PRP-10 receipt must contain its eligibility rule")
        expected = _receipt_sha256(self, excluded={"receipt_id", "receipt_sha256"})
        if self.receipt_sha256 != expected:
            raise ValueError("coordinate import receipt digest mismatch")
        if self.receipt_id != f"coordinate-import:{expected[:24]}":
            raise ValueError("coordinate import receipt ID mismatch")
        return self


class PrivatePreviewArtifactReceipt(_Contract):
    """Exact-byte private artifact bound to source, project, and command."""

    schema_version: str = Field(
        default=PRIVATE_PREVIEW_ARTIFACT_SCHEMA_VERSION,
        pattern=r"^chemsmart\.private-preview-artifact-receipt\.v1$",
    )
    receipt_id: str = Field(pattern=_IDENTIFIER)
    receipt_sha256: str = Field(pattern=_SHA256)
    preview_artifact_id: str = Field(pattern=_IDENTIFIER)
    source_artifact_id: str = Field(pattern=_IDENTIFIER)
    source_artifact_sha256: str = Field(pattern=_SHA256)
    source_receipt_id: str = Field(pattern=_IDENTIFIER)
    source_receipt_sha256: str = Field(pattern=_SHA256)
    project_id: str = Field(pattern=_IDENTIFIER)
    project_sha256: str = Field(pattern=_SHA256)
    command_id: str = Field(pattern=_IDENTIFIER)
    command_sha256: str = Field(pattern=_SHA256)
    copied_sha256: str = Field(pattern=_SHA256)
    size_bytes: int = Field(ge=1, le=MAX_COORDINATE_ARTIFACT_BYTES)
    exact_byte_copy_verified: Literal[True] = True

    @model_validator(mode="after")
    def _validate_binding(self) -> "PrivatePreviewArtifactReceipt":
        if self.source_artifact_sha256 != self.copied_sha256:
            raise ValueError("private preview is not an exact source-byte copy")
        expected = _receipt_sha256(self, excluded={"receipt_id", "receipt_sha256"})
        if self.receipt_sha256 != expected:
            raise ValueError("private preview receipt digest mismatch")
        if self.receipt_id != f"private-preview:{expected[:24]}":
            raise ValueError("private preview receipt ID mismatch")
        return self


def assess_coordinate_source(
    *,
    source_format: CoordinateFormat | str,
    acquisition_method: CoordinateAcquisitionMethod | str,
    coordinate_units: str,
) -> CoordinateSourceAssessment:
    """Classify a proposed source without converting or reading coordinates."""

    source_format = CoordinateFormat(source_format)
    acquisition_method = CoordinateAcquisitionMethod(acquisition_method)
    units = coordinate_units.strip().lower()

    decision, rule_ids = _coordinate_source_policy(
        source_format=source_format,
        acquisition_method=acquisition_method,
        coordinate_units=units,
    )

    return CoordinateSourceAssessment(
        source_format=source_format,
        acquisition_method=acquisition_method,
        coordinate_units=units,
        decision=decision,
        rule_ids=rule_ids,
    )


def require_prp10_eligible_source(
    assessment: CoordinateSourceAssessment,
) -> None:
    """Fail closed unless the source is an exact official Angstrom XYZ."""

    if assessment.decision is CoordinateSourceDecision.PRP10_ELIGIBLE:
        return
    rule_id = assessment.rule_ids[0]
    raise CoordinateImportError(
        rule_id,
        "coordinate source is not eligible for the PRP-10 campaign",
    )


def import_official_xyz(
    source_path: str | Path,
    destination_path: str | Path,
    *,
    source_artifact_id: str,
    imported_artifact_id: str,
    source_url: str,
    expected_source_sha256: str,
    archive_member: str | None,
    coordinate_units: str,
    identity_approval_id: str,
    identity_approval_sha256: str,
    license_id: str,
    provenance_kind: OfficialCoordinateProvenance | str,
    provenance_receipt_id: str,
    provenance_receipt_sha256: str,
) -> CoordinateImportReceipt:
    """Validate and copy one official XYZ without changing a single byte."""

    _validate_identifier(source_artifact_id, "source_artifact_id")
    _validate_identifier(imported_artifact_id, "imported_artifact_id")
    _validate_identifier(identity_approval_id, "identity_approval_id")
    _validate_sha256(identity_approval_sha256, "identity_approval_sha256")
    _validate_identifier(provenance_receipt_id, "provenance_receipt_id")
    _validate_sha256(provenance_receipt_sha256, "provenance_receipt_sha256")
    _validate_sha256(expected_source_sha256, "expected_source_sha256")
    _validate_source_url(source_url)
    if archive_member is not None:
        _validate_archive_member(archive_member)
    elif ".xyz" not in urlsplit(source_url).path.lower():
        raise CoordinateImportError(
            RULE_NON_XYZ,
            "a direct official coordinate URL must identify an XYZ artifact",
        )
    if not isinstance(license_id, str) or not license_id.strip():
        raise CoordinateImportError(
            "coordinate.source.license_missing",
            "coordinate source requires an explicit license binding",
        )

    assessment = assess_coordinate_source(
        source_format=CoordinateFormat.XYZ,
        acquisition_method=CoordinateAcquisitionMethod.EXACT_OFFICIAL_FILE,
        coordinate_units=coordinate_units,
    )
    require_prp10_eligible_source(assessment)

    source_bytes = _read_bounded_bytes(source_path)
    source_sha256 = _sha256_bytes(source_bytes)
    if source_sha256 != expected_source_sha256:
        raise CoordinateImportError(
            RULE_SOURCE_HASH,
            "official coordinate bytes do not match the declared digest",
        )
    manifest, atom_order_sha256 = _strict_xyz_manifest(source_bytes)
    copied_sha256 = _copy_exact_bytes(source_bytes, destination_path)
    if copied_sha256 != source_sha256:
        raise CoordinateImportError(
            RULE_SOURCE_HASH,
            "imported coordinate bytes do not match the official source",
        )

    payload = {
        "schema_version": COORDINATE_IMPORT_SCHEMA_VERSION,
        "source_artifact_id": source_artifact_id,
        "imported_artifact_id": imported_artifact_id,
        "source_url": source_url,
        "archive_member": archive_member,
        "source_sha256": source_sha256,
        "imported_sha256": copied_sha256,
        "size_bytes": len(source_bytes),
        "source_format": "xyz",
        "coordinate_units": "angstrom",
        "atom_count": manifest.atom_count,
        "element_counts": manifest.element_counts,
        "atom_order_sha256": atom_order_sha256,
        "ordered_geometry_sha256": manifest.ordered_geometry_sha256,
        "identity_approval_id": identity_approval_id,
        "identity_approval_sha256": identity_approval_sha256,
        "license_id": license_id.strip(),
        "provenance_kind": OfficialCoordinateProvenance(provenance_kind),
        "provenance_receipt_id": provenance_receipt_id,
        "provenance_receipt_sha256": provenance_receipt_sha256,
        "exact_byte_copy_verified": True,
        "prp10_eligible": True,
        "rule_ids": (RULE_PRP10_ELIGIBLE,),
    }
    digest = _sha256_json(_jsonable(payload))
    return CoordinateImportReceipt(
        receipt_id=f"coordinate-import:{digest[:24]}",
        receipt_sha256=digest,
        **payload,
    )


def copy_private_preview_artifact(
    source_path: str | Path,
    destination_path: str | Path,
    *,
    preview_artifact_id: str,
    source_artifact_id: str,
    expected_source_sha256: str,
    source_receipt_id: str,
    source_receipt_sha256: str,
    project_id: str,
    project_sha256: str,
    command_id: str,
    command_sha256: str,
) -> PrivatePreviewArtifactReceipt:
    """Copy private preview bytes and return only a content-addressed binding."""

    for name, value in (
        ("preview_artifact_id", preview_artifact_id),
        ("source_artifact_id", source_artifact_id),
        ("source_receipt_id", source_receipt_id),
        ("project_id", project_id),
        ("command_id", command_id),
    ):
        _validate_identifier(value, name)
    for name, value in (
        ("expected_source_sha256", expected_source_sha256),
        ("source_receipt_sha256", source_receipt_sha256),
        ("project_sha256", project_sha256),
        ("command_sha256", command_sha256),
    ):
        _validate_sha256(value, name)

    source_bytes = _read_bounded_bytes(source_path)
    source_sha256 = _sha256_bytes(source_bytes)
    if source_sha256 != expected_source_sha256:
        raise CoordinateImportError(
            RULE_PREVIEW_SOURCE_HASH,
            "private preview source does not match its bound digest",
        )
    copied_sha256 = _copy_exact_bytes(source_bytes, destination_path)
    if copied_sha256 != source_sha256:
        raise CoordinateImportError(
            RULE_PREVIEW_SOURCE_HASH,
            "private preview copy does not match its bound source",
        )

    payload = {
        "schema_version": PRIVATE_PREVIEW_ARTIFACT_SCHEMA_VERSION,
        "preview_artifact_id": preview_artifact_id,
        "source_artifact_id": source_artifact_id,
        "source_artifact_sha256": source_sha256,
        "source_receipt_id": source_receipt_id,
        "source_receipt_sha256": source_receipt_sha256,
        "project_id": project_id,
        "project_sha256": project_sha256,
        "command_id": command_id,
        "command_sha256": command_sha256,
        "copied_sha256": copied_sha256,
        "size_bytes": len(source_bytes),
        "exact_byte_copy_verified": True,
    }
    digest = _sha256_json(payload)
    return PrivatePreviewArtifactReceipt(
        receipt_id=f"private-preview:{digest[:24]}",
        receipt_sha256=digest,
        **payload,
    )


def _strict_xyz_manifest(source_bytes: bytes):
    try:
        text = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise CoordinateImportError(
            RULE_XYZ_UTF8,
            "official XYZ must be valid UTF-8 text",
        ) from exc

    lines = text.splitlines()
    if len(lines) < 2:
        raise CoordinateImportError(
            RULE_XYZ_MALFORMED,
            "XYZ requires atom-count and comment lines",
        )
    try:
        atom_count = int(lines[0].strip())
    except ValueError as exc:
        raise CoordinateImportError(
            RULE_XYZ_MALFORMED,
            "XYZ atom count is malformed",
        ) from exc
    if atom_count < 1 or len(lines[2 : 2 + atom_count]) != atom_count:
        raise CoordinateImportError(
            RULE_XYZ_MALFORMED,
            "XYZ coordinate count does not match its atom count",
        )
    trailing = [line for line in lines[2 + atom_count :] if line.strip()]
    if trailing:
        try:
            next_count = int(trailing[0].strip())
        except ValueError:
            next_count = 0
        rule_id = RULE_XYZ_MULTI_FRAME if next_count > 0 else RULE_XYZ_MALFORMED
        raise CoordinateImportError(
            rule_id,
            "XYZ contains a second frame or non-frame trailing content",
        )

    symbols: list[str] = []
    for line in lines[2 : 2 + atom_count]:
        tokens = line.split()
        if len(tokens) != 4 or _ELEMENT.fullmatch(tokens[0]) is None:
            raise CoordinateImportError(
                RULE_XYZ_MALFORMED,
                "XYZ rows must contain one element and exactly three coordinates",
            )
        try:
            coordinates = tuple(float(value) for value in tokens[1:])
        except ValueError as exc:
            raise CoordinateImportError(
                RULE_XYZ_MALFORMED,
                "XYZ coordinates must be numeric",
            ) from exc
        if not all(math.isfinite(value) for value in coordinates):
            raise CoordinateImportError(
                RULE_XYZ_MALFORMED,
                "XYZ coordinates must be finite",
            )
        symbols.append(tokens[0])

    try:
        manifest = xyz_text_geometry_manifest(text)
    except ValueError as exc:
        raise CoordinateImportError(
            RULE_XYZ_MALFORMED,
            "XYZ failed deterministic geometry validation",
        ) from exc
    atom_order_sha256 = _sha256_json(
        {"atom_count": atom_count, "symbols": symbols}
    )
    return manifest, atom_order_sha256


def _coordinate_source_policy(
    *,
    source_format: CoordinateFormat,
    acquisition_method: CoordinateAcquisitionMethod,
    coordinate_units: str,
) -> tuple[CoordinateSourceDecision, tuple[str, ...]]:
    forbidden = {
        CoordinateAcquisitionMethod.COORDINATE_TABLE_REWRITE: RULE_TABLE_REWRITE,
        CoordinateAcquisitionMethod.OCR: RULE_OCR,
        CoordinateAcquisitionMethod.SMILES_TO_3D: RULE_SMILES_3D,
        CoordinateAcquisitionMethod.MODEL_GENERATION: RULE_MODEL_GENERATION,
    }
    if acquisition_method in forbidden:
        return CoordinateSourceDecision.REJECTED, (forbidden[acquisition_method],)
    if acquisition_method is CoordinateAcquisitionMethod.FORMAT_CONVERSION:
        return CoordinateSourceDecision.NON_PRP_REFERENCE, (RULE_CONVERSION,)
    if source_format is not CoordinateFormat.XYZ:
        return CoordinateSourceDecision.NON_PRP_REFERENCE, (RULE_NON_XYZ,)
    if coordinate_units.strip().lower() != "angstrom":
        return CoordinateSourceDecision.NON_PRP_REFERENCE, (RULE_UNITS,)
    return CoordinateSourceDecision.PRP10_ELIGIBLE, (RULE_PRP10_ELIGIBLE,)


def _read_bounded_bytes(path: str | Path) -> bytes:
    source = Path(path)
    try:
        if not source.is_file() or source.is_symlink():
            raise OSError
        size = source.stat().st_size
        if size < 1 or size > MAX_COORDINATE_ARTIFACT_BYTES:
            raise CoordinateImportError(
                "coordinate.source.size_invalid",
                "artifact size is outside the bounded import contract",
            )
        content = source.read_bytes()
    except CoordinateImportError:
        raise
    except OSError as exc:
        raise CoordinateImportError(
            "coordinate.source.unreadable",
            "artifact could not be read as a private regular file",
        ) from exc
    if len(content) != size:
        raise CoordinateImportError(
            "coordinate.source.read_size_mismatch",
            "artifact changed during its bounded read",
        )
    return content


def _copy_exact_bytes(content: bytes, destination_path: str | Path) -> str:
    destination = Path(destination_path)
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink() or destination.is_symlink():
        raise CoordinateImportError(
            RULE_DESTINATION_CONFLICT,
            "private destination must be inside an existing real directory",
        )
    if destination.exists():
        existing = _read_bounded_bytes(destination)
        if existing != content:
            raise CoordinateImportError(
                RULE_DESTINATION_CONFLICT,
                "private destination already contains different bytes",
            )
        return _sha256_bytes(existing)

    try:
        with destination.open("xb") as handle:
            handle.write(content)
            handle.flush()
    except OSError as exc:
        raise CoordinateImportError(
            RULE_DESTINATION_CONFLICT,
            "private destination could not be created without overwrite",
        ) from exc

    copied = _read_bounded_bytes(destination)
    if copied != content:
        try:
            destination.unlink()
        except OSError:
            pass
        raise CoordinateImportError(
            RULE_DESTINATION_CONFLICT,
            "private destination failed exact-byte verification",
        )
    return _sha256_bytes(copied)


def _validate_source_url(value: str) -> None:
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or not parts.netloc
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError("coordinate source must use a credential-free HTTPS URL")


def _validate_archive_member(value: str) -> None:
    member = PurePosixPath(value)
    if (
        member.is_absolute()
        or ".." in member.parts
        or member.suffix.lower() != ".xyz"
    ):
        raise ValueError("archive member must be a safe relative XYZ path")


def _validate_identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str) or re.fullmatch(_IDENTIFIER, value) is None:
        raise ValueError(f"{field_name} must be a stable opaque identifier")


def _validate_sha256(value: str, field_name: str) -> None:
    if not isinstance(value, str) or re.fullmatch(_SHA256, value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_json(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _receipt_sha256(receipt: BaseModel, *, excluded: set[str]) -> str:
    payload = receipt.model_dump(mode="json", exclude=excluded)
    return _sha256_json(payload)


__all__ = [
    "COORDINATE_IMPORT_SCHEMA_VERSION",
    "COORDINATE_SOURCE_ASSESSMENT_SCHEMA_VERSION",
    "PRIVATE_PREVIEW_ARTIFACT_SCHEMA_VERSION",
    "CoordinateAcquisitionMethod",
    "CoordinateFormat",
    "CoordinateImportError",
    "CoordinateImportReceipt",
    "CoordinateSourceAssessment",
    "CoordinateSourceDecision",
    "OfficialCoordinateProvenance",
    "PrivatePreviewArtifactReceipt",
    "assess_coordinate_source",
    "copy_private_preview_artifact",
    "import_official_xyz",
    "require_prp10_eligible_source",
]
