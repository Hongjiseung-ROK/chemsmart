"""Safe desktop adapter over ChemSmart's structured database APIs."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar

from chemsmart.gui.application.database_models import (
    MAX_DATABASE_ASSEMBLE_BYTES,
    MAX_DATABASE_ASSEMBLE_FILES,
    DatabaseAssembleRequest,
    DatabaseAssembleResult,
    DatabaseBrowseRequest,
    DatabaseColumn,
    DatabaseDetail,
    DatabaseDetailRequest,
    DatabaseExportRequest,
    DatabaseExportResult,
    DatabasePage,
    DatabaseRow,
    DetailField,
    DetailSection,
    StructurePreview,
)

T = TypeVar("T")


@dataclass(frozen=True)
class _SourceDependency:
    path: Path
    relative_path: str
    size_bytes: int
    sha256: str
    device: int
    inode: int
    modified_ns: int


class _TaskContext(Protocol):
    def report_indeterminate(self, message: str = "") -> None: ...

    def report_progress(
        self, current: int, total: int, message: str = ""
    ) -> None: ...

    def raise_if_cancelled(self) -> None: ...

    def commit(self, action: Callable[[], T]) -> T: ...


class _NullContext:
    def report_indeterminate(self, message: str = "") -> None:
        del message

    def report_progress(
        self, current: int, total: int, message: str = ""
    ) -> None:
        del current, total, message

    def raise_if_cancelled(self) -> None:
        return

    def commit(self, action: Callable[[], T]) -> T:
        return action()


class DatabaseService:
    """Translate domain dictionaries into bounded, typed desktop DTOs."""

    def assemble(
        self,
        request: DatabaseAssembleRequest,
        context: _TaskContext | None = None,
    ) -> DatabaseAssembleResult:
        """Create a new database through a verified, no-overwrite publish."""

        from chemsmart.database.assemble import SingleFileAssembler
        from chemsmart.database.database import Database
        from chemsmart.database.utils import (
            check_schema_version,
            is_chemsmart_database,
            sha256_file,
        )
        from chemsmart.io.folder import BaseFolder
        from chemsmart.io.orca.output import ORCAOutput

        task = context or _NullContext()
        task.report_indeterminate("Checking source folder and destination…")
        source = request.input_directory.expanduser().resolve()
        if not source.is_dir():
            raise ValueError("Choose an existing calculation output folder.")
        destination = self._validated_new_destination(
            request.output_file, ".db"
        )
        task.raise_if_cancelled()

        programs = (
            ("gaussian", "orca")
            if request.program == "auto"
            else (request.program,)
        )
        folder = BaseFolder(folder=str(source))
        discovered: list[Path] = []
        for program in programs:
            task.raise_if_cancelled()
            discovered.extend(
                Path(filename)
                for filename in folder.get_all_output_files_in_current_folder_and_subfolders_by_program(
                    program=program
                )
            )
        files = self._validated_source_files(source, discovered)
        if not files:
            raise ValueError(
                "No supported Gaussian or ORCA output files were found."
            )
        dependencies_by_output = self._validated_source_dependencies(
            source,
            files,
            ORCAOutput,
            sha256_file,
            task,
        )
        unique_dependencies = {
            dependency.path: dependency
            for dependencies in dependencies_by_output.values()
            for dependency in dependencies
        }
        source_resource_count = len(files) + len(unique_dependencies)
        if source_resource_count > MAX_DATABASE_ASSEMBLE_FILES:
            raise ValueError(
                f"Desktop assembly is limited to {MAX_DATABASE_ASSEMBLE_FILES} "
                "files per run, counting outputs and referenced geometries. "
                "Split this source folder into smaller batches."
            )
        total_bytes = sum(
            dependency.size_bytes
            for dependency in unique_dependencies.values()
        )
        for path in files:
            task.raise_if_cancelled()
            total_bytes += path.stat().st_size
            if total_bytes > MAX_DATABASE_ASSEMBLE_BYTES:
                raise ValueError(
                    "Desktop assembly is limited to 2 GiB of source output per run."
                )

        rows = []
        skipped: list[str] = []
        failed: list[str] = []
        total = len(files)
        for index, path in enumerate(files, start=1):
            task.report_progress(
                index - 1,
                total,
                f"Parsing calculation output {index} of {total}…",
            )
            task.raise_if_cancelled()
            try:
                row = SingleFileAssembler(
                    filename=str(path),
                    index=request.structure_index,
                    include_failed=request.include_failed,
                ).assemble(suppress_errors=False)
            except Exception as exc:
                failed.append(f"{path.name} ({type(exc).__name__})")
                if not request.continue_on_parse_errors:
                    raise ValueError(
                        f"Could not parse {path.name} ({type(exc).__name__}). "
                        "No database was created."
                    ) from exc
                continue
            if row is None:
                skipped.append(path.name)
            else:
                self._validate_dependency_provenance(
                    path,
                    row,
                    dependencies_by_output.get(path, ()),
                    sha256_file,
                )
                rows.append(row)
            task.report_progress(
                index,
                total,
                f"Parsed calculation output {index} of {total}.",
            )
        task.raise_if_cancelled()
        if not rows:
            raise ValueError(
                "No records could be assembled; no database was created."
            )

        task.report_indeterminate(
            "Writing and checking a private staging database…"
        )
        temporary = self._new_sibling_temp(destination)
        try:
            database = Database(str(temporary))
            database.create()
            connection = database.get_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                for row in rows:
                    task.raise_if_cancelled()
                    database.insert_record(row, connection)
                integrity = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]
                foreign_key_errors = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
                stored = connection.execute(
                    "SELECT COUNT(*) FROM records"
                ).fetchone()[0]
                if integrity != "ok" or foreign_key_errors:
                    raise RuntimeError(
                        "The staging database failed integrity checks."
                    )
                expected_unique = len({row.record_id for row in rows})
                if stored != expected_unique:
                    raise RuntimeError(
                        "The staging database record count did not match the parsed records."
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

            task.raise_if_cancelled()
            if not is_chemsmart_database(str(temporary)):
                raise RuntimeError(
                    "The staging file is not a ChemSmart database."
                )
            check_schema_version(str(temporary))
            output_bytes = temporary.stat().st_size
            digest = self._sha256(temporary)
            task.raise_if_cancelled()
            task.commit(
                lambda: self._publish_no_overwrite(temporary, destination)
            )
        finally:
            self._cleanup_staging(temporary)

        return DatabaseAssembleResult(
            input_directory=source,
            output_file=destination,
            program=request.program,
            files_found=len(files),
            records_parsed=len(rows),
            records_stored=stored,
            skipped_files=tuple(skipped),
            failed_files=tuple(failed),
            duplicate_records=len(rows) - stored,
            dependency_files=tuple(
                dependency.relative_path
                for dependency in sorted(
                    unique_dependencies.values(),
                    key=lambda item: item.relative_path,
                )
            ),
            dependency_bytes=sum(
                dependency.size_bytes
                for dependency in unique_dependencies.values()
            ),
            output_bytes=output_bytes,
            sha256=digest,
        )

    def export(
        self,
        request: DatabaseExportRequest,
        context: _TaskContext | None = None,
    ) -> DatabaseExportResult:
        """Export to a sibling staging file and publish without overwriting."""

        from chemsmart.database.export import (
            DatabaseExporter,
            resolve_method_basis,
            validate_export_options,
        )

        task = context or _NullContext()
        task.report_indeterminate("Validating database and export selection…")
        db_file = self._validated_database(request.db_file)
        destination = self._validated_new_destination(
            request.output_file, request.output_file.suffix.lower()
        )
        if destination == db_file:
            raise ValueError(
                "The export destination cannot be the source database."
            )
        keys = ",".join(request.csv_keys) if request.csv_keys else None
        method_basis = (
            request.method_basis.strip() if request.method_basis else None
        )
        format_name = validate_export_options(
            destination,
            record_index=request.record_index,
            record_id=request.record_id,
            structure_index=request.structure_index,
            structure_id=request.structure_id,
            molecule_id=request.molecule_id,
            keys=keys,
            method_basis=method_basis,
        )
        method = basis = None
        if method_basis is not None:
            method, basis = resolve_method_basis(db_file, method_basis)
        task.raise_if_cancelled()

        temporary = self._new_sibling_temp(destination)
        try:
            task.report_indeterminate(
                "Writing a private export copy; cancellation takes effect before publish…"
            )
            export_summary = DatabaseExporter(
                db_file=str(db_file),
                output=str(temporary),
                output_label=destination.name,
                record_index=request.record_index,
                record_id=request.record_id,
                structure_index=request.structure_index,
                structure_id=request.structure_id,
                molecule_id=request.molecule_id,
                keys=keys,
                method=method,
                basis=basis,
            ).export()
            task.raise_if_cancelled()
            self._validate_export_file(temporary, format_name)
            output_bytes = temporary.stat().st_size
            digest = self._sha256(temporary)
            task.raise_if_cancelled()
            task.commit(
                lambda: self._publish_no_overwrite(temporary, destination)
            )
        finally:
            self._cleanup_staging(temporary)

        scope = self._export_scope(request)
        return DatabaseExportResult(
            db_file=db_file,
            output_file=destination,
            format=format_name,
            scope=scope,
            requested_items=export_summary.requested_count,
            exported_items=export_summary.exported_count,
            skipped_structure_ids=export_summary.skipped_structure_ids,
            output_bytes=output_bytes,
            sha256=digest,
        )

    def browse(
        self,
        request: DatabaseBrowseRequest,
        context: _TaskContext | None = None,
    ) -> DatabasePage:
        from chemsmart.database.inspect import DatabaseInspector
        from chemsmart.database.query import TARGET_CONFIG, DatabaseQuery

        task = context or _NullContext()
        task.report_indeterminate("Validating ChemSmart database…")
        db_file = self._validated_database(request.db_file)
        task.raise_if_cancelled()

        task.report_indeterminate(f"Reading {request.target}…")
        query = DatabaseQuery(
            str(db_file),
            request.query.strip() or None,
            target=request.target,
            limit=request.limit,
            cancel_callback=task.raise_if_cancelled,
        )
        summaries = query.query_summaries()
        task.raise_if_cancelled()
        total_count = query.count_total()
        matched_count = query.count_matched()
        task.raise_if_cancelled()
        overview = DatabaseInspector(str(db_file)).overview()

        columns = tuple(
            DatabaseColumn(key=key, label=label)
            for label, key, _width, _alignment in TARGET_CONFIG[
                request.target
            ]["table_columns"]
        )
        id_key = {
            "records": "record_id",
            "molecules": "molecule_id",
            "structures": "structure_id",
        }[request.target]
        rows = tuple(
            DatabaseRow(
                target=request.target,
                entity_id=str(summary[id_key]),
                values=tuple(summary.items()),
            )
            for summary in summaries
        )
        task.raise_if_cancelled()
        return DatabasePage(
            db_file=db_file,
            target=request.target,
            columns=columns,
            rows=rows,
            total_count=total_count,
            matched_count=matched_count,
            overview=tuple(overview.items()),
        )

    def detail(
        self,
        request: DatabaseDetailRequest,
        context: _TaskContext | None = None,
    ) -> DatabaseDetail:
        from chemsmart.database.inspect import DatabaseInspector
        from chemsmart.database.utils import sort_structure_dicts_by_energy

        task = context or _NullContext()
        task.report_indeterminate("Loading structured database detail…")
        db_file = self._validated_database(request.db_file)
        task.raise_if_cancelled()
        inspector = DatabaseInspector(str(db_file))

        if request.target == "records":
            inspector.record_id = request.entity_id
            record = inspector.record_detail()
            structures = record.get("molecules", [])
            preview_source = next(
                (
                    item
                    for item in structures
                    if item.get("is_optimized_structure")
                ),
                structures[-1] if structures else None,
            )
            sections = (
                self._section(
                    "Record",
                    {
                        "record_index": record.get("record_index"),
                        "record_id": record.get("record_id"),
                        "structures": len(structures),
                    },
                ),
                self._section("Method and job", record.get("meta", {})),
                self._section("Results", record.get("results", {})),
                self._section("Provenance", record.get("provenance", {})),
            )
            title = f"Record {self._short_id(request.entity_id)}"
        elif request.target == "molecules":
            inspector.molecule_id = request.entity_id
            molecule, structures, records = inspector.molecule_detail()
            sorted_structures = sort_structure_dicts_by_energy(
                str(db_file), structures
            )
            preview_source = (
                sorted_structures[0] if sorted_structures else None
            )
            sections = (
                self._section("Molecule", molecule),
                self._section(
                    "Related data",
                    {
                        "structures": len(structures),
                        "records": len(records),
                    },
                ),
            )
            title = molecule.get("chemical_formula") or self._short_id(
                request.entity_id
            )
        else:
            inspector.structure_id = request.entity_id
            structure, records = inspector.standalone_structure_detail()
            preview_source = structure
            sections = (
                self._section("Structure", structure, exclude_geometry=True),
                self._section("Related data", {"records": len(records)}),
            )
            title = f"Structure {self._short_id(request.entity_id)}"

        task.raise_if_cancelled()
        return DatabaseDetail(
            target=request.target,
            entity_id=request.entity_id,
            title=str(title),
            sections=tuple(section for section in sections if section.fields),
            structure=self._structure_preview(preview_source),
        )

    @staticmethod
    def _validated_database(path: Path) -> Path:
        from chemsmart.database.utils import (
            check_schema_version,
            is_chemsmart_database,
        )

        db_file = path.expanduser().resolve()
        if db_file.suffix.lower() != ".db" or not db_file.is_file():
            raise ValueError("Choose an existing ChemSmart .db file.")
        if not is_chemsmart_database(str(db_file)):
            raise ValueError("The selected file is not a ChemSmart database.")
        check_schema_version(str(db_file))
        return db_file

    @staticmethod
    def _validated_new_destination(path: Path, suffix: str) -> Path:
        expanded = path.expanduser()
        if not expanded.is_absolute():
            expanded = Path.cwd() / expanded
        parent = expanded.parent.resolve()
        if not parent.is_dir():
            raise ValueError("Choose an existing destination folder.")
        destination = parent / expanded.name
        if destination.suffix.lower() != suffix.lower():
            raise ValueError(f"The destination must end in {suffix}.")
        if os.path.lexists(destination):
            raise ValueError(
                "The destination already exists. Choose a new file name; "
                "ChemSmart never overwrites database outputs."
            )
        return destination

    @staticmethod
    def _validated_source_files(
        root: Path, discovered: Sequence[Path]
    ) -> list[Path]:
        unique: dict[str, Path] = {}
        for candidate in discovered:
            if candidate.is_symlink():
                raise ValueError(
                    f"Source symlink {candidate.name} is not accepted for assembly."
                )
            resolved = candidate.resolve(strict=True)
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise ValueError(
                    f"Source file {candidate.name} resolves outside the selected folder."
                ) from exc
            if not resolved.is_file():
                continue
            unique[str(resolved)] = resolved
        return [unique[key] for key in sorted(unique)]

    @classmethod
    def _validated_source_dependencies(
        cls,
        root: Path,
        output_files: Sequence[Path],
        parser_class: type,
        hash_file: Callable[[Path], str],
        task: _TaskContext,
    ) -> dict[Path, tuple[_SourceDependency, ...]]:
        """Preflight indirect geometry files before an assembler opens them."""

        dependencies: dict[Path, tuple[_SourceDependency, ...]] = {}
        for output_file in output_files:
            task.raise_if_cancelled()
            parser = parser_class(str(output_file))
            referenced = parser.referenced_geometry_filename
            if referenced is None:
                dependencies[output_file] = ()
                continue
            if ".." in Path(referenced).parts:
                raise ValueError(
                    f"Referenced geometry for {output_file.name} contains a parent path."
                )
            candidate = parser.referenced_geometry_path
            dependency = cls._validated_dependency(
                root,
                output_file,
                candidate,
                hash_file,
            )
            dependencies[output_file] = (dependency,)
        return dependencies

    @staticmethod
    def _validated_dependency(
        root: Path,
        output_file: Path,
        candidate: Path,
        hash_file: Callable[[Path], str],
    ) -> _SourceDependency:
        lexical = Path(os.path.abspath(candidate))
        try:
            relative = lexical.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"Referenced geometry for {output_file.name} is outside the selected folder."
            ) from exc

        current = root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(
                    f"Referenced geometry symlink for {output_file.name} is not accepted."
                )
        try:
            resolved = lexical.resolve(strict=True)
        except (FileNotFoundError, OSError) as exc:
            raise ValueError(
                f"Referenced geometry for {output_file.name} does not exist."
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"Referenced geometry for {output_file.name} resolves outside the selected folder."
            ) from exc
        if not resolved.is_file():
            raise ValueError(
                f"Referenced geometry for {output_file.name} is not a regular file."
            )

        before = resolved.stat()
        digest = hash_file(resolved)
        after = resolved.stat()
        before_signature = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
        after_signature = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        if before_signature != after_signature:
            raise ValueError(
                f"Referenced geometry for {output_file.name} changed during validation."
            )
        return _SourceDependency(
            path=resolved,
            relative_path=relative.as_posix(),
            size_bytes=after.st_size,
            sha256=digest,
            device=after.st_dev,
            inode=after.st_ino,
            modified_ns=after.st_mtime_ns,
        )

    @staticmethod
    def _validate_dependency_provenance(
        output_file: Path,
        row: Any,
        expected: Sequence[_SourceDependency],
        hash_file: Callable[[Path], str],
    ) -> None:
        """Reject dependency mutation or provenance loss before DB staging."""

        provenance = getattr(row, "provenance", None)
        if provenance is None and isinstance(row, Mapping):
            provenance = row.get("provenance")
        provenance = provenance or {}
        actual = provenance.get("source_dependencies") or []
        expected_payload = [
            {
                "role": "orca_xyzfile_geometry",
                "path": str(dependency.path),
                "sha256": dependency.sha256,
                "size_bytes": dependency.size_bytes,
            }
            for dependency in expected
        ]

        for dependency in expected:
            try:
                resolved = dependency.path.resolve(strict=True)
                stat = dependency.path.stat()
            except (FileNotFoundError, OSError) as exc:
                raise ValueError(
                    f"Referenced geometry for {output_file.name} disappeared during parsing."
                ) from exc
            current_signature = (
                stat.st_dev,
                stat.st_ino,
                stat.st_size,
                stat.st_mtime_ns,
            )
            expected_signature = (
                dependency.device,
                dependency.inode,
                dependency.size_bytes,
                dependency.modified_ns,
            )
            if (
                resolved != dependency.path
                or current_signature != expected_signature
                or hash_file(dependency.path) != dependency.sha256
            ):
                raise ValueError(
                    f"Referenced geometry for {output_file.name} changed during parsing."
                )
        if actual != expected_payload:
            raise RuntimeError(
                f"Referenced geometry provenance for {output_file.name} did not match validation."
            )

    @staticmethod
    def _new_sibling_temp(destination: Path) -> Path:
        descriptor, filename = tempfile.mkstemp(
            prefix=f".{destination.stem}.",
            suffix=destination.suffix,
            dir=destination.parent,
        )
        os.close(descriptor)
        return Path(filename)

    @staticmethod
    def _publish_no_overwrite(temporary: Path, destination: Path) -> None:
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise ValueError(
                "The destination was created by another task. Nothing was overwritten."
            ) from exc
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        try:
            directory_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass

    @staticmethod
    def _cleanup_staging(temporary: Path) -> None:
        for suffix in ("", "-journal", "-wal", "-shm"):
            candidate = Path(f"{temporary}{suffix}")
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _validate_export_file(path: Path, format_name: str) -> None:
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("The staging export is empty.")
        if format_name == ".json":
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, list):
                raise RuntimeError(
                    "The JSON export did not contain a record list."
                )
        elif format_name == ".csv":
            with path.open(newline="", encoding="utf-8") as handle:
                header = next(csv.reader(handle), [])
            required = {"record_index", "record_id", "chemical_formula"}
            if not required.issubset(header):
                raise RuntimeError("The CSV export header failed validation.")
        else:
            with path.open(encoding="utf-8") as handle:
                first = handle.readline().strip()
                second = handle.readline().strip()
            try:
                atom_count = int(first)
            except ValueError as exc:
                raise RuntimeError(
                    "The XYZ export atom count is invalid."
                ) from exc
            if atom_count <= 0 or not second:
                raise RuntimeError("The XYZ export frame is incomplete.")
            if format_name == ".extxyz" and "Properties=" not in second:
                raise RuntimeError(
                    "The extended XYZ header failed validation."
                )

    @staticmethod
    def _export_scope(request: DatabaseExportRequest) -> str:
        for label, value in (
            ("record index", request.record_index),
            ("record ID", request.record_id),
            ("structure ID", request.structure_id),
            ("molecule ID", request.molecule_id),
        ):
            if value is not None:
                return label
        return "whole database"

    @classmethod
    def _section(
        cls,
        title: str,
        values: Mapping[str, Any],
        *,
        exclude_geometry: bool = False,
    ) -> DetailSection:
        excluded = {
            "chemical_symbols",
            "positions",
            "vibrational_modes",
            "forces",
        }
        fields = []
        for key, value in values.items():
            if exclude_geometry and key in excluded:
                continue
            if value is None or key in {"vibrational_modes", "forces"}:
                continue
            fields.append(
                DetailField(
                    label=key.replace("_", " ").strip().capitalize(),
                    value=cls._display_value(value),
                )
            )
        return DetailSection(title=title, fields=tuple(fields))

    @staticmethod
    def _display_value(value: Any) -> str:
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, float):
            return f"{value:.10g}"
        if isinstance(value, Mapping):
            rendered = json.dumps(value, sort_keys=True, default=str)
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            rendered = json.dumps(list(value), default=str)
        else:
            rendered = str(value)
        return rendered if len(rendered) <= 320 else f"{rendered[:317]}…"

    @staticmethod
    def _structure_preview(
        structure: Mapping[str, Any] | None,
    ) -> StructurePreview | None:
        if not structure:
            return None
        symbols = structure.get("chemical_symbols")
        positions = structure.get("positions")
        if not symbols or not positions or len(symbols) != len(positions):
            return None
        return StructurePreview(
            symbols=tuple(str(symbol) for symbol in symbols),
            positions=tuple(
                (float(position[0]), float(position[1]), float(position[2]))
                for position in positions
            ),
            charge=structure.get("charge"),
            multiplicity=structure.get("multiplicity"),
        )

    @staticmethod
    def _short_id(value: str) -> str:
        return value if len(value) <= 14 else f"{value[:12]}…"


__all__ = ["DatabaseService"]
