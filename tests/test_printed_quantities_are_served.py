"""What a program prints and the science uses reaches the typed layer.

R10 Q13 counted, over 1,459 archived real outputs, the quantities the four
programs print that no reader served.  Each quantity served here was
printed, asked for or needed, and unreachable: the Agent could at best be
told that a log printed it.  Every test reads archived real bytes through
the registered reader, as extraction does; a value is compared with the
line the program printed.
"""

from pathlib import Path

import pytest

from chemsmart.analysis.quantity_expressions import normalize_numeric_value
from chemsmart.analysis.result_quantities import supported_selectors
from chemsmart.analysis.result_readers import (
    MissingQuantityError,
    reader_for,
)

DATA = Path(__file__).resolve().parent / "data"
GAUSSIAN = DATA / "GaussianTests" / "outputs"


def _printed(path, marker, field_after):
    """Every number the log prints after ``field_after`` on ``marker`` lines."""

    values = []
    for line in path.read_text(errors="replace").splitlines():
        if marker in line:
            values.append(float(line.split(field_after, 1)[1].split()[0]))
    return values


@pytest.mark.capability("selector:gaussian:sp:electronic_spatial_extent")
@pytest.mark.capability("selector:gaussian:opt:electronic_spatial_extent")
@pytest.mark.parametrize(
    "log",
    [
        # Q10's LG1 (CUHK 2151662): the value its session was refused.
        "water_hf_631gd_sp_lg1.log",
        # Optimisations: the first print is the supplied structure's, the
        # last the reached structure's, and benzene's differ.
        "benzene.log",
        "co2.log",
        # MP2: the population analysis is the SCF density's.
        "water_mp2.log",
    ],
)
def test_the_spatial_extent_is_the_last_scf_density_print(log):
    path = GAUSSIAN / log
    reader = reader_for("gaussian")
    output = reader.open_output(path)
    value, unit = reader.read(output, "electronic_spatial_extent")
    printed = _printed(path, "Electronic spatial extent (au):", "<R**2>=")
    assert value == printed[-1]
    assert unit == "bohr^2"
    angstrom2, canonical, _dimension = normalize_numeric_value(value, unit)
    assert canonical == "angstrom^2"
    assert angstrom2 == pytest.approx(value * 0.529177210903**2)
    assert reader.structural_state("electronic_spatial_extent") == (
        "as_reached"
    )
    assert reader.electronic_provenance("electronic_spatial_extent") == (
        "reference"
    )
    assert "electronic_spatial_extent" in supported_selectors()


def test_the_lg1_value_is_the_one_its_session_could_not_have():
    """18.9424 bohr^2 for water at HF/6-31G(d): inside the band LG1
    pre-registered (15 .. 25), and now a reading instead of a pointer."""

    reader = reader_for("gaussian")
    output = reader.open_output(GAUSSIAN / "water_hf_631gd_sp_lg1.log")
    assert output.jobtype == "sp"
    assert "electronic_spatial_extent" in reader.selectors_for_jobtype("sp")
    assert reader.read(output, "electronic_spatial_extent") == (
        18.9424,
        "bohr^2",
    )


def test_a_spatial_extent_about_the_users_origin_is_not_served():
    """<R**2> depends on the origin.  An IRC runs in the input orientation,
    so Gaussian takes it about the coordinates' own origin, which says
    nothing about the molecule: the archived IRC branch prints it twice
    and it is refused, by name."""

    path = GAUSSIAN / "malonaldehyde_pt_ircf.log"
    reader = reader_for("gaussian")
    output = reader.open_output(path)
    assert _printed(path, "Electronic spatial extent (au):", "<R**2>=")
    assert not output.standard_orientations
    with pytest.raises(MissingQuantityError) as absent:
        reader.read(output, "electronic_spatial_extent")
    assert "origin" in str(absent.value)


ORCA = DATA / "ORCATests" / "outputs"


@pytest.mark.capability("selector:orca:sp:t1_diagnostic")
@pytest.mark.parametrize(
    "out,prints",
    [
        # canonical CCSD(T)/cc-pVDZ water (R10 Q2's oracle, CUHK)
        ("water_ccsdt_ccpvdz_sp_q2.out", 1),
        # DLPNO-CCSD(T) extrapolated over two bases: one print per basis
        ("water_dlpno_ccsdt_sp.out", 2),
        ("dlpno_ccsdt_singlepoint_neutral_in_cpcm.out", 2),
    ],
)
def test_the_t1_diagnostic_of_the_last_coupled_cluster_run_is_served(
    out, prints
):
    path = ORCA / out
    reader = reader_for("orca")
    output = reader.open_output(path)
    printed = _printed(path, "T1 diagnostic", "...")
    assert len(printed) == prints
    assert reader.read(output, "t1_diagnostic") == (printed[-1], "1")
    assert "t1_diagnostic" in reader.selectors_for_jobtype("sp")
    assert reader.electronic_provenance("t1_diagnostic") == "correlated"
    assert "t1_diagnostic" in supported_selectors()


def test_a_result_without_coupled_cluster_has_no_t1_diagnostic():
    reader = reader_for("orca")
    output = reader.open_output(ORCA / "phenol_pka_B_sp.out")
    with pytest.raises(MissingQuantityError) as absent:
        reader.read(output, "t1_diagnostic")
    assert "no coupled-cluster calculation ran" in str(absent.value)


GAUSSIAN_STABILITY = DATA / "GaussianTests" / "stability"
PYSCF = DATA / "PySCFTests" / "outputs"


def _pyscf_record(case):
    from chemsmart.io.pyscf.output import PySCFOutput

    path = sorted((PYSCF / case).glob("*.h5"))[0]
    return PySCFOutput(filename=str(path)).scf_stability


@pytest.mark.capability("selector:gaussian:sp:wavefunction_stability_verdict")
@pytest.mark.capability(
    "selector:gaussian:sp:wavefunction_stability_lowest_eigenvalue"
)
@pytest.mark.capability(
    "selector:gaussian:sp:wavefunction_stability_rotation_space"
)
def test_gaussians_rhf_to_uhf_sentence_is_a_verdict_with_its_space():
    """Singlet O2 at RB3LYP/def2-SVP (CUHK 2152098, Gaussian 16 `stable`):
    "The wavefunction has an RHF -> UHF instability." was read as no
    verdict at all, so the result said nothing about a reference Gaussian
    called unstable."""

    path = GAUSSIAN_STABILITY / "g_o2_singlet_stable_gas_phase.log"
    reader = reader_for("gaussian")
    output = reader.open_output(path)
    assert reader.read(output, "wavefunction_stability_verdict") == (
        "external_instability",
        "",
    )
    assert reader.read(output, "wavefunction_stability_rotation_space") == (
        "RHF -> UHF",
        "",
    )
    printed = _printed(path, "Eigenvector   1:", "Eigenvalue=")
    assert reader.read(output, "wavefunction_stability_lowest_eigenvalue") == (
        printed[-1],
        "Eh",
    )
    assert printed[-1] < 0
    diagnostics = reader.reference_diagnostics_for_output(output)
    assert diagnostics["unstable"] == (
        {
            "question": "external",
            "rotation_space": "RHF -> UHF",
            "lowest_eigenvalue": printed[-1],
        },
    )


@pytest.mark.capability(
    "selector:gaussian:sp:wavefunction_stability_lowest_eigenvalue"
)
@pytest.mark.parametrize(
    "log,pyscf_case",
    [
        ("g_o2_singlet_stable_gas_phase.log", "o2_singlet_sp_stability_heard"),
        ("g_water_stable_gas_phase.log", "water_sp_stability_heard"),
    ],
)
def test_two_programs_print_the_same_restricted_to_unrestricted_root(
    log, pyscf_case
):
    """The differential oracle across programs, at one level and geometry
    (B3LYP with Gaussian's VWN form, def2-SVP): Gaussian's lowest
    stability eigenvalue -- the triplet root, the RHF -> UHF question --
    and PySCF's RHF/RKS -> UHF/UKS eigenvalue agree to 1e-5 Eh."""

    gaussian = reader_for("gaussian")
    value, _unit = gaussian.read(
        gaussian.open_output(GAUSSIAN_STABILITY / log),
        "wavefunction_stability_lowest_eigenvalue",
    )
    pyscf_value = _pyscf_record(pyscf_case)["analyses"]["external"][
        "lowest_eigenvalues"
    ][0]
    assert value == pytest.approx(pyscf_value, abs=1e-5)


def test_pyscfs_internal_root_is_four_times_gaussians_singlet_root():
    """Why PySCF's numbers keep PySCF's names: its internal eigenvalue is
    four times the singlet root Gaussian prints for the same molecule."""

    from chemsmart.io.gaussian.output import Gaussian16Output

    records = Gaussian16Output(
        str(GAUSSIAN_STABILITY / "g_water_stable_gas_phase.log")
    ).wavefunction_stability_records
    singlet = min(
        row["eigenvalue"]
        for row in records[-1]["eigenvalues"]
        if row["spin_square"] == 0.0
    )
    internal = _pyscf_record("water_sp_stability_heard")["analyses"][
        "internal"
    ]["lowest_eigenvalues"][0]
    assert internal == pytest.approx(4.0 * singlet, abs=5e-5)


@pytest.mark.capability("signal:scf.reference_unstable")
def test_the_sensor_raises_on_a_reference_gaussian_calls_unstable():
    """Through the step the executor runs on every finished node: a
    Gaussian RHF -> UHF instability now reaches the host's sensor with the
    space Gaussian named and the eigenvalue that tripped it."""

    from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    path = (GAUSSIAN_STABILITY / "g_o2_singlet_stable_gas_phase.log").resolve()
    evaluation = CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="gaussian",
        jobtype="sp",
        charge=0,
        multiplicity=1,
        output_artifacts=(
            TrustedArtifactRefV1(
                artifact_id="result.o2",
                kind="gaussian_output",
                sha256=file_sha256(path),
                size_bytes=path.stat().st_size,
                path=str(path),
                cli_value=str(path),
            ),
        ),
        exit_status=0,
    )
    signals = {item["signal_id"]: item for item in evaluation.anomalies}
    anomaly = signals["scf.reference_unstable"]
    assert anomaly["unstable_rotation_spaces"] == ["RHF -> UHF"]
    carried = evaluation.observations["gaussian"]["reference_stability"]
    assert carried["unstable"][0]["lowest_eigenvalue"] == pytest.approx(
        -0.0926178
    )


@pytest.mark.capability(
    "selector:gaussian:sp:solvation_nonelectrostatic_energy"
)
@pytest.mark.capability(
    "selector:gaussian:opt:solvation_nonelectrostatic_energy"
)
@pytest.mark.parametrize(
    "log,prints",
    [
        ("5PQ_Me_ts1_b_no_pd_opt_sp_smd_generic.log", 1),
        # an optimisation in the continuum: one print per step
        ("benzene.log", 2),
        ("ozone.log", 7),
    ],
)
def test_gaussians_smd_cds_term_is_the_one_orca_and_pyscf_serve(log, prints):
    """The non-electrostatic part of an SMD solvation free energy, printed
    beneath every SMD SCF in kcal/mol and served under the name ORCA's and
    PySCF's readers already use; the last print is the reached
    structure's."""

    path = GAUSSIAN / log
    reader = reader_for("gaussian")
    output = reader.open_output(path)
    printed = _printed(path, "SMD-CDS (non-electrostatic) energy", "=")
    assert len(printed) == prints
    value, unit = reader.read(output, "solvation_nonelectrostatic_energy")
    assert (value, unit) == (printed[-1], "kcal/mol")
    hartree, canonical, _dimension = normalize_numeric_value(value, unit)
    assert canonical == "hartree"
    assert hartree == pytest.approx(printed[-1] / 627.5094740631, rel=1e-6)
    assert "smd" in reader.level_for_output(output)["solvent_model"]
    # read beside the model that gives the term its meaning
    assert reader.read(output, "solvation_model") == ("smd", "")
    assert reader.read(output, "solvent")[0]
    assert "solvation_nonelectrostatic_energy" in reader.selectors_for_jobtype(
        output.jobtype
    )


def test_a_gas_phase_gaussian_run_has_no_smd_cds_term():
    reader = reader_for("gaussian")
    output = reader.open_output(GAUSSIAN / "co2.log")
    with pytest.raises(MissingQuantityError) as absent:
        reader.read(output, "solvation_nonelectrostatic_energy")
    assert "gas phase" in str(absent.value)


@pytest.mark.capability("selector:gaussian:sp:molecular_volume")
@pytest.mark.parametrize(
    "log",
    [
        # water B3LYP/def2-SVP (CUHK 2152098): 178.644 bohr^3, 15.942 cm^3/mol
        "stability/g_water_volume_gas_phase.log",
        # iodine(III) reagents, M06-2X/genecp with the volume keyword
        "volume/pida_n.log",
        "volume/pida_ra.log",
    ],
)
def test_the_volume_keywords_molecular_volume_is_served(log):
    """The per-molecule figure Gaussian prints beside the molar one: the
    molar figure is N_A times it, which the test checks from the line."""

    path = DATA / "GaussianTests" / log
    reader = reader_for("gaussian")
    output = reader.open_output(path)
    value, unit = reader.read(output, "molecular_volume")
    assert unit == "bohr^3"
    line = next(
        text
        for text in path.read_text(errors="replace").splitlines()
        if text.strip().startswith("Molar volume") and "bohr**3" in text
    )
    assert value == float(line.split("=")[1].split()[0])
    molar = float(line.split("(")[1].split()[0])
    # bohr^3 per molecule -> cm^3 per mole
    assert value * 0.529177210903e-8**3 * 6.02214076e23 == pytest.approx(
        molar, rel=1e-3
    )
    angstrom3, canonical, _dimension = normalize_numeric_value(value, unit)
    assert canonical == "angstrom^3"
    assert "molecular_volume" in reader.selectors_for_jobtype("sp")


def test_a_solvents_molar_volume_parameter_is_not_the_molecules():
    """An SMD(generic) run prints the solvent's parameter under the same
    words, "Molar volume = 0.000000 cm**3/mol": not a volume of anything
    the run computed, and not served."""

    path = GAUSSIAN / "5PQ_Me_ts1_b_no_pd_opt_sp_smd_generic.log"
    assert "Molar volume" in path.read_text(errors="replace")
    reader = reader_for("gaussian")
    with pytest.raises(MissingQuantityError) as absent:
        reader.read(reader.open_output(path), "molecular_volume")
    assert "did not ask for volume" in str(absent.value)


def _printed_mayer_pairs(path):
    """``{(i, j): order}`` from the last printed Mayer bond-order block."""

    import re

    lines = path.read_text(errors="replace").splitlines()
    start = max(
        index
        for index, line in enumerate(lines)
        if "Mayer bond orders larger than" in line
    )
    pairs = {}
    for line in lines[start + 1 :]:
        if not line.strip():
            break
        for match in re.finditer(
            r"B\(\s*(\d+)-\s*\w+\s*,\s*(\d+)-\s*\w+\s*\)\s*:\s*(\S+)", line
        ):
            i, j = sorted((int(match.group(1)), int(match.group(2))))
            pairs[(i, j)] = float(match.group(3))
    return pairs


@pytest.mark.capability("selector:orca:sp:mayer_bond_orders")
@pytest.mark.capability("selector:orca:opt:mayer_bond_orders")
@pytest.mark.parametrize(
    "out,metal_bonds",
    [
        # phenoxide at its sp: a C-O order of 1.785, between single and double
        ("phenol_pka_B_sp.out", 0),
        # an Fe(II)(H2O)4 quintet: the four Fe-O bonds a one-capital-letter
        # pattern drops ("B(  0-Fe,  1-O )")
        ("fe2_quintet.out", 4),
    ],
)
def test_every_printed_mayer_bond_order_is_served(out, metal_bonds):
    path = ORCA / out
    reader = reader_for("orca")
    output = reader.open_output(path)
    rows, unit = reader.read(output, "mayer_bond_orders")
    assert unit == "1"
    served = {(row[0], row[1]): row[2] for row in rows}
    assert served == _printed_mayer_pairs(path)
    symbols, _ = reader.read(output, "symbols")
    assert (
        sum(
            1
            for i, j in served
            if len(symbols[i]) == 2 or len(symbols[j]) == 2
        )
        == metal_bonds
    )
    assert "mayer_bond_orders" in reader.selectors_for_jobtype(output.jobtype)


@pytest.mark.capability("selector:orca:sp:mayer_bond_orders")
def test_mayer_bond_orders_reach_a_receipt_as_bond_rows():
    """Through the extraction the Agent calls: the rows arrive as the
    sparse [atom_i, atom_j, order] matrix Wiberg orders already do."""

    from chemsmart.analysis.result_quantities import (
        QuantitySelectorV1,
        ResultQuantityExtractionRequestV1,
        result_file_sha256,
    )
    from chemsmart.analysis.result_readers import extract_logged_quantities

    path = ORCA / "phenol_pka_B_sp.out"
    receipt = extract_logged_quantities(
        request=ResultQuantityExtractionRequestV1(
            schema_version="chemsmart.quantity-extraction-request.v1",
            artifact_id="result.phenoxide",
            artifact_sha256=result_file_sha256(path),
            program="orca",
            selectors=(
                QuantitySelectorV1(
                    quantity_id="mayer", selector="mayer_bond_orders"
                ),
            ),
        ),
        artifact_path=path,
    )
    (quantity,) = receipt.quantities
    assert quantity.data_kind == "matrix"
    assert (0, 6, 1.7852) in quantity.value


@pytest.mark.capability("selector:orca:opt:mayer_free_valence")
def test_mayer_free_valence_marks_the_open_shell():
    """Zero on every closed-shell atom; on the high-spin Fe(II) quintet
    the iron carries 3.66 of free valence, the unpaired population the
    bonded valence does not use."""

    reader = reader_for("orca")
    closed, _ = reader.read(
        reader.open_output(ORCA / "phenol_pka_B_sp.out"), "mayer_free_valence"
    )
    assert max(abs(value) for value in closed) < 1e-3
    quintet = reader.open_output(ORCA / "fe2_quintet.out")
    free, _ = reader.read(quintet, "mayer_free_valence")
    symbols, _ = reader.read(quintet, "symbols")
    assert symbols[0] == "Fe" and free[0] == pytest.approx(3.6559)
    assert len(free) == len(symbols)
