from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from chemsmart.agent.project_readiness import (
    ProjectReadinessReceiptV1,
    TypedProjectSupportStatus,
    assess_typed_project_readiness,
    project_readiness_evidence_ref_sha256,
    project_readiness_receipt_sha256,
)


REGISTRY_RESOLUTION_SHA256 = "a" * 64


def test_receipt_separates_registry_discovery_from_typed_project_support():
    kwargs = {
        "case_id": "orca-solvated-pd-project",
        "program": "orca",
        "job_kind": "sp",
        "method": {
            "functional": "B3LYP",
            "basis": "def2-TZVP",
            "dispersion": "D3BJ",
            "solvent_model": "smd",
            "solvent_id": "water",
            "freq": True,
            "solv_freq": False,
            "ecp_binding": "required_elements",
            "required_ecp_elements": ("Pd",),
        },
        "registry_resolution_sha256s": (REGISTRY_RESOLUTION_SHA256,),
    }

    receipt = assess_typed_project_readiness(**kwargs)
    replay = assess_typed_project_readiness(**kwargs)
    evidence_ref = receipt.evidence_ref()

    assert receipt.receipt_sha256 == replay.receipt_sha256
    assert receipt.receipt_sha256 == project_readiness_receipt_sha256(receipt)
    assert evidence_ref.artifact_sha256 == receipt.receipt_sha256
    assert evidence_ref.request_sha256 == receipt.request.request_sha256
    assert evidence_ref.ref_sha256 == project_readiness_evidence_ref_sha256(
        evidence_ref
    )
    assert receipt.registry_discovery.resolution_sha256s == (
        REGISTRY_RESOLUTION_SHA256,
    )
    assert receipt.registry_discovery.establishes_typed_project_support is False
    assert receipt.basis_ecp.verdict == "ok"
    assert receipt.basis_ecp.observed_ecp_elements == ("Pd",)
    support = receipt.typed_project_support
    assert support.status is TypedProjectSupportStatus.TYPED_PROJECT_SUPPORTED
    assert support.required_job_observation is not None
    assert support.required_job_observation.jobtype == "sp"
    assert support.required_job_observation.basis == "def2tzvp"
    assert support.required_job_observation.dispersion == "D3BJ"
    assert support.required_job_observation.solvent_model == "smd"
    assert support.required_job_observation.solvent_id == "water"
    assert receipt.safety.model_dump() == {
        "workspace_project_writes": 0,
        "native_input_previews": 0,
        "chemistry_engine_calls": 0,
        "hpc_calls": 0,
        "registry_discovery_grants_support": False,
    }
    ProjectReadinessReceiptV1.model_validate(receipt.model_dump(mode="json"))
    tampered = receipt.model_dump(mode="json")
    tampered["request"]["method"]["basis"] = "def2-SVP"
    with pytest.raises(ValidationError, match="digest mismatch"):
        ProjectReadinessReceiptV1.model_validate(tampered)


def test_gaussian_d4_is_separately_blocked_as_unsupported():
    receipt = assess_typed_project_readiness(
        case_id="gaussian-explicit-d4",
        program="gaussian",
        job_kind="opt",
        method={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "dispersion": "D4",
            "freq": True,
        },
        registry_resolution_sha256s=(REGISTRY_RESOLUTION_SHA256,),
    )

    support = receipt.typed_project_support
    assert (
        support.status
        is TypedProjectSupportStatus.BLOCKED_UNSUPPORTED_SETTING
    )
    assert support.renderer_status == "blocked_unsupported_setting"
    assert support.project_yaml_sha256 is None
    assert support.validation_verdict == "not_run"
    assert "paper.project.dispersion_unsupported" in support.blocking_rule_ids
    assert receipt.registry_discovery.establishes_typed_project_support is False


@pytest.mark.parametrize(
    ("method", "rule_id"),
    (
        (
            {"functional": "B3LYP", "basis": "def2-SVP"},
            "paper.project.frequency_missing",
        ),
        (
            {"functional": "B3LYP", "freq": True},
            "paper.project.basis_missing",
        ),
    ),
)
def test_missing_project_evidence_is_not_mislabeled_invalid(method, rule_id):
    receipt = assess_typed_project_readiness(
        case_id=f"orca-missing-{rule_id.rsplit('.', 1)[-1]}",
        program="orca",
        job_kind="opt",
        method=method,
    )

    support = receipt.typed_project_support
    assert support.status is TypedProjectSupportStatus.BLOCKED_MISSING_EVIDENCE
    assert support.renderer_status == "blocked_missing_evidence"
    assert rule_id in support.blocking_rule_ids


def test_gaussian_mixed_basis_binds_ecp_to_heavy_basis():
    receipt = assess_typed_project_readiness(
        case_id="gaussian-pd-genecp",
        program="gaussian",
        job_kind="opt",
        method={
            "functional": "B3LYP",
            "basis": "genecp",
            "heavy_elements": ("Pd",),
            "heavy_elements_basis": "def2-TZVP",
            "light_elements_basis": "def2-SVP",
            "freq": True,
            "ecp_binding": "required_elements",
            "required_ecp_elements": ("Pd",),
        },
    )

    assert receipt.basis_ecp.basis == "def2-TZVP"
    assert receipt.basis_ecp.observed_ecp_elements == ("Pd",)
    support = receipt.typed_project_support
    assert support.status is TypedProjectSupportStatus.TYPED_PROJECT_SUPPORTED
    assert support.required_job_observation is not None
    assert support.required_job_observation.basis == "genecp"
    assert support.required_job_observation.heavy_elements == ("Pd",)
    assert support.required_job_observation.heavy_elements_basis == "def2tzvp"
    assert support.required_job_observation.light_elements_basis == "def2svp"


def test_correct_jobtype_with_method_and_basis_drift_is_blocked(monkeypatch):
    import chemsmart.agent.project_yaml as project_yaml

    project_yaml._VALIDATION_CACHE.clear()
    real_loader = project_yaml._load_project_yaml_via_runtime

    def loader_with_semantic_drift(**kwargs):
        summary = real_loader(**kwargs)
        summary["opt"]["functional"] = "pbe0"
        summary["opt"]["basis"] = "def2-TZVP"
        assert summary["opt"]["jobtype"] == "opt"
        return summary

    monkeypatch.setattr(
        project_yaml,
        "_load_project_yaml_via_runtime",
        loader_with_semantic_drift,
    )
    receipt = assess_typed_project_readiness(
        case_id="orca-loader-semantic-drift",
        program="orca",
        job_kind="opt",
        method={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "dispersion": "D3BJ",
            "freq": False,
        },
    )

    support = receipt.typed_project_support
    assert support.status is TypedProjectSupportStatus.BLOCKED_SEMANTIC_DRIFT
    assert support.required_job_observation is not None
    assert support.required_job_observation.jobtype == "opt"
    assert "yaml.runtime.required_job_semantic_mismatch" in (
        support.blocking_rule_ids
    )
    project_yaml._VALIDATION_CACHE.clear()


def test_gaussian_grid_drift_is_blocked(monkeypatch):
    import chemsmart.agent.project_yaml as project_yaml

    project_yaml._VALIDATION_CACHE.clear()
    real_loader = project_yaml._load_project_yaml_via_runtime

    def loader_without_grid(**kwargs):
        summary = real_loader(**kwargs)
        assert summary["opt"]["additional_route_parameters"] == "Int=UltraFine"
        summary["opt"]["additional_route_parameters"] = None
        return summary

    monkeypatch.setattr(
        project_yaml,
        "_load_project_yaml_via_runtime",
        loader_without_grid,
    )
    receipt = assess_typed_project_readiness(
        case_id="gaussian-loader-grid-drift",
        program="gaussian",
        job_kind="opt",
        method={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "integration_grid": "ultrafine",
            "freq": True,
        },
    )

    support = receipt.typed_project_support
    assert support.status is TypedProjectSupportStatus.BLOCKED_SEMANTIC_DRIFT
    assert support.required_job_observation is not None
    assert support.required_job_observation.additional_route_parameters is None
    assert "yaml.runtime.required_job_semantic_mismatch" in (
        support.blocking_rule_ids
    )
    project_yaml._VALIDATION_CACHE.clear()


def test_supported_receipt_rejects_semantic_observation_drift_after_rehash():
    receipt = assess_typed_project_readiness(
        case_id="orca-rehashed-observation-drift",
        program="orca",
        job_kind="opt",
        method={
            "functional": "B3LYP",
            "basis": "def2-TZVP",
            "freq": False,
        },
    )
    payload = receipt.model_dump(mode="json")
    payload["typed_project_support"]["required_job_observation"][
        "functional"
    ] = "pbe0"
    payload["typed_project_support"]["required_job_observation"][
        "basis"
    ] = "def2svp"
    payload["receipt_sha256"] = project_readiness_receipt_sha256(payload)

    with pytest.raises(ValidationError, match="derived from runtime body"):
        ProjectReadinessReceiptV1.model_validate(payload)


def test_supported_receipt_embeds_replayable_yaml_validation_and_runtime():
    receipt = assess_typed_project_readiness(
        case_id="gaussian-embedded-readiness-evidence",
        program="gaussian",
        job_kind="opt",
        method={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "dispersion": "D3BJ",
            "integration_grid": "ultrafine",
            "freq": True,
        },
    )
    support = receipt.typed_project_support

    assert support.project_yaml_text is not None
    assert "additional_route_parameters: Int=UltraFine" in (
        support.project_yaml_text
    )
    assert support.validation_record["runtime_summary"] == (
        support.runtime_summary
    )
    assert support.required_job_observation is not None
    assert (
        support.required_job_observation.additional_route_parameters
        == "Int=UltraFine"
    )


def test_ecp_request_rejects_unbound_not_requested_observation_after_rehash():
    receipt = assess_typed_project_readiness(
        case_id="orca-ecp-binding-coherence",
        program="orca",
        job_kind="sp",
        method={
            "functional": "B3LYP",
            "basis": "def2-TZVP",
            "freq": False,
            "ecp_binding": "required_elements",
            "required_ecp_elements": ("Pd",),
        },
    )
    payload = receipt.model_dump(mode="json")
    payload["basis_ecp"] = {
        "assessment": "not_requested",
        "required_elements": [],
        "observed_ecp_elements": [],
        "verdict": "not_checked",
        "status": "not_requested",
        "rule_ids": [],
    }
    payload["receipt_sha256"] = project_readiness_receipt_sha256(payload)

    with pytest.raises(ValidationError, match="current local BSE observation"):
        ProjectReadinessReceiptV1.model_validate(payload)


def test_receipt_replays_loader_and_rejects_coherent_fabricated_runtime():
    receipt = assess_typed_project_readiness(
        case_id="orca-fabricated-loader-body",
        program="orca",
        job_kind="opt",
        method={
            "functional": "B3LYP",
            "basis": "def2-TZVP",
            "freq": False,
        },
    )
    payload = receipt.model_dump(mode="json")
    support = payload["typed_project_support"]
    validation = json.loads(support["validation_record_json"])
    runtime = json.loads(support["runtime_summary_json"])
    for body in (validation["runtime_summary"]["opt"], runtime["opt"]):
        body["functional"] = "pbe0"
        body["basis"] = "def2svp"
    support["required_job_observation"]["functional"] = "pbe0"
    support["required_job_observation"]["basis"] = "def2svp"
    canonical_validation = json.dumps(
        validation,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    canonical_runtime = json.dumps(
        runtime,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    support["validation_record_json"] = canonical_validation
    support["runtime_summary_json"] = canonical_runtime
    support["validation_sha256"] = hashlib.sha256(
        canonical_validation.encode("utf-8")
    ).hexdigest()
    support["runtime_summary_sha256"] = hashlib.sha256(
        canonical_runtime.encode("utf-8")
    ).hexdigest()
    payload["receipt_sha256"] = project_readiness_receipt_sha256(payload)

    with pytest.raises(ValidationError, match="current loader output"):
        ProjectReadinessReceiptV1.model_validate(payload)


def test_receipt_replays_bse_and_rejects_fabricated_ecp_support():
    receipt = assess_typed_project_readiness(
        case_id="orca-fabricated-fe-ecp",
        program="orca",
        job_kind="sp",
        method={
            "functional": "B3LYP",
            "basis": "def2-TZVP",
            "freq": False,
            "ecp_binding": "required_elements",
            "required_ecp_elements": ("Fe",),
        },
    )
    assert receipt.typed_project_support.status is (
        TypedProjectSupportStatus.BLOCKED_ECP_BINDING
    )
    payload = receipt.model_dump(mode="json")
    payload["basis_ecp"].update(
        {
            "observed_ecp_elements": ["Fe"],
            "verdict": "ok",
            "rule_ids": [],
            "basis_element_receipt_sha256": "f" * 64,
        }
    )
    support = payload["typed_project_support"]
    support["status"] = "typed_project_supported"
    support["finding_rule_ids"] = []
    support["blocking_rule_ids"] = []
    payload["receipt_sha256"] = project_readiness_receipt_sha256(payload)

    with pytest.raises(ValidationError, match="current local BSE observation"):
        ProjectReadinessReceiptV1.model_validate(payload)
