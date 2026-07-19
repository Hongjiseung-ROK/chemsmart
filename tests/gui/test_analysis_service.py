"""Scientific parity contracts for desktop analysis adapters."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from chemsmart.gui.application.analysis_models import (
    GROUPER_STRATEGIES,
    DIASRequest,
    GrouperRequest,
    ThermochemistryRequest,
    WBIRequest,
)
from chemsmart.gui.services.analysis_service import AnalysisService

CO2 = Path("tests/data/GaussianTests/outputs/co2.log").resolve()
ORCA_CO2 = Path("tests/data/ORCATests/outputs/CO2.out").resolve()
CONFORMERS = Path(
    "tests/data/StructuresTests/xyz/crest_conformers.xyz"
).resolve()
ORCA_DIAS = Path("tests/data/ORCATests/dias").resolve()
WBI_OUTPUT = Path(
    "tests/data/GaussianTests/outputs/TS_5coord_XIII_wbi.log"
).resolve()


class ContextProbe:
    def __init__(self) -> None:
        self.progress = []
        self.messages = []

    def report_indeterminate(self, message: str = "") -> None:
        self.messages.append(message)

    def report_progress(
        self, current: int, total: int, message: str = ""
    ) -> None:
        self.progress.append((current, total, message))

    def raise_if_cancelled(self) -> None:
        return


def _numeric_values(row) -> tuple:
    return (
        row.electronic_energy,
        row.zero_point_energy,
        row.enthalpy,
        row.qrrho_enthalpy,
        row.entropy_times_temperature,
        row.qrrho_entropy_times_temperature,
        row.gibbs_free_energy,
        row.qrrho_gibbs_free_energy,
    )


def test_single_thermochemistry_result_exactly_maps_domain_tuple() -> None:
    from chemsmart.analysis.thermochemistry import Thermochemistry

    request = ThermochemistryRequest((CO2,))
    context = ContextProbe()
    result = AnalysisService().thermochemistry(request, context)
    direct = Thermochemistry(
        filename=str(CO2),
        temperature=298.15,
        pressure=1.0,
        use_weighted_mass=True,
        alpha=4,
        energy_units="hartree",
        check_imaginary_frequencies=True,
    ).compute_thermochemistry()

    assert result.rows[0].structure == direct[0]
    assert np.allclose(
        [
            value
            for value in _numeric_values(result.rows[0])
            if value is not None
        ],
        [value for value in direct[1:] if value is not None],
    )
    assert context.progress[0][:2] == (0, 1)
    assert context.progress[-1][:2] == (1, 1)


def test_batch_reports_determinate_file_boundaries_and_keeps_units() -> None:
    context = ContextProbe()
    result = AnalysisService().thermochemistry(
        ThermochemistryRequest(
            (CO2, ORCA_CO2),
            temperature=350.0,
            pressure=1.5,
            energy_units="kJ/mol",
        ),
        context,
    )

    assert len(result.rows) == 2
    assert result.energy_units == "kJ/mol"
    assert [(current, total) for current, total, _ in context.progress] == [
        (0, 2),
        (1, 2),
        (1, 2),
        (2, 2),
    ]


def test_boltzmann_result_exactly_maps_domain_average() -> None:
    from chemsmart.analysis.thermochemistry import (
        BoltzmannAverageThermochemistry,
    )

    request = ThermochemistryRequest(
        (CO2, CO2),
        boltzmann_average=True,
        weighting_energy="electronic",
    )
    context = ContextProbe()
    result = AnalysisService().thermochemistry(request, context)
    direct = BoltzmannAverageThermochemistry(
        files=[str(CO2), str(CO2)],
        energy_type="electronic",
        temperature=298.15,
        pressure=1.0,
        use_weighted_mass=True,
        alpha=4,
        energy_units="hartree",
        check_imaginary_frequencies=True,
    ).compute_boltzmann_averages()

    assert result.boltzmann_average
    assert result.weighting_energy == "electronic"
    assert result.rows[0].structure == direct[0]
    assert np.allclose(
        [
            value
            for value in _numeric_values(result.rows[0])
            if value is not None
        ],
        [value for value in direct[1:] if value is not None],
    )
    assert context.messages
    assert context.progress == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"temperature": 0}, "greater than 0 K"),
        ({"pressure": 0}, "greater than 0 atm"),
        ({"entropy_method": "grimme"}, "positive cutoff"),
        ({"entropy_cutoff_cm": 100}, "Choose Grimme or Truhlar"),
        ({"boltzmann_average": True}, "at least two"),
    ],
)
def test_thermochemistry_request_validation(kwargs, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ThermochemistryRequest((CO2,), **kwargs)


def test_thermochemistry_adapter_does_not_write_result_files(
    tmp_path: Path,
) -> None:
    before = set(tmp_path.iterdir())
    AnalysisService().thermochemistry(
        ThermochemistryRequest((CO2,)), ContextProbe()
    )
    assert set(tmp_path.iterdir()) == before


def test_thermochemistry_observes_pre_parser_cancellation() -> None:
    from chemsmart.gui.application.task_controller import TaskCancelled

    class Cancelled(ContextProbe):
        def raise_if_cancelled(self) -> None:
            raise TaskCancelled("cancelled by test")

    with pytest.raises(TaskCancelled):
        AnalysisService().thermochemistry(
            ThermochemistryRequest((CO2,)), Cancelled()
        )


def test_grouper_strategy_inventory_keeps_pymol_as_explicit_boundary() -> None:
    assert GROUPER_STRATEGIES == (
        "rmsd",
        "hrmsd",
        "spyrmsd",
        "irmsd",
        "pymolrmsd",
        "tanimoto",
        "torsion",
        "isomorphism",
        "formula",
        "connectivity",
        "energy",
    )
    with pytest.raises(ValueError, match="separately cancellable"):
        GrouperRequest(CONFORMERS, strategy="pymolrmsd")


def test_rmsd_grouper_matches_domain_without_writing(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.io.molecules.structure import Molecule
    from chemsmart.jobs.grouper.rmsd import BasicRMSDGrouper

    molecules = Molecule.from_filepath(CONFORMERS, index=":", return_list=True)
    direct_groups, direct_indices = BasicRMSDGrouper(
        molecules,
        threshold=0.5,
        record_results=False,
    ).group()
    assert len(direct_groups) == 12

    monkeypatch.chdir(tmp_path)
    context = ContextProbe()
    result = AnalysisService().group_structures(
        GrouperRequest(CONFORMERS, strategy="rmsd", threshold=0.5),
        context,
    )

    assert result.total_molecules == 18
    assert len(result.groups) == len(direct_groups) == 12
    assert [group.member_indices for group in result.groups] == [
        tuple(index + 1 for index in indices) for indices in direct_indices
    ]
    assert context.progress[0][:2] == (0, 153)
    assert context.progress[-1][:2] == (153, 153)
    assert list(tmp_path.iterdir()) == []


def test_formula_grouper_uses_structured_domain_result_without_output(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = AnalysisService().group_structures(
        GrouperRequest(CONFORMERS, strategy="formula"), ContextProbe()
    )

    assert result.total_molecules == 18
    assert len(result.groups) == 1
    assert result.groups[0].member_indices == tuple(range(1, 19))
    assert result.groups[0].preview.symbols
    assert list(tmp_path.iterdir()) == []


def test_grouper_adapter_passes_exact_irmsd_contract_to_factory(
    monkeypatch,
) -> None:
    from chemsmart.utils.grouper import StructureGrouperFactory

    captured = {}

    class GrouperProbe:
        def __init__(self, molecules) -> None:
            self.molecules = molecules

        def group(self):
            return [[self.molecules[0]]], [[0]]

    def create(molecules, **kwargs):
        captured.update(kwargs)
        return GrouperProbe(molecules)

    monkeypatch.setattr(StructureGrouperFactory, "create", create)
    result = AnalysisService().group_structures(
        GrouperRequest(
            CONFORMERS,
            strategy="irmsd",
            threshold=0.125,
            ignore_hydrogens=True,
            inversion="on",
        ),
        ContextProbe(),
    )

    assert result.threshold == 0.125
    assert captured["threshold"] == 0.125
    assert captured["ignore_hydrogens"] is True
    assert captured["inversion"] == "on"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"threshold": 0.5, "num_groups": 2}, "either a threshold"),
        ({"threshold": 1.1, "strategy": "tanimoto"}, "at most 1"),
        ({"num_groups": 0}, "at least 1"),
        ({"num_procs": 9}, "between 1 and 8"),
        ({"strategy": "energy", "ignore_hydrogens": True}, "does not support"),
        ({"strategy": "irmsd", "inversion": "yes"}, "auto, on, or off"),
    ],
)
def test_grouper_request_validation(kwargs, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        GrouperRequest(CONFORMERS, **kwargs)


def test_grouper_rejects_target_count_above_structure_count() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        AnalysisService().group_structures(
            GrouperRequest(CONFORMERS, strategy="rmsd", num_groups=19),
            ContextProbe(),
        )


def test_grouper_cancels_inside_pairwise_loop(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.gui.application.task_controller import TaskCancelled

    class CancelAfterThree(ContextProbe):
        def raise_if_cancelled(self) -> None:
            if self.progress and self.progress[-1][0] >= 3:
                raise TaskCancelled("cancelled by test")

    monkeypatch.chdir(tmp_path)
    with pytest.raises(TaskCancelled):
        AnalysisService().group_structures(
            GrouperRequest(CONFORMERS, strategy="rmsd", threshold=0.5),
            CancelAfterThree(),
        )
    assert list(tmp_path.iterdir()) == []


def test_orca_dias_matches_characterized_fixture_without_writing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    context = ContextProbe()
    result = AnalysisService().dias(
        DIASRequest(ORCA_DIAS, atom1=5, atom2=7), context
    )

    assert result.program == "orca"
    assert len(result.points) == 3
    assert np.allclose(
        [point.reaction_coordinate_angstrom for point in result.points],
        [1.6689598622321626, 2.4464549185065727, 2.634055159243443],
    )
    assert np.allclose(
        [point.total_energy_kcal_mol for point in result.points],
        [26.683497385587543, -7.226552615407854, -11.878373825456947],
    )
    assert np.allclose(
        [point.distortion_energy_kcal_mol for point in result.points],
        [55.4584811439272, 7.0201836712658405, 4.639531101100147],
    )
    assert np.allclose(
        [point.interaction_energy_kcal_mol for point in result.points],
        [-28.77498375833966, -14.246736286673695, -16.517904926557094],
    )
    assert context.progress[-1][:2] == (3, 3)
    assert list(tmp_path.iterdir()) == []


def test_orca_dias_zero_reference_uses_domain_minimum() -> None:
    service = AnalysisService()
    baseline = service.dias(
        DIASRequest(ORCA_DIAS, atom1=5, atom2=7, program="orca"),
        ContextProbe(),
    )
    result = service.dias(
        DIASRequest(
            ORCA_DIAS,
            atom1=5,
            atom2=7,
            program="orca",
            zero_reference=True,
        ),
        ContextProbe(),
    )

    assert np.allclose(
        [point.total_energy_kcal_mol for point in result.points],
        [38.56187121104449, 4.651821210049093, 0.0],
    )
    assert np.allclose(
        [point.distortion_energy_kcal_mol for point in result.points],
        [point.distortion_energy_kcal_mol for point in baseline.points],
    )
    reference_offset = min(
        point.total_energy_kcal_mol for point in baseline.points
    )
    assert np.allclose(
        [point.interaction_energy_kcal_mol for point in result.points],
        [
            point.interaction_energy_kcal_mol - reference_offset
            for point in baseline.points
        ],
    )
    assert np.allclose(
        [point.total_energy_kcal_mol for point in result.points],
        [
            point.distortion_energy_kcal_mol
            + point.interaction_energy_kcal_mol
            for point in result.points
        ],
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"atom1": 0, "atom2": 2}, "positive"),
        ({"atom1": 2, "atom2": 2}, "different atoms"),
        ({"atom1": 1, "atom2": 2, "program": "other"}, "Unsupported"),
    ],
)
def test_dias_request_validation(kwargs, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        DIASRequest(ORCA_DIAS, **kwargs)


def test_wbi_maps_named_nbo_population_fields_and_filter() -> None:
    context = ContextProbe()
    result = AnalysisService().wbi(
        WBIRequest(WBI_OUTPUT, atom_indices=(1, 100)), context
    )

    assert result.nbo_version == "3.1"
    assert [atom.label for atom in result.atoms] == ["Ni1", "C100"]
    nickel, carbon = result.atoms
    assert nickel.natural_charge == 0.52827
    assert nickel.total_electrons == 27.47173
    assert nickel.nao_count == 31
    assert np.isclose(nickel.total_nao_occupancy, 27.47171, rtol=1e-4)
    assert nickel.electronic_configuration == "[core]4S(0.27)3d(8.70)4p(0.51)"
    assert carbon.natural_charge == -0.42062
    assert context.progress[-1][:2] == (2, 2)


def test_wbi_unfiltered_returns_all_characterized_atoms_without_writing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = AnalysisService().wbi(WBIRequest(WBI_OUTPUT), ContextProbe())

    assert len(result.atoms) == 128
    assert result.atoms[127].label == "H128"
    assert result.atoms[127].nao_count == 5
    assert list(tmp_path.iterdir()) == []


def test_wbi_rejects_missing_atom_filter() -> None:
    with pytest.raises(ValueError, match="not found: 999"):
        AnalysisService().wbi(
            WBIRequest(WBI_OUTPUT, atom_indices=(999,)), ContextProbe()
        )


def test_dias_missing_or_mixed_program_inputs_fail_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="uniquely detect"):
        AnalysisService().dias(
            DIASRequest(tmp_path, atom1=1, atom2=2), ContextProbe()
        )


def test_wbi_missing_population_table_fails_closed(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.log"
    malformed.write_text(
        "Gaussian output without NBO tables\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="No Natural Population Analysis"):
        AnalysisService().wbi(WBIRequest(malformed), ContextProbe())


def test_wbi_npa_without_nao_table_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.io.gaussian import output as gaussian_output

    output_file = tmp_path / "npa_only.log"
    output_file.write_text("NPA-only fixture\n", encoding="utf-8")

    class NPAOnlyOutput:
        def __init__(self, filename: str) -> None:
            assert filename == str(output_file)
            self.natural_population_analysis = {
                "C1": {
                    "natural_charge": 0.0,
                    "core_electrons": 2.0,
                    "valence_electrons": 4.0,
                    "rydberg_electrons": 0.0,
                    "total_electrons": 6.0,
                }
            }
            self.natural_atomic_orbitals = {}
            self.electronic_configuration = {}
            self.nbo_version = "test"

    monkeypatch.setattr(gaussian_output, "Gaussian16WBIOutput", NPAOnlyOutput)
    with pytest.raises(ValueError, match="No Natural Atomic Orbital"):
        AnalysisService().wbi(WBIRequest(output_file), ContextProbe())


def test_wbi_cancels_during_atom_mapping() -> None:
    from chemsmart.gui.application.task_controller import TaskCancelled

    class CancelAfterThree(ContextProbe):
        def raise_if_cancelled(self) -> None:
            if self.progress and self.progress[-1][0] >= 3:
                raise TaskCancelled("cancelled during NBO mapping")

    with pytest.raises(TaskCancelled, match="during NBO mapping"):
        AnalysisService().wbi(WBIRequest(WBI_OUTPUT), CancelAfterThree())


def test_repeated_dias_and_wbi_calls_do_not_retain_prior_state() -> None:
    service = AnalysisService()
    first_dias = service.dias(
        DIASRequest(ORCA_DIAS, atom1=5, atom2=7), ContextProbe()
    )
    second_dias = service.dias(
        DIASRequest(
            ORCA_DIAS,
            atom1=5,
            atom2=7,
            zero_reference=True,
        ),
        ContextProbe(),
    )
    first_wbi = service.wbi(
        WBIRequest(WBI_OUTPUT, atom_indices=(1,)), ContextProbe()
    )
    second_wbi = service.wbi(
        WBIRequest(WBI_OUTPUT, atom_indices=(100,)), ContextProbe()
    )

    assert first_dias.points[2].total_energy_kcal_mol != 0.0
    assert second_dias.points[2].total_energy_kcal_mol == 0.0
    assert first_wbi.atoms[0].label == "Ni1"
    assert second_wbi.atoms[0].label == "C100"
