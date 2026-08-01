#!/usr/bin/env python3
"""Emit one sanitized P3 v2 DeepSeek tool-formation specimen receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chemsmart.agent.harness.frontier_live_provider import FrontierLiveCapabilityError
from chemsmart.agent.harness.frontier_live_provider_v2 import (
    P3_LIVE_V2_PROFILE_ID,
    load_v2_profile,
    preflight_credential_resolution_v2,
    run_live_capability_specimen_v2,
    validate_live_capability_v2_receipt,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--credential-preflight", action="store_true")
    args = parser.parse_args()
    try:
        profile = load_v2_profile(repo_root=args.repo_root)
    except FrontierLiveCapabilityError as exc:
        print(json.dumps({
            "schema_version": 1,
            "phase": "P3",
            "receipt_id": P3_LIVE_V2_PROFILE_ID,
            "status": "blocked",
            "outcome": "profile_preflight_failed_no_request",
            "error_class": type(exc).__name__,
            "error_text_retained": False,
        }, sort_keys=True))
        return 2
    if args.dry_run:
        print(json.dumps({
            "schema_version": 1,
            "phase": "P3",
            "receipt_id": P3_LIVE_V2_PROFILE_ID,
            "status": "preflight_ready",
            "outcome": "no_request_dry_run",
            "model": profile.p1_profile.model,
            "p1_receipt_sha256": profile.p1_profile.p1_receipt_sha256,
            "p3_v1_receipt_sha256": profile.p3_v1_receipt_sha256,
            "credentials_retained": False,
            "raw_prompt_retained": False,
        }, sort_keys=True))
        return 0
    if args.credential_preflight:
        try:
            resolution = preflight_credential_resolution_v2(profile=profile)
        except FrontierLiveCapabilityError as exc:
            print(json.dumps({
                "schema_version": 1,
                "phase": "P3",
                "receipt_id": P3_LIVE_V2_PROFILE_ID,
                "status": "blocked",
                "outcome": "credential_preflight_failed_no_request",
                "error_class": type(exc).__name__,
                "error_text_retained": False,
            }, sort_keys=True))
            return 2
        print(json.dumps({
            "schema_version": 1,
            "phase": "P3",
            "receipt_id": P3_LIVE_V2_PROFILE_ID,
            "status": "preflight_ready",
            "outcome": "credential_resolved_no_request",
            "canonical_alias": resolution.canonical_alias,
            "source_class": resolution.source_class,
            "source_alias": resolution.source_alias,
            "bound_in_process": resolution.bound_in_process,
            "credential_value_retained": False,
        }, sort_keys=True))
        return 0
    receipt = run_live_capability_specimen_v2(profile=profile)
    issues = validate_live_capability_v2_receipt(receipt)
    if issues:
        receipt["validation_issues"] = sorted(set(receipt["validation_issues"]) | set(issues))
        receipt["status"] = "blocked"
        receipt["outcome"] = "local_receipt_validation_failed"
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
