"""Side-effect-free desktop adapters over ChemSmart analysis libraries."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from chemsmart.gui.application.analysis_models import (
    DIASPoint,
    DIASRequest,
    DIASResult,
    GrouperGroup,
    GrouperRequest,
    GrouperResult,
    MoleculePreview,
    ThermochemistryRequest,
    ThermochemistryResult,
    ThermochemistryRow,
    WBIAtom,
    WBIRequest,
    WBIResult,
)


class _TaskContext(Protocol):
    def report_indeterminate(self, message: str = "") -> None: ...

    def report_progress(
        self, current: int, total: int, message: str = ""
    ) -> None: ...

    def raise_if_cancelled(self) -> None: ...


class AnalysisService:
    """Compute named result DTOs without invoking CLI or job file writers."""

    def thermochemistry(
        self,
        request: ThermochemistryRequest,
        context: _TaskContext,
    ) -> ThermochemistryResult:
        from chemsmart.analysis.thermochemistry import (
            BoltzmannAverageThermochemistry,
            Thermochemistry,
        )

        files = self._validated_output_files(request.files)
        kwargs = self._thermochemistry_kwargs(request)
        context.raise_if_cancelled()

        if request.boltzmann_average:
            context.report_indeterminate(
                "Parsing conformers and computing a Boltzmann average…"
            )
            calculator = BoltzmannAverageThermochemistry(
                files=[str(path) for path in files],
                energy_type=request.weighting_energy,
                **kwargs,
            )
            context.raise_if_cancelled()
            rows = (
                ThermochemistryRow.from_domain_tuple(
                    calculator.compute_boltzmann_averages()
                ),
            )
            context.raise_if_cancelled()
        else:
            computed = []
            total = len(files)
            for index, path in enumerate(files, start=1):
                context.raise_if_cancelled()
                context.report_progress(
                    index - 1,
                    total,
                    f"Computing {path.name} ({index}/{total})…",
                )
                calculator = Thermochemistry(filename=str(path), **kwargs)
                computed.append(
                    ThermochemistryRow.from_domain_tuple(
                        calculator.compute_thermochemistry()
                    )
                )
                context.report_progress(
                    index,
                    total,
                    f"Computed {path.name} ({index}/{total}).",
                )
            rows = tuple(computed)

        return ThermochemistryResult(
            files=files,
            rows=rows,
            temperature=request.temperature,
            pressure=request.pressure,
            concentration=request.concentration,
            energy_units=request.energy_units,
            boltzmann_average=request.boltzmann_average,
            weighting_energy=(
                request.weighting_energy if request.boltzmann_average else None
            ),
        )

    def group_structures(
        self,
        request: GrouperRequest,
        context: _TaskContext,
    ) -> GrouperResult:
        from chemsmart.io.molecules.structure import Molecule
        from chemsmart.utils.grouper import StructureGrouperFactory

        input_file = request.input_file.expanduser().resolve()
        if not input_file.is_file():
            raise ValueError(
                "Choose an existing multi-structure molecule file."
            )
        if input_file.stat().st_size > 256 * 1024 * 1024:
            raise ValueError("The selected grouping input exceeds 256 MiB.")
        context.report_indeterminate("Parsing molecular structures…")
        molecules = Molecule.from_filepath(
            input_file,
            index=":",
            return_list=True,
        )
        if not isinstance(molecules, list) or len(molecules) < 2:
            raise ValueError(
                "Grouping needs at least two molecular structures."
            )
        if len(molecules) > 2000:
            raise ValueError(
                "Desktop grouping is limited to 2,000 structures."
            )
        if request.num_groups is not None and request.num_groups > len(
            molecules
        ):
            raise ValueError(
                "Target groups cannot exceed the number of structures."
            )
        context.raise_if_cancelled()

        def progress(current: int, total: int) -> None:
            context.report_progress(
                current,
                max(1, total),
                f"Grouping comparisons {current}/{total}…",
            )

        grouper = StructureGrouperFactory.create(
            molecules,
            strategy=request.strategy,
            num_procs=request.num_procs,
            threshold=request.threshold,
            num_groups=request.num_groups,
            ignore_hydrogens=request.ignore_hydrogens,
            record_results=False,
            progress_callback=progress,
            cancel_callback=context.raise_if_cancelled,
            fingerprint_type=request.fingerprint_type,
            inversion=request.inversion,
            use_weights=request.torsion_use_weights,
            max_dev=request.torsion_max_deviation,
        )
        groups, index_groups = grouper.group()
        context.raise_if_cancelled()

        result_groups = []
        for group_number, (group, indices) in enumerate(
            zip(groups, index_groups), start=1
        ):
            representative, representative_index = self._representative(
                group, indices
            )
            result_groups.append(
                GrouperGroup(
                    group_number=group_number,
                    member_indices=tuple(index + 1 for index in indices),
                    representative_index=representative_index + 1,
                    representative_energy=(
                        float(representative.energy)
                        if representative.energy is not None
                        else None
                    ),
                    preview=MoleculePreview(
                        symbols=tuple(representative.chemical_symbols),
                        positions=tuple(
                            (float(x), float(y), float(z))
                            for x, y, z in representative.positions
                        ),
                        charge=getattr(representative, "charge", None),
                        multiplicity=getattr(
                            representative, "multiplicity", None
                        ),
                    ),
                )
            )
        return GrouperResult(
            input_file=input_file,
            strategy=request.strategy,
            total_molecules=len(molecules),
            groups=tuple(result_groups),
            threshold=request.threshold,
            target_groups=request.num_groups,
            ignore_hydrogens=request.ignore_hydrogens,
        )

    def dias(self, request: DIASRequest, context: _TaskContext) -> DIASResult:
        from chemsmart.analysis.dias import (
            GaussianDIASLogFolder,
            ORCADIASOutFolder,
        )

        folder = request.folder.expanduser().resolve()
        if not folder.is_dir():
            raise ValueError("Choose an existing DIAS output folder.")
        entries = tuple(path for path in folder.iterdir() if path.is_file())
        if len(entries) > 5000:
            raise ValueError(
                "The DIAS folder exceeds the 5,000-file desktop limit."
            )
        if sum(path.stat().st_size for path in entries) > 2 * 1024**3:
            raise ValueError(
                "The DIAS folder exceeds the 2 GiB desktop limit."
            )

        gaussian_files = tuple(folder.glob("*_p*.log"))
        orca_files = tuple(folder.glob("*_p*.out"))
        program = request.program
        if program == "auto":
            detected = [
                name
                for name, files in (
                    ("gaussian", gaussian_files),
                    ("orca", orca_files),
                )
                if files
            ]
            if len(detected) != 1:
                raise ValueError(
                    "Could not uniquely detect Gaussian or ORCA DIAS outputs. "
                    "Choose the program explicitly."
                )
            program = detected[0]
        elif program == "gaussian" and not gaussian_files:
            raise ValueError("No Gaussian DIAS point outputs were found.")
        elif program == "orca" and not orca_files:
            raise ValueError("No ORCA DIAS point outputs were found.")

        context.raise_if_cancelled()
        context.report_indeterminate(
            f"Parsing {program.upper()} DIAS point and fragment outputs…"
        )
        domain_type = (
            GaussianDIASLogFolder
            if program == "gaussian"
            else ORCADIASOutFolder
        )
        try:
            domain = domain_type(
                folder=str(folder),
                atom1=request.atom1,
                atom2=request.atom2,
                zero=request.zero_reference,
            )
            total, distortion, interaction = domain.get_data()
        except (AssertionError, IndexError) as exc:
            raise ValueError(
                f"Incomplete or incompatible DIAS output set: {exc}"
            ) from exc
        context.raise_if_cancelled()
        coordinates = tuple(float(value) for value in domain.list_rc)
        if not (
            len(coordinates)
            == len(total)
            == len(distortion)
            == len(interaction)
        ):
            raise ValueError(
                "DIAS coordinate and energy series have different lengths."
            )
        points = tuple(
            DIASPoint(
                reaction_coordinate_angstrom=coordinate,
                total_energy_kcal_mol=float(total_energy),
                distortion_energy_kcal_mol=float(distortion_energy),
                interaction_energy_kcal_mol=float(interaction_energy),
            )
            for coordinate, total_energy, distortion_energy, interaction_energy in zip(
                coordinates, total, distortion, interaction
            )
        )
        if not points:
            raise ValueError("No complete DIAS points were found.")
        context.report_progress(
            len(points), len(points), f"Parsed {len(points)} DIAS points."
        )
        return DIASResult(
            folder=folder,
            program=program,
            atom1=request.atom1,
            atom2=request.atom2,
            zero_reference=request.zero_reference,
            points=points,
        )

    def wbi(self, request: WBIRequest, context: _TaskContext) -> WBIResult:
        from chemsmart.io.gaussian.output import Gaussian16WBIOutput

        output_file = request.output_file.expanduser().resolve()
        if not output_file.is_file():
            raise ValueError("Choose an existing Gaussian NBO output file.")
        if output_file.suffix.lower() != ".log":
            raise ValueError(
                "WBI/NBO population analysis requires a Gaussian .log file."
            )
        if output_file.stat().st_size > 512 * 1024**2:
            raise ValueError(
                "The WBI/NBO output exceeds the 512 MiB desktop limit."
            )
        context.raise_if_cancelled()
        context.report_indeterminate(
            "Parsing Gaussian NBO population analysis…"
        )
        output = Gaussian16WBIOutput(filename=str(output_file))
        population = output.natural_population_analysis
        orbitals = output.natural_atomic_orbitals
        configurations = output.electronic_configuration
        context.raise_if_cancelled()
        if not population:
            raise ValueError("No Natural Population Analysis table was found.")
        if not orbitals:
            raise ValueError("No Natural Atomic Orbital table was found.")

        requested = set(request.atom_indices)
        selected = []
        for label, values in population.items():
            match = re.fullmatch(r"([A-Z][a-z]?)(\d+)", label)
            if match is None:
                raise ValueError(f"Unexpected NBO atom label: {label}")
            element, index_text = match.groups()
            atom_index = int(index_text)
            if requested and atom_index not in requested:
                continue
            selected.append((atom_index, element, label, values))
        selected.sort(key=lambda item: item[0])
        if requested and {item[0] for item in selected} != requested:
            missing = sorted(requested - {item[0] for item in selected})
            raise ValueError(
                "Requested WBI/NBO atom indices were not found: "
                + ", ".join(str(index) for index in missing)
            )

        atoms = []
        total_atoms = len(selected)
        for current, (atom_index, element, label, values) in enumerate(
            selected, start=1
        ):
            context.raise_if_cancelled()
            atom_orbitals = orbitals.get(label)
            if not atom_orbitals:
                raise ValueError(
                    f"Natural Atomic Orbital data is missing for {label}."
                )
            atoms.append(
                WBIAtom(
                    atom_index=atom_index,
                    element=element,
                    label=label,
                    natural_charge=float(values["natural_charge"]),
                    core_electrons=float(values["core_electrons"]),
                    valence_electrons=float(values["valence_electrons"]),
                    rydberg_electrons=float(values["rydberg_electrons"]),
                    total_electrons=float(values["total_electrons"]),
                    nao_count=len(atom_orbitals),
                    total_nao_occupancy=sum(
                        float(orbital["occupancy"])
                        for orbital in atom_orbitals.values()
                    ),
                    electronic_configuration=configurations.get(label),
                )
            )
            context.report_progress(
                current,
                max(1, total_atoms),
                f"Mapped NBO atom {current}/{total_atoms}…",
            )
        return WBIResult(
            output_file=output_file,
            nbo_version=output.nbo_version,
            atoms=tuple(atoms),
        )

    @staticmethod
    def _representative(group, indices):
        paired = list(zip(group, indices))
        with_energy = [pair for pair in paired if pair[0].energy is not None]
        return (
            min(with_energy, key=lambda pair: pair[0].energy)
            if with_energy
            else paired[0]
        )

    @staticmethod
    def _thermochemistry_kwargs(request: ThermochemistryRequest) -> dict:
        return {
            "temperature": request.temperature,
            "pressure": request.pressure,
            "concentration": request.concentration,
            "use_weighted_mass": request.use_weighted_mass,
            "alpha": request.alpha,
            "s_freq_cutoff": request.entropy_cutoff_cm,
            "entropy_method": (
                None
                if request.entropy_method == "none"
                else request.entropy_method
            ),
            "h_freq_cutoff": request.enthalpy_cutoff_cm,
            "energy_units": request.energy_units,
            "check_imaginary_frequencies": request.check_imaginary_frequencies,
        }

    @staticmethod
    def _validated_output_files(files: tuple[Path, ...]) -> tuple[Path, ...]:
        resolved = tuple(path.expanduser().resolve() for path in files)
        total_bytes = 0
        for path in resolved:
            if not path.is_file():
                raise ValueError(f"Output file does not exist: {path.name}")
            total_bytes += path.stat().st_size
        if total_bytes > 512 * 1024 * 1024:
            raise ValueError("The selected analysis batch exceeds 512 MiB.")
        return resolved


__all__ = ["AnalysisService"]
