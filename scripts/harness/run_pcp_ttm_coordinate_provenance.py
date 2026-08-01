#!/usr/bin/env python3
"""Audit and privately import the PCP--TTM Zenodo XYZ artifacts.

The requested record (15679510) is an earlier version of the Zenodo concept
record whose latest published version is 17301951.  This slice downloads both
versions only into an ignored private directory, validates Zenodo's declared
MD5 checksums, computes SHA-256, and imports only exact XYZ bytes that are also
unchanged in the latest record.  Version-divergent files remain blocked.

No coordinate text or private filesystem path is written to the public
receipt.  No structure conversion, native-input generation, chemistry engine,
or scheduler is invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import requests

from chemsmart.agent.coordinate_import import (
    CoordinateAcquisitionMethod,
    CoordinateFormat,
    OfficialCoordinateProvenance,
    assess_coordinate_source,
    import_official_xyz,
)


SCHEMA_VERSION = "chemsmart.prp10-coordinate-provenance.v1"
PAPER_DOI = "10.1039/D5TC02343B"
PAPER_URL = "https://pubs.rsc.org/en/content/articlehtml/2026/tc/d5tc02343b"
REQUESTED_RECORD_ID = 15679510
EXPECTED_LATEST_RECORD_ID = 17301951
EXPECTED_CONCEPT_DOI = "10.5281/zenodo.15679509"
EXPECTED_LICENSE_ID = "cc-by-4.0"
ZENODO_API_ORIGIN = "https://zenodo.org"
MAX_METADATA_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024

IDENTITY_AUTHORITY = {
    "authority": "user-approved PRP-10 coordinate-source contract",
    "scope": (
        "exact official single-frame XYZ artifacts may be imported after "
        "provenance and license verification"
    ),
    "coordinate_units": "angstrom",
    "identity_boundary": (
        "bind the literal official depositor filename to its exact bytes; do "
        "not infer chemical meaning for filename tokens"
    ),
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_zenodo_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "zenodo.org":
        raise ValueError("Zenodo evidence URL must use the official HTTPS host")


def _safe_filename(key: str) -> str:
    path = PurePosixPath(key)
    if path.is_absolute() or len(path.parts) != 1 or path.name != key:
        raise ValueError("Zenodo file key is not a safe single filename")
    if not key.lower().endswith(".xyz"):
        raise ValueError("coordinate campaign accepts only XYZ assets")
    return key


def _write_private(path: Path, content: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(content)
    path.chmod(0o600)


def _get_bounded(
    session: requests.Session,
    url: str,
    *,
    limit: int,
    timeout_seconds: float,
) -> tuple[bytes, str]:
    _validate_zenodo_url(url)
    response = session.get(
        url,
        headers={"Accept": "application/json"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    _validate_zenodo_url(response.url)
    content = response.content
    if not content or len(content) > limit:
        raise ValueError("Zenodo response is empty or exceeds its byte bound")
    return content, response.url


def _read_metadata(
    session: requests.Session,
    url: str,
    *,
    private_path: Path,
    timeout_seconds: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    content, final_url = _get_bounded(
        session,
        url,
        limit=MAX_METADATA_BYTES,
        timeout_seconds=timeout_seconds,
    )
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Zenodo metadata response is not JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Zenodo metadata response is not an object")
    _write_private(private_path, content)
    return payload, {
        "request_url": url,
        "final_url": final_url,
        "sha256": _sha256_bytes(content),
        "size_bytes": len(content),
        "private_store_ref": f"private-store:{private_path.stem}",
    }


def _record_observation(
    payload: dict[str, Any],
    response_observation: dict[str, Any],
) -> dict[str, Any]:
    metadata = payload.get("metadata")
    links = payload.get("links")
    files = payload.get("files")
    if not isinstance(metadata, dict) or not isinstance(links, dict):
        raise ValueError("Zenodo record is missing metadata or links")
    if not isinstance(files, list) or not files:
        raise ValueError("Zenodo record has no files")
    license_record = metadata.get("license")
    if not isinstance(license_record, dict):
        raise ValueError("Zenodo record has no structured license")
    concept_doi = payload.get("conceptdoi")
    record = {
        "record_id": int(payload["id"]),
        "doi": str(payload["doi"]),
        "concept_doi": str(concept_doi),
        "title": str(metadata["title"]),
        "publication_date": str(metadata["publication_date"]),
        "created": str(payload["created"]),
        "updated": str(payload["updated"]),
        "status": str(payload["status"]),
        "access_right": str(metadata["access_right"]),
        "license_id": str(license_record["id"]),
        "record_url": str(links["self_html"]),
        "api_url": str(links["self"]),
        "latest_api_url": str(links["latest"]),
        "metadata_response": response_observation,
    }
    for url_key in ("record_url", "api_url", "latest_api_url"):
        _validate_zenodo_url(record[url_key])
    if record["concept_doi"] != EXPECTED_CONCEPT_DOI:
        raise ValueError("Zenodo concept DOI does not match the pinned campaign")
    if record["license_id"] != EXPECTED_LICENSE_ID:
        raise ValueError("Zenodo license differs from the pinned campaign license")
    return record


def _xyz_files(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in payload["files"]:
        if not isinstance(raw, dict):
            raise ValueError("Zenodo file metadata is malformed")
        key = str(raw["key"])
        if not key.lower().endswith(".xyz"):
            continue
        key = _safe_filename(key)
        links = raw.get("links")
        if not isinstance(links, dict):
            raise ValueError("Zenodo file has no links object")
        url = str(links["self"])
        _validate_zenodo_url(url)
        checksum = str(raw["checksum"])
        if not checksum.startswith("md5:") or len(checksum) != 36:
            raise ValueError("Zenodo XYZ file lacks its expected MD5 checksum")
        if key in result:
            raise ValueError("Zenodo record contains a duplicate XYZ key")
        result[key] = {
            "filename": key,
            "size_bytes": int(raw["size"]),
            "zenodo_md5": checksum.removeprefix("md5:"),
            "download_url": url,
        }
    if not result:
        raise ValueError("Zenodo record contains no XYZ assets")
    return result


def _download_xyz(
    session: requests.Session,
    metadata: dict[str, Any],
    *,
    private_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    content, final_url = _get_bounded(
        session,
        str(metadata["download_url"]),
        limit=MAX_ARTIFACT_BYTES,
        timeout_seconds=timeout_seconds,
    )
    observed_md5 = hashlib.md5(content, usedforsecurity=False).hexdigest()
    if observed_md5 != metadata["zenodo_md5"]:
        raise ValueError("downloaded XYZ does not match Zenodo's MD5 checksum")
    if len(content) != metadata["size_bytes"]:
        raise ValueError("downloaded XYZ does not match Zenodo's byte size")
    _write_private(private_path, content)
    return {
        **metadata,
        "final_url": final_url,
        "sha256": _sha256_bytes(content),
        "private_store_ref": f"private-store:{private_path.parent.name}/{metadata['filename']}",
    }


def _identity_approval(filename: str, current_sha256: str) -> dict[str, Any]:
    payload = {
        **IDENTITY_AUTHORITY,
        "paper_doi": PAPER_DOI,
        "zenodo_concept_doi": EXPECTED_CONCEPT_DOI,
        "latest_record_id": EXPECTED_LATEST_RECORD_ID,
        "official_filename": filename,
        "official_sha256": current_sha256,
    }
    digest = _sha256_json(payload)
    return {
        "approval_id": f"approval:pcp-ttm:{digest[:24]}",
        "approval_sha256": digest,
        "binding": payload,
    }


def _provenance_binding(
    *,
    filename: str,
    requested: dict[str, Any],
    current: dict[str, Any],
    requested_record: dict[str, Any],
    current_record: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "paper_doi": PAPER_DOI,
        "zenodo_concept_doi": EXPECTED_CONCEPT_DOI,
        "requested_record_id": requested_record["record_id"],
        "requested_record_doi": requested_record["doi"],
        "latest_record_id": current_record["record_id"],
        "latest_record_doi": current_record["doi"],
        "license_id": requested_record["license_id"],
        "filename": filename,
        "requested_download_url": requested["download_url"],
        "requested_sha256": requested["sha256"],
        "latest_download_url": current["download_url"],
        "latest_sha256": current["sha256"],
        "exact_version_match": requested["sha256"] == current["sha256"],
    }
    digest = _sha256_json(payload)
    return {
        "provenance_receipt_id": f"retrieval:pcp-ttm:{digest[:24]}",
        "provenance_receipt_sha256": digest,
        "binding": payload,
    }


def _build_receipt(
    *,
    started_at: str,
    finished_at: str,
    requested_record: dict[str, Any],
    current_record: dict[str, Any],
    assets: list[dict[str, Any]],
) -> dict[str, Any]:
    eligible = sum(asset["state"] == "validated_private_import" for asset in assets)
    blocked = sum(asset["state"] == "blocked_version_conflict" for asset in assets)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "campaign_slice_id": "prp10-pcp-ttm-coordinate-provenance-2026-08-02",
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "paper": {
            "doi": PAPER_DOI,
            "publisher_url": PAPER_URL,
            "publisher_data_record_doi": "10.5281/zenodo.17301951",
            "binding_status": "publisher_locator_and_zenodo_concept_version_match",
        },
        "coordinate_contract": {
            **IDENTITY_AUTHORITY,
            "conversion_performed": False,
            "coordinate_generation_performed": False,
        },
        "requested_record": requested_record,
        "latest_record": current_record,
        "assets": assets,
        "summary": {
            "xyz_assets_in_requested_record": len(assets),
            "validated_private_imports": eligible,
            "blocked_version_conflicts": blocked,
            "record_relation": "same_concept_doi_earlier_and_latest_versions",
            "paper_coordinate_state": (
                "blocked_partial_version_conflict" if blocked else "validated"
            ),
            "chemistry_engine_invocations": 0,
            "hpc_invocations": 0,
            "native_inputs_generated": 0,
            "coordinate_bytes_in_public_receipt": False,
            "private_paths_in_public_receipt": False,
        },
    }
    digest = _sha256_json(payload)
    return {
        "receipt_id": f"prp10-coordinate-provenance:{digest[:24]}",
        "receipt_sha256": digest,
        **payload,
    }


def run(
    *,
    run_root: Path,
    receipt_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    if run_root.exists():
        raise FileExistsError(f"private run root already exists: {run_root}")
    if receipt_path.exists():
        raise FileExistsError(f"public receipt already exists: {receipt_path}")
    private_root = run_root / "private"
    private_root.mkdir(mode=0o700, parents=True)
    started_at = _utc_now()

    session = requests.Session()
    session.trust_env = False
    requested_payload, requested_response = _read_metadata(
        session,
        f"{ZENODO_API_ORIGIN}/api/records/{REQUESTED_RECORD_ID}",
        private_path=private_root / "metadata" / "requested-record.json",
        timeout_seconds=timeout_seconds,
    )
    latest_url = str(requested_payload["links"]["latest"])
    current_payload, current_response = _read_metadata(
        session,
        latest_url,
        private_path=private_root / "metadata" / "latest-record.json",
        timeout_seconds=timeout_seconds,
    )
    requested_record = _record_observation(requested_payload, requested_response)
    current_record = _record_observation(current_payload, current_response)
    if requested_record["record_id"] != REQUESTED_RECORD_ID:
        raise ValueError("requested Zenodo record ID changed unexpectedly")
    if current_record["record_id"] != EXPECTED_LATEST_RECORD_ID:
        raise ValueError("latest Zenodo version differs from the pinned article record")
    if requested_record["concept_doi"] != current_record["concept_doi"]:
        raise ValueError("requested and latest records are not concept versions")

    requested_files = _xyz_files(requested_payload)
    current_files = _xyz_files(current_payload)
    if set(requested_files) != set(current_files):
        raise ValueError("XYZ file inventory differs between concept versions")

    assets: list[dict[str, Any]] = []
    for filename in sorted(requested_files):
        requested = _download_xyz(
            session,
            requested_files[filename],
            private_path=private_root / "source" / str(REQUESTED_RECORD_ID) / filename,
            timeout_seconds=timeout_seconds,
        )
        current = _download_xyz(
            session,
            current_files[filename],
            private_path=private_root / "source" / str(EXPECTED_LATEST_RECORD_ID) / filename,
            timeout_seconds=timeout_seconds,
        )
        assessment = assess_coordinate_source(
            source_format=CoordinateFormat.XYZ,
            acquisition_method=CoordinateAcquisitionMethod.EXACT_OFFICIAL_FILE,
            coordinate_units="angstrom",
        )
        provenance = _provenance_binding(
            filename=filename,
            requested=requested,
            current=current,
            requested_record=requested_record,
            current_record=current_record,
        )
        common = {
            "filename": filename,
            "requested": requested,
            "latest": current,
            "source_assessment": assessment.model_dump(mode="json"),
            "provenance": provenance,
            "version_relation": (
                "exact_byte_match"
                if requested["sha256"] == current["sha256"]
                else "sha256_divergent"
            ),
        }
        if requested["sha256"] != current["sha256"]:
            assets.append(
                {
                    **common,
                    "identity_approval": None,
                    "coordinate_import_receipt": None,
                    "state": "blocked_version_conflict",
                    "blocker_rule_ids": (
                        "coordinate.provenance.superseded_version_conflict",
                    ),
                }
            )
            continue

        approval = _identity_approval(filename, current["sha256"])
        imported_path = private_root / "imported" / filename
        imported_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        import_receipt = import_official_xyz(
            private_root / "source" / str(REQUESTED_RECORD_ID) / filename,
            imported_path,
            source_artifact_id=f"source:zenodo:{requested['sha256'][:24]}",
            imported_artifact_id=f"geometry:pcp-ttm:{requested['sha256'][:24]}",
            source_url=requested["download_url"],
            expected_source_sha256=requested["sha256"],
            archive_member=None,
            coordinate_units="angstrom",
            identity_approval_id=approval["approval_id"],
            identity_approval_sha256=approval["approval_sha256"],
            license_id=requested_record["license_id"],
            provenance_kind=OfficialCoordinateProvenance.OFFICIAL_REPOSITORY,
            provenance_receipt_id=provenance["provenance_receipt_id"],
            provenance_receipt_sha256=provenance["provenance_receipt_sha256"],
        )
        assets.append(
            {
                **common,
                "identity_approval": approval,
                "coordinate_import_receipt": import_receipt.model_dump(mode="json"),
                "state": "validated_private_import",
                "blocker_rule_ids": (),
            }
        )

    receipt = _build_receipt(
        started_at=started_at,
        finished_at=_utc_now(),
        requested_record=requested_record,
        current_record=current_record,
        assets=assets,
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path(
            "tmp/prp10-adaptive/"
            "pcp-ttm-coordinate-provenance-2026-08-02-02"
        ),
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path(
            "docs/evaluation/receipts/"
            "pcp-ttm-coordinate-provenance-2026-08-02.json"
        ),
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.timeout_seconds > 120:
        parser.error("--timeout-seconds must be in (0, 120]")
    receipt = run(
        run_root=args.run_root,
        receipt_path=args.receipt,
        timeout_seconds=args.timeout_seconds,
    )
    print(
        json.dumps(
            {
                "receipt_id": receipt["receipt_id"],
                "receipt_sha256": receipt["receipt_sha256"],
                "summary": receipt["summary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
