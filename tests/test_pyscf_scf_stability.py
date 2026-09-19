"""Whether the converged reference is a minimum in orbital-rotation space.

Every PySCF energy, orbital energy, population, spin expectation, gradient
and Hessian ChemSmart delivers stands on a converged SCF solution, and an
internally or externally unstable solution is a saddle in that space: the
SCF "converged", every receipt is green, and the numbers describe the
wrong state.  Nothing here graded that, and nothing here recorded it.

Three facts these tests hold, each measured on PySCF 2.14.0 before it was
designed around:

- ``external`` is not one question.  ``rhf_external`` searches
  RHF/RKS -> UHF/UKS and ``uhf_external`` searches UHF/UKS -> GHF/GKS, so
  a bare "externally unstable" means different things on a restricted and
  an unrestricted reference and the record names the space.
- Both of those functions *also* solve the real -> complex question, log
  it, and return only the other flag.  This host cannot determine it, so
  it is recorded by name as undetermined rather than folded into a
  boolean a reader would take for it.
- ``rohf_stability`` runs the internal Davidson and then raises
  ``NotImplementedError`` from ``rohf_external``, so one combined call
  throws away an answer PySCF already computed.  The driver asks the two
  questions separately for that reason, and the hydrogen-atom fixture is
  where that is visible.

Absence is never stability: an artifact written under a contract that did
not carry the field, or a run nobody asked, reads as ``None`` and
``not_requested``.
"""

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from chemsmart.io.pyscf.output import PySCFOutput, read_pyscf_h5
from chemsmart.jobs.pyscf.settings import (
    PYSCF_STABILITY_SPACES,
    PYSCF_STABILITY_UNRETURNED_SPACE,
)
from chemsmart.jobs.pyscf.writer import (
    PySCFScriptWriter,
    applied_pyscf_spec_fields,
)

FIXTURES = Path(__file__).resolve().parent / "data" / "PySCFTests" / "outputs"

#: The stability round's own artifacts, with the reference family PySCF
#: built for each.  Real runs through the human CLI; see the README.
STABILITY_CASES = {
    "water_sp_stability": ("rks", "water_sp_stability_gas_phase.h5"),
    "o2_singlet_sp_stability": (
        "rks",
        "o2_singlet_sp_stability_gas_phase.h5",
    ),
    "o2_triplet_sp_stability": (
        "uks",
        "o2_triplet_sp_stability_gas_phase.h5",
    ),
    "o2_singlet_hf_sp_stability": (
        "rhf",
        "o2_singlet_hf_sp_stability_gas_phase.h5",
    ),
    "water_sp_stability_cpcm": (
        "rks",
        "water_sp_stability_cpcm_cpcm_water.h5",
    ),
    "hydrogen_atom_sp_stability": (
        "rohf",
        "hydrogen_atom_sp_stability_gas_phase.h5",
    ),
}

_WATER_XYZ = (
    "3\nwater\nO 0.083323 0.083323 0.0\n"
    "H 1.043716 -0.026894 0.0\nH -0.026894 1.043716 0.0\n"
)


def _artifact(case):
    directory, name = case, STABILITY_CASES[case][1]
    path = FIXTURES / directory / name
    if not path.exists():  # pragma: no cover - fixture inventory
        pytest.skip(f"archived stability fixture {case} is not present")
    return path


def _reference(case):
    path = _artifact(case).with_suffix(".reference.json")
    return json.loads(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------
# the public control
# ----------------------------------------------------------------------


@pytest.mark.capability("setting:pyscf:scf_stability")
def test_the_project_key_reaches_the_previewed_spec(tmp_path):
    """Project YAML -> the live CLI -> the applied spec of the artifact.

    Driven through ``run --fake`` rather than by constructing a settings
    object, because the failure this guards against is a key the loader
    accepts and the writer drops.
    """

    from chemsmart.agent.live_session import _preview_server_profile
    from chemsmart.cli.main import entry_point

    xyz = tmp_path / "water.xyz"
    xyz.write_text(_WATER_XYZ, encoding="utf-8")
    server = tmp_path / "preview-server.yaml"
    server.write_text(_preview_server_profile(), encoding="utf-8")

    observed = {}
    for requested in (True, False):
        project = tmp_path / f"project-{requested}.yaml"
        project.write_text(
            yaml.safe_dump(
                {
                    "sp": {
                        "functional": "b3lyp",
                        "basis": "def2-svp",
                        "scf_stability": requested,
                    }
                }
            ),
            encoding="utf-8",
        )
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            result = runner.invoke(
                entry_point,
                [
                    "run",
                    "--server",
                    str(server),
                    "--fake",
                    "--no-scratch",
                    "pyscf",
                    "--project",
                    str(project),
                    "--filename",
                    str(xyz),
                    "--charge",
                    "0",
                    "--multiplicity",
                    "1",
                    "--no-gpu",
                    "--label",
                    "preview",
                    "sp",
                ],
            )
            assert result.exit_code == 0, (
                f"scf_stability: {requested} is a declared project key and "
                f"the public command refused it: {result.output[-800:]} "
                f"{result.exception!r}"
            )
            artifacts = list(Path(cwd).rglob("preview*.h5"))
            assert artifacts, f"no preview artifact in {cwd}"
            spec, _prov, _status, _results = read_pyscf_h5(artifacts[0])
        observed[requested] = spec.get("scf_stability")

    assert observed == {True: True, False: False}, (
        "the requested flag did not survive project YAML -> writer -> "
        f"applied spec: {observed}"
    )


@pytest.mark.capability("setting:pyscf:scf_stability")
def test_the_cli_flag_overrides_the_project_and_reaches_the_settings():
    """``--scf-stability`` must be on the merge whitelist.

    A CLI override whose name was never appended to ``keywords`` is
    dropped silently, which is the most common defect in this codebase;
    the flag is read back off the resolved settings object here.
    """

    from chemsmart.jobs.pyscf.settings import PySCFJobSettings

    project = PySCFJobSettings(
        jobtype="sp", functional="b3lyp", basis="def2-svp"
    )
    assert project.scf_stability is False
    override = PySCFJobSettings.default()
    override.scf_stability = True
    merged = project.merge(override, keywords=("scf_stability",))
    assert merged.scf_stability is True
    assert project.scf_stability is False


# ----------------------------------------------------------------------
# absence is never stability
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    ["water_sp", "hydroxyl_sp", "water_td_singlet", "water_mp2_opt_v6"],
)
def test_an_artifact_whose_contract_never_carried_it_says_nothing(case):
    """A pre-v7 artifact reads ``None``, never ``stable`` and never False.

    ``False`` would be a claim about the reference; the honest answer is
    that this contract has no opinion.
    """

    directory = FIXTURES / case
    artifacts = sorted(directory.glob("*.h5"))
    assert artifacts, f"no archived artifact under {directory}"
    output = PySCFOutput(filename=str(artifacts[0]))
    assert output.scf_stability is None
    assert output.scf_stability_requested is None
    assert output.scf_stable is None
    # and it is not reported as a failed property either
    assert "scf_stability" not in output.property_failures


@pytest.mark.parametrize("case", ["water_sp_no_stability"])
def test_a_run_nobody_asked_records_that_nobody_asked(case):
    """Under the current contract the absence is a written fact."""

    path = FIXTURES / case / "water_sp_no_stability_gas_phase.h5"
    if not path.exists():  # pragma: no cover - fixture inventory
        pytest.skip("the not-requested control fixture is not present")
    output = PySCFOutput(filename=str(path))
    assert output.scf_stability_requested is False
    assert output.scf_stability is None
    record = output.property_status["scf_stability"]
    assert record["status"] == "not_requested"
    # Absence is not failure: a property nobody asked for must not read
    # as an unavailable one.
    assert "scf_stability" not in output.property_failures


# ----------------------------------------------------------------------
# what the record says, on bytes PySCF wrote
# ----------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(STABILITY_CASES))
def test_every_recorded_answer_names_the_space_it_is_about(case):
    """A boolean with no named question is the defect this prevents."""

    family = STABILITY_CASES[case][0]
    output = PySCFOutput(filename=str(_artifact(case)))
    assert output.scf_stability_requested is True
    record = output.scf_stability
    assert record is not None, "a requested analysis recorded nothing"
    assert record["reference_family"] == family
    assert record["applies_to"] == "reference"
    assert record["scf_converged"] is True

    spaces = PYSCF_STABILITY_SPACES[family]
    questions = record["analyses"]
    assert set(questions) == {"internal", "external"}
    for question, entry in questions.items():
        if entry.get("stable") is None:
            # An answer this host did not get must say why, and must not
            # be readable as stable.
            assert entry.get("unavailable")
            continue
        assert entry["rotation_space"] == spaces[question], (
            f"{case}: the {question} answer is recorded against "
            f"{entry['rotation_space']!r}"
        )


def test_external_means_two_different_questions_across_references():
    """The measurement the design turns on, on this round's own bytes.

    Restricted and unrestricted references both answer ``external`` and
    they answer about different rotation spaces, so one boolean named
    ``stable_external`` would have carried two meanings.
    """

    restricted = PySCFOutput(
        filename=str(_artifact("o2_singlet_sp_stability"))
    )
    unrestricted = PySCFOutput(
        filename=str(_artifact("o2_triplet_sp_stability"))
    )
    spaces = {}
    for output in (restricted, unrestricted):
        record = output.scf_stability
        spaces[record["reference_family"]] = record["analyses"]["external"][
            "rotation_space"
        ]
    assert spaces == {
        "rks": "RHF/RKS -> UHF/UKS",
        "uks": "UHF/UKS -> GHF/GKS",
    }, spaces


@pytest.mark.parametrize("case", sorted(STABILITY_CASES))
def test_the_question_pyscf_discards_is_recorded_as_undetermined(case):
    """PySCF solves real -> complex inside the external analysis and logs
    it without returning it, so the record names it rather than letting a
    reader take the returned flag for it."""

    record = PySCFOutput(filename=str(_artifact(case))).scf_stability
    external = record["analyses"]["external"]
    undetermined = {
        entry["rotation_space"] for entry in record["not_determined"].values()
    }
    if external.get("stable") is None:
        # No external analysis ran, so nothing solved real -> complex
        # either; claiming it was left undetermined would be a second
        # false sentence.
        assert not undetermined
    else:
        assert undetermined == {PYSCF_STABILITY_UNRETURNED_SPACE}


def test_an_unavailable_external_never_costs_the_internal_answer():
    """The hydrogen atom, which is why the two questions are two calls.

    ``pyscf.scf.stability.rohf_stability(internal=True, external=True)``
    runs the internal Davidson and then raises from ``rohf_external``;
    a driver that asked once would have recorded nothing at all.
    """

    record = PySCFOutput(
        filename=str(_artifact("hydrogen_atom_sp_stability"))
    ).scf_stability
    questions = record["analyses"]
    assert questions["internal"]["stable"] is True
    assert questions["external"]["stable"] is None
    assert "NotImplementedError" in questions["external"]["unavailable"]


@pytest.mark.parametrize("case", sorted(STABILITY_CASES))
def test_the_recorded_flags_are_what_pyscf_itself_answers(case):
    """The differential oracle: PySCF's own recomputation beside each."""

    record = PySCFOutput(filename=str(_artifact(case))).scf_stability
    reference = _reference(case)["scf_stability"]
    for question, entry in record["analyses"].items():
        key = f"stable_{question}"
        if entry.get("stable") is None:
            assert reference.get(key) is None
            assert f"{key}_error" in reference
        else:
            assert entry["stable"] is reference[key], (
                f"{case}: the artifact and PySCF's own recomputation "
                f"disagree on {question}"
            )


def test_the_closed_shell_singlet_is_unstable_and_the_control_is_not():
    """The physics the round was built to be able to say out loud.

    Closed-shell singlet O2 has two electrons in a doubly degenerate
    pi* shell; a restricted reference forces them into one spatial
    orbital, and the lower solution is the spin-broken one.  Water at
    the same level has no such solution.  Both are observations; neither
    refuses anything.
    """

    unstable = PySCFOutput(
        filename=str(_artifact("o2_singlet_sp_stability"))
    ).scf_stable
    control = PySCFOutput(
        filename=str(_artifact("water_sp_stability"))
    ).scf_stable
    assert unstable["internal"] is True
    assert unstable["external"] is False
    assert control == {"internal": True, "external": True}


def test_a_solvated_reference_is_analysed_with_its_solvent_response():
    """PySCF's solvated ``stability`` sets ``equilibrium_solvation`` for
    the duration of the analysis, so the solvent response enters the
    orbital Hessian.  The fixture holds that the analysis runs at all on
    a solvated object, which the record names."""

    output = PySCFOutput(filename=str(_artifact("water_sp_stability_cpcm")))
    record = output.scf_stability
    assert "PCM" in record["reference_class"]
    assert record["reference_family"] == "rks"
    assert output.scf_stable == {"internal": True, "external": True}


# ----------------------------------------------------------------------
# requested against applied
# ----------------------------------------------------------------------


def _validate(path, *, scf_stability, functional="b3lyp", ab_initio=None):
    from chemsmart.jobs.pyscf.settings import PySCFJobSettings
    from chemsmart.jobs.pyscf.validation import validate_pyscf_result

    spec, _provenance, _status, _results = read_pyscf_h5(path)
    settings = PySCFJobSettings(
        jobtype="sp",
        functional=None if ab_initio else functional,
        ab_initio=ab_initio,
        basis="def2-svp",
        charge=int(spec["charge"]),
        multiplicity=int(spec["multiplicity"]),
        engine="cpu",
        scf_stability=scf_stability,
        solvent_model=spec.get("solvent_model"),
        solvent_id=spec.get("solvent_id"),
    )
    return validate_pyscf_result(
        path,
        settings=settings,
        expected_jobtype="sp",
        expected_charge=int(spec["charge"]),
        expected_multiplicity=int(spec["multiplicity"]),
        expected_symbols=spec["symbols"],
        expected_positions=spec["positions"],
    )


def test_a_stability_artifact_validates_against_the_request_that_made_it():
    path = _artifact("o2_singlet_sp_stability")
    assert _validate(path, scf_stability=True)["state"] == "validated"


def test_a_request_that_disagrees_with_the_record_is_a_finding():
    """The applied flag is compared like any other applied setting.

    This is the requested-against-applied check, not a judgement of the
    answer: what it refuses is an artifact that does not carry the
    analysis its request asked for.
    """

    path = _artifact("o2_singlet_sp_stability")
    verdict = _validate(path, scf_stability=False)
    assert verdict["state"] == "failed"
    assert any(
        finding.field == "scf_stability" for finding in verdict["findings"]
    )


# ----------------------------------------------------------------------
# the vocabulary is frozen per contract, on every artifact on disk
# ----------------------------------------------------------------------


def test_every_archived_applied_settings_digest_still_reconstructs():
    """The gate a new applied-spec field is most likely to break.

    The digest stored in an artifact was computed over the vocabulary of
    *that* artifact's contract, so extending the current tuple in place
    marks every archived artifact of that version tampered.  This holds
    the relation over every PySCF artifact this repository carries, at
    whatever contract each was written under.
    """

    checked = 0
    mismatched = []
    for path in sorted(FIXTURES.rglob("*.h5")):
        spec, _provenance, _status, _results = read_pyscf_h5(path)
        stored = spec.get("applied_settings_sha256")
        if not isinstance(stored, str) or len(stored) != 64:
            continue  # a preview or a run that never reached the driver
        fields = applied_pyscf_spec_fields(spec)
        rebuilt = PySCFScriptWriter.settings_digest(
            {field: spec.get(field) for field in fields}
        )
        checked += 1
        if rebuilt != stored:
            mismatched.append(
                (
                    path.relative_to(FIXTURES).as_posix(),
                    spec.get("result_contract_version"),
                )
            )
    assert checked >= 20, f"only {checked} artifacts carried a digest"
    assert not mismatched, (
        "these archived artifacts no longer reconstruct their own "
        f"applied-settings digest: {mismatched}"
    )
