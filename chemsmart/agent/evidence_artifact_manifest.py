"""Deterministic exact-byte manifests for agent evidence directories."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EVIDENCE_ARTIFACT_MANIFEST_SCHEMA_VERSION = (
    "chemsmart.evidence-artifact-manifest.v1"
)
EVIDENCE_ARTIFACT_MANIFEST_V2_SCHEMA_VERSION = (
    "chemsmart.evidence-artifact-manifest.v2"
)
_SHA256 = r"^[0-9a-f]{64}$"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class EvidenceArtifactV1(_Contract):
    locator: str = Field(min_length=1, max_length=1000)
    artifact_sha256: str = Field(pattern=_SHA256)
    size_bytes: int = Field(ge=0)

    @field_validator("locator")
    @classmethod
    def _safe_relative_locator(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
            raise ValueError("evidence artifact locator must be safe and relative")
        return value


class EvidenceArtifactManifestV1(_Contract):
    schema_version: Literal[
        "chemsmart.evidence-artifact-manifest.v1"
    ] = EVIDENCE_ARTIFACT_MANIFEST_SCHEMA_VERSION
    manifest_id: str = Field(pattern=_IDENTIFIER)
    scope: Literal["public", "private"]
    artifact_count: int = Field(ge=1)
    total_bytes: int = Field(ge=0)
    artifacts: tuple[EvidenceArtifactV1, ...] = Field(min_length=1)
    manifest_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _manifest_is_canonical(self) -> "EvidenceArtifactManifestV1":
        locators = tuple(item.locator for item in self.artifacts)
        if locators != tuple(sorted(set(locators))):
            raise ValueError("evidence artifacts must be unique and sorted")
        if self.artifact_count != len(self.artifacts):
            raise ValueError("evidence artifact count is inconsistent")
        if self.total_bytes != sum(item.size_bytes for item in self.artifacts):
            raise ValueError("evidence artifact byte total is inconsistent")
        if self.manifest_sha256 != evidence_artifact_manifest_sha256(self):
            raise ValueError("evidence artifact manifest digest mismatch")
        return self


class EvidenceArtifactManifestV2(_Contract):
    """Manifest with an explicit, replayable final-envelope exclusion set."""

    schema_version: Literal[
        "chemsmart.evidence-artifact-manifest.v2"
    ] = EVIDENCE_ARTIFACT_MANIFEST_V2_SCHEMA_VERSION
    manifest_id: str = Field(pattern=_IDENTIFIER)
    scope: Literal["public", "private"]
    excluded_locators: tuple[str, ...] = Field(min_length=1)
    artifact_count: int = Field(ge=1)
    total_bytes: int = Field(ge=0)
    artifacts: tuple[EvidenceArtifactV1, ...] = Field(min_length=1)
    manifest_sha256: str = Field(pattern=_SHA256)

    @field_validator("excluded_locators")
    @classmethod
    def _excluded_are_safe(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("excluded locators must be unique and sorted")
        for value in values:
            EvidenceArtifactV1(
                locator=value,
                artifact_sha256="0" * 64,
                size_bytes=0,
            )
        if "artifact-manifest.json" not in values:
            raise ValueError("manifest must explicitly exclude its own bytes")
        return values

    @model_validator(mode="after")
    def _manifest_is_canonical(self) -> "EvidenceArtifactManifestV2":
        locators = tuple(item.locator for item in self.artifacts)
        if locators != tuple(sorted(set(locators))):
            raise ValueError("evidence artifacts must be unique and sorted")
        if set(locators) & set(self.excluded_locators):
            raise ValueError("excluded artifact was included in the manifest")
        if self.artifact_count != len(self.artifacts):
            raise ValueError("evidence artifact count is inconsistent")
        if self.total_bytes != sum(item.size_bytes for item in self.artifacts):
            raise ValueError("evidence artifact byte total is inconsistent")
        if self.manifest_sha256 != evidence_artifact_manifest_v2_sha256(self):
            raise ValueError("evidence artifact manifest V2 digest mismatch")
        return self


def build_evidence_artifact_manifest(
    root: Path,
    *,
    manifest_id: str,
    scope: Literal["public", "private"],
    excluded_locators: tuple[str, ...] = (),
) -> EvidenceArtifactManifestV1:
    """Hash every regular file below ``root`` without recording its host path."""

    resolved_root = root.resolve(strict=True)
    excluded = set(excluded_locators)
    artifacts: list[EvidenceArtifactV1] = []
    for path in sorted(resolved_root.rglob("*")):
        if path.is_symlink():
            raise ValueError("evidence manifests do not follow symbolic links")
        if not path.is_file():
            continue
        locator = path.relative_to(resolved_root).as_posix()
        if locator in excluded:
            continue
        payload = path.read_bytes()
        artifacts.append(
            EvidenceArtifactV1(
                locator=locator,
                artifact_sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
            )
        )
    if not artifacts:
        raise ValueError("evidence manifest scope contains no artifacts")
    body = {
        "schema_version": EVIDENCE_ARTIFACT_MANIFEST_SCHEMA_VERSION,
        "manifest_id": manifest_id,
        "scope": scope,
        "artifact_count": len(artifacts),
        "total_bytes": sum(item.size_bytes for item in artifacts),
        "artifacts": [item.model_dump(mode="json") for item in artifacts],
        "manifest_sha256": "0" * 64,
    }
    body["manifest_sha256"] = _manifest_sha256(body)
    return EvidenceArtifactManifestV1.model_validate(body)


def verify_evidence_artifact_manifest(
    root: Path,
    manifest: EvidenceArtifactManifestV1,
) -> None:
    """Replay every exact-byte binding and reject extra or missing files."""

    excluded = ("artifact-manifest.json",)
    replayed = build_evidence_artifact_manifest(
        root,
        manifest_id=manifest.manifest_id,
        scope=manifest.scope,
        excluded_locators=excluded,
    )
    if replayed != manifest:
        raise ValueError("evidence artifact manifest does not replay")


def build_evidence_artifact_manifest_v2(
    root: Path,
    *,
    manifest_id: str,
    scope: Literal["public", "private"],
    excluded_locators: tuple[str, ...],
) -> EvidenceArtifactManifestV2:
    canonical_exclusions = tuple(sorted(set(excluded_locators)))
    if canonical_exclusions != excluded_locators:
        raise ValueError("V2 exclusions must be unique and sorted")
    resolved_root = root.resolve(strict=True)
    artifacts: list[EvidenceArtifactV1] = []
    for path in sorted(resolved_root.rglob("*")):
        if path.is_symlink():
            raise ValueError("evidence manifests do not follow symbolic links")
        if not path.is_file():
            continue
        locator = path.relative_to(resolved_root).as_posix()
        if locator in canonical_exclusions:
            continue
        payload = path.read_bytes()
        artifacts.append(
            EvidenceArtifactV1(
                locator=locator,
                artifact_sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
            )
        )
    if not artifacts:
        raise ValueError("evidence manifest scope contains no artifacts")
    body = {
        "schema_version": EVIDENCE_ARTIFACT_MANIFEST_V2_SCHEMA_VERSION,
        "manifest_id": manifest_id,
        "scope": scope,
        "excluded_locators": canonical_exclusions,
        "artifact_count": len(artifacts),
        "total_bytes": sum(item.size_bytes for item in artifacts),
        "artifacts": [item.model_dump(mode="json") for item in artifacts],
        "manifest_sha256": "0" * 64,
    }
    body["manifest_sha256"] = _manifest_sha256(body)
    return EvidenceArtifactManifestV2.model_validate(body)


def verify_evidence_artifact_manifest_v2(
    root: Path,
    manifest: EvidenceArtifactManifestV2,
) -> None:
    replayed = build_evidence_artifact_manifest_v2(
        root,
        manifest_id=manifest.manifest_id,
        scope=manifest.scope,
        excluded_locators=manifest.excluded_locators,
    )
    if replayed != manifest:
        raise ValueError("evidence artifact manifest V2 does not replay")


def evidence_artifact_manifest_sha256(
    value: EvidenceArtifactManifestV1,
) -> str:
    return _manifest_sha256(value.model_dump(mode="json"))


def evidence_artifact_manifest_v2_sha256(
    value: EvidenceArtifactManifestV2,
) -> str:
    return _manifest_sha256(value.model_dump(mode="json"))


def manifest_json_bytes(value: EvidenceArtifactManifestV1) -> bytes:
    return (
        json.dumps(
            value.model_dump(mode="json"),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def manifest_v2_json_bytes(value: EvidenceArtifactManifestV2) -> bytes:
    return (
        json.dumps(
            value.model_dump(mode="json"),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _manifest_sha256(value: dict[str, object]) -> str:
    body = {key: item for key, item in value.items() if key != "manifest_sha256"}
    return hashlib.sha256(
        json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "EVIDENCE_ARTIFACT_MANIFEST_SCHEMA_VERSION",
    "EVIDENCE_ARTIFACT_MANIFEST_V2_SCHEMA_VERSION",
    "EvidenceArtifactManifestV1",
    "EvidenceArtifactManifestV2",
    "EvidenceArtifactV1",
    "build_evidence_artifact_manifest",
    "build_evidence_artifact_manifest_v2",
    "evidence_artifact_manifest_sha256",
    "evidence_artifact_manifest_v2_sha256",
    "manifest_json_bytes",
    "manifest_v2_json_bytes",
    "verify_evidence_artifact_manifest",
    "verify_evidence_artifact_manifest_v2",
]
