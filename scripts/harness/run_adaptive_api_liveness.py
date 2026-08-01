#!/usr/bin/env python3
"""Run one unique, deterministic liveness hypothesis per authorized API.

There is no campaign request-count cap.  Each hypothesis receives a one-call
credential lease per transport attempt and bounded transient retries.  Raw
literature responses are stored only in the ignored private run directory;
the public receipt contains hashes and sanitized observations only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from dotenv import dotenv_values

from chemsmart.agent.adaptive_api_campaign import (
    AdaptiveErrorAction,
    AdaptiveProviderPurpose,
    build_adaptive_api_campaign_policy_v1,
    build_adaptive_hypothesis_v1,
    build_adaptive_network_budget_v1,
    classify_adaptive_provider_error,
)
from chemsmart.agent.api_access import (
    ApiProvider,
    ApiUsageBudget,
    CredentialAccessController,
    CredentialProbeError,
    CredentialProbeObservation,
    CredentialStatus,
)


MODEL = "deepseek-v4-flash"
EL_AGENTE_Q_DOI = "10.1016/j.matt.2025.102263"
MAX_RESPONSE_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class LiveCase:
    case_id: str
    provider: ApiProvider
    purpose: AdaptiveProviderPurpose
    method: str
    relative_path: str
    query_label: str
    expected_label: str
    persist_private_response: bool

    def public_request(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "provider": self.provider.value,
            "purpose": self.purpose.value,
            "method": self.method,
            "relative_path": self.relative_path,
            "query_sha256": _sha256_text(self.query_label),
        }


CASES = (
    LiveCase(
        case_id="deepseek.model-catalog.v4-flash",
        provider=ApiProvider.DEEPSEEK,
        purpose=AdaptiveProviderPurpose.HARNESS_VALIDATION,
        method="GET",
        relative_path="/models",
        query_label="official model catalog contains deepseek-v4-flash",
        expected_label="HTTP 2xx JSON model catalog containing deepseek-v4-flash",
        persist_private_response=False,
    ),
    LiveCase(
        case_id="elsevier.el-agente-q.full-text",
        provider=ApiProvider.ELSEVIER,
        purpose=AdaptiveProviderPurpose.ARTICLE_FULL_TEXT,
        method="GET",
        relative_path=f"/content/article/doi/{quote(EL_AGENTE_Q_DOI, safe='')}",
        query_label=f"Elsevier full text DOI {EL_AGENTE_Q_DOI}",
        expected_label="retrieved full text or explicit entitlement denial",
        persist_private_response=True,
    ),
    LiveCase(
        case_id="serpapi.prp10.exact-xyz-discovery",
        provider=ApiProvider.SERPAPI,
        purpose=AdaptiveProviderPurpose.LITERATURE_DISCOVERY,
        method="GET",
        relative_path="/search.json",
        query_label=(
            'computational chemistry "XYZ" Zenodo ORCA Gaussian '
            'supporting information'
        ),
        expected_label="Google Scholar discovery response with at least one result",
        persist_private_response=True,
    ),
    LiveCase(
        case_id="tavily.prp10.exact-xyz-discovery",
        provider=ApiProvider.TAVILY,
        purpose=AdaptiveProviderPurpose.LITERATURE_DISCOVERY,
        method="POST",
        relative_path="/search",
        query_label=(
            'open access computational chemistry paper exact XYZ coordinates '
            'Zenodo Gaussian ORCA'
        ),
        expected_label="Tavily discovery response with at least one result",
        persist_private_response=True,
    ),
)


class _SanitizedTransportFailure(RuntimeError):
    pass


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


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


def _credential_environment(api_env: Path) -> dict[str, str]:
    values = {
        str(key): str(value)
        for key, value in dotenv_values(api_env).items()
        if key and value
    }
    aliases = {
        "CHEMSMART_DEEPSEEK_API_KEY": (
            "CHEMSMART_DEEPSEEK_API_KEY",
            "DEEPSEEK_API_KEY",
            "DEEPSEEK-api-key",
        ),
        "CHEMSMART_ELSEVIER_API_KEY": (
            "CHEMSMART_ELSEVIER_API_KEY",
            "ELSEVIER_API_KEY",
            "Elsivier_api_key",
        ),
        "CHEMSMART_SERPAPI_API_KEY": (
            "CHEMSMART_SERPAPI_API_KEY",
            "SERPAPI_API_KEY",
            "SerpApi_api_key",
        ),
        "CHEMSMART_TAVILY_API_KEY": (
            "CHEMSMART_TAVILY_API_KEY",
            "TAVILY_API_KEY",
            "Tavily_api_key",
        ),
    }
    environment: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        selected = next(
            (values[name] for name in candidates if values.get(name)), None
        )
        if selected:
            environment[canonical] = selected
    values.clear()
    return environment


def _hypotheses(cases: tuple[LiveCase, ...]):
    common_precondition = _sha256_text(
        "no engine or HPC execution; exact provider scope; private raw evidence"
    )
    return tuple(
        build_adaptive_hypothesis_v1(
            hypothesis_id=f"hypothesis:{case.case_id}",
            provider=case.provider,
            purpose=case.purpose,
            prompt_sha256=_sha256_json(case.public_request()),
            input_state_sha256=_sha256_text("credential availability checked locally"),
            expected_observation_sha256=_sha256_text(case.expected_label),
            precondition_sha256s=tuple(
                sorted(
                    (
                        common_precondition,
                        _sha256_text(f"provider:{case.provider.value}"),
                    )
                )
            ),
        )
        for case in cases
    )


def _request(
    case: LiveCase,
    *,
    secret: str,
    origin: str,
    timeout_seconds: float,
) -> tuple[int, dict[str, str], bytes, int, bool]:
    headers = {"Accept": "application/json"}
    params: dict[str, Any] | None = None
    json_body: dict[str, Any] | None = None
    if case.provider is ApiProvider.DEEPSEEK:
        headers["Authorization"] = f"Bearer {secret}"
    elif case.provider is ApiProvider.ELSEVIER:
        headers["X-ELS-APIKey"] = secret
        headers["X-ELS-ResourceVersion"] = "XOCS"
    elif case.provider is ApiProvider.SERPAPI:
        params = {
            "api_key": secret,
            "engine": "google_scholar",
            "num": 3,
            "q": case.query_label,
        }
    elif case.provider is ApiProvider.TAVILY:
        json_body = {
            "api_key": secret,
            "query": case.query_label,
            "max_results": 3,
            "search_depth": "advanced",
        }
    started = time.perf_counter()
    try:
        response = requests.request(
            case.method,
            origin + case.relative_path,
            headers=headers,
            params=params,
            json=json_body,
            timeout=(10, timeout_seconds),
            stream=True,
        )
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=65_536):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                response.close()
                raise _SanitizedTransportFailure("response_too_large")
            chunks.append(chunk)
        body = b"".join(chunks)
        response_headers = {
            key.lower(): value
            for key, value in response.headers.items()
            if key.lower() in {"content-type", "retry-after"}
        }
        return (
            response.status_code,
            response_headers,
            body,
            int((time.perf_counter() - started) * 1000),
            False,
        )
    except requests.Timeout:
        return 0, {}, b"", int((time.perf_counter() - started) * 1000), True
    except requests.RequestException:
        raise _SanitizedTransportFailure("connection") from None


def _validate_response(case: LiveCase, body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"valid": False, "rule_ids": ["provider.response.invalid_json"]}
    if not isinstance(payload, dict):
        return {"valid": False, "rule_ids": ["provider.response.invalid_shape"]}
    if case.provider is ApiProvider.DEEPSEEK:
        entries = payload.get("data")
        model_ids = sorted(
            str(item.get("id"))
            for item in entries or []
            if isinstance(item, dict) and item.get("id")
        )
        return {
            "valid": MODEL in model_ids,
            "observed_model_count": len(model_ids),
            "target_model_present": MODEL in model_ids,
            "model_ids_sha256": _sha256_json(model_ids),
            "rule_ids": [] if MODEL in model_ids else ["provider.model.not_listed"],
        }
    if case.provider is ApiProvider.ELSEVIER:
        has_article = any(
            key in payload
            for key in ("full-text-retrieval-response", "article", "originalText")
        )
        return {
            "valid": has_article,
            "article_container_present": has_article,
            "rule_ids": [] if has_article else ["literature.full_text.shape_missing"],
        }
    results = payload.get("organic_results") if case.provider is ApiProvider.SERPAPI else payload.get("results")
    result_count = len(results) if isinstance(results, list) else 0
    has_error = bool(payload.get("error"))
    return {
        "valid": result_count > 0 and not has_error,
        "result_count": result_count,
        "provider_error_field_present": has_error,
        "rule_ids": (
            []
            if result_count > 0 and not has_error
            else ["literature.discovery.no_valid_results"]
        ),
    }


def _explicit_quota(body: bytes) -> bool:
    lowered = body[:16_384].lower()
    return any(
        marker in lowered
        for marker in (
            b"insufficient balance",
            b"insufficient_balance",
            b"quota exceeded",
            b"quota_exceeded",
        )
    )


def _run_case(
    case: LiveCase,
    *,
    controller: CredentialAccessController,
    network_budget,
    private_root: Path,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    transient_ordinal = 0
    while True:
        one_request_budget = ApiUsageBudget(1)
        permit = controller.prepare_status_probe(
            case.provider,
            caller="chemsmart-adaptive-api-campaign",
            purpose=case.case_id,
            budget=one_request_budget,
        )
        captured: dict[str, Any] = {}

        def operation(secret: str, origin: str) -> CredentialProbeObservation:
            try:
                status, headers, body, latency_ms, timed_out = _request(
                    case,
                    secret=secret,
                    origin=origin,
                    timeout_seconds=min(60.0, network_budget.task_wall_time_seconds),
                )
            except _SanitizedTransportFailure:
                captured.update({"connection_error": True})
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
            if case.provider is ApiProvider.ELSEVIER and status == 403:
                return CredentialProbeObservation(
                    CredentialStatus.INVALID_ENTITLEMENT
                )
            if timed_out or not 200 <= status < 300:
                raise _SanitizedTransportFailure("provider_status")
            return CredentialProbeObservation(CredentialStatus.VALID)

        credential_status = "unknown"
        try:
            status_receipt = controller.invoke_authorized_probe(permit, operation)
            credential_status = status_receipt.status.value
        except CredentialProbeError:
            pass

        body = captured.get("body", b"")
        http_status = int(captured.get("http_status") or 0)
        timed_out = bool(captured.get("timed_out"))
        attempt = {
            "ordinal": len(attempts) + 1,
            "http_status": http_status or None,
            "credential_status": credential_status,
            "latency_ms": int(captured.get("latency_ms") or 0),
            "response_bytes": len(body),
            "response_sha256": _sha256_bytes(body),
            "timed_out": timed_out,
        }
        attempts.append(attempt)

        if case.provider is ApiProvider.ELSEVIER and http_status == 403:
            return {
                "case_id": case.case_id,
                "provider": case.provider.value,
                "status": "entitlement_denied",
                "attempts": attempts,
                "validation": {"valid": False, "rule_ids": ["provider.stop.elsevier_entitlement_403"]},
            }
        if 200 <= http_status < 300:
            validation = _validate_response(case, body)
            private_ref = None
            if case.persist_private_response:
                path = private_root / f"{case.case_id}.response"
                path.write_bytes(body)
                path.chmod(0o600)
                private_ref = f"private-store:{case.case_id}"
            return {
                "case_id": case.case_id,
                "provider": case.provider.value,
                "status": "observed",
                "attempts": attempts,
                "validation": validation,
                "private_store_ref": private_ref,
            }
        if captured.get("connection_error"):
            return {
                "case_id": case.case_id,
                "provider": case.provider.value,
                "status": "failed",
                "attempts": attempts,
                "validation": {"valid": False, "rule_ids": ["provider.fail.connection"]},
            }

        transient_ordinal += 1
        retry_after = None
        raw_retry_after = (captured.get("headers") or {}).get("retry-after")
        if raw_retry_after:
            try:
                retry_after = float(raw_retry_after)
            except ValueError:
                retry_after = None
        try:
            decision = classify_adaptive_provider_error(
                case.provider,
                budget=network_budget,
                explicit_quota_exhausted=_explicit_quota(body),
                http_status=(http_status or None),
                retry_after_seconds=retry_after,
                timed_out=timed_out,
                transient_failure_ordinal=transient_ordinal,
            )
        except ValueError:
            return {
                "case_id": case.case_id,
                "provider": case.provider.value,
                "status": "failed",
                "attempts": attempts,
                "validation": {"valid": False, "rule_ids": ["provider.fail.unclassified"]},
            }
        attempt["error_class"] = decision.error_class.value
        attempt["error_rule_id"] = decision.rule_id
        if decision.action not in {
            AdaptiveErrorAction.RETRY_AFTER,
            AdaptiveErrorAction.BOUNDED_BACKOFF,
        }:
            return {
                "case_id": case.case_id,
                "provider": case.provider.value,
                "status": "stopped" if decision.stop_provider else "failed",
                "attempts": attempts,
                "validation": {"valid": False, "rule_ids": [decision.rule_id]},
            }
        time.sleep(float(decision.delay_seconds or 0))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-env", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--public-receipt", type=Path, required=True)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.mkdir(parents=True, exist_ok=False)
    private_root = run_root / "private"
    private_root.mkdir(mode=0o700)

    environment = _credential_environment(args.api_env.expanduser())
    controller = CredentialAccessController(
        keychain_reader=lambda _service, _account: None,
        environment=environment,
        permit_ttl_seconds=120,
    )
    local_status = {
        provider: controller.credential_status(provider)
        for provider in ApiProvider
    }
    network_budget = build_adaptive_network_budget_v1(
        deepseek_initial_concurrency=1,
        max_context_tokens_per_request=160_000,
        max_output_tokens_per_request=8_192,
        task_wall_time_seconds=3_600,
        max_transient_retries_per_hypothesis=2,
        backoff_base_seconds=1,
        backoff_max_seconds=30,
        retry_after_max_seconds=30,
    )
    hypotheses = _hypotheses(CASES)
    policy = build_adaptive_api_campaign_policy_v1(
        campaign_id="campaign:prp10-adaptive-api-liveness-2026-08-01",
        hypotheses=hypotheses,
        network_budget=network_budget,
    )
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    try:
        for case in CASES:
            if local_status[case.provider].status is CredentialStatus.MISSING:
                results.append(
                    {
                        "case_id": case.case_id,
                        "provider": case.provider.value,
                        "status": "credential_missing",
                        "attempts": [],
                        "validation": {
                            "valid": False,
                            "rule_ids": ["provider.stop.credential_missing"],
                        },
                    }
                )
                continue
            results.append(
                _run_case(
                    case,
                    controller=controller,
                    network_budget=network_budget,
                    private_root=private_root,
                )
            )
    finally:
        environment.clear()

    public: dict[str, Any] = {
        "schema_version": "chemsmart.adaptive-api-liveness-receipt.v1",
        "campaign_policy_sha256": policy.policy_sha256,
        "network_budget_sha256": network_budget.budget_sha256,
        "transport_attempt_limit": None,
        "attempt_counts_are_observational": True,
        "quota_source": "current_user_account",
        "top_up_allowed": False,
        "provider_bypass_allowed": False,
        "chemistry_engine_calls": 0,
        "hpc_calls": 0,
        "credential_availability": {
            provider.value: local_status[provider].status.value
            for provider in ApiProvider
        },
        "hypotheses": [
            {
                "hypothesis_id": item.hypothesis_id,
                "hypothesis_sha256": item.hypothesis_sha256,
                "provider": item.provider.value,
                "purpose": item.purpose.value,
                "prompt_sha256": item.prompt_sha256,
                "input_state_sha256": item.input_state_sha256,
                "expected_observation_sha256": item.expected_observation_sha256,
                "precondition_sha256s": list(item.precondition_sha256s),
            }
            for item in hypotheses
        ],
        "results": results,
        "totals": {
            "transport_attempts": sum(len(item["attempts"]) for item in results),
            "latency_ms": sum(
                int(attempt.get("latency_ms") or 0)
                for item in results
                for attempt in item["attempts"]
            ),
            "wall_time_ms": int((time.perf_counter() - started) * 1000),
        },
        "termination_reason": "campaign.stop.all_unique_hypotheses_observed",
        "secret_material_persisted": False,
        "raw_model_response_persisted": False,
    }
    public["receipt_sha256"] = _sha256_json(public)
    args.public_receipt.parent.mkdir(parents=True, exist_ok=True)
    args.public_receipt.write_text(
        json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "receipt_sha256": public["receipt_sha256"],
                "transport_attempts": public["totals"]["transport_attempts"],
                "statuses": {
                    item["provider"]: item["status"] for item in results
                },
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
