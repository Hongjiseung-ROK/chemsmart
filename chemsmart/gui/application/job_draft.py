"""Typed, execution-neutral state for one desktop chemistry job."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from pathlib import Path
from typing import Any, Mapping


class SourceKind(str, Enum):
    FILE = "file"
    PUBCHEM = "pubchem"
    DATABASE = "database"
    PRIOR_ARTIFACT = "prior_artifact"




@dataclass(frozen=True)
class DatabaseSelection:
    """Valid Gaussian/ORCA selection within one ChemSmart database."""

    record_index: int | None = None
    record_id: str = ""
    structure_index: str = ""
    structure_id: str = ""

    def __post_init__(self) -> None:
        if self.record_index is not None and self.record_index < 1:
            raise ValueError("Database record index must be 1-based.")
        primary = sum(
            (
                self.record_index is not None,
                bool(self.record_id.strip()),
                bool(self.structure_id.strip()),
            )
        )
        if primary != 1:
            raise ValueError(
                "Database jobs need exactly one record index, record ID, "
                "or global structure ID."
            )
        if (
            self.structure_index.strip()
            and self.record_index is None
            and not self.record_id.strip()
        ):
            raise ValueError(
                "A structure index requires a record index or record ID."
            )


@dataclass(frozen=True)
class MoleculeSource:
    kind: SourceKind
    value: str
    database: DatabaseSelection | None = None

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Molecule source value must be non-empty.")
        if self.kind == SourceKind.DATABASE:
            if not self.value.lower().endswith(".db"):
                raise ValueError("Database source must name a .db file.")
            if self.database is None:
                raise ValueError("Database source needs a reviewed selection.")
        elif self.database is not None:
            raise ValueError("Only database sources carry database selection.")


class ProvenanceKind(str, Enum):
    MANUAL = "manual"
    AGENT_RECEIPT = "agent_receipt"


@dataclass(frozen=True)
class DraftProvenance:
    kind: ProvenanceKind = ProvenanceKind.MANUAL
    receipt_ref: str = ""

    def __post_init__(self) -> None:
        if self.kind == ProvenanceKind.AGENT_RECEIPT and not self.receipt_ref:
            raise ValueError("Agent provenance requires a receipt reference.")
        if self.kind == ProvenanceKind.MANUAL and self.receipt_ref:
            raise ValueError("Manual provenance cannot carry an agent receipt.")


@dataclass(frozen=True)
class JobDraft:
    """Typed draft rendered by the live CLI schema adapter."""

    program: str
    kind: str
    source: MoleculeSource | None = None
    project: str | None = None
    charge: str | None = None
    multiplicity: str | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)
    resources: Mapping[str, Any] = field(default_factory=dict)
    provenance: DraftProvenance = field(default_factory=DraftProvenance)

    def __post_init__(self) -> None:
        if self.program not in {"gaussian", "orca", "xtb"}:
            raise ValueError(
                "Desktop JobDraft supports Gaussian, ORCA, and xTB only."
            )
        if not self.kind.strip():
            raise ValueError("JobDraft kind must be non-empty.")
        object.__setattr__(
            self,
            "settings",
            MappingProxyType(dict(self.settings)),
        )
        object.__setattr__(
            self,
            "resources",
            MappingProxyType(dict(self.resources)),
        )

    def preview_issues(self, cwd: Path) -> tuple[str, ...]:
        """Return desktop workflow blockers without duplicating CLI chemistry.

        The real parser and generated-input invariants remain authoritative.
        These checks only prevent obviously incomplete or network-dependent
        drafts from starting a background child process.
        """

        issues: list[str] = []
        if self.source is None:
            issues.append("Choose a molecule source.")
        elif self.source.kind == SourceKind.PUBCHEM:
            issues.append(
                "PubChem lookup needs network access and is unavailable in "
                "offline safe preview."
            )
        else:
            source_path = Path(self.source.value).expanduser()
            if not source_path.is_absolute():
                source_path = cwd / source_path
            if not source_path.is_file():
                issues.append("Choose an existing local molecule file.")
        if not (self.project or "").strip():
            issues.append("Choose a project configuration.")
        if not _is_integer(self.charge):
            issues.append("Enter an integer molecular charge.")
        if not _is_positive_integer(self.multiplicity):
            issues.append("Enter a positive integer spin multiplicity.")
        return tuple(issues)


def _is_integer(value: str | None) -> bool:
    try:
        int(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _is_positive_integer(value: str | None) -> bool:
    try:
        return int(str(value)) > 0
    except (TypeError, ValueError):
        return False


__all__ = [
    "DatabaseSelection",
    "DraftProvenance",
    "JobDraft",
    "MoleculeSource",
    "ProvenanceKind",
    "SourceKind",
]
