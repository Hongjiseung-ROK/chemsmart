"""A .db record's geometry is admitted; its stored state is never believed.

The batch round's admission seam: a chemsmart database row is provenance a
session may read, not authority it may inherit.  The ASE-kin row guarantees
only geometry and metadata -- charge and multiplicity may be stored, stale,
or absent entirely -- so the host copies exact coordinate bytes into an
ordinary workspace geometry artifact with full lineage (database digest,
record, structure) and the session binds the electronic state explicitly
afterwards, exactly as it does for a derived species.  Execution never
reads the .db again.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import (
    ContractError,
    TrustedArtifactRefV1,
    file_sha256,
)
from chemsmart.agent.execution import (
    extract_trusted_database_record_geometry,
)
from chemsmart.agent.live_session import (
    _scan_database_artifacts,
    _task_spec_sha256,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.database.database import Database

_WATER = {
    "molecule_id": "mol-water",
    "structure_id": "struct-water-1",
    "chemical_formula": "H2O",
    "number_of_atoms": 3,
    "chemical_symbols": ["O", "H", "H"],
    "positions": [
        [0.0, 0.0, 0.117],
        [0.0, 0.757, -0.469],
        [0.0, -0.757, -0.469],
    ],
    "charge": 0,
    "multiplicity": 1,
    "energy": -76.401234,
    "index": 0,
    "is_optimized_structure": True,
}

#: A stored row may carry no electronic state at all; only geometry is
#: guaranteed.  This is the row shape the observation-not-binding rule
#: exists for.
_BARE_METHYL = {
    "molecule_id": "mol-methyl",
    "structure_id": "struct-methyl-1",
    "chemical_formula": "CH3",
    "number_of_atoms": 4,
    "chemical_symbols": ["C", "H", "H", "H"],
    "positions": [
        [0.0, 0.0, 0.0],
        [0.0, 1.078, 0.0],
        [0.934, -0.539, 0.0],
        [-0.934, -0.539, 0.0],
    ],
    "charge": None,
    "multiplicity": None,
    "energy": None,
    "index": 0,
    "is_optimized_structure": False,
}

_METHYL_TWISTED = {
    **_BARE_METHYL,
    "structure_id": "struct-methyl-2",
    "positions": [
        [0.0, 0.0, 0.05],
        [0.0, 1.078, 0.1],
        [0.934, -0.539, 0.1],
        [-0.934, -0.539, 0.1],
    ],
    "index": 1,
}


def _write_database(path: Path) -> Path:
    database = Database(str(path))
    database.create()
    database.insert_record(
        {
            "record_id": "water-sp-0001",
            "meta": {"method": "gfn2-xtb", "basis": None},
            "results": {},
            "molecules": [dict(_WATER)],
            "provenance": {"program": "xtb"},
        }
    )
    database.insert_record(
        {
            "record_id": "methyl-guess-0002",
            "meta": {"method": None, "basis": None},
            "results": {},
            "molecules": [dict(_BARE_METHYL), dict(_METHYL_TWISTED)],
            "provenance": {"program": "unknown"},
        }
    )
    return Path(database.db_file)


def _database_artifact(path: Path, artifact_id="database-fixture"):
    return TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind="chemsmart_db",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )


def test_a_workspace_database_is_discovered_with_its_record_count(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_database(workspace / "acids.db")
    # A file the database layer cannot open is ignored rather than
    # misrepresented as an enumerable record set.
    (workspace / "garbage.db").write_bytes(b"not a database at all")

    observations = _scan_database_artifacts(workspace)

    assert len(observations) == 1
    observation = observations[0]
    assert observation.artifact.kind == "chemsmart_db"
    assert observation.record_count == 2
    record = observation.public_record()
    assert record["record_count"] == 2
    assert "never" in record["stored_fields_role"]


def test_a_database_enters_the_task_digest_only_when_present(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_database(workspace / "acids.db")
    observations = _scan_database_artifacts(workspace)

    without = _task_spec_sha256("carry the batch", ())
    explicit_empty = _task_spec_sha256(
        "carry the batch", (), database_observations=()
    )
    with_database = _task_spec_sha256(
        "carry the batch", (), database_observations=observations
    )

    # Pre-database task digests are unchanged; a present database is part
    # of what the task means.
    assert without == explicit_empty
    assert with_database != without


def test_extraction_copies_exact_bytes_with_full_lineage(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database_path = _write_database(workspace / "acids.db")
    artifact = _database_artifact(database_path)

    extracted, receipt = extract_trusted_database_record_geometry(
        approved_workspace=workspace,
        extracted_artifact_id="water-start",
        database_artifact=artifact,
        record_id="water-sp-0001",
    )

    written = Path(extracted.path)
    assert written == workspace / "artifacts" / "water-start.xyz"
    text = written.read_text()
    assert text.splitlines()[0] == "3"
    assert "electronic state deliberately unbound" in text
    assert "record water-sp-0001" in text
    assert receipt.database_sha256 == artifact.sha256
    assert receipt.database_filename == "acids.db"
    assert receipt.record_id == "water-sp-0001"
    assert receipt.structure_index == 1
    assert receipt.structure_count == 1
    assert receipt.formula == "H2O"
    assert receipt.stored_charge == 0
    assert receipt.stored_multiplicity == 1
    assert receipt.stored_energy == pytest.approx(-76.401234)
    assert receipt.stored_is_optimized is True
    assert "never identity bindings" in receipt.stored_fields_role


def test_a_stored_row_may_carry_no_electronic_state_at_all(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database_path = _write_database(workspace / "acids.db")
    artifact = _database_artifact(database_path)

    _extracted, receipt = extract_trusted_database_record_geometry(
        approved_workspace=workspace,
        extracted_artifact_id="methyl-start",
        database_artifact=artifact,
        record_id="methyl-guess-0002",
        structure_index=1,
    )

    # CH3 as stored decides nothing: radical, cation, and anion all share
    # these coordinates.  The receipt records the absence honestly.
    assert receipt.stored_charge is None
    assert receipt.stored_multiplicity is None
    assert receipt.stored_energy is None
    assert receipt.stored_is_optimized is False


def test_a_record_with_several_structures_demands_an_explicit_choice(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database_path = _write_database(workspace / "acids.db")
    artifact = _database_artifact(database_path)

    with pytest.raises(ContractError) as excinfo:
        extract_trusted_database_record_geometry(
            approved_workspace=workspace,
            extracted_artifact_id="methyl-ambiguous",
            database_artifact=artifact,
            record_id="methyl-guess-0002",
        )
    assert "2 structures" in str(excinfo.value)
    assert "structure_index" in str(excinfo.value)

    extracted, receipt = extract_trusted_database_record_geometry(
        approved_workspace=workspace,
        extracted_artifact_id="methyl-second",
        database_artifact=artifact,
        record_id="methyl-guess-0002",
        structure_index=2,
    )
    assert receipt.structure_index == 2
    assert "0.0500000000" in Path(extracted.path).read_text()


def test_an_unknown_record_is_refused_naming_the_available_set(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database_path = _write_database(workspace / "acids.db")
    artifact = _database_artifact(database_path)

    with pytest.raises(ContractError) as excinfo:
        extract_trusted_database_record_geometry(
            approved_workspace=workspace,
            extracted_artifact_id="nope",
            database_artifact=artifact,
            record_id="benzoic",
        )
    message = str(excinfo.value)
    assert "water-sp-0001" in message
    assert "methyl-guess-0002" in message


def _host_with_database(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    database_path = _write_database(workspace / "acids.db")
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s1"
        ),
        task_spec_sha256s=("a" * 64,),
        approved_workspace=workspace,
    )
    artifact = _database_artifact(database_path)
    host.artifacts[artifact.artifact_id] = artifact
    return host


def test_the_session_inspects_records_as_observations(tmp_path):
    host = _host_with_database(tmp_path)

    result = host.dispatch(
        turn_id="t1",
        tool_name="inspect_database_records",
        arguments={"database_artifact_id": "database-fixture"},
    )["result"]

    assert result["record_count"] == 2
    assert result["returned_records"] == 2
    by_id = {item["record_id"]: item for item in result["records"]}
    water = by_id["water-sp-0001"]
    assert water["structure_count"] == 1
    assert water["structures"][0]["stored_charge"] == 0
    methyl = by_id["methyl-guess-0002"]
    assert methyl["structures"][0]["stored_charge"] is None
    assert "never" in result["stored_fields_role"]
    assert "bind_scientific_identity" in result["next_action"]


def test_an_invalid_query_is_refused_naming_the_supported_fields(tmp_path):
    host = _host_with_database(tmp_path)

    with pytest.raises(ContractError) as excinfo:
        host.dispatch(
            turn_id="t1",
            tool_name="inspect_database_records",
            arguments={
                "database_artifact_id": "database-fixture",
                "query": "flavor = 'sour'",
            },
        )
    assert "flavor" in str(excinfo.value)
    assert "Supported fields" in str(excinfo.value)


def test_extraction_lands_an_artifact_and_the_binding_stays_explicit(
    tmp_path,
):
    host = _host_with_database(tmp_path)

    result = host.dispatch(
        turn_id="t1",
        tool_name="extract_database_record_geometry",
        arguments={
            "extracted_artifact_id": "water-start",
            "database_artifact_id": "database-fixture",
            "record_id": "water-sp-0001",
        },
    )["result"]

    assert result["artifact"]["kind"] == "geometry_xyz"
    assert result["stored_state_observation"]["charge"] == 0
    assert "bind charge and multiplicity explicitly" in result["next_action"]
    kinds = [event.kind for event in host.event_store.read_events()]
    assert EventKind.DATABASE_RECORD_EXTRACTED.value in kinds

    # The extracted artifact is an ordinary geometry input: the explicit
    # state binding is the same act every other geometry takes.
    bound = host.dispatch(
        turn_id="t2",
        tool_name="bind_scientific_identity",
        arguments={
            "input_artifact_id": "water-start",
            "charge": 0,
            "multiplicity": 1,
        },
    )["result"]
    assert bound["binding_sha256"]

    # One geometry, one artifact id: a second extraction under the same
    # name is refused rather than silently overwritten.
    with pytest.raises(ContractError):
        host.dispatch(
            turn_id="t3",
            tool_name="extract_database_record_geometry",
            arguments={
                "extracted_artifact_id": "water-start",
                "database_artifact_id": "database-fixture",
                "record_id": "water-sp-0001",
            },
        )


def test_a_geometry_artifact_is_not_a_database(tmp_path):
    host = _host_with_database(tmp_path)
    xyz = tmp_path / "workspace" / "loose.xyz"
    xyz.write_text("1\nhelium\nHe 0.0 0.0 0.0\n")
    loose = TrustedArtifactRefV1(
        artifact_id="loose-geometry",
        kind="geometry_xyz",
        sha256=file_sha256(xyz),
        size_bytes=xyz.stat().st_size,
        path=str(xyz),
        cli_value=str(xyz),
    )
    host.artifacts[loose.artifact_id] = loose

    with pytest.raises(ContractError) as excinfo:
        host.dispatch(
            turn_id="t1",
            tool_name="inspect_database_records",
            arguments={"database_artifact_id": "loose-geometry"},
        )
    assert "chemsmart_db" in str(excinfo.value)
