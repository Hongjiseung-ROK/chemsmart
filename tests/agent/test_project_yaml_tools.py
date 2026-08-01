from __future__ import annotations

import yaml

from chemsmart.agent.permissions import (
    ApprovalDecision,
    PermissionMode,
    PermissionPolicy,
    ResolvedDecision,
)
from chemsmart.agent.project_yaml import (
    critic_project_yaml,
    extract_project_protocol,
    read_project_yaml,
    render_project_yaml,
    tool_input_json_schema,
    update_project_yaml,
    validate_project_yaml,
    write_project_yaml,
)
from chemsmart.agent.provider_adapter import ToolRequest
from chemsmart.agent.registry import ToolRegistry

PROFESSOR_CO2_PROMPT = """
I want to set up a project yaml for my project on CO2, you can name it as
co2.yaml using the following reported methods:

The model catalyst was conformationally sampled to locate the most stable
complex. The conformational sampling was carried out using Grimme's CREST
program, which used metadynamics (MTD) with genetic z-matrix crossing (GC)
performed at the GFN2-xTB extended semiempirical tight-binding level of theory
with opt=vtight option. Ten of the lowest energy GFN2-xTB optimized structures
from the CREST search were further optimized using density functional theory
(DFT), implemented in Gaussian16 rev. B.01 software, in the gas phase using the
B3LYP hybrid functional with Grimme's D3 dispersion correction with
Becke-Johnson damping (hereafter denoted B3LYP-D3BJ) and the def2-SVPD
Karlsruhe-family basis set for Br atom and def2-SVP basis set for all other
atoms. Minima and transition structures on the potential energy surface (PES)
were confirmed as such by harmonic frequency analysis, showing respectively
zero and one imaginary frequency.
"""


def test_professor_co2_prompt_renders_valid_gaussian_project_yaml():
    protocol = extract_project_protocol(
        PROFESSOR_CO2_PROMPT,
        project_name="co2.yaml",
        program="gaussian",
    )
    rendered = render_project_yaml(protocol)

    assert protocol["project_name"] == "co2"
    assert protocol["method"]["functional_route"] == (
        "b3lyp empiricaldispersion=gd3bj"
    )
    assert protocol["method"]["heavy_elements"] == ["Br"]
    assert protocol["method"]["heavy_elements_basis"] == "def2svpd"
    assert protocol["method"]["light_elements_basis"] == "def2svp"
    assert (
        "CREST/GFN2-xTB conformer sampling workflow"
        in protocol["unsupported_yaml_features"]
    )
    assert rendered["validation"]["verdict"] == "ok"

    parsed = yaml.safe_load(rendered["yaml_text"])
    expected_block = {
        "functional": "b3lyp empiricaldispersion=gd3bj",
        "basis": "gen",
        "freq": True,
        "heavy_elements": ["Br"],
        "heavy_elements_basis": "def2svpd",
        "light_elements_basis": "def2svp",
    }
    expected_solv_block = dict(expected_block)
    expected_solv_block["freq"] = False
    assert parsed == {"gas": expected_block, "solv": expected_solv_block}

    validation = validate_project_yaml(
        rendered["yaml_text"],
        program="gaussian",
        project_name="co2",
    )
    assert validation["verdict"] == "ok"
    assert validation["runtime_summary"]["opt"]["functional"] == (
        "b3lyp empiricaldispersion=gd3bj"
    )
    assert validation["runtime_summary"]["opt"]["basis"] == "gen"

    critic = critic_project_yaml(
        rendered["yaml_text"],
        protocol=protocol,
        program="gaussian",
        project_name="co2",
    )
    assert critic["verdict"] == "warn"
    assert any(
        issue["rule_id"] == "protocol.unsupported_yaml_feature"
        for issue in critic["issues"]
    )


def test_project_yaml_handles_cited_basis_and_method_only_render_input():
    protocol = extract_project_protocol(
        "Gaussian16 gas phase B3LYP-D3BJ with def2-SVPD[12,13] "
        "Karlsruhe-family basis set for Br atomand def2-SVP[12,14] "
        "for all other atoms. Frequency analysis confirmed minima.",
        project_name="co2.yaml",
        program="gaussian",
    )

    rendered = render_project_yaml(
        protocol["method"],
        project_name="co2",
        program="gaussian",
    )
    parsed = yaml.safe_load(rendered["yaml_text"])

    assert protocol["method"]["heavy_elements"] == ["Br"]
    assert protocol["method"]["heavy_elements_basis"] == "def2svpd"
    assert parsed["gas"]["functional"] == "b3lyp empiricaldispersion=gd3bj"
    assert parsed["gas"]["basis"] == "gen"
    assert parsed["gas"]["heavy_elements"] == ["Br"]


def test_project_yaml_extracts_solvent_and_rejects_missing_method():
    protocol = extract_project_protocol(
        "Use Gaussian optimization with M06-2X-D3BJ/def2-TZVP and confirm "
        "the minimum by frequency analysis. Use SMD(acetonitrile) for the "
        "solvated single-point stage.",
        project_name="nitrile",
        program="gaussian",
    )
    rendered = render_project_yaml(protocol)
    parsed = yaml.safe_load(rendered["yaml_text"])

    assert parsed["gas"]["functional"] == "m062x empiricaldispersion=gd3bj"
    assert parsed["gas"]["basis"] == "def2tzvp"
    assert "solvent_model" not in parsed["gas"]
    assert parsed["solv"]["freq"] is False
    assert parsed["solv"]["solvent_model"] == "smd"
    assert parsed["solv"]["solvent_id"] == "acetonitrile"

    invalid = validate_project_yaml(
        "gas:\n  functional: null\n  basis: def2svp\nsolv:\n"
        "  functional: null\n  basis: def2svp\n",
        program="gaussian",
    )
    assert invalid["verdict"] == "reject"
    assert any(
        issue["rule_id"] == "yaml.method_missing_functional"
        for issue in invalid["issues"]
    )


def test_project_yaml_preserves_a_distinct_gaussian_td_method():
    protocol = extract_project_protocol(
        "Optimize in the gas phase using PBE0/def2-SVP. For TD-DFT, use "
        "CAM-B3LYP/def2-SVP to calculate the absorption spectrum.",
        project_name="photo",
        program="gaussian",
    )
    rendered = render_project_yaml(protocol)
    parsed = yaml.safe_load(rendered["yaml_text"])

    assert protocol["method"]["functional"] == "pbe0"
    assert protocol["td"]["functional"] == "camb3lyp"
    assert parsed["gas"]["functional"] == "pbe0"
    assert parsed["td"]["functional"] == "camb3lyp"
    assert parsed["td"]["basis"] == "def2svp"

    validation = validate_project_yaml(
        rendered["yaml_text"], program="gaussian", project_name="photo"
    )
    assert validation["verdict"] == "ok"
    assert validation["runtime_summary"]["td"]["functional"] == "camb3lyp"

    critic = critic_project_yaml(
        rendered["yaml_text"], protocol=protocol, program="gaussian"
    )
    assert critic["verdict"] == "ok"


def test_single_basis_protocol_renders_and_validates_without_mixed_basis_leak():
    # A plain single-basis protocol must NOT emit heavy/light basis sections;
    # doing so under a non-gen basis trips the chemsmart mixed-basis guard.
    protocol = extract_project_protocol(
        "All structures were optimized in water using the SMD implicit "
        "solvation model at the B3LYP-D3BJ/def2-SVP level of theory in "
        "Gaussian 16. Frequency analysis confirmed all minima.",
        project_name="h2o",
        program="gaussian",
    )
    assert protocol["method"]["heavy_elements"] == []
    assert protocol["method"]["light_elements_basis"] is None

    rendered = render_project_yaml(protocol, project_name="h2o")
    parsed = yaml.safe_load(rendered["yaml_text"])
    assert parsed["gas"]["basis"] == "def2svp"
    assert "light_elements_basis" not in parsed["gas"]
    assert "heavy_elements" not in parsed["gas"]

    validation = validate_project_yaml(
        rendered["yaml_text"], program="gaussian", project_name="h2o"
    )
    assert validation["verdict"] == "ok"
    assert validation["runtime_summary"]["opt"]["basis"] == "def2svp"

    critic = critic_project_yaml(
        rendered["yaml_text"],
        protocol=protocol,
        program="gaussian",
        project_name="h2o",
    )
    assert critic["verdict"] == "ok"


def test_project_yaml_canonicalizes_model_supplied_mixed_basis_method_dict():
    rendered = render_project_yaml(
        {
            "functional": "B3LYP-D3BJ",
            "basis": "def2-SVP",
            "freq": True,
            "heavy_elements": ["I"],
            "heavy_elements_basis": "def2-SVPD",
        },
        project_name="iodobenzene_mixed",
        program="gaussian",
    )
    parsed = yaml.safe_load(rendered["yaml_text"])

    assert parsed["gas"]["functional"] == "b3lyp empiricaldispersion=gd3bj"
    assert parsed["gas"]["basis"] == "gen"
    assert parsed["gas"]["heavy_elements"] == ["I"]
    assert parsed["gas"]["heavy_elements_basis"] == "def2svpd"
    assert parsed["gas"]["light_elements_basis"] == "def2svp"


def test_project_yaml_extracts_spoken_light_atom_basis_phrase():
    protocol = extract_project_protocol(
        "I want to create a project yaml named co2.yaml for a CO2 reduction "
        "project. Use Gaussian for DFT refinements. The method should be "
        "B3LYP-D3BJ with def2-SVP for light atoms and def2-SVPD for Br. "
        "Use gas phase optimization followed by harmonic frequency analysis "
        "to confirm minima and transition states. The conformer search was "
        "done externally with CREST at GFN2-xTB, so include that as protocol "
        "context but do not make it the Gaussian calculation method.",
        project_name="co2.yaml",
        program="gaussian",
    )
    rendered = render_project_yaml(protocol)
    parsed = yaml.safe_load(rendered["yaml_text"])

    assert protocol["method"]["basis"] == "gen"
    assert protocol["method"]["heavy_elements_basis"] == "def2svpd"
    assert protocol["method"]["light_elements_basis"] == "def2svp"
    assert parsed["gas"]["basis"] == "gen"
    assert parsed["gas"]["heavy_elements"] == ["Br"]
    assert parsed["gas"]["heavy_elements_basis"] == "def2svpd"
    assert parsed["gas"]["light_elements_basis"] == "def2svp"

    critic = critic_project_yaml(
        rendered["yaml_text"],
        protocol=protocol,
        program="gaussian",
        project_name="co2",
    )
    assert critic["verdict"] == "warn"
    assert all(issue["severity"] != "reject" for issue in critic["issues"])
    assert (
        validate_project_yaml(
            rendered["yaml_text"],
            program="gaussian",
            project_name="iodobenzene_mixed",
        )["verdict"]
        == "ok"
    )


def test_validate_accepts_render_result_dict_chained_from_model():
    # The tool-loop model often passes the whole render_project_yaml result as
    # yaml_text; the harness must unwrap the yaml_text field instead of erroring.
    protocol = extract_project_protocol(
        "Optimize in water with SMD at B3LYP-D3BJ/def2-SVP; freq confirms "
        "minima.",
        project_name="h2o",
        program="gaussian",
    )
    rendered = render_project_yaml(protocol, project_name="h2o")

    from_string = validate_project_yaml(
        rendered["yaml_text"], program="gaussian", project_name="h2o"
    )
    from_dict = validate_project_yaml(
        rendered, program="gaussian", project_name="h2o"
    )
    assert from_string["verdict"] == from_dict["verdict"] == "ok"

    critic = critic_project_yaml(
        rendered, protocol=protocol, program="gaussian", project_name="h2o"
    )
    assert critic["verdict"] == "ok"


def test_validate_dedups_identical_candidate(monkeypatch):
    # Re-validating an unchanged candidate must not repeat the runtime loader
    # (dedup guard against build-mode re-validation loops).
    import chemsmart.agent.project_yaml as pj

    pj._VALIDATION_CACHE.clear()
    yaml_text = (
        "gas:\n  functional: b3lyp\n  basis: def2svp\n  freq: true\n"
        "solv:\n  functional: b3lyp\n  basis: def2svp\n  freq: false\n"
    )

    calls = {"n": 0}
    real_loader = pj._load_project_yaml_via_runtime

    def counting_loader(**kwargs):
        calls["n"] += 1
        return real_loader(**kwargs)

    monkeypatch.setattr(pj, "_load_project_yaml_via_runtime", counting_loader)

    first = pj.validate_project_yaml(yaml_text, program="gaussian")
    second = pj.validate_project_yaml(yaml_text, program="gaussian")

    assert first["verdict"] == second["verdict"] == "ok"
    assert calls["n"] == 1  # runtime loader ran once, second hit the cache
    assert "revalidation_skipped" not in first
    assert second["revalidation_skipped"] is True


def test_project_yaml_validator_rejects_mixed_basis_without_gen():
    yaml_text = """
gas:
  functional: b3lyp empiricaldispersion=gd3bj
  basis: def2svp
  heavy_elements: [Br]
  heavy_elements_basis: def2svpd
  light_elements_basis: def2svp
"""

    result = validate_project_yaml(yaml_text, program="gaussian")

    assert result["verdict"] == "reject"
    assert any(
        issue["rule_id"] == "yaml.gaussian.mixed_basis_without_gen"
        for issue in result["issues"]
    )


def test_project_yaml_write_uses_workspace_config_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    yaml_text = """
gas:
  functional: b3lyp empiricaldispersion=gd3bj
  basis: def2svp
  freq: true
solv:
  functional: b3lyp empiricaldispersion=gd3bj
  basis: def2svp
  freq: false
"""

    result = write_project_yaml("co2.yaml", yaml_text, program="gaussian")

    target = tmp_path / ".chemsmart" / "gaussian" / "co2.yaml"
    assert result["ok"] is True
    assert result["written_path"] == str(target)
    assert target.read_text(encoding="utf-8").endswith("\n")

    from chemsmart.settings.gaussian import GaussianProjectSettings

    settings = GaussianProjectSettings.from_project("co2")
    assert settings.opt_settings().functional == (
        "b3lyp empiricaldispersion=gd3bj"
    )


def test_project_yaml_read_and_update_use_workspace_config_dir(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    yaml_text = """
gas:
  functional: b3lyp
  basis: def2svp
  freq: true
solv:
  functional: b3lyp
  basis: def2svp
  freq: false
"""
    written = write_project_yaml("demo", yaml_text, program="gaussian")
    assert written["ok"] is True

    loaded = read_project_yaml()
    assert loaded["ok"] is True
    assert loaded["project_name"] == "demo"
    assert loaded["program"] == "gaussian"
    assert loaded["parsed"]["gas"]["functional"] == "b3lyp"

    updated = update_project_yaml(
        {"gas.functional": "m062x", "solv.functional": "m062x"},
        project_name="demo",
        program="gaussian",
    )
    assert updated["ok"] is True
    assert "-  functional: b3lyp" in updated["diff"]
    assert "+  functional: m062x" in updated["diff"]

    loaded_after = read_project_yaml("demo", "gaussian")
    assert loaded_after["parsed"]["gas"]["functional"] == "m062x"


def test_project_yaml_tools_are_registered_and_write_requires_approval():
    registry = ToolRegistry.default()
    names = {tool.name for tool in registry.list_tools()}

    assert {
        "extract_project_protocol",
        "render_project_yaml",
        "validate_project_yaml",
        "critic_project_yaml",
        "write_project_yaml",
        "read_project_yaml",
        "update_project_yaml",
        "synthesize_command",
        "repair_command",
        "execute_chemsmart_command",
    }.issubset(names)

    request = ToolRequest(
        request_id="req",
        provider="test",
        provider_call_id="call",
        name="write_project_yaml",
        arguments_json="{}",
        arguments={},
        raw={},
    )
    policy = PermissionPolicy(mode=PermissionMode.PERMISSION)
    resolved = policy.resolve(request)
    assert resolved.decision == ResolvedDecision.NEEDS_USER
    policy.record("write_project_yaml", ApprovalDecision.ALLOW_SESSION)
    assert "write_project_yaml" not in policy.session_allow


def test_plain_d3_dispersion_is_preserved_not_dropped():
    # "b3lyp-d3" (zero-damping D3, not BJ) must render the gd3 route keyword;
    # it was previously silently dropped because only d3bj was handled.
    for functional in ("b3lyp-d3", "B3LYP empiricaldispersion=gd3"):
        rendered = render_project_yaml(
            {
                "functional": functional,
                "basis": "genecp",
                "freq": True,
                "heavy_elements": ["Br"],
                "heavy_elements_basis": "SDD",
                "light_elements_basis": "6-31G**",
            },
            project_name="ch3br",
            program="gaussian",
        )
        parsed = yaml.safe_load(rendered["yaml_text"])
        assert parsed["gas"]["functional"] == (
            "b3lyp empiricaldispersion=gd3"
        ), functional

    # D3BJ still renders gd3bj (no regression).
    rendered = render_project_yaml(
        {"functional": "b3lyp-d3bj", "basis": "def2svp", "freq": True},
        project_name="x",
        program="gaussian",
    )
    parsed = yaml.safe_load(rendered["yaml_text"])
    assert parsed["gas"]["functional"] == "b3lyp empiricaldispersion=gd3bj"

    # ORCA plain D3 maps to the ORCA D3 keyword.
    rendered = render_project_yaml(
        {"functional": "pbe0", "dispersion": "d3", "basis": "def2tzvp"},
        project_name="cat",
        program="orca",
    )
    parsed = yaml.safe_load(rendered["yaml_text"])
    assert parsed["gas"]["functional"] == "pbe0"
    assert parsed["gas"]["dispersion"] == "D3"

    # Gaussian route syntax must never leak into the ORCA functional field.
    rendered = render_project_yaml(
        {
            "functional": "b3lyp empiricaldispersion=gd3bj",
            "basis": "def2tzvp",
        },
        project_name="cat_bj",
        program="orca",
    )
    parsed = yaml.safe_load(rendered["yaml_text"])
    assert parsed["gas"]["functional"] == "b3lyp"
    assert parsed["gas"]["dispersion"] == "D3BJ"


def test_orca_native_ma_def2_tzvp_is_not_rejected_as_missing_from_bse():
    rendered = render_project_yaml(
        {
            "program": "orca",
            "method": {
                "functional": "b3lyp",
                "dispersion": "d3bj",
                "basis": "ma-def2-TZVP",
                "freq": True,
            },
        },
        project_name="orca_native_basis",
        program="orca",
        profile="paper",
    )

    parsed = yaml.safe_load(rendered["yaml_text"])
    assert rendered["validation"]["verdict"] == "ok"
    assert parsed["gas"]["functional"] == "b3lyp"
    assert parsed["gas"]["dispersion"] == "D3BJ"
    assert parsed["gas"]["basis"] == "ma-def2-TZVP"

    gaussian = render_project_yaml(
        {
            "program": "gaussian",
            "method": {
                "functional": "b3lyp",
                "basis": "ma-def2-TZVP",
                "freq": True,
            },
        },
        project_name="gaussian_native_basis",
        program="gaussian",
        profile="paper",
    )
    assert gaussian["validation"]["verdict"] == "reject"


def test_orca_canonical_uppercase_dispersion_is_preserved():
    rendered = render_project_yaml(
        {
            "program": "orca",
            "method": {
                "functional": "B3LYP",
                "dispersion": "D3BJ",
                "basis": "ma-def2-TZVP",
                "freq": True,
            },
        },
        project_name="orca_uppercase_dispersion",
        program="orca",
        profile="paper",
    )

    parsed = yaml.safe_load(rendered["yaml_text"])
    assert rendered["validation"]["verdict"] == "ok"
    assert parsed["gas"]["functional"] == "b3lyp"
    assert parsed["gas"]["dispersion"] == "D3BJ"


def test_orca_required_job_kinds_observe_each_loader_path():
    rendered = render_project_yaml(
        {
            "program": "orca",
            "method": {
                "functional": "B3LYP",
                "dispersion": "D3BJ",
                "basis": "ma-def2-TZVP",
                # A NEB stage and a stationary-point frequency stage require
                # separate project settings. This test observes loader paths.
                "freq": False,
            },
        },
        project_name="orca_required_jobs",
        program="orca",
        profile="paper",
        required_job_kinds=("opt", "neb", "ts", "sp"),
    )

    validation = rendered["validation"]
    assert validation["verdict"] == "ok"
    assert validation["required_job_kinds"] == ["neb", "opt", "sp", "ts"]
    for job_kind in validation["required_job_kinds"]:
        assert validation["runtime_summary"][job_kind]["jobtype"] == job_kind
    neb = validation["runtime_summary"]["neb"]
    assert neb["functional"] == "b3lyp"
    assert neb["basis"] == "ma-def2-TZVP"
    assert neb["dispersion"] == "D3BJ"
    assert neb["freq"] is False
    assert neb["jobtype_observation"] == {
        "kind": "loader_jobtype",
        "observed": "neb",
        "origin": "derived",
        "source_block": "gas",
        "setting_origins": {
            "ab_initio": "default",
            "semiempirical": "default",
            "functional": "derived",
            "gfn_version": "default",
            "basis": "derived",
            "gen_genecp_file": "default",
            "heavy_elements": "default",
            "heavy_elements_basis": "default",
            "light_elements_basis": "default",
            "dispersion": "derived",
            "solvent_model": "default",
            "solvent_id": "default",
            "custom_solvent": "default",
            "freq": "derived",
            "numfreq": "default",
            "optimization_level": "default",
        },
    }


def test_required_job_kinds_fail_closed_when_neb_observation_is_missing(
    monkeypatch,
):
    import chemsmart.agent.project_yaml as project_yaml

    project_yaml._VALIDATION_CACHE.clear()

    real_loader = project_yaml._load_project_yaml_via_runtime

    def loader_without_neb(**kwargs):
        assert kwargs["required_job_kinds"] == ("neb", "opt", "sp", "ts")
        summary = real_loader(**kwargs)
        summary.pop("neb")
        return summary

    monkeypatch.setattr(
        project_yaml,
        "_load_project_yaml_via_runtime",
        loader_without_neb,
    )
    validation = validate_project_yaml(
        "gas:\n"
        "  functional: b3lyp\n"
        "  basis: def2svp\n"
        "  freq: true\n"
        "solv:\n"
        "  functional: b3lyp\n"
        "  basis: def2svp\n"
        "  freq: false\n",
        program="orca",
        project_name="missing_neb_observation",
        required_job_kinds=("opt", "neb", "ts", "sp"),
    )

    assert validation["verdict"] == "reject"
    assert "neb" not in validation["runtime_summary"]
    assert {
        issue["rule_id"] for issue in validation["issues"]
    } == {"yaml.runtime.required_jobtype_unobserved"}
    project_yaml._VALIDATION_CACHE.clear()


def test_required_job_kinds_fail_closed_on_method_or_basis_drift(monkeypatch):
    import chemsmart.agent.project_yaml as project_yaml

    project_yaml._VALIDATION_CACHE.clear()
    real_loader = project_yaml._load_project_yaml_via_runtime

    def loader_with_semantic_drift(**kwargs):
        summary = real_loader(**kwargs)
        summary["neb"]["functional"] = "pbe0"
        summary["neb"]["basis"] = "def2-SVP"
        return summary

    monkeypatch.setattr(
        project_yaml,
        "_load_project_yaml_via_runtime",
        loader_with_semantic_drift,
    )
    validation = validate_project_yaml(
        "gas:\n"
        "  functional: b3lyp\n"
        "  dispersion: D3BJ\n"
        "  basis: ma-def2-TZVP\n"
        "  freq: false\n"
        "solv:\n"
        "  functional: b3lyp\n"
        "  dispersion: D3BJ\n"
        "  basis: ma-def2-TZVP\n"
        "  freq: false\n",
        program="orca",
        project_name="required_job_semantic_drift",
        required_job_kinds=("neb",),
    )

    assert validation["verdict"] == "reject"
    mismatches = [
        issue
        for issue in validation["issues"]
        if issue["rule_id"]
        == "yaml.runtime.required_job_semantic_mismatch"
    ]
    assert len(mismatches) == 2
    assert {"functional", "basis"} == {
        field
        for field in ("functional", "basis")
        if any(field in issue["message"] for issue in mismatches)
    }
    project_yaml._VALIDATION_CACHE.clear()


def test_xtb_project_yaml_uses_real_loader_and_keeps_state_in_command():
    protocol = extract_project_protocol(
        "Use GFN2-xTB with opt=vtight and ALPB(water) for conformer refinement.",
        project_name="ensemble",
        program="xtb",
    )

    rendered = render_project_yaml(protocol, program="xtb")
    parsed = yaml.safe_load(rendered["yaml_text"])

    assert protocol["method"] == {
        "gfn_version": "gfn2",
        "optimization_level": "vtight",
        "solvent_model": "alpb",
        "solvent_id": "water",
    }
    assert set(parsed) == {"sp", "opt", "hess"}
    assert parsed["opt"]["gfn_version"] == "gfn2"
    assert parsed["opt"]["optimization_level"] == "vtight"
    assert "charge" not in parsed["opt"]
    assert "multiplicity" not in parsed["opt"]
    assert rendered["validation"]["verdict"] == "ok"
    assert rendered["validation"]["runtime_summary"]["opt"] == {
        "jobtype": "opt",
        "gfn_version": "gfn2",
        "optimization_level": "vtight",
        "functional": None,
        "basis": None,
        "freq": None,
        "solvent_model": "alpb",
        "solvent_id": "water",
        "heavy_elements": None,
        "heavy_elements_basis": None,
        "light_elements_basis": None,
    }


def test_xtb_project_yaml_rejects_missing_gfn_and_molecular_state():
    rendered = render_project_yaml(
        {"optimization_level": "tight"},
        project_name="incomplete",
        program="xtb",
    )
    assert rendered["validation"]["verdict"] == "reject"
    assert any(
        issue["rule_id"] == "yaml.xtb.gfn_invalid"
        for issue in rendered["validation"]["issues"]
    )

    invalid = validate_project_yaml(
        "opt:\n  gfn_version: gfn2\n  charge: 1\n  multiplicity: 2\n",
        program="xtb",
    )
    assert invalid["verdict"] == "reject"
    assert any(
        issue["rule_id"] == "yaml.xtb.molecular_state_forbidden"
        for issue in invalid["issues"]
    )


def test_xtb_project_yaml_rejects_every_undeclared_job_key():
    counterexamples = (
        ("sp", "optimization_level", "tight"),
        ("sp", "jobtype", "opt"),
        ("opt", "grad", True),
        ("opt", "multiplicity", 2),
        ("hess", "charge", -1),
        ("hess", "unrecognized_setting", "value"),
    )

    for job, key, value in counterexamples:
        yaml_text = yaml.safe_dump(
            {job: {"gfn_version": "gfn2", key: value}},
            sort_keys=False,
        )
        validation = validate_project_yaml(yaml_text, program="xtb")

        assert validation["verdict"] == "reject", (job, key)
        assert any(
            issue["rule_id"] == "yaml.xtb.undeclared_job_key"
            and key in issue["message"]
            for issue in validation["issues"]
        ), (job, key)


def test_xtb_project_yaml_rejects_effective_job_family_drift(monkeypatch):
    import chemsmart.agent.project_yaml as project_yaml

    project_yaml._VALIDATION_CACHE.clear()

    def mismatched_loader(**_kwargs):
        return {
            "sp": {"jobtype": "opt"},
            "opt": {"jobtype": "opt"},
            "hess": {"jobtype": "hess"},
        }

    monkeypatch.setattr(
        project_yaml,
        "_load_project_yaml_via_runtime",
        mismatched_loader,
    )
    validation = validate_project_yaml(
        "sp:\n  gfn_version: gfn2\n",
        program="xtb",
        project_name="effective-job-family-drift",
    )

    assert validation["verdict"] == "reject"
    assert any(
        issue["rule_id"] == "yaml.xtb.effective_jobtype_mismatch"
        and "sp" in issue["message"]
        and "opt" in issue["message"]
        for issue in validation["issues"]
    )
    project_yaml._VALIDATION_CACHE.clear()


def test_paper_profile_blocks_missing_basis_and_frequency_evidence():
    protocol = extract_project_protocol(
        "ORCA calculations used the B3LYP functional.",
        project_name="paper_incomplete",
        program="orca",
        profile="paper",
    )

    blocked = render_project_yaml(
        protocol,
        program="orca",
        profile="paper",
    )
    legacy = render_project_yaml(protocol, program="orca")

    assert blocked["ok"] is False
    assert blocked["status"] == "blocked_missing_evidence"
    assert blocked["yaml_text"] is None
    assert {
        issue["rule_id"] for issue in blocked["blocking_issues"]
    } == {
        "paper.project.basis_missing",
        "paper.project.frequency_missing",
    }
    assert legacy["yaml_text"] is not None


def test_render_project_yaml_provider_schema_keeps_derived_route_compatibility():
    schema = tool_input_json_schema("render_project_yaml")

    assert schema is not None
    protocol_properties = schema["properties"]["protocol"]["properties"]
    method_properties = protocol_properties["method"]["properties"]
    td_properties = protocol_properties["td"]["properties"]
    assert method_properties["functional_route"]["deprecated"] is True
    assert td_properties["functional_route"]["deprecated"] is True
    assert method_properties["solv_freq"]["type"] == ["boolean", "null"]
    assert "solv_freq" not in td_properties

    protocol = extract_project_protocol(
        "Gaussian B3LYP-D3BJ/def2-SVP with frequency analysis.",
        program="gaussian",
        profile="paper",
    )
    tool = ToolRegistry.default().get_tool("render_project_yaml")
    assert tool is not None
    validated = tool.validate_args(
        {"protocol": protocol, "program": "gaussian", "profile": "paper"}
    )
    rendered = render_project_yaml(**validated)

    assert rendered["validation"]["verdict"] == "ok"
    assert yaml.safe_load(rendered["yaml_text"])["gas"]["functional"] == (
        "b3lyp empiricaldispersion=gd3bj"
    )


def test_paper_profile_rejects_program_inapplicable_method_fields():
    base_methods = {
        "gaussian": {
            "functional": "b3lyp",
            "basis": "def2svp",
            "freq": True,
        },
        "orca": {
            "functional": "b3lyp",
            "basis": "def2svp",
            "freq": True,
        },
        "xtb": {"gfn_version": "gfn2"},
    }
    cases = (
        ("gaussian", "gfn_version", "gfn2"),
        ("gaussian", "optimization_level", "tight"),
        ("orca", "integration_grid", "ultrafine"),
        ("orca", "gfn_version", "gfn2"),
        ("orca", "optimization_level", "tight"),
        ("xtb", "functional", "b3lyp"),
        ("xtb", "functional_route", "b3lyp"),
        ("xtb", "basis", "def2svp"),
        ("xtb", "dispersion", "d3bj"),
        ("xtb", "freq", False),
        ("xtb", "solv_freq", True),
        ("xtb", "integration_grid", "ultrafine"),
        ("xtb", "heavy_elements", ["Br"]),
        ("xtb", "heavy_elements_basis", "def2svpd"),
        ("xtb", "light_elements_basis", "def2svp"),
    )

    for program, field, value in cases:
        method = dict(base_methods[program])
        method[field] = value
        blocked = render_project_yaml(
            {"program": program, "method": method},
            project_name=f"{program}_{field}",
            program=program,
            profile="paper",
        )

        assert blocked["ok"] is False, (program, field)
        assert blocked["status"] == "blocked_unsupported_setting"
        assert any(
            issue["rule_id"] == "paper.project.field_not_applicable"
            and issue["field"] == f"method.{field}"
            for issue in blocked["blocking_issues"]
        ), (program, field, blocked["blocking_issues"])


def test_paper_profile_rejects_td_that_selected_program_cannot_render():
    for program, method in (
        (
            "orca",
            {"functional": "b3lyp", "basis": "def2svp", "freq": True},
        ),
        ("xtb", {"gfn_version": "gfn2"}),
    ):
        protocol = {
            "program": program,
            "method": method,
            "td": {
                "functional": "camb3lyp",
                "basis": "def2svp",
                "freq": True,
            },
        }
        blocked = render_project_yaml(
            protocol,
            project_name=f"{program}_td",
            program=program,
            profile="paper",
        )
        legacy = render_project_yaml(
            protocol,
            project_name=f"{program}_td_legacy",
            program=program,
        )

        assert any(
            issue["rule_id"] == "paper.project.td_not_applicable"
            and issue["field"] == "td"
            for issue in blocked["blocking_issues"]
        )
        assert blocked["status"] == "blocked_unsupported_setting"
        assert "td" not in yaml.safe_load(legacy["yaml_text"])


def test_paper_profile_rejects_fields_ignored_inside_gaussian_td():
    blocked = render_project_yaml(
        {
            "program": "gaussian",
            "method": {
                "functional": "b3lyp",
                "basis": "def2svp",
                "freq": True,
            },
            "td": {
                "functional": "camb3lyp",
                "basis": "def2svp",
                "freq": True,
                "solvent_model": "smd",
                "solvent_id": "water",
            },
        },
        project_name="gaussian_td_solvent",
        program="gaussian",
        profile="paper",
    )

    assert {
        issue["field"]
        for issue in blocked["blocking_issues"]
        if issue["rule_id"] == "paper.project.field_not_applicable"
    } == {"td.solvent_id", "td.solvent_model"}
    assert blocked["status"] == "blocked_unsupported_setting"


def test_paper_profile_rejects_dispersion_the_compiler_drops():
    for program in ("gaussian", "orca"):
        for dispersion in ("D2", "D3ZERO", "D4"):
            protocol = {
                "program": program,
                "method": {
                    "functional": "b3lyp",
                    "dispersion": dispersion,
                    "basis": "def2svp",
                    "freq": True,
                },
            }
            blocked = render_project_yaml(
                protocol,
                project_name=f"{program}_{dispersion.lower()}",
                program=program,
                profile="paper",
            )
            legacy = render_project_yaml(
                protocol,
                project_name=f"{program}_{dispersion.lower()}_legacy",
                program=program,
            )

            assert any(
                issue["rule_id"] == "paper.project.dispersion_unsupported"
                and issue["field"] == "method.dispersion"
                for issue in blocked["blocking_issues"]
            )
            assert blocked["status"] == "blocked_unsupported_setting"
            assert "dispersion" not in yaml.safe_load(legacy["yaml_text"])[
                "gas"
            ]


def test_paper_profile_rejects_unchecked_embedded_dispersion_without_loss():
    for program in ("gaussian", "orca"):
        for functional in ("B3LYP-D2", "B3LYP-D3ZERO", "B3LYP-D4"):
            protocol = {
                "program": program,
                "method": {
                    "functional": functional,
                    "basis": "def2svp",
                    "freq": True,
                },
            }
            blocked = render_project_yaml(
                protocol,
                project_name=f"{program}_{functional.lower()}",
                program=program,
                profile="paper",
            )
            legacy = render_project_yaml(
                protocol,
                project_name=f"{program}_{functional.lower()}_legacy",
                program=program,
            )

            assert blocked["status"] == "blocked_unsupported_setting"
            assert blocked["yaml_text"] is None
            assert any(
                issue["rule_id"] == "paper.project.dispersion_unsupported"
                and issue["field"] == "method.functional"
                for issue in blocked["blocking_issues"]
            )
            assert yaml.safe_load(legacy["yaml_text"])["gas"][
                "functional"
            ] == "b3lyp"


def test_paper_profile_preserves_functional_and_dispersion_alias_intent():
    gaussian_cases = {
        "M06-2X": "m062x",
        "wB97X-D": "wb97xd",
        "B3LYP-D3": "b3lyp empiricaldispersion=gd3",
        "B3LYP-D3BJ": "b3lyp empiricaldispersion=gd3bj",
    }
    for functional, expected in gaussian_cases.items():
        rendered = render_project_yaml(
            {
                "method": {
                    "functional": functional,
                    "basis": "def2svp",
                    "freq": True,
                }
            },
            project_name=f"gaussian_{functional.lower()}",
            program="gaussian",
            profile="paper",
        )

        assert rendered["validation"]["verdict"] == "ok"
        assert yaml.safe_load(rendered["yaml_text"])["gas"][
            "functional"
        ] == expected

    for functional, expected_dispersion in (
        ("B3LYP-D3", "D3"),
        ("B3LYP-D3BJ", "D3BJ"),
    ):
        rendered = render_project_yaml(
            {
                "method": {
                    "functional": functional,
                    "basis": "def2svp",
                    "freq": True,
                }
            },
            project_name=f"orca_{functional.lower()}",
            program="orca",
            profile="paper",
        )
        gas = yaml.safe_load(rendered["yaml_text"])["gas"]

        assert rendered["validation"]["verdict"] == "ok"
        assert gas["functional"] == "b3lyp"
        assert gas["dispersion"] == expected_dispersion


def test_paper_profile_preserves_checked_orca_compound_functional():
    rendered = render_project_yaml(
        {
            "method": {
                "functional": "B97M-D4",
                "basis": "def2svp",
                "freq": True,
            }
        },
        project_name="orca_b97m_d4",
        program="orca",
        profile="paper",
    )

    assert rendered["validation"]["verdict"] == "ok"
    gas = yaml.safe_load(rendered["yaml_text"])["gas"]
    assert gas["functional"] == "b97m-d4"
    assert "dispersion" not in gas


def test_paper_profile_preserves_supported_dispersion_for_both_programs():
    expected = {
        ("gaussian", "D3"): ("functional", "b3lyp empiricaldispersion=gd3"),
        ("gaussian", "D3BJ"): (
            "functional",
            "b3lyp empiricaldispersion=gd3bj",
        ),
        ("orca", "D3"): ("dispersion", "D3"),
        ("orca", "D3BJ"): ("dispersion", "D3BJ"),
    }

    for (program, dispersion), (key, value) in expected.items():
        rendered = render_project_yaml(
            {
                "program": program,
                "method": {
                    "functional": "b3lyp",
                    "dispersion": dispersion,
                    "basis": "def2svp",
                    "freq": True,
                },
            },
            project_name=f"{program}_{dispersion.lower()}_preserved",
            program=program,
            profile="paper",
        )

        assert rendered["validation"]["verdict"] == "ok"
        assert yaml.safe_load(rendered["yaml_text"])["gas"][key] == value


def test_paper_profile_rejects_unknown_method_and_td_fields():
    unknown_method = render_project_yaml(
        {
            "program": "orca",
            "method": {
                "functional": "b3lyp",
                "basis": "def2svp",
                "freq": True,
                "native_route": "VeryTightSCF",
            },
        },
        project_name="unknown_method_field",
        program="orca",
        profile="paper",
    )
    unknown_td = render_project_yaml(
        {
            "program": "gaussian",
            "method": {
                "functional": "b3lyp",
                "basis": "def2svp",
                "freq": True,
            },
            "td": {
                "functional": "camb3lyp",
                "basis": "def2svp",
                "freq": True,
                "root_count": 10,
            },
        },
        project_name="unknown_td_field",
        program="gaussian",
        profile="paper",
    )

    assert any(
        issue["rule_id"] == "paper.project.field_unknown"
        and issue["field"] == "method.native_route"
        for issue in unknown_method["blocking_issues"]
    )
    assert any(
        issue["rule_id"] == "paper.project.field_unknown"
        and issue["field"] == "td.root_count"
        for issue in unknown_td["blocking_issues"]
    )
    assert unknown_method["status"] == "blocked_invalid_specification"
    assert unknown_td["status"] == "blocked_invalid_specification"


def test_paper_profile_rejects_native_route_fragments_as_functionals():
    for functional in (
        "b3lyp nosymm",
        "b3lyp/def2svp",
        "b3lyp empiricaldispersion=gd3bj",
    ):
        blocked = render_project_yaml(
            {
                "method": {
                    "functional": functional,
                    "basis": "def2svp",
                    "freq": True,
                }
            },
            project_name="raw_functional",
            program="gaussian",
            profile="paper",
        )

        assert blocked["status"] == "blocked_invalid_specification"
        assert any(
            issue["rule_id"] == "paper.project.functional_not_atomic"
            for issue in blocked["blocking_issues"]
        )


def test_paper_profile_rejects_wrong_types_without_legacy_regression():
    cases = (
        ("functional", True),
        ("freq", 1),
        ("solv_freq", "true"),
        ("heavy_elements", "Br"),
    )
    for field, value in cases:
        method = {
            "functional": "b3lyp",
            "basis": "def2svp",
            "freq": True,
            field: value,
        }
        blocked = render_project_yaml(
            {"method": method},
            project_name=f"wrong_type_{field}",
            program="gaussian",
            profile="paper",
        )

        assert blocked["status"] == "blocked_invalid_specification"
        assert any(
            issue["rule_id"] == "paper.project.field_type_invalid"
            and issue["field"] == f"method.{field}"
            for issue in blocked["blocking_issues"]
        )

    mixed_keys = {
        "functional": "b3lyp",
        "basis": "def2svp",
        "freq": True,
        7: "route",
    }
    blocked = render_project_yaml(
        {"method": mixed_keys},
        project_name="mixed_keys",
        program="gaussian",
        profile="paper",
    )
    legacy = render_project_yaml(
        {"method": mixed_keys},
        project_name="mixed_keys_legacy",
        program="gaussian",
    )

    assert blocked["status"] == "blocked_invalid_specification"
    assert any(
        issue["rule_id"] == "paper.project.field_key_invalid"
        for issue in blocked["blocking_issues"]
    )
    assert legacy["yaml_text"] is not None


def test_paper_profile_returns_structured_blockers_for_incomplete_td():
    blocked = render_project_yaml(
        {
            "method": {
                "functional": "b3lyp",
                "basis": "def2svp",
                "freq": True,
            },
            "td": {},
        },
        project_name="incomplete_td",
        program="gaussian",
        profile="paper",
    )

    assert blocked["status"] == "blocked_missing_evidence"
    assert {
        (issue["rule_id"], issue["field"])
        for issue in blocked["blocking_issues"]
    } == {
        ("paper.project.basis_missing", "td.basis"),
        ("paper.project.frequency_missing", "td.freq"),
        ("paper.project.functional_missing", "td.functional"),
    }


def test_paper_profile_renders_typed_solv_frequency_setting():
    for program in ("gaussian", "orca"):
        rendered = render_project_yaml(
            {
                "method": {
                    "functional": "b3lyp",
                    "basis": "def2svp",
                    "freq": False,
                    "solv_freq": True,
                }
            },
            project_name=f"{program}_solv_freq",
            program=program,
            profile="paper",
        )
        document = yaml.safe_load(rendered["yaml_text"])

        assert rendered["validation"]["verdict"] == "ok"
        assert document["gas"]["freq"] is False
        assert document["solv"]["freq"] is True


def test_paper_functional_route_must_be_deterministically_derived():
    matched = render_project_yaml(
        {
            "program": "gaussian",
            "method": {
                "functional": "B3LYP",
                "dispersion": "D3BJ",
                "functional_route": "b3lyp empiricaldispersion=gd3bj",
                "basis": "def2svp",
                "freq": True,
            },
        },
        project_name="derived_route",
        program="gaussian",
        profile="paper",
    )
    mismatched_protocol = {
        "program": "gaussian",
        "method": {
            "functional": "b3lyp",
            "functional_route": "pbe0 nosymm",
            "basis": "def2svp",
            "freq": True,
        },
    }
    blocked = render_project_yaml(
        mismatched_protocol,
        project_name="alternate_route",
        program="gaussian",
        profile="paper",
    )
    legacy = render_project_yaml(
        mismatched_protocol,
        project_name="alternate_route_legacy",
        program="gaussian",
    )

    assert matched["validation"]["verdict"] == "ok"
    assert any(
        issue["rule_id"] == "paper.project.functional_route_not_derived"
        and issue["field"] == "method.functional_route"
        for issue in blocked["blocking_issues"]
    )
    assert blocked["status"] == "blocked_invalid_specification"
    assert yaml.safe_load(legacy["yaml_text"])["gas"]["functional"] == "pbe0"


def test_paper_profile_preserves_explicit_negative_frequency_setting():
    protocol = extract_project_protocol(
        (
            "ORCA calculations used B3LYP/def2-SVP. Harmonic frequency "
            "calculations were not performed."
        ),
        project_name="paper_no_frequency",
        program="orca",
        profile="paper",
    )
    rendered = render_project_yaml(
        protocol,
        program="orca",
        profile="paper",
    )

    assert protocol["method"]["freq"] is False
    assert rendered["validation"]["verdict"] == "ok"
    assert yaml.safe_load(rendered["yaml_text"])["gas"]["freq"] is False


def test_paper_profile_rejects_incomplete_mixed_basis_mapping():
    blocked = render_project_yaml(
        {
            "program": "gaussian",
            "method": {
                "functional": "b3lyp",
                "basis": "gen",
                "freq": True,
                "heavy_elements": ["Br"],
                "heavy_elements_basis": "def2svpd",
            },
        },
        project_name="mixed_basis_gap",
        program="gaussian",
        profile="paper",
    )

    assert blocked["status"] == "blocked_missing_evidence"
    assert "paper.project.mixed_basis_incomplete" in {
        issue["rule_id"] for issue in blocked["blocking_issues"]
    }


def test_paper_xtb_profile_distinguishes_method_from_crest_workflow():
    protocol = extract_project_protocol(
        "Use GFN2-xTB with opt=vtight and ALPB(water).",
        project_name="xtb_paper",
        program="xtb",
        profile="paper",
    )
    rendered = render_project_yaml(
        protocol,
        program="xtb",
        profile="paper",
        required_job_kinds=("opt",),
    )

    assert protocol["unsupported_yaml_features"] == []
    assert rendered["validation"]["verdict"] == "ok"

    crest_protocol = extract_project_protocol(
        "Use CREST metadynamics at GFN2-xTB.",
        project_name="crest_paper",
        program="xtb",
        profile="paper",
    )
    blocked = render_project_yaml(
        crest_protocol,
        program="xtb",
        profile="paper",
    )
    assert blocked["status"] == "blocked_unsupported_setting"
    assert "paper.project.unsupported_protocol_feature" in {
        issue["rule_id"] for issue in blocked["blocking_issues"]
    }


def test_xtb_validation_binds_every_used_command_job_block():
    validation = validate_project_yaml(
        "sp:\n  gfn_version: gfn2\n",
        program="xtb",
        project_name="partial_xtb",
        required_job_kinds=("opt",),
    )

    assert validation["verdict"] == "reject"
    assert "yaml.xtb.required_job_block_missing" in {
        issue["rule_id"] for issue in validation["issues"]
    }
