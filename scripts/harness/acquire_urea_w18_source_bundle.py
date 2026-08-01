#!/usr/bin/env python3
"""Acquire and audit the public urea--W18 paper source bundle.

This script performs three hypothesis-bound network observations:

* retrieve the article through the official Elsevier DOI endpoint;
* retrieve official Zenodo record 8285735 metadata; and
* retrieve the record's ``Supporting_Material.zip`` bytes.

Licensed source bytes are written only below the caller-provided ignored
private run root.  The public receipt contains locators, hashes, byte counts,
license observations, ZIP-member metadata, and deterministic XYZ syntax
observations.  It deliberately does not infer molecular identity, charge,
multiplicity, or archive-member scientific roles, and it creates no coordinate
import receipt without a separately bound identity approval.

No native input, chemistry engine, scheduler, model API, or HPC system is
invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import time
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urlsplit

import requests
from dotenv import dotenv_values

from chemsmart.agent.api_access import (
    ApiProvider,
    ApiUsageBudget,
    CredentialAccessController,
    CredentialProbeError,
    CredentialProbeObservation,
    CredentialStatus,
)
from chemsmart.agent.geometry_identity import ordered_geometry_manifest


SCHEMA_VERSION = "chemsmart.prp10-source-acquisition.v1"
CAMPAIGN_SLICE_ID = "prp10-explicit-cluster-urea-w18-source-2026-08-02"
PAPER_DOI = "10.1016/j.icarus.2023.115848"
PAPER_PII = "S001910352300427X"
PAPER_TITLE = (
    "Synthesis of urea on the surface of interstellar water ice clusters. "
    "A quantum chemical study"
)
ELSEVIER_ORIGIN = "https://api.elsevier.com"
ELSEVIER_PATH = f"/content/article/doi/{quote(PAPER_DOI, safe='')}"
ZENODO_ORIGIN = "https://zenodo.org"
ZENODO_RECORD_ID = 8_285_735
ZENODO_RECORD_DOI = "10.5281/zenodo.8285735"
ZENODO_RECORD_URL = f"{ZENODO_ORIGIN}/api/records/{ZENODO_RECORD_ID}"
EXPECTED_LICENSE_ID = "cc-by-4.0"
ARCHIVE_NAME = "Supporting_Material.zip"
EXPECTED_ARCHIVE_MD5 = "5281173814f215dda06db86789bed0d1"
EXPECTED_ARCHIVE_SHA256 = (
    "07e14f9fa7823cbdb845101f192a7b063b7047d7607f86f42d1174ee9d94180a"
)

MAX_ELSEVIER_BYTES = 64 * 1024 * 1024
MAX_METADATA_BYTES = 4 * 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 512
MAX_TRANSIENT_RETRIES = 2
MAX_RETRY_AFTER_SECONDS = 30.0
REQUEST_TIMEOUT_SECONDS = 90.0
TASK_WALL_TIME_SECONDS = 900.0

_ELEMENT = re.compile(r"^[A-Z][a-z]?$|^X$")


class _SanitizedTransportFailure(RuntimeError):
    """Transport failure whose text cannot contain a provider response."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_private_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_ancestors: list[Path] = []
    cursor = path.parent
    while cursor.name != "private":
        if cursor.parent == cursor:
            raise ValueError("private artifact is outside a private store")
        private_ancestors.append(cursor)
        cursor = cursor.parent
    private_ancestors.append(cursor)
    for directory in private_ancestors:
        directory.chmod(0o700)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"private artifact already exists: {path.name}")
    with path.open("xb") as handle:
        handle.write(content)
    path.chmod(0o600)


def _safe_member_name(name: str) -> PurePosixPath:
    if not name or "\\" in name or "\x00" in name:
        raise ValueError("ZIP member name is unsafe")
    member = PurePosixPath(name)
    if member.is_absolute() or ".." in member.parts:
        raise ValueError("ZIP member path escapes the archive root")
    return member


def _validate_https_url(url: str, *, host: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != host
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"source URL must remain on official host {host}")


def _read_stream_bounded(response: requests.Response, *, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_content(chunk_size=65_536):
        if not chunk:
            continue
        size += len(chunk)
        if size > limit:
            response.close()
            raise _SanitizedTransportFailure("response_too_large")
        chunks.append(chunk)
    body = b"".join(chunks)
    if not body:
        raise _SanitizedTransportFailure("empty_response")
    return body


def _retry_delay(
    *,
    http_status: int | None,
    retry_after: str | None,
    timed_out: bool,
    ordinal: int,
) -> tuple[str, float | None]:
    if http_status == 401:
        return "credential_invalid", None
    if http_status == 403:
        return "entitlement_denied", None
    if http_status == 429:
        try:
            delay = float(retry_after) if retry_after is not None else 1.0
        except ValueError:
            delay = 1.0
        if not math.isfinite(delay) or delay < 0:
            delay = 1.0
        return "rate_limited", min(delay, MAX_RETRY_AFTER_SECONDS)
    if timed_out:
        return "timeout", min(2.0 ** max(0, ordinal - 1), 8.0)
    if http_status is not None and 500 <= http_status < 600:
        return "server_5xx", min(2.0 ** max(0, ordinal - 1), 8.0)
    if http_status is not None and 200 <= http_status < 300:
        return "none", None
    return "other_http_error", None


def _request_once(
    session: requests.Session,
    *,
    url: str,
    host: str,
    headers: dict[str, str],
    byte_limit: int,
) -> tuple[int | None, dict[str, str], bytes, int, bool]:
    _validate_https_url(url, host=host)
    started = time.perf_counter()
    try:
        response = session.get(
            url,
            headers=headers,
            timeout=(10.0, REQUEST_TIMEOUT_SECONDS),
            stream=True,
            allow_redirects=True,
        )
        _validate_https_url(response.url, host=host)
        body = _read_stream_bounded(response, limit=byte_limit)
        selected_headers = {
            key.lower(): value
            for key, value in response.headers.items()
            if key.lower() in {"content-type", "retry-after"}
        }
        return (
            response.status_code,
            selected_headers,
            body,
            int((time.perf_counter() - started) * 1000),
            False,
        )
    except requests.Timeout:
        return (
            None,
            {},
            b"",
            int((time.perf_counter() - started) * 1000),
            True,
        )
    except requests.RequestException:
        raise _SanitizedTransportFailure("connection") from None


def _bounded_public_get(
    session: requests.Session,
    *,
    case_id: str,
    url: str,
    host: str,
    accept: str,
    byte_limit: int,
    deadline: float,
) -> tuple[bytes | None, list[dict[str, Any]], str]:
    attempts: list[dict[str, Any]] = []
    for ordinal in range(1, MAX_TRANSIENT_RETRIES + 2):
        if time.monotonic() >= deadline:
            return None, attempts, "task_wall_time_exhausted"
        try:
            status, headers, body, latency_ms, timed_out = _request_once(
                session,
                url=url,
                host=host,
                headers={"Accept": accept},
                byte_limit=byte_limit,
            )
            connection_error = False
        except _SanitizedTransportFailure:
            status, headers, body, latency_ms, timed_out = (
                None,
                {},
                b"",
                0,
                False,
            )
            connection_error = True
        error_class, delay = _retry_delay(
            http_status=status,
            retry_after=headers.get("retry-after"),
            timed_out=timed_out,
            ordinal=ordinal,
        )
        if connection_error:
            error_class = "connection"
            delay = min(2.0 ** max(0, ordinal - 1), 8.0)
        attempts.append(
            {
                "attempt_id": f"{case_id}:attempt:{ordinal}",
                "ordinal": ordinal,
                "http_status": status,
                "latency_ms": latency_ms,
                "response_bytes": len(body),
                "response_sha256": _sha256_bytes(body),
                "error_class": error_class,
                "retry_reason": error_class if delay is not None else None,
            }
        )
        if status is not None and 200 <= status < 300:
            return body, attempts, "observed"
        if delay is None or ordinal > MAX_TRANSIENT_RETRIES:
            return None, attempts, error_class
        if time.monotonic() + delay >= deadline:
            return None, attempts, "task_wall_time_exhausted"
        time.sleep(delay)
    raise AssertionError("bounded public request loop did not terminate")


def _bounded_elsevier_get(
    session: requests.Session,
    *,
    controller: CredentialAccessController,
    case_id: str,
    deadline: float,
) -> tuple[bytes | None, list[dict[str, Any]], str]:
    attempts: list[dict[str, Any]] = []
    url = ELSEVIER_ORIGIN + ELSEVIER_PATH
    for ordinal in range(1, MAX_TRANSIENT_RETRIES + 2):
        if time.monotonic() >= deadline:
            return None, attempts, "task_wall_time_exhausted"
        one_request_budget = ApiUsageBudget(1)
        permit = controller.prepare_status_probe(
            ApiProvider.ELSEVIER,
            caller="chemsmart-prp10-source-acquisition",
            purpose=case_id,
            budget=one_request_budget,
        )
        captured: dict[str, Any] = {}

        def operation(secret: str, origin: str) -> CredentialProbeObservation:
            if origin != ELSEVIER_ORIGIN:
                raise _SanitizedTransportFailure("origin_mismatch")
            try:
                status, headers, body, latency_ms, timed_out = _request_once(
                    session,
                    url=url,
                    host="api.elsevier.com",
                    headers={
                        "Accept": "application/json",
                        "X-ELS-APIKey": secret,
                        "X-ELS-ResourceVersion": "XOCS",
                    },
                    byte_limit=MAX_ELSEVIER_BYTES,
                )
            except _SanitizedTransportFailure:
                captured["connection_error"] = True
                raise
            captured.update(
                {
                    "http_status": status,
                    "headers": headers,
                    "body": body,
                    "latency_ms": latency_ms,
                    "timed_out": timed_out,
                }
            )
            if status == 403:
                return CredentialProbeObservation(
                    CredentialStatus.INVALID_ENTITLEMENT
                )
            if status is None or not 200 <= status < 300:
                raise _SanitizedTransportFailure("provider_status")
            return CredentialProbeObservation(CredentialStatus.VALID)

        credential_status = "unknown"
        try:
            status_receipt = controller.invoke_authorized_probe(permit, operation)
            credential_status = status_receipt.status.value
        except (CredentialProbeError, _SanitizedTransportFailure):
            pass

        status = captured.get("http_status")
        headers = captured.get("headers") or {}
        body = captured.get("body") or b""
        timed_out = bool(captured.get("timed_out"))
        error_class, delay = _retry_delay(
            http_status=status,
            retry_after=headers.get("retry-after"),
            timed_out=timed_out,
            ordinal=ordinal,
        )
        if captured.get("connection_error"):
            error_class = "connection"
            delay = min(2.0 ** max(0, ordinal - 1), 8.0)
        attempts.append(
            {
                "attempt_id": f"{case_id}:attempt:{ordinal}",
                "ordinal": ordinal,
                "http_status": status,
                "credential_status": credential_status,
                "latency_ms": int(captured.get("latency_ms") or 0),
                "response_bytes": len(body),
                "response_sha256": _sha256_bytes(body),
                "error_class": error_class,
                "retry_reason": error_class if delay is not None else None,
            }
        )
        if status is not None and 200 <= status < 300:
            return body, attempts, "observed"
        if delay is None or ordinal > MAX_TRANSIENT_RETRIES:
            return None, attempts, error_class
        if time.monotonic() + delay >= deadline:
            return None, attempts, "task_wall_time_exhausted"
        time.sleep(delay)
    raise AssertionError("bounded Elsevier request loop did not terminate")


def _credential_environment(api_env: Path) -> dict[str, str]:
    values = {
        str(key): str(value)
        for key, value in dotenv_values(api_env).items()
        if key and value
    }
    selected = next(
        (
            values[name]
            for name in (
                "CHEMSMART_ELSEVIER_API_KEY",
                "ELSEVIER_API_KEY",
                "Elsivier_api_key",
            )
            if values.get(name)
        ),
        None,
    )
    values.clear()
    if selected is None:
        return {}
    return {"CHEMSMART_ELSEVIER_API_KEY": selected}


def _article_observation(body: bytes | None, transport_state: str) -> dict[str, Any]:
    if body is None:
        return {
            "state": transport_state,
            "container_present": False,
            "full_text_present": False,
            "validation_rule_ids": ("paper.source.full_text_unavailable",),
        }
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "state": "invalid_json",
            "container_present": False,
            "full_text_present": False,
            "validation_rule_ids": ("paper.source.full_text_invalid_json",),
        }
    root = payload.get("full-text-retrieval-response")
    if not isinstance(root, dict):
        return {
            "state": "invalid_shape",
            "container_present": False,
            "full_text_present": False,
            "validation_rule_ids": ("paper.source.full_text_container_missing",),
        }
    core = root.get("coredata")
    core = core if isinstance(core, dict) else {}
    original_text = root.get("originalText")
    full_text_present = isinstance(original_text, str) and bool(
        original_text.strip()
    )
    observed_doi = str(core.get("prism:doi") or "")
    observed_pii = str(core.get("pii") or "")
    observed_title = str(core.get("dc:title") or "")
    license_url = str(core.get("openaccessUserLicense") or "")
    canonical_observed_pii = re.sub(r"[^A-Za-z0-9]", "", observed_pii).upper()
    canonical_expected_pii = re.sub(r"[^A-Za-z0-9]", "", PAPER_PII).upper()
    pii_match = canonical_observed_pii == canonical_expected_pii
    license_parts = urlsplit(license_url)
    cc_by_4 = (
        license_parts.hostname in {"creativecommons.org", "www.creativecommons.org"}
        and license_parts.path.rstrip("/") == "/licenses/by/4.0"
    )
    title_match = " ".join(observed_title.split()) == " ".join(PAPER_TITLE.split())
    rule_ids: list[str] = []
    if observed_doi.lower() != PAPER_DOI.lower():
        rule_ids.append("paper.source.article_doi_mismatch")
    if not pii_match:
        rule_ids.append("paper.source.article_pii_mismatch")
    if not title_match:
        rule_ids.append("paper.source.article_title_mismatch")
    if not full_text_present:
        rule_ids.append("paper.source.full_text_missing")
    if not cc_by_4:
        rule_ids.append("paper.source.article_license_unverified")
    return {
        "state": "validated" if not rule_ids else "blocked",
        "container_present": True,
        "full_text_present": full_text_present,
        "response_sha256": _sha256_bytes(body),
        "response_bytes": len(body),
        "original_text_sha256": (
            _sha256_text(original_text) if isinstance(original_text, str) else None
        ),
        "original_text_characters": (
            len(original_text) if isinstance(original_text, str) else 0
        ),
        "observed_doi": observed_doi or None,
        "doi_match": observed_doi.lower() == PAPER_DOI.lower(),
        "observed_pii": observed_pii or None,
        "canonical_observed_pii": canonical_observed_pii or None,
        "canonical_expected_pii": canonical_expected_pii,
        "pii_match": pii_match,
        "observed_title": observed_title or None,
        "title_match": title_match,
        "open_access": str(core.get("openaccess") or "") == "1",
        "license_url": license_url or None,
        "cc_by_4_0_verified": cc_by_4,
        "private_store_ref": "private-store:article/elsevier-full-text.json",
        "validation_rule_ids": tuple(rule_ids),
    }


def _zenodo_observation(body: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Zenodo metadata response is not JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Zenodo metadata response is not an object")
    metadata = payload.get("metadata")
    files = payload.get("files")
    links = payload.get("links")
    if not isinstance(metadata, dict) or not isinstance(files, list):
        raise ValueError("Zenodo metadata is missing required fields")
    if not isinstance(links, dict):
        raise ValueError("Zenodo metadata is missing official links")
    license_record = metadata.get("license")
    if not isinstance(license_record, dict):
        raise ValueError("Zenodo metadata has no structured license")
    record_id = int(payload.get("id"))
    doi = str(payload.get("doi") or "")
    license_id = str(license_record.get("id") or "")
    access_right = str(metadata.get("access_right") or "")
    if record_id != ZENODO_RECORD_ID:
        raise ValueError("Zenodo record ID differs from the pinned record")
    if doi != ZENODO_RECORD_DOI:
        raise ValueError("Zenodo DOI differs from the pinned record")
    if license_id != EXPECTED_LICENSE_ID or access_right != "open":
        raise ValueError("Zenodo access or license differs from the pinned record")

    archive: dict[str, Any] | None = None
    inventory: list[dict[str, Any]] = []
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Zenodo file metadata is malformed")
        key = str(item.get("key") or "")
        file_links = item.get("links")
        if not isinstance(file_links, dict):
            raise ValueError("Zenodo file lacks official links")
        download_url = str(file_links.get("self") or file_links.get("content") or "")
        _validate_https_url(download_url, host="zenodo.org")
        entry = {
            "name": key,
            "size_bytes": int(item.get("size") or 0),
            "checksum": str(item.get("checksum") or ""),
            "download_url": download_url,
        }
        inventory.append(entry)
        if key == ARCHIVE_NAME:
            if archive is not None:
                raise ValueError("Zenodo record contains a duplicate target archive")
            archive = entry
    if archive is None:
        raise ValueError("Zenodo record does not contain Supporting_Material.zip")
    if archive["checksum"] != f"md5:{EXPECTED_ARCHIVE_MD5}":
        raise ValueError("Zenodo archive MD5 differs from the pinned checksum")
    observation = {
        "state": "validated",
        "record_id": record_id,
        "doi": doi,
        "concept_doi": str(payload.get("conceptdoi") or "") or None,
        "title": str(metadata.get("title") or ""),
        "publication_date": str(metadata.get("publication_date") or ""),
        "access_right": access_right,
        "license_id": license_id,
        "license_verified": True,
        "record_url": str(links.get("self_html") or ""),
        "metadata_sha256": _sha256_bytes(body),
        "metadata_bytes": len(body),
        "file_inventory": sorted(inventory, key=lambda item: item["name"]),
        "private_store_ref": "private-store:zenodo/record-8285735.json",
    }
    return observation, archive


def _strict_xyz_observation(content: bytes) -> dict[str, Any]:
    text = content.decode("utf-8", errors="strict")
    lines = text.splitlines()
    if len(lines) < 2:
        raise ValueError("XYZ requires atom count and comment lines")
    atom_count = int(lines[0].strip())
    if atom_count < 1:
        raise ValueError("XYZ atom count must be positive")
    coordinate_lines = lines[2 : 2 + atom_count]
    if len(coordinate_lines) != atom_count:
        raise ValueError("XYZ coordinate count does not match atom count")
    if any(line.strip() for line in lines[2 + atom_count :]):
        raise ValueError("XYZ contains a second frame or trailing content")
    symbols: list[str] = []
    coordinates: list[tuple[float, float, float]] = []
    for line in coordinate_lines:
        tokens = line.split()
        if len(tokens) != 4 or _ELEMENT.fullmatch(tokens[0]) is None:
            raise ValueError("XYZ row must contain one element and three coordinates")
        point = tuple(float(value) for value in tokens[1:])
        if not all(math.isfinite(value) for value in point):
            raise ValueError("XYZ coordinate must be finite")
        symbols.append(tokens[0])
        coordinates.append(point)  # type: ignore[arg-type]
    manifest = ordered_geometry_manifest(symbols, coordinates)
    atom_order_sha256 = _sha256_json(
        {"atom_count": atom_count, "symbols": symbols}
    )
    return {
        "syntax_state": "exact_single_frame_xyz_valid",
        "atom_count": manifest.atom_count,
        "element_counts": dict(manifest.element_counts),
        "atom_order_sha256": atom_order_sha256,
        "ordered_geometry_sha256": manifest.ordered_geometry_sha256,
        "coordinate_units_state": "not_encoded_by_xyz_and_not_bound",
        "identity_state": "not_bound",
        "charge_state": "unknown",
        "multiplicity_state": "unknown",
    }


def _zip_inventory(
    archive_bytes: bytes,
    *,
    private_member_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise ValueError("archive exceeds its compressed byte bound")
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_ARCHIVE_MEMBERS:
            raise ValueError("archive member count is outside its bound")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("archive contains duplicate member names")
        if sum(info.file_size for info in infos) > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError("archive exceeds its total uncompressed byte bound")

        observations: list[dict[str, Any]] = []
        xyz_count = 0
        valid_xyz = 0
        invalid_xyz = 0
        regular_files = 0
        directories = 0
        for info in sorted(infos, key=lambda item: item.filename):
            member = _safe_member_name(info.filename)
            unix_mode = info.external_attr >> 16
            if info.flag_bits & 0x1:
                raise ValueError("archive contains an encrypted member")
            if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
                raise ValueError("archive contains a symbolic-link member")
            if info.is_dir():
                directories += 1
                observations.append(
                    {
                        "member": info.filename,
                        "kind": "directory",
                        "size_bytes": 0,
                        "compressed_size_bytes": info.compress_size,
                        "crc32": f"{info.CRC:08x}",
                    }
                )
                continue
            regular_files += 1
            if info.file_size < 1 or info.file_size > MAX_MEMBER_BYTES:
                raise ValueError("archive member size is outside its bound")
            content = archive.read(info)
            if len(content) != info.file_size:
                raise ValueError("archive member read length differs from metadata")
            destination = private_member_root.joinpath(*member.parts)
            _safe_private_write(destination, content)
            observation: dict[str, Any] = {
                "member": info.filename,
                "kind": "file",
                "size_bytes": len(content),
                "compressed_size_bytes": info.compress_size,
                "crc32": f"{info.CRC:08x}",
                "sha256": _sha256_bytes(content),
                "private_store_ref": f"private-store:zenodo/members/{info.filename}",
            }
            if member.suffix.lower() == ".xyz":
                xyz_count += 1
                try:
                    observation["xyz"] = _strict_xyz_observation(content)
                    valid_xyz += 1
                except (UnicodeDecodeError, ValueError):
                    observation["xyz"] = {
                        "syntax_state": "invalid",
                        "coordinate_units_state": "not_bound",
                        "identity_state": "not_bound",
                        "charge_state": "unknown",
                        "multiplicity_state": "unknown",
                    }
                    invalid_xyz += 1
            observations.append(observation)

    return observations, {
        "members": len(observations),
        "regular_files": regular_files,
        "directories": directories,
        "xyz_members": xyz_count,
        "valid_single_frame_xyz_members": valid_xyz,
        "invalid_xyz_members": invalid_xyz,
    }


def _hypotheses(
    *,
    tool_sha256: str,
    configuration_sha256: str,
    prior_reconciliation_sha256: str | None,
) -> list[dict[str, str]]:
    no_prompt = _sha256_text("no model prompt; deterministic retrieval only")
    cases = (
        (
            "urea-w18.elsevier.full-text",
            "candidate-ledger entitlement-dependent article state",
            "official Elsevier DOI response contains matching full text and license metadata",
            "HTTP 2xx JSON; DOI, PII, title, originalText, and CC-BY-4.0 license match",
            ELSEVIER_ORIGIN + ELSEVIER_PATH,
            (
                "rechecks exact article bytes after a prior run failed before receipt"
                if prior_reconciliation_sha256
                else "changes article evidence from entitlement-unverified to an observed response"
            ),
        ),
        (
            "urea-w18.zenodo.record-metadata",
            "candidate-ledger depositor archive assertion",
            "official record identifies the pinned DOI, open access, CC-BY-4.0, and archive checksum",
            "record ID, DOI, access, license, filename, and official MD5 exact match",
            ZENODO_RECORD_URL,
            (
                "rechecks exact metadata bytes after a prior run failed before receipt"
                if prior_reconciliation_sha256
                else "validates metadata independently of previously reported private archive bytes"
            ),
        ),
        (
            "urea-w18.zenodo.supporting-archive",
            "candidate-ledger private audit SHA-256",
            "official archive bytes match both Zenodo MD5 and the frozen private-audit SHA-256",
            "size plus MD5 plus SHA-256 match; ZIP safety and each XYZ syntax are deterministic",
            f"{ZENODO_RECORD_URL}/files/{ARCHIVE_NAME}/content",
            (
                "retries the failed archive hypothesis with the Accept header used by the validated Zenodo transport"
                if prior_reconciliation_sha256
                else "validates the actual official artifact rather than metadata or a search result"
            ),
        ),
    )
    return [
        {
            "hypothesis_id": case_id,
            "comparator": comparator,
            "changed_factor": "retrieved source artifact",
            "expected_outcome": expected,
            "deterministic_oracle": oracle,
            "source_sha256": _sha256_text(source),
            "prompt_sha256": no_prompt,
            "tool_sha256": tool_sha256,
            "configuration_sha256": configuration_sha256,
            "nonduplicate_reason": reason,
            **(
                {"prior_reconciliation_sha256": prior_reconciliation_sha256}
                if prior_reconciliation_sha256
                else {}
            ),
        }
        for case_id, comparator, expected, oracle, source, reason in cases
    ]


def _canonical_configuration() -> dict[str, Any]:
    return {
        "paper_doi": PAPER_DOI,
        "paper_pii": PAPER_PII,
        "zenodo_record_id": ZENODO_RECORD_ID,
        "archive_name": ARCHIVE_NAME,
        "expected_license_id": EXPECTED_LICENSE_ID,
        "expected_archive_md5": EXPECTED_ARCHIVE_MD5,
        "expected_archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "max_elsevier_bytes": MAX_ELSEVIER_BYTES,
        "max_metadata_bytes": MAX_METADATA_BYTES,
        "max_archive_bytes": MAX_ARCHIVE_BYTES,
        "max_member_bytes": MAX_MEMBER_BYTES,
        "max_total_uncompressed_bytes": MAX_TOTAL_UNCOMPRESSED_BYTES,
        "max_archive_members": MAX_ARCHIVE_MEMBERS,
        "max_transient_retries_per_hypothesis": MAX_TRANSIENT_RETRIES,
        "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "task_wall_time_seconds": TASK_WALL_TIME_SECONDS,
        "transport_attempt_limit": None,
        "current_quota_only": True,
        "top_up_allowed": False,
    }


def _prior_failed_run_reconciliation(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    article_path = path / "private" / "article" / "elsevier-full-text.json"
    metadata_path = path / "private" / "zenodo" / "record-8285735.json"
    observations: list[dict[str, Any]] = []
    for artifact, artifact_path in (
        ("elsevier_full_text", article_path),
        ("zenodo_metadata", metadata_path),
    ):
        if not artifact_path.is_file() or artifact_path.is_symlink():
            continue
        content = artifact_path.read_bytes()
        observations.append(
            {
                "artifact": artifact,
                "size_bytes": len(content),
                "sha256": _sha256_bytes(content),
            }
        )
    payload = {
        "state": "failed_before_public_receipt",
        "known_private_artifacts": observations,
        "observed_terminal_error_class": "other_http_error",
        "failed_case_id": "urea-w18.zenodo.supporting-archive",
        "exact_transport_attempt_count": "unknown",
        "latency_metrics": "unknown",
        "defect_rule_id": "acquisition.failure_receipt.not_persisted",
        "private_failed_run_retained": True,
    }
    return {**payload, "reconciliation_sha256": _sha256_json(payload)}


def _archive_result(
    *,
    body: bytes,
    expected_size: int,
    private_member_root: Path,
) -> dict[str, Any]:
    observed_md5 = hashlib.md5(body, usedforsecurity=False).hexdigest()
    observed_sha256 = _sha256_bytes(body)
    if len(body) != expected_size:
        raise ValueError("downloaded archive size differs from Zenodo metadata")
    if observed_md5 != EXPECTED_ARCHIVE_MD5:
        raise ValueError("downloaded archive differs from Zenodo MD5")
    if observed_sha256 != EXPECTED_ARCHIVE_SHA256:
        raise ValueError("downloaded archive differs from frozen SHA-256")
    inventory, summary = _zip_inventory(
        body,
        private_member_root=private_member_root,
    )
    return {
        "state": "validated" if summary["invalid_xyz_members"] == 0 else "blocked",
        "name": ARCHIVE_NAME,
        "size_bytes": len(body),
        "official_md5": EXPECTED_ARCHIVE_MD5,
        "observed_md5": observed_md5,
        "sha256": observed_sha256,
        "checksum_match": True,
        "private_store_ref": "private-store:zenodo/Supporting_Material.zip",
        "member_inventory": inventory,
        "summary": summary,
        "identity_approval_state": "not_bound",
        "coordinate_import_receipts_created": 0,
        "coordinate_conversion_performed": False,
        "coordinate_generation_performed": False,
    }


def run(
    *,
    api_env: Path,
    run_root: Path,
    public_receipt: Path,
    prior_failed_run: Path | None,
) -> dict[str, Any]:
    if run_root.exists():
        raise FileExistsError(f"private run root already exists: {run_root}")
    if public_receipt.exists():
        raise FileExistsError(f"public receipt already exists: {public_receipt}")
    run_root.mkdir(mode=0o700, parents=True)
    private_root = run_root / "private"
    private_root.mkdir(mode=0o700)

    prior_reconciliation = _prior_failed_run_reconciliation(prior_failed_run)
    configuration = _canonical_configuration()
    configuration_sha256 = _sha256_json(configuration)
    tool_sha256 = _sha256_bytes(Path(__file__).read_bytes())
    hypotheses = _hypotheses(
        tool_sha256=tool_sha256,
        configuration_sha256=configuration_sha256,
        prior_reconciliation_sha256=(
            str(prior_reconciliation["reconciliation_sha256"])
            if prior_reconciliation
            else None
        ),
    )
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    deadline = started_monotonic + TASK_WALL_TIME_SECONDS

    credential_environment = _credential_environment(api_env)
    secret_values = tuple(credential_environment.values())
    controller = CredentialAccessController(
        keychain_reader=lambda _service, _account: None,
        environment=credential_environment,
        permit_ttl_seconds=120,
    )
    credential_receipt = controller.credential_status(ApiProvider.ELSEVIER)

    session = requests.Session()
    session.trust_env = False

    article_body: bytes | None = None
    article_attempts: list[dict[str, Any]] = []
    article_transport_state = "credential_missing"
    if credential_receipt.status is not CredentialStatus.MISSING:
        article_body, article_attempts, article_transport_state = (
            _bounded_elsevier_get(
                session,
                controller=controller,
                case_id="urea-w18.elsevier.full-text",
                deadline=deadline,
            )
        )
    if article_body is not None:
        _safe_private_write(
            private_root / "article" / "elsevier-full-text.json",
            article_body,
        )
    article = _article_observation(article_body, article_transport_state)

    metadata_body, metadata_attempts, metadata_transport_state = (
        _bounded_public_get(
            session,
            case_id="urea-w18.zenodo.record-metadata",
            url=ZENODO_RECORD_URL,
            host="zenodo.org",
            accept="application/json",
            byte_limit=MAX_METADATA_BYTES,
            deadline=deadline,
        )
    )
    if metadata_body is None:
        raise RuntimeError(
            "Zenodo metadata acquisition failed with sanitized state "
            f"{metadata_transport_state}"
        )
    _safe_private_write(
        private_root / "zenodo" / "record-8285735.json",
        metadata_body,
    )
    zenodo, archive_metadata = _zenodo_observation(metadata_body)

    archive_url = str(archive_metadata["download_url"])
    archive_body, archive_attempts, archive_transport_state = (
        _bounded_public_get(
            session,
            case_id="urea-w18.zenodo.supporting-archive",
            url=archive_url,
            host="zenodo.org",
            accept="application/json",
            byte_limit=MAX_ARCHIVE_BYTES,
            deadline=deadline,
        )
    )
    if archive_body is None:
        raise RuntimeError(
            "Zenodo archive acquisition failed with sanitized state "
            f"{archive_transport_state}"
        )
    _safe_private_write(
        private_root / "zenodo" / ARCHIVE_NAME,
        archive_body,
    )
    archive = _archive_result(
        body=archive_body,
        expected_size=int(archive_metadata["size_bytes"]),
        private_member_root=private_root / "zenodo" / "members",
    )

    blockers: list[str] = []
    if article["state"] != "validated":
        blockers.append("paper.source.full_text_not_validated")
    if zenodo["state"] != "validated":
        blockers.append("paper.source.repository_not_validated")
    if archive["state"] != "validated":
        blockers.append("paper.coordinate.archive_xyz_invalid")
    blockers.extend(
        (
            "paper.identity.approval_missing",
            "paper.electronic_state.binding_missing",
            "paper.coordinate.units_binding_missing",
        )
    )

    all_attempts = article_attempts + metadata_attempts + archive_attempts
    payload = {
        "schema_version": SCHEMA_VERSION,
        "campaign_slice_id": CAMPAIGN_SLICE_ID,
        "started_at_utc": started_at,
        "finished_at_utc": _utc_now(),
        "paper": {
            "doi": PAPER_DOI,
            "pii": PAPER_PII,
            "title": PAPER_TITLE,
            "publisher_locator": f"https://doi.org/{PAPER_DOI}",
        },
        "adaptive_api_policy": {
            "transport_attempt_limit": None,
            "attempt_counts_are_observational": True,
            "current_user_quota_only": True,
            "top_up_allowed": False,
            "provider_bypass_allowed": False,
            "literature_concurrency": 1,
            "max_transient_retries_per_hypothesis": MAX_TRANSIENT_RETRIES,
            "task_wall_time_seconds": TASK_WALL_TIME_SECONDS,
            "termination_reason": "bounded_source_slice_complete",
        },
        "configuration": configuration,
        "configuration_sha256": configuration_sha256,
        "tool_sha256": tool_sha256,
        "hypotheses": hypotheses,
        "prior_failed_run_reconciliation": prior_reconciliation,
        "credential": credential_receipt.to_public_dict(),
        "network_attempts": all_attempts,
        "network_metrics": {
            "transport_attempts": len(all_attempts),
            "successful_attempts": sum(
                attempt["error_class"] == "none" for attempt in all_attempts
            ),
            "retry_attempts": sum(
                int(attempt["ordinal"]) > 1 for attempt in all_attempts
            ),
            "latency_ms": sum(int(attempt["latency_ms"]) for attempt in all_attempts),
            "response_bytes": sum(
                int(attempt["response_bytes"]) for attempt in all_attempts
            ),
            "model_api_attempts": 0,
        },
        "article_full_text": article,
        "zenodo_record": zenodo,
        "supporting_archive": archive,
        "scientific_boundary": {
            "molecular_identity": "not_inferred",
            "charge": "unknown",
            "multiplicity": "unknown",
            "archive_member_roles": "not_inferred_from_filenames",
            "coordinate_units": "not_encoded_by_xyz_and_not_bound",
            "identity_approval": "not_bound",
            "coordinate_import_receipts_created": 0,
            "native_inputs_generated": 0,
            "chemistry_engine_invocations": 0,
            "hpc_invocations": 0,
        },
        "source_bundle_state": (
            "acquired_identity_and_electronic_state_unbound"
            if article["state"] == zenodo["state"] == archive["state"] == "validated"
            else "blocked_source_acquisition_incomplete"
        ),
        "prp10_readiness": "blocked",
        "blocker_rule_ids": sorted(set(blockers)),
        "public_receipt_contains_source_text": False,
        "public_receipt_contains_coordinate_rows": False,
        "public_receipt_contains_private_paths": False,
        "public_receipt_contains_secrets": False,
        "wall_time_ms": int((time.monotonic() - started_monotonic) * 1000),
    }
    digest = _sha256_json(payload)
    receipt = {
        "receipt_id": f"prp10-source-acquisition:{digest[:24]}",
        "receipt_sha256": digest,
        **payload,
    }
    encoded = json.dumps(
        receipt,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    if any(secret.encode("utf-8") in encoded for secret in secret_values):
        raise RuntimeError("secret redaction invariant failed")
    if str(run_root).encode("utf-8") in encoded:
        raise RuntimeError("private path redaction invariant failed")
    public_receipt.parent.mkdir(parents=True, exist_ok=True)
    if public_receipt.exists() or public_receipt.is_symlink():
        raise FileExistsError("public receipt destination is not empty")
    with public_receipt.open("xb") as handle:
        handle.write(encoded)
    credential_environment.clear()
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-env", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--public-receipt", type=Path, required=True)
    parser.add_argument("--prior-failed-run", type=Path)
    args = parser.parse_args()
    receipt = run(
        api_env=args.api_env.expanduser().resolve(),
        run_root=args.run_root.resolve(),
        public_receipt=args.public_receipt.resolve(),
        prior_failed_run=(
            args.prior_failed_run.resolve() if args.prior_failed_run else None
        ),
    )
    print(
        json.dumps(
            {
                "receipt_id": receipt["receipt_id"],
                "receipt_sha256": receipt["receipt_sha256"],
                "source_bundle_state": receipt["source_bundle_state"],
                "prp10_readiness": receipt["prp10_readiness"],
                "transport_attempts": receipt["network_metrics"][
                    "transport_attempts"
                ],
                "valid_xyz_members": receipt["supporting_archive"]["summary"][
                    "valid_single_frame_xyz_members"
                ],
                "chemistry_engine_invocations": 0,
                "hpc_invocations": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
