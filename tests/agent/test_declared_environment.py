"""The agent's environment must be the one ChemSmart declares.

The harness once hard-coded which programs existed.  That made its view of the
host *different from* ChemSmart's rather than a narrower slice of it: a program
the server YAML declared could be invisible, and a program it never declared
could appear.  These tests pin the direction of the dependency -- declaration
first, observation second.
"""

import os
import stat

import pytest

from chemsmart.agent import live_session


@pytest.fixture
def declared_server(tmp_path, monkeypatch):
    """Point ChemSmart at a config dir holding one fixture server YAML."""

    server_dir = tmp_path / "server"
    server_dir.mkdir(parents=True)
    present = tmp_path / "present"
    present.mkdir()
    (present / "orca").write_text("#!/bin/sh\nexit 0\n")
    (present / "orca").chmod(0o700)
    (server_dir / "local.yaml").write_text(
        "SERVER:\n"
        "  SCHEDULER: SLURM\n"
        "  NUM_CORES: 8\n"
        "ORCA:\n"
        f"  EXEFOLDER: {present}\n"
        "GAUSSIAN:\n"
        f"  EXEFOLDER: {tmp_path / 'absent'}\n"
    )
    monkeypatch.setenv("CHEMSMART_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CHEMSMART_AGENT_SERVER", "local")
    return tmp_path


def test_declared_programs_follow_the_server_yaml(declared_server):
    declared = dict(live_session._declared_server_programs())
    assert set(declared) == {"orca", "gaussian"}
    assert declared["orca"].endswith("present")


def test_scheduler_key_is_not_mistaken_for_a_program(declared_server):
    assert "server" not in dict(live_session._declared_server_programs())


def test_a_declared_program_with_no_folder_is_observed_as_missing(
    declared_server,
):
    """Absent is not the same fact as undeclared, so it must not be dropped."""

    records = [
        item
        for item in live_session._observe_environments()[2]
        if item.get("record_kind") == "program_environment"
    ]
    by_program = {item["program"]: item for item in records}
    assert by_program["gaussian"]["status"] == "missing"
    assert by_program["orca"]["status"] == "available"


def test_discovery_targets_cover_every_declared_program(declared_server):
    targets = live_session._observe_environments()[0]
    programs = {item.program for item in targets}
    assert {"orca", "gaussian"} <= programs


def test_executable_name_comes_from_chemsmart_not_the_program_name(tmp_path):
    """Gaussian's binary is ``g16``; guessing ``gaussian`` would never resolve."""

    resolved = live_session._declared_executable_path(
        "gaussian", str(tmp_path)
    )
    assert resolved == str(tmp_path / "g16")
    assert live_session._declared_executable_path(
        "orca", str(tmp_path)
    ) == str(tmp_path / "orca")


def test_a_discovery_stub_is_reported_as_a_stub(tmp_path):
    """A placeholder that cannot compute must not read as a usable program."""

    stub = tmp_path / "g16"
    stub.write_text(
        "#!/bin/sh\n# ChemSmart agent-harness DISCOVERY STUB -- not Gaussian.\n"
        "exit 127\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    assert live_session._executable_is_discovery_stub(str(stub)) is True

    real = tmp_path / "orca"
    real.write_text("#!/bin/sh\necho real\n")
    assert live_session._executable_is_discovery_stub(str(real)) is False
    assert live_session._executable_is_discovery_stub("") is False
    assert (
        live_session._executable_is_discovery_stub(str(tmp_path / "nope"))
        is False
    )


def test_conformance_matrix_is_derived_from_declarations(declared_server):
    """Adding a program to ChemSmart must not require editing the session."""

    from chemsmart.settings.capabilities import EXECUTABLE_PROGRAMS

    programs = set(live_session._conformance_programs())
    assert programs <= set(EXECUTABLE_PROGRAMS)
    # A program declaring no core stage contributes no conformance work.
    assert "nciplot" not in programs
    # Per-engine capability is honoured: GPU PySCF previews no excited state.
    assert "td" in live_session._conformance_jobtypes("pyscf", "cpu")
    assert "td" not in live_session._conformance_jobtypes("pyscf", "gpu")


def test_project_requiring_programs_get_a_fixture(declared_server):
    for program in ("orca", "gaussian", "pyscf"):
        assert live_session._conformance_project_sections(program) is not None
    assert live_session._conformance_project_sections("xtb") is None


def test_a_fixture_declares_every_stage_it_claims_to_cover(declared_server):
    """A stage with no section makes the loader return ``None`` and the CLI crash."""

    for program in ("gaussian", "orca", "pyscf"):
        sections = live_session._conformance_project_sections(program)
        for stage in live_session._conformance_jobtypes(program, "cpu"):
            if stage in live_session._ROUTE_PROGRAM_STAGE_SECTIONS or (
                program == "pyscf"
            ):
                assert stage in sections, f"{program} fixture omits {stage}"


def test_a_fixture_carries_only_project_owned_keys(declared_server):
    """An unknown project key raises, so one bad key breaks every stage."""

    from chemsmart.settings.capabilities import PROGRAM_CAPABILITIES

    for program in ("gaussian", "orca"):
        allowed = set(PROGRAM_CAPABILITIES[program].project_owned_parameters)
        for settings in live_session._conformance_project_sections(
            program
        ).values():
            assert set(settings) <= allowed

    assert (
        live_session._conformance_project_sections("gaussian")["td"]["states"]
        == "singlets"
    )
    assert live_session._conformance_project_sections("orca")["td"] == {
        "basis": "def2-SVP",
        "functional": "B3LYP",
        "nstates": 3,
        "response_method": "tda",
        "state_manifold": "singlet",
    }


def test_environment_observation_does_not_depend_on_the_process_path(
    declared_server, monkeypatch
):
    """A program on PATH but undeclared is not part of ChemSmart's environment."""

    monkeypatch.setenv("PATH", os.devnull)
    records = [
        item
        for item in live_session._observe_environments()[2]
        if item.get("record_kind") == "program_environment"
    ]
    assert {item["program"] for item in records} >= {"orca", "gaussian"}


def _orca_record(tmp_path, monkeypatch, *, envars, extra=""):
    """The environment record of an ORCA declared with ``envars``."""

    server_dir = tmp_path / "server"
    server_dir.mkdir(parents=True, exist_ok=True)
    present = tmp_path / "present"
    present.mkdir(exist_ok=True)
    (present / "orca").write_text("#!/bin/sh\nexit 0\n")
    (present / "orca").chmod(0o700)
    block = "".join(f"    {line}\n" for line in envars)
    (server_dir / "local.yaml").write_text(
        "SERVER:\n"
        "  SCHEDULER: SLURM\n"
        "  NUM_CORES: 8\n"
        "ORCA:\n"
        f"  EXEFOLDER: {present}\n"
        "  ENVARS: |\n"
        f"{block}"
        f"{extra}"
    )
    monkeypatch.setenv("CHEMSMART_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CHEMSMART_AGENT_SERVER", "local")
    records = [
        item
        for item in live_session._observe_environments()[2]
        if item.get("record_kind") == "program_environment"
        and item.get("program") == "orca"
    ]
    assert len(records) == 1
    return records[0]


def test_a_parallel_program_says_whether_its_launcher_can_be_found(
    tmp_path, monkeypatch
):
    """ORCA starts its own ranks with ``mpirun``; the binary being there is
    not the program being runnable.

    Three approved ORCA calls died in 22 seconds with ``mpirun: command not
    found`` (CUHK job 2142445, 2026-09-21) under an environment record that
    read ``available``, because the record asked only whether ``orca``
    existed. The launcher is looked for where the engine will look: on the
    search path the program's own ENVARS build, not the controller's.
    """

    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.setenv("PATH", str(bare))
    missing = _orca_record(
        tmp_path, monkeypatch, envars=[f"export PATH={bare}:$PATH"]
    )
    assert missing["status"] == "available"
    assert missing["parallel_launcher"] == "mpirun"
    assert missing["parallel_launcher_status"] == "missing"
    assert missing["parallel_launcher_path"] == ""

    openmpi = tmp_path / "openmpi" / "bin"
    openmpi.mkdir(parents=True)
    (openmpi / "mpirun").write_text("#!/bin/sh\nexit 0\n")
    (openmpi / "mpirun").chmod(0o700)
    found = _orca_record(
        tmp_path, monkeypatch, envars=[f"export PATH={openmpi}:$PATH"]
    )
    assert found["parallel_launcher_status"] == "available"
    assert found["parallel_launcher_path"] == str(openmpi / "mpirun")


def test_what_only_a_job_script_would_apply_is_said_not_dropped(
    tmp_path, monkeypatch
):
    """``MODULES``, ``SCRIPTS`` and ``CONDA_ENV`` are shell text that only
    ``chemsmart sub`` writes into a job script. An engine started by ``run``
    never sees them, and an operator who put ``module load openmpi`` there
    should be told so rather than find out at the first parallel job."""

    monkeypatch.setenv("PATH", str(tmp_path))
    record = _orca_record(
        tmp_path,
        monkeypatch,
        envars=["export OMPI_MCA_plm=isolated"],
        extra=(
            "  MODULES: |\n"
            "    module load openmpi/4.1.8\n"
            "  CONDA_ENV: |\n"
            "    # nothing is activated\n"
        ),
    )
    assert record["applied_only_by_job_scripts"] == ["MODULES"]


def test_a_declared_program_with_no_folder_set_is_misconfigured_not_gone(
    tmp_path, monkeypatch
):
    """Misconfigured is not the same fact as absent, or as undeclared.

    A wizard-written profile declares ``GAUSSIAN:`` and ``ORCA:`` with
    ``EXEFOLDER: null`` until someone fills them in. Those blocks used to be
    dropped while the profile was read, so a session concluded the programs
    did not exist on this installation -- when ChemSmart knew about them and
    one line was missing. A library program that needs no folder (PySCF runs
    in an interpreter, xTB may come from PATH) is not misconfigured by lacking
    one.
    """

    server_dir = tmp_path / "server"
    server_dir.mkdir(parents=True)
    (server_dir / "local.yaml").write_text(
        "SERVER:\n"
        "  SCHEDULER: SLURM\n"
        "  NUM_CORES: 8\n"
        "GAUSSIAN:\n"
        "  EXEFOLDER: null\n"
        "  LOCAL_RUN: true\n"
        "ORCA:\n"
        "  EXEFOLDER: null\n"
        "PYSCF:\n"
        "  LOCAL_RUN: true\n"
        "XTB:\n"
        "  LOCAL_RUN: true\n"
    )
    monkeypatch.setenv("CHEMSMART_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CHEMSMART_AGENT_SERVER", "local")

    declared = dict(live_session._declared_server_programs())
    assert declared == {"gaussian": "", "orca": ""}

    by_program = {
        item["program"]: item
        for item in live_session._observe_environments()[2]
        if item.get("record_kind") == "program_environment"
        and item.get("engine") == "cpu"
    }
    assert by_program["gaussian"]["status"] == "misconfigured"
    assert by_program["orca"]["status"] == "misconfigured"


def test_a_program_asked_to_run_without_its_folder_says_which_key_is_missing(
    tmp_path,
):
    """``None input.com`` is not an error message."""

    from chemsmart.settings.executable import (
        GaussianExecutable,
        ORCAExecutable,
    )

    profile = tmp_path / "site.yaml"
    profile.write_text(
        "SERVER:\n  SCHEDULER: SLURM\n"
        "GAUSSIAN:\n  EXEFOLDER: null\n"
        "ORCA:\n  EXEFOLDER: null\n"
    )
    for executable_class in (GaussianExecutable, ORCAExecutable):
        executable = executable_class.from_servername(str(profile))
        with pytest.raises(FileNotFoundError, match="EXEFOLDER"):
            executable.get_executable()
