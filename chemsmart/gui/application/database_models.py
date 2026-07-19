"""Typed desktop contracts for ChemSmart database workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATABASE_TARGETS = ("records", "molecules", "structures")
MAX_DATABASE_PAGE_SIZE = 500
DATABASE_ASSEMBLE_PROGRAMS = ("auto", "gaussian", "orca")
DATABASE_ASSEMBLE_INDEXES = (":", "-1")
DATABASE_EXPORT_FORMATS = (".json", ".csv", ".xyz", ".extxyz")
MAX_DATABASE_ASSEMBLE_FILES = 2000
MAX_DATABASE_ASSEMBLE_BYTES = 2 * 1024**3


@dataclass(frozen=True)
class DatabaseAssembleRequest:
    input_directory: Path
    output_file: Path
    program: str = "auto"
    structure_index: str = ":"
    include_failed: bool = False
    continue_on_parse_errors: bool = False

    def __post_init__(self) -> None:
        if self.program not in DATABASE_ASSEMBLE_PROGRAMS:
            raise ValueError(f"Unsupported assembly program: {self.program}")
        if self.structure_index not in DATABASE_ASSEMBLE_INDEXES:
            raise ValueError(
                "Desktop assembly supports all structures or the final structure."
            )
        if self.output_file.suffix.lower() != ".db":
            raise ValueError(
                "The assembled database destination must end in .db."
            )


@dataclass(frozen=True)
class DatabaseAssembleResult:
    input_directory: Path
    output_file: Path
    program: str
    files_found: int
    records_parsed: int
    records_stored: int
    skipped_files: tuple[str, ...]
    failed_files: tuple[str, ...]
    duplicate_records: int
    dependency_files: tuple[str, ...]
    dependency_bytes: int
    output_bytes: int
    sha256: str


@dataclass(frozen=True)
class DatabaseExportRequest:
    db_file: Path
    output_file: Path
    record_index: int | None = None
    record_id: str | None = None
    structure_index: str | None = None
    structure_id: str | None = None
    molecule_id: str | None = None
    csv_keys: tuple[str, ...] = ()
    method_basis: str | None = None

    def __post_init__(self) -> None:
        if self.output_file.suffix.lower() not in DATABASE_EXPORT_FORMATS:
            supported = ", ".join(DATABASE_EXPORT_FORMATS)
            raise ValueError(f"Database export must use one of: {supported}.")
        if self.record_index is not None and self.record_index < 1:
            raise ValueError("Record index must be positive and one-based.")
        for label, value in (
            ("record ID", self.record_id),
            ("structure index", self.structure_index),
            ("structure ID", self.structure_id),
            ("molecule ID", self.molecule_id),
        ):
            if value is not None and not value.strip():
                raise ValueError(f"Database export {label} cannot be blank.")


@dataclass(frozen=True)
class DatabaseExportResult:
    db_file: Path
    output_file: Path
    format: str
    scope: str
    requested_items: int
    exported_items: int
    skipped_structure_ids: tuple[str, ...]
    output_bytes: int
    sha256: str


@dataclass(frozen=True)
class DatabaseBrowseRequest:
    db_file: Path
    target: str = "records"
    query: str = ""
    limit: int = 250

    def __post_init__(self) -> None:
        if self.target not in DATABASE_TARGETS:
            raise ValueError(f"Unsupported database target: {self.target}")
        if not 1 <= self.limit <= MAX_DATABASE_PAGE_SIZE:
            raise ValueError(
                f"Database result limit must be between 1 and {MAX_DATABASE_PAGE_SIZE}."
            )


@dataclass(frozen=True)
class DatabaseDetailRequest:
    db_file: Path
    target: str
    entity_id: str

    def __post_init__(self) -> None:
        if self.target not in DATABASE_TARGETS:
            raise ValueError(f"Unsupported database target: {self.target}")
        if not self.entity_id.strip():
            raise ValueError("A database entity ID is required.")


@dataclass(frozen=True)
class DatabaseColumn:
    key: str
    label: str


@dataclass(frozen=True)
class DatabaseRow:
    target: str
    entity_id: str
    values: tuple[tuple[str, Any], ...]

    def value(self, key: str) -> Any:
        return dict(self.values).get(key)


@dataclass(frozen=True)
class DatabasePage:
    db_file: Path
    target: str
    columns: tuple[DatabaseColumn, ...]
    rows: tuple[DatabaseRow, ...]
    total_count: int
    matched_count: int
    overview: tuple[tuple[str, Any], ...]

    @property
    def truncated(self) -> bool:
        return self.matched_count > len(self.rows)


@dataclass(frozen=True)
class DetailField:
    label: str
    value: str


@dataclass(frozen=True)
class DetailSection:
    title: str
    fields: tuple[DetailField, ...]


@dataclass(frozen=True)
class StructurePreview:
    symbols: tuple[str, ...]
    positions: tuple[tuple[float, float, float], ...]
    charge: int | None = None
    multiplicity: int | None = None

    def __post_init__(self) -> None:
        if not self.symbols or len(self.symbols) != len(self.positions):
            raise ValueError(
                "Structure preview symbols and positions must align."
            )


@dataclass(frozen=True)
class DatabaseDetail:
    target: str
    entity_id: str
    title: str
    sections: tuple[DetailSection, ...]
    structure: StructurePreview | None = None


__all__ = [
    "DATABASE_TARGETS",
    "DATABASE_ASSEMBLE_INDEXES",
    "DATABASE_ASSEMBLE_PROGRAMS",
    "DATABASE_EXPORT_FORMATS",
    "MAX_DATABASE_ASSEMBLE_BYTES",
    "MAX_DATABASE_ASSEMBLE_FILES",
    "MAX_DATABASE_PAGE_SIZE",
    "DatabaseAssembleRequest",
    "DatabaseAssembleResult",
    "DatabaseBrowseRequest",
    "DatabaseColumn",
    "DatabaseDetail",
    "DatabaseDetailRequest",
    "DatabaseExportRequest",
    "DatabaseExportResult",
    "DatabasePage",
    "DatabaseRow",
    "DetailField",
    "DetailSection",
    "StructurePreview",
]
