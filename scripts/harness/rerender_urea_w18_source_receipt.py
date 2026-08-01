#!/usr/bin/env python3
"""Rerender the urea--W18 public receipt from frozen private source bytes.

This is a zero-network recovery path for a deterministic validator correction.
It verifies the prior content-addressed receipt, article/metadata/archive hashes,
all retained archive members, and every XYZ syntax observation before changing
only the PII comparison to punctuation-insensitive canonical form.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from scripts.harness.acquire_urea_w18_source_bundle import (
    ARCHIVE_NAME,
    _article_observation,
    _sha256_bytes,
    _sha256_json,
    _strict_xyz_observation,
    _utc_now,
    _zenodo_observation,
)


SCHEMA_VERSION = "chemsmart.prp10-source-receipt-rerender.v1"


def _verify_prior_receipt(receipt: dict[str, object]) -> None:
    expected = receipt.get("receipt_sha256")
    payload = {
        key: value
        for key, value in receipt.items()
        if key not in {"receipt_id", "receipt_sha256"}
    }
    if not isinstance(expected, str) or _sha256_json(payload) != expected:
        raise ValueError("prior public receipt digest is invalid")


def _read_exact(path: Path, *, sha256: str, size_bytes: int) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError("required private artifact is missing or unsafe")
    content = path.read_bytes()
    if len(content) != size_bytes or _sha256_bytes(content) != sha256:
        raise ValueError("private artifact differs from its public receipt")
    return content


def _verify_members(
    *,
    archive_bytes: bytes,
    private_root: Path,
    inventory: list[dict[str, object]],
) -> None:
    with zipfile.ZipFile(Path(private_root / "zenodo" / ARCHIVE_NAME)) as archive:
        archive_names = [item.filename for item in archive.infolist()]
        receipt_names = [str(item["member"]) for item in inventory]
        if sorted(archive_names) != sorted(receipt_names):
            raise ValueError("ZIP inventory differs from the public receipt")
        if _sha256_bytes(Path(private_root / "zenodo" / ARCHIVE_NAME).read_bytes()) != (
            _sha256_bytes(archive_bytes)
        ):
            raise ValueError("ZIP bytes changed during offline verification")
        for observation in inventory:
            member = str(observation["member"])
            info = archive.getinfo(member)
            if observation["kind"] == "directory":
                if not info.is_dir():
                    raise ValueError("ZIP member kind differs from receipt")
                continue
            content = archive.read(info)
            _read_exact(
                private_root / "zenodo" / "members" / member,
                sha256=str(observation["sha256"]),
                size_bytes=int(observation["size_bytes"]),
            )
            if _sha256_bytes(content) != observation["sha256"]:
                raise ValueError("ZIP member bytes differ from receipt")
            xyz = observation.get("xyz")
            if isinstance(xyz, dict):
                if _strict_xyz_observation(content) != xyz:
                    raise ValueError("XYZ syntax observation is not reproducible")


def rerender(
    *,
    private_run: Path,
    source_receipt_path: Path,
    output_path: Path,
) -> dict[str, object]:
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError("rerender output already exists")
    source = json.loads(source_receipt_path.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("source receipt is not an object")
    _verify_prior_receipt(source)

    private_root = private_run / "private"
    article_record = source["article_full_text"]
    zenodo_record = source["zenodo_record"]
    archive_record = source["supporting_archive"]
    if not isinstance(article_record, dict):
        raise ValueError("source article observation is malformed")
    if not isinstance(zenodo_record, dict) or not isinstance(archive_record, dict):
        raise ValueError("source repository observation is malformed")

    article_bytes = _read_exact(
        private_root / "article" / "elsevier-full-text.json",
        sha256=str(article_record["response_sha256"]),
        size_bytes=int(article_record["response_bytes"]),
    )
    metadata_bytes = _read_exact(
        private_root / "zenodo" / "record-8285735.json",
        sha256=str(zenodo_record["metadata_sha256"]),
        size_bytes=int(zenodo_record["metadata_bytes"]),
    )
    archive_bytes = _read_exact(
        private_root / "zenodo" / ARCHIVE_NAME,
        sha256=str(archive_record["sha256"]),
        size_bytes=int(archive_record["size_bytes"]),
    )
    rerendered_article = _article_observation(article_bytes, "observed")
    rerendered_zenodo, _archive_metadata = _zenodo_observation(metadata_bytes)
    if rerendered_zenodo["metadata_sha256"] != zenodo_record["metadata_sha256"]:
        raise ValueError("Zenodo metadata observation is not reproducible")
    inventory = archive_record.get("member_inventory")
    if not isinstance(inventory, list):
        raise ValueError("source archive inventory is malformed")
    _verify_members(
        archive_bytes=archive_bytes,
        private_root=private_root,
        inventory=inventory,
    )
    if rerendered_article["state"] != "validated":
        raise ValueError("PII canonicalization did not resolve the sole article defect")

    updated = dict(source)
    source_receipt_id = str(source["receipt_id"])
    source_receipt_sha256 = str(source["receipt_sha256"])
    updated.pop("receipt_id", None)
    updated.pop("receipt_sha256", None)
    updated["finished_at_utc"] = _utc_now()
    updated["article_full_text"] = rerendered_article
    updated["source_bundle_state"] = "acquired_identity_and_electronic_state_unbound"
    blockers = [
        rule
        for rule in source["blocker_rule_ids"]
        if rule != "paper.source.full_text_not_validated"
    ]
    updated["blocker_rule_ids"] = sorted(set(blockers))
    rerender_payload = {
        "schema_version": SCHEMA_VERSION,
        "source_receipt_id": source_receipt_id,
        "source_receipt_sha256": source_receipt_sha256,
        "changed_factor": "Elsevier PII punctuation canonicalization only",
        "deterministic_oracle": (
            "remove non-alphanumeric characters and compare uppercase PII values"
        ),
        "observed_pii": rerendered_article["observed_pii"],
        "canonical_observed_pii": rerendered_article[
            "canonical_observed_pii"
        ],
        "canonical_expected_pii": rerendered_article[
            "canonical_expected_pii"
        ],
        "pii_match": rerendered_article["pii_match"],
        "verified_private_artifact_sha256s": sorted(
            (
                _sha256_bytes(article_bytes),
                _sha256_bytes(metadata_bytes),
                _sha256_bytes(archive_bytes),
            )
        ),
        "network_attempts": 0,
        "model_api_attempts": 0,
        "chemistry_engine_invocations": 0,
        "hpc_invocations": 0,
    }
    updated["validator_rerender"] = {
        **rerender_payload,
        "rerender_sha256": _sha256_json(rerender_payload),
    }
    digest = _sha256_json(updated)
    receipt: dict[str, object] = {
        "receipt_id": f"prp10-source-acquisition:{digest[:24]}",
        "receipt_sha256": digest,
        **updated,
    }
    encoded = json.dumps(
        receipt,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    if str(private_run).encode("utf-8") in encoded:
        raise ValueError("private path leaked into rerendered receipt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as handle:
        handle.write(encoded)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-run", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = rerender(
        private_run=args.private_run.resolve(),
        source_receipt_path=args.source_receipt.resolve(),
        output_path=args.output.resolve(),
    )
    print(
        json.dumps(
            {
                "receipt_id": receipt["receipt_id"],
                "receipt_sha256": receipt["receipt_sha256"],
                "source_bundle_state": receipt["source_bundle_state"],
                "prp10_readiness": receipt["prp10_readiness"],
                "network_attempts": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
