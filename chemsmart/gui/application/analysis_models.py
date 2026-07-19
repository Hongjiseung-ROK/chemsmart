"""Typed desktop contracts for ChemSmart analysis workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ENERGY_UNITS = ("hartree", "eV", "kcal/mol", "kJ/mol")
ENTROPY_METHODS = ("none", "grimme", "truhlar")
GROUPER_STRATEGIES = (
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
IGNORE_HYDROGENS_STRATEGIES = frozenset(
    {
        "rmsd",
        "hrmsd",
        "spyrmsd",
        "irmsd",
        "tanimoto",
        "torsion",
        "isomorphism",
        "connectivity",
    }
)
MAX_WBI_ATOM_FILTER = 500
DIAS_PROGRAMS = ("auto", "gaussian", "orca")


@dataclass(frozen=True)
class ThermochemistryRequest:
    files: tuple[Path, ...]
    temperature: float = 298.15
    pressure: float = 1.0
    concentration: float | None = None
    use_weighted_mass: bool = True
    alpha: int = 4
    entropy_method: str = "none"
    entropy_cutoff_cm: float | None = None
    enthalpy_cutoff_cm: float | None = None
    energy_units: str = "hartree"
    check_imaginary_frequencies: bool = True
    boltzmann_average: bool = False
    weighting_energy: str = "gibbs"

    def __post_init__(self) -> None:
        if not self.files:
            raise ValueError(
                "Choose at least one Gaussian or ORCA output file."
            )
        if len(self.files) > 100:
            raise ValueError(
                "A desktop thermochemistry batch is limited to 100 files."
            )
        if self.temperature <= 0:
            raise ValueError("Temperature must be greater than 0 K.")
        if self.pressure <= 0:
            raise ValueError("Pressure must be greater than 0 atm.")
        if self.concentration is not None and self.concentration <= 0:
            raise ValueError("Concentration must be greater than 0 mol/L.")
        if self.alpha <= 0:
            raise ValueError("The quasi-RRHO alpha exponent must be positive.")
        if self.energy_units not in ENERGY_UNITS:
            raise ValueError(f"Unsupported energy units: {self.energy_units}")
        if self.entropy_method not in ENTROPY_METHODS:
            raise ValueError(
                f"Unsupported entropy method: {self.entropy_method}"
            )
        if (
            self.entropy_method == "none"
            and self.entropy_cutoff_cm is not None
        ):
            raise ValueError("Choose Grimme or Truhlar for an entropy cutoff.")
        if self.entropy_method != "none" and (
            self.entropy_cutoff_cm is None or self.entropy_cutoff_cm <= 0
        ):
            raise ValueError(
                "The selected entropy correction needs a positive cutoff."
            )
        if (
            self.enthalpy_cutoff_cm is not None
            and self.enthalpy_cutoff_cm <= 0
        ):
            raise ValueError("The enthalpy cutoff must be positive.")
        if self.weighting_energy not in {"gibbs", "electronic"}:
            raise ValueError(
                "Boltzmann weighting must use Gibbs or electronic energy."
            )
        if self.boltzmann_average and len(self.files) < 2:
            raise ValueError(
                "Boltzmann averaging needs at least two conformer files."
            )


@dataclass(frozen=True)
class ThermochemistryRow:
    structure: str
    electronic_energy: float | None
    zero_point_energy: float | None
    enthalpy: float | None
    qrrho_enthalpy: float | None
    entropy_times_temperature: float | None
    qrrho_entropy_times_temperature: float | None
    gibbs_free_energy: float | None
    qrrho_gibbs_free_energy: float | None

    @classmethod
    def from_domain_tuple(cls, values: tuple) -> "ThermochemistryRow":
        if len(values) != 9:
            raise ValueError("Unexpected thermochemistry result shape.")
        return cls(*values)


@dataclass(frozen=True)
class ThermochemistryResult:
    files: tuple[Path, ...]
    rows: tuple[ThermochemistryRow, ...]
    temperature: float
    pressure: float
    concentration: float | None
    energy_units: str
    boltzmann_average: bool
    weighting_energy: str | None


@dataclass(frozen=True)
class GrouperRequest:
    input_file: Path
    strategy: str = "rmsd"
    threshold: float | None = None
    num_groups: int | None = None
    ignore_hydrogens: bool = False
    num_procs: int = 1
    fingerprint_type: str = "rdkit"
    inversion: str = "auto"
    torsion_use_weights: bool = True
    torsion_max_deviation: str = "equal"

    def __post_init__(self) -> None:
        if self.strategy not in GROUPER_STRATEGIES:
            raise ValueError(f"Unsupported grouping strategy: {self.strategy}")
        if self.strategy == "pymolrmsd":
            raise ValueError(
                "PyMOL RMSD needs the separately cancellable optional renderer boundary."
            )
        if self.threshold is not None and self.num_groups is not None:
            raise ValueError(
                "Choose either a threshold or target groups, not both."
            )
        if self.threshold is not None and self.threshold <= 0:
            raise ValueError("The grouping threshold must be positive.")
        if self.strategy in {"tanimoto", "torsion"} and (
            self.threshold is not None and self.threshold > 1
        ):
            raise ValueError(f"{self.strategy} threshold must be at most 1.")
        if self.num_groups is not None and self.num_groups < 1:
            raise ValueError("Target groups must be at least 1.")
        if not 1 <= self.num_procs <= 8:
            raise ValueError(
                "Desktop grouping supports between 1 and 8 workers."
            )
        if self.fingerprint_type not in {
            "rdkit",
            "rdk",
            "morgan",
            "maccs",
            "atompair",
            "torsion",
            "usr",
            "usrcat",
        }:
            raise ValueError("Unsupported Tanimoto fingerprint type.")
        if self.ignore_hydrogens and (
            self.strategy not in IGNORE_HYDROGENS_STRATEGIES
        ):
            raise ValueError(
                f"{self.strategy} does not support ignoring hydrogen atoms."
            )
        if self.inversion not in {"auto", "on", "off"}:
            raise ValueError("IRMSD inversion must be auto, on, or off.")
        if self.torsion_max_deviation not in {"equal", "spec"}:
            raise ValueError("TFD maximum deviation must be equal or spec.")


@dataclass(frozen=True)
class MoleculePreview:
    symbols: tuple[str, ...]
    positions: tuple[tuple[float, float, float], ...]
    charge: int | None = None
    multiplicity: int | None = None


@dataclass(frozen=True)
class GrouperGroup:
    group_number: int
    member_indices: tuple[int, ...]
    representative_index: int
    representative_energy: float | None
    preview: MoleculePreview


@dataclass(frozen=True)
class GrouperResult:
    input_file: Path
    strategy: str
    total_molecules: int
    groups: tuple[GrouperGroup, ...]
    threshold: float | None
    target_groups: int | None
    ignore_hydrogens: bool


@dataclass(frozen=True)
class DIASRequest:
    folder: Path
    atom1: int
    atom2: int
    program: str = "auto"
    zero_reference: bool = False

    def __post_init__(self) -> None:
        if self.program not in DIAS_PROGRAMS:
            raise ValueError(f"Unsupported DIAS program: {self.program}")
        if self.atom1 < 1 or self.atom2 < 1:
            raise ValueError(
                "DIAS atom numbers use positive, one-based indices."
            )
        if self.atom1 == self.atom2:
            raise ValueError(
                "Choose two different atoms for the reaction coordinate."
            )


@dataclass(frozen=True)
class DIASPoint:
    reaction_coordinate_angstrom: float
    total_energy_kcal_mol: float
    distortion_energy_kcal_mol: float
    interaction_energy_kcal_mol: float


@dataclass(frozen=True)
class DIASResult:
    folder: Path
    program: str
    atom1: int
    atom2: int
    zero_reference: bool
    points: tuple[DIASPoint, ...]


@dataclass(frozen=True)
class WBIRequest:
    output_file: Path
    atom_indices: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if any(index < 1 for index in self.atom_indices):
            raise ValueError(
                "WBI atom filters use positive, one-based indices."
            )
        if len(set(self.atom_indices)) != len(self.atom_indices):
            raise ValueError("WBI atom filters must not contain duplicates.")
        if len(self.atom_indices) > MAX_WBI_ATOM_FILTER:
            raise ValueError(
                f"WBI atom filtering is limited to {MAX_WBI_ATOM_FILTER} indices."
            )


@dataclass(frozen=True)
class WBIAtom:
    atom_index: int
    element: str
    label: str
    natural_charge: float
    core_electrons: float
    valence_electrons: float
    rydberg_electrons: float
    total_electrons: float
    nao_count: int
    total_nao_occupancy: float
    electronic_configuration: str | None


@dataclass(frozen=True)
class WBIResult:
    output_file: Path
    nbo_version: str | None
    atoms: tuple[WBIAtom, ...]


__all__ = [
    "DIAS_PROGRAMS",
    "DIASPoint",
    "DIASRequest",
    "DIASResult",
    "ENERGY_UNITS",
    "ENTROPY_METHODS",
    "GROUPER_STRATEGIES",
    "IGNORE_HYDROGENS_STRATEGIES",
    "MAX_WBI_ATOM_FILTER",
    "GrouperGroup",
    "GrouperRequest",
    "GrouperResult",
    "MoleculePreview",
    "ThermochemistryRequest",
    "ThermochemistryResult",
    "ThermochemistryRow",
    "WBIAtom",
    "WBIRequest",
    "WBIResult",
]
