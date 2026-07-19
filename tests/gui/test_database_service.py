"""Contracts for the native structured database adapter."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.gui.application.database_models import (
    DatabaseAssembleRequest,
    DatabaseBrowseRequest,
    DatabaseDetailRequest,
    DatabaseExportRequest,
)
from chemsmart.gui.services.database_service import DatabaseService

FIXTURE = Path("tests/data/DatabaseTests/chemsmart.db").resolve()


@pytest.mark.parametrize(
    ("target", "expected_total", "id_key"),
    [
        ("records", 47, "record_id"),
        ("molecules", 33, "molecule_id"),
        ("structures", 314, "structure_id"),
    ],
)
def test_database_browse_matches_domain_query(
    target: str,
    expected_total: int,
    id_key: str,
) -> None:
    from chemsmart.database.query import DatabaseQuery

    service = DatabaseService()
    page = service.browse(
        DatabaseBrowseRequest(FIXTURE, target=target, limit=7)
    )
    direct = DatabaseQuery(str(FIXTURE), None, target=target, limit=7)
    direct_rows = direct.query_summaries()

    assert page.total_count == expected_total == direct.count_total()
    assert page.matched_count == expected_total
    assert len(page.rows) == len(direct_rows) == 7
    assert page.truncated
    assert [row.entity_id for row in page.rows] == [
        row[id_key] for row in direct_rows
    ]
    assert page.rows[0].value(id_key) == direct_rows[0][id_key]
    assert dict(page.overview)[f"num_{target}"] == expected_total


def test_database_query_filter_and_empty_result_are_structured() -> None:
    service = DatabaseService()
    gaussian = service.browse(
        DatabaseBrowseRequest(
            FIXTURE,
            target="records",
            query="program = 'gaussian' AND normal_termination = 1",
            limit=500,
        )
    )
    empty = service.browse(
        DatabaseBrowseRequest(
            FIXTURE,
            target="molecules",
            query="number_of_atoms > 100000",
            limit=10,
        )
    )

    assert gaussian.rows
    assert all(row.value("program") == "gaussian" for row in gaussian.rows)
    assert gaussian.matched_count == len(gaussian.rows)
    assert empty.rows == ()
    assert empty.matched_count == 0
    assert empty.total_count == 33


@pytest.mark.parametrize("target", ["records", "molecules", "structures"])
def test_database_detail_uses_domain_entities_and_geometry(
    target: str,
) -> None:
    service = DatabaseService()
    page = service.browse(
        DatabaseBrowseRequest(FIXTURE, target=target, limit=1)
    )
    detail = service.detail(
        DatabaseDetailRequest(FIXTURE, target, page.rows[0].entity_id)
    )

    assert detail.target == target
    assert detail.entity_id == page.rows[0].entity_id
    assert detail.sections
    assert detail.structure is not None
    assert len(detail.structure.symbols) == len(detail.structure.positions)
    assert all(len(position) == 3 for position in detail.structure.positions)


def test_database_requests_and_files_fail_closed(tmp_path: Path) -> None:
    service = DatabaseService()
    invalid = tmp_path / "not-chemsmart.db"
    invalid.write_text("not a sqlite database", encoding="utf-8")

    with pytest.raises(ValueError, match="between 1 and 500"):
        DatabaseBrowseRequest(FIXTURE, limit=501)
    with pytest.raises(ValueError, match="Unsupported database target"):
        DatabaseBrowseRequest(FIXTURE, target="tables")
    with pytest.raises(ValueError, match="not a ChemSmart database"):
        service.browse(DatabaseBrowseRequest(invalid))
    with pytest.raises(ValueError, match="existing ChemSmart"):
        service.browse(DatabaseBrowseRequest(tmp_path / "missing.db"))


def test_database_service_observes_cooperative_cancellation() -> None:
    from chemsmart.gui.application.task_controller import TaskCancelled

    class CancelledContext:
        def report_indeterminate(self, message: str = "") -> None:
            assert message

        def raise_if_cancelled(self) -> None:
            raise TaskCancelled("cancelled by test")

    with pytest.raises(TaskCancelled):
        DatabaseService().browse(
            DatabaseBrowseRequest(FIXTURE), CancelledContext()
        )


def test_database_service_interrupts_cancellation_inside_sqlite_query() -> (
    None
):
    from chemsmart.gui.application.task_controller import TaskCancelled

    class CancelInsideQuery:
        def __init__(self) -> None:
            self.checkpoints = 0

        def report_indeterminate(self, message: str = "") -> None:
            assert message

        def raise_if_cancelled(self) -> None:
            self.checkpoints += 1
            if self.checkpoints >= 2:
                raise TaskCancelled("cancelled inside sqlite")

    context = CancelInsideQuery()
    with pytest.raises(TaskCancelled, match="inside sqlite"):
        DatabaseService().browse(
            DatabaseBrowseRequest(FIXTURE, limit=500), context
        )
    assert context.checkpoints == 2


@pytest.mark.parametrize("suffix", [".json", ".csv", ".xyz", ".extxyz"])
def test_database_export_is_verified_and_published_once(
    tmp_path: Path, suffix: str
) -> None:
    output = tmp_path / f"verified{suffix}"
    request_kwargs = {"record_index": 1} if "xyz" in suffix else {}

    result = DatabaseService().export(
        DatabaseExportRequest(FIXTURE, output, **request_kwargs)
    )

    assert result.output_file == output
    assert result.output_bytes == output.stat().st_size > 0
    assert len(result.sha256) == 64
    assert result.format == suffix
    assert result.requested_items == result.exported_items
    assert result.skipped_structure_ids == ()
    if suffix == ".json":
        assert output.read_text(encoding="utf-8").startswith("[")
    elif suffix == ".csv":
        assert output.read_text(encoding="utf-8").startswith(
            "record_index,record_id,chemical_formula"
        )
    elif suffix == ".extxyz":
        assert (
            "Properties=" in output.read_text(encoding="utf-8").splitlines()[1]
        )
    else:
        assert int(output.read_text(encoding="utf-8").splitlines()[0]) > 0
    assert not list(tmp_path.glob(f".{output.stem}.*{suffix}"))


@pytest.mark.parametrize(
    ("suffix", "method_basis"),
    [(".xyz", "m062x/def2svp"), (".extxyz", None)],
)
def test_molecule_export_reports_every_filtered_structure(
    tmp_path: Path, suffix: str, method_basis: str | None
) -> None:
    molecule_id = "CURLTUGMZLYLDI-UHFFFAOYSA-N"
    output = tmp_path / f"partial{suffix}"

    result = DatabaseService().export(
        DatabaseExportRequest(
            FIXTURE,
            output,
            molecule_id=molecule_id,
            method_basis=method_basis,
        )
    )

    assert result.requested_items == 7
    assert result.exported_items == 4
    assert len(result.skipped_structure_ids) == 3
    assert all(
        len(structure_id) == 64
        for structure_id in result.skipped_structure_ids
    )
    assert output.is_file()


def test_database_export_existing_destination_is_unchanged(
    tmp_path: Path,
) -> None:
    output = tmp_path / "protected.csv"
    original = b"researcher-owned-data\n"
    output.write_bytes(original)

    with pytest.raises(ValueError, match="already exists"):
        DatabaseService().export(DatabaseExportRequest(FIXTURE, output))

    assert output.read_bytes() == original


def test_database_export_cancellation_removes_staging_file(
    tmp_path: Path,
) -> None:
    from chemsmart.gui.application.task_controller import TaskCancelled

    class CancelBeforePublish:
        def __init__(self) -> None:
            self.checkpoints = 0

        def report_indeterminate(self, message: str = "") -> None:
            assert message

        def report_progress(
            self, current: int, total: int, message: str = ""
        ) -> None:
            del current, total, message

        def raise_if_cancelled(self) -> None:
            self.checkpoints += 1
            if self.checkpoints >= 3:
                raise TaskCancelled("cancel before publish")

    output = tmp_path / "cancelled.csv"
    with pytest.raises(TaskCancelled, match="before publish"):
        DatabaseService().export(
            DatabaseExportRequest(FIXTURE, output), CancelBeforePublish()
        )

    assert not output.exists()
    assert not list(tmp_path.glob(".cancelled.*.csv"))


def test_concurrent_exports_never_overwrite(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    output = tmp_path / "race.csv"
    request = DatabaseExportRequest(FIXTURE, output)

    def run():
        try:
            return DatabaseService().export(request)
        except ValueError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _index: run(), range(2)))

    successes = [item for item in outcomes if not isinstance(item, Exception)]
    failures = [item for item in outcomes if isinstance(item, Exception)]
    assert len(successes) == len(failures) == 1
    assert "another task" in str(failures[0])
    assert output.stat().st_size == successes[0].output_bytes
    assert not list(tmp_path.glob(".race.*.csv"))


def _fixture_record():
    from chemsmart.database.database import Database
    from chemsmart.database.records import AssembledRecord

    record = Database(str(FIXTURE)).get_record(record_index=1)
    return AssembledRecord(
        record_id=record["record_id"],
        meta=record["meta"],
        results=record["results"],
        molecules=record["molecules"],
        provenance=record["provenance"],
    )


def _fixture_record_with_dependencies(dependencies):
    from chemsmart.database.records import AssembledRecord

    record = _fixture_record()
    return AssembledRecord(
        record_id=record.record_id,
        meta=record.meta,
        results=record.results,
        molecules=record.molecules,
        provenance={
            **record.provenance,
            "source_dependencies": dependencies,
        },
    )


def test_database_assemble_stages_checks_and_publishes(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.database.assemble import SingleFileAssembler
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    calculation = source / "water.log"
    calculation.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(calculation)] if program == "gaussian" else []
        ),
    )
    monkeypatch.setattr(
        SingleFileAssembler,
        "assemble",
        lambda self, suppress_errors=True: _fixture_record(),
    )
    output = tmp_path / "assembled.db"

    result = DatabaseService().assemble(
        DatabaseAssembleRequest(source, output, program="gaussian")
    )

    assert (
        result.files_found
        == result.records_parsed
        == result.records_stored
        == 1
    )
    assert result.failed_files == result.skipped_files == ()
    assert output.is_file()
    assert len(result.sha256) == 64
    assert not list(tmp_path.glob(".assembled.*.db"))


def test_database_assemble_parser_error_is_fail_closed(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.database.assemble import SingleFileAssembler
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    calculation = source / "broken.out"
    calculation.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(calculation)] if program == "orca" else []
        ),
    )

    def fail(self, suppress_errors=True):
        del self, suppress_errors
        raise RuntimeError("parser payload must remain redacted")

    monkeypatch.setattr(SingleFileAssembler, "assemble", fail)
    output = tmp_path / "not-created.db"

    with pytest.raises(ValueError, match="Could not parse broken.out"):
        DatabaseService().assemble(
            DatabaseAssembleRequest(source, output, program="orca")
        )

    assert not output.exists()
    assert not list(tmp_path.glob(".not-created.*.db"))


def test_database_assemble_partial_batch_requires_explicit_toggle(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.database.assemble import SingleFileAssembler
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    good = source / "good.log"
    bad = source / "bad.log"
    good.write_text("fixture", encoding="utf-8")
    bad.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(good), str(bad)] if program == "gaussian" else []
        ),
    )

    def assemble(self, suppress_errors=True):
        del suppress_errors
        if Path(self.filename).name == "bad.log":
            raise RuntimeError("fixture parser failure")
        return _fixture_record()

    monkeypatch.setattr(SingleFileAssembler, "assemble", assemble)
    output = tmp_path / "partial.db"

    result = DatabaseService().assemble(
        DatabaseAssembleRequest(
            source,
            output,
            program="gaussian",
            continue_on_parse_errors=True,
        )
    )

    assert result.records_stored == 1
    assert result.failed_files == ("bad.log (RuntimeError)",)
    assert output.is_file()


def test_database_assemble_normal_file_without_structures_is_fail_closed(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.database.assemble import SingleFileAssembler
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    calculation = source / "empty-geometry.log"
    calculation.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(calculation)] if program == "gaussian" else []
        ),
    )

    class Output:
        normal_termination = True

    class EmptyAssembler:
        output = Output()

        @staticmethod
        def assemble():
            return None

    monkeypatch.setattr(
        SingleFileAssembler,
        "_get_assembler",
        lambda self, filename: EmptyAssembler(),
    )
    output = tmp_path / "not-created.db"

    with pytest.raises(ValueError, match="Could not parse empty-geometry.log"):
        DatabaseService().assemble(
            DatabaseAssembleRequest(source, output, program="gaussian")
        )

    assert not output.exists()
    assert not list(tmp_path.glob(".not-created.*.db"))


def test_strict_assembler_preserves_intentional_abnormal_skip(
    monkeypatch,
) -> None:
    from chemsmart.database.assemble import SingleFileAssembler

    class Output:
        normal_termination = False

    class AbnormalAssembler:
        output = Output()

        @staticmethod
        def assemble():
            return None

    assembler = SingleFileAssembler("abnormal.log", include_failed=False)
    monkeypatch.setattr(
        assembler,
        "_get_assembler",
        lambda filename: AbnormalAssembler(),
    )

    assert assembler.assemble(suppress_errors=False) is None


def test_database_assemble_rejects_source_symlink(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    real = source / "real.log"
    real.write_text("fixture", encoding="utf-8")
    linked = source / "linked.log"
    linked.symlink_to(real)
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(linked)] if program == "gaussian" else []
        ),
    )

    with pytest.raises(ValueError, match="Source symlink"):
        DatabaseService().assemble(
            DatabaseAssembleRequest(
                source, tmp_path / "never.db", program="gaussian"
            )
        )

    assert not (tmp_path / "never.db").exists()


def test_database_assemble_rejects_geometry_parent_escape(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    calculation = source / "single-point.out"
    calculation.write_text(
        "The coordinates will be read from file: ../outside.xyz\n",
        encoding="utf-8",
    )
    (tmp_path / "outside.xyz").write_text("1\noutside\nH 0 0 0\n")
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(calculation)] if program == "orca" else []
        ),
    )

    with pytest.raises(ValueError, match="contains a parent path"):
        DatabaseService().assemble(
            DatabaseAssembleRequest(
                source, tmp_path / "never.db", program="orca"
            )
        )
    assert not (tmp_path / "never.db").exists()


def test_database_assemble_rejects_geometry_symlink(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    calculation = source / "single-point.out"
    calculation.write_text(
        "The coordinates will be read from file: linked.xyz\n",
        encoding="utf-8",
    )
    geometry = source / "geometry.xyz"
    geometry.write_text("1\ninside\nH 0 0 0\n", encoding="utf-8")
    (source / "linked.xyz").symlink_to(geometry)
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(calculation)] if program == "orca" else []
        ),
    )

    with pytest.raises(ValueError, match="geometry symlink"):
        DatabaseService().assemble(
            DatabaseAssembleRequest(
                source, tmp_path / "never.db", program="orca"
            )
        )
    assert not (tmp_path / "never.db").exists()


def test_database_assemble_rejects_missing_geometry_dependency(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    calculation = source / "single-point.out"
    calculation.write_text(
        "The coordinates will be read from file: missing.xyz\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(calculation)] if program == "orca" else []
        ),
    )

    with pytest.raises(ValueError, match="does not exist"):
        DatabaseService().assemble(
            DatabaseAssembleRequest(
                source, tmp_path / "never.db", program="orca"
            )
        )
    assert not (tmp_path / "never.db").exists()


def test_database_assemble_counts_geometry_dependency_toward_byte_limit(
    tmp_path: Path, monkeypatch
) -> None:
    import chemsmart.gui.services.database_service as service_module
    from chemsmart.database.assemble import SingleFileAssembler
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    calculation = source / "single-point.out"
    calculation.write_text(
        "The coordinates will be read from file: geometry.xyz\n",
        encoding="utf-8",
    )
    geometry = source / "geometry.xyz"
    geometry.write_text("1\nbounded\nH 0 0 0\n", encoding="utf-8")
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(calculation)] if program == "orca" else []
        ),
    )
    monkeypatch.setattr(
        service_module,
        "MAX_DATABASE_ASSEMBLE_BYTES",
        calculation.stat().st_size + geometry.stat().st_size - 1,
    )
    parsed = False

    def should_not_parse(self, suppress_errors=True):
        nonlocal parsed
        del self, suppress_errors
        parsed = True

    monkeypatch.setattr(SingleFileAssembler, "assemble", should_not_parse)

    with pytest.raises(ValueError, match="limited to 2 GiB"):
        DatabaseService().assemble(
            DatabaseAssembleRequest(
                source, tmp_path / "never.db", program="orca"
            )
        )
    assert not parsed
    assert not (tmp_path / "never.db").exists()


def test_database_assemble_rejects_geometry_mutated_during_parse(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.database.assemble import SingleFileAssembler
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    calculation = source / "single-point.out"
    calculation.write_text(
        "The coordinates will be read from file: geometry.xyz\n",
        encoding="utf-8",
    )
    geometry = source / "geometry.xyz"
    geometry.write_text("1\nbefore\nH 0 0 0\n", encoding="utf-8")
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(calculation)] if program == "orca" else []
        ),
    )

    def mutate_then_assemble(self, suppress_errors=True):
        del self, suppress_errors
        geometry.write_text("1\nafter mutation\nH 0 0 1\n", encoding="utf-8")
        return _fixture_record()

    monkeypatch.setattr(SingleFileAssembler, "assemble", mutate_then_assemble)

    with pytest.raises(ValueError, match="changed during parsing"):
        DatabaseService().assemble(
            DatabaseAssembleRequest(
                source, tmp_path / "never.db", program="orca"
            )
        )
    assert not (tmp_path / "never.db").exists()


def test_database_assemble_persists_verified_geometry_dependency(
    tmp_path: Path, monkeypatch
) -> None:
    from chemsmart.database.assemble import SingleFileAssembler
    from chemsmart.database.database import Database
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    calculation = source / "single-point.out"
    calculation.write_text(
        "The coordinates will be read from file: geometry.xyz\n",
        encoding="utf-8",
    )
    geometry = source / "geometry.xyz"
    geometry.write_text("1\nverified\nH 0 0 0\n", encoding="utf-8")
    dependency = {
        "role": "orca_xyzfile_geometry",
        "path": str(geometry.resolve()),
        "sha256": hashlib.sha256(geometry.read_bytes()).hexdigest(),
        "size_bytes": geometry.stat().st_size,
    }
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(calculation)] if program == "orca" else []
        ),
    )
    monkeypatch.setattr(
        SingleFileAssembler,
        "assemble",
        lambda self, suppress_errors=True: _fixture_record_with_dependencies(
            [dependency]
        ),
    )
    output = tmp_path / "verified.db"

    result = DatabaseService().assemble(
        DatabaseAssembleRequest(source, output, program="orca")
    )

    assert result.dependency_files == ("geometry.xyz",)
    assert result.dependency_bytes == geometry.stat().st_size
    record = Database(str(output)).get_record(record_index=1)
    assert record["provenance"]["source_dependencies"] == [dependency]


def test_database_export_domain_rejects_invalid_selector_combinations() -> (
    None
):
    from chemsmart.database.export import validate_export_options

    with pytest.raises(ValueError, match="always covers the entire database"):
        validate_export_options("records.json", record_index=1)
    with pytest.raises(ValueError, match="requires exactly one"):
        validate_export_options("records.xyz")
    with pytest.raises(ValueError, match="requires exactly one"):
        validate_export_options(
            "records.extxyz", record_id="one", structure_id="two"
        )
    with pytest.raises(ValueError, match="Structure index"):
        validate_export_options(
            "records.xyz", structure_id="one", structure_index=":"
        )
    with pytest.raises(ValueError, match="Method/basis"):
        validate_export_options(
            "records.xyz", record_index=1, method_basis="m/b"
        )


def test_database_assemble_limits_are_checked_before_parsing(
    tmp_path: Path, monkeypatch
) -> None:
    import chemsmart.gui.services.database_service as service_module
    from chemsmart.database.assemble import SingleFileAssembler
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    files = []
    for index in range(3):
        path = source / f"calc-{index}.log"
        path.write_text("1234", encoding="utf-8")
        files.append(str(path))
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: files if program == "gaussian" else [],
    )
    monkeypatch.setattr(service_module, "MAX_DATABASE_ASSEMBLE_FILES", 2)
    parsed = False

    def should_not_parse(self, suppress_errors=True):
        nonlocal parsed
        del self, suppress_errors
        parsed = True

    monkeypatch.setattr(SingleFileAssembler, "assemble", should_not_parse)

    with pytest.raises(ValueError, match="limited to 2 files"):
        DatabaseService().assemble(
            DatabaseAssembleRequest(
                source, tmp_path / "bounded.db", program="gaussian"
            )
        )
    assert not parsed
    assert not (tmp_path / "bounded.db").exists()

    monkeypatch.setattr(service_module, "MAX_DATABASE_ASSEMBLE_FILES", 10)
    monkeypatch.setattr(service_module, "MAX_DATABASE_ASSEMBLE_BYTES", 5)
    with pytest.raises(ValueError, match="limited to 2 GiB"):
        DatabaseService().assemble(
            DatabaseAssembleRequest(
                source, tmp_path / "bounded-bytes.db", program="gaussian"
            )
        )
    assert not parsed
    assert not (tmp_path / "bounded-bytes.db").exists()


def test_concurrent_database_assembly_publishes_exactly_once(
    tmp_path: Path, monkeypatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from chemsmart.database.assemble import SingleFileAssembler
    from chemsmart.io.folder import BaseFolder

    source = tmp_path / "outputs"
    source.mkdir()
    calculation = source / "water.log"
    calculation.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        BaseFolder,
        "get_all_output_files_in_current_folder_and_subfolders_by_program",
        lambda self, program=None: (
            [str(calculation)] if program == "gaussian" else []
        ),
    )
    monkeypatch.setattr(
        SingleFileAssembler,
        "assemble",
        lambda self, suppress_errors=True: _fixture_record(),
    )
    output = tmp_path / "race.db"
    request = DatabaseAssembleRequest(source, output, program="gaussian")

    def run():
        try:
            return DatabaseService().assemble(request)
        except ValueError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _index: run(), range(2)))

    successes = [item for item in outcomes if not isinstance(item, Exception)]
    failures = [item for item in outcomes if isinstance(item, Exception)]
    assert len(successes) == len(failures) == 1
    assert "another task" in str(failures[0])
    assert output.stat().st_size == successes[0].output_bytes
    assert not list(tmp_path.glob(".race.*.db"))


def test_database_destination_symlink_is_never_followed(
    tmp_path: Path,
) -> None:
    real = tmp_path / "researcher-owned.csv"
    real.write_bytes(b"keep-me")
    linked = tmp_path / "linked.csv"
    linked.symlink_to(real)

    with pytest.raises(ValueError, match="already exists"):
        DatabaseService().export(DatabaseExportRequest(FIXTURE, linked))

    assert real.read_bytes() == b"keep-me"


def test_real_database_assembly_round_trip_when_openbabel_is_available(
    tmp_path: Path,
) -> None:
    import shutil

    pytest.importorskip("openbabel")
    source = tmp_path / "real-outputs"
    source.mkdir()
    shutil.copy2(
        Path("tests/data/GaussianTests/outputs/water_mp2.log"),
        source / "water_mp2.log",
    )
    shutil.copy2(
        Path("tests/data/ORCATests/outputs/water_opt.out"),
        source / "water_opt.out",
    )
    output = tmp_path / "real.db"

    result = DatabaseService().assemble(
        DatabaseAssembleRequest(source, output)
    )

    assert (
        result.files_found
        == result.records_parsed
        == result.records_stored
        == 2
    )
    assert result.failed_files == result.skipped_files == ()
    page = DatabaseService().browse(
        DatabaseBrowseRequest(output, target="records", limit=10)
    )
    assert page.total_count == page.matched_count == len(page.rows) == 2
