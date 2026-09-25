"""A CLI option the user never typed must not overwrite project YAML.

FUNDAMENTAL: project YAML is where the computational-chemistry rationale
lives, and the CLI is how a human or an agent drives it. Every ``jobtype``
command therefore reads its project's settings first and applies an option
only when the caller actually supplied one -- the pattern its own comment
states as "only update value if user explicitly specifies a value for the
attribute to preserve project defaults".

That pattern is expressed as ``if option is not None:`` over a Click option
whose default is ``None``. A non-``None`` default silently defeats it: the
guard is always true and the flag nobody passed wins.

po3-r17 (2026-09-11) lost a whole 12-hour window to exactly that. The
session declared ``recalc_hess: 999`` in project YAML so a saddle search
could not become an unbounded chain of numerical second derivatives; the
written ORCA input carried ``5``; the preview validator correctly reported
``expected 999, observed 5`` and the workflow was refused. ``recalc_hess``
was not the only option in the CLI shaped that way.

The invariant is held by
``tests/agent/test_a_stated_setting_reaches_the_input.py``, which reads
the defaults Click passes. The scan that stood here read the callbacks'
Python signatures instead, which Click never consults, and skipped
``False``: it passed over Gaussian's IRC options defaulting to 512, 128,
20 and 6 (every Gaussian IRC through R10 Q28 ran maxpoints=512) and over
the fourteen options R10 Q31 found (ORCA ``--tssearch-type optts``, five
ORCA IRC booleans, ``forces``). This file keeps the live loss.
"""

import pytest


@pytest.mark.capability("program_jobtype:orca:cpu:ts")
def test_a_project_recalc_hess_reaches_the_job(
    tmp_path, orca_jobrunner_no_scratch
):
    """The live loss, driven through the real command.

    Both halves matter: the project's declared value must survive, and a
    project that declares nothing must still have its OptTS written with
    Recalc_Hess 5, so restoring project authority changes no existing
    input. (The 5 is the writer's for an OptTS since R10 Q31: a ScanTS is
    written with no recalculation, which ORCA 6.1.1 cannot run.)
    """

    from unittest.mock import MagicMock, patch

    import yaml
    from click.testing import CliRunner

    from chemsmart.cli.orca.orca import orca as orca_cli

    molecule = tmp_path / "h2.xyz"
    molecule.write_text("2\nh2\nH 0.0 0.0 0.0\nH 0.0 0.0 0.74\n")
    projects = tmp_path / "project_yaml"
    projects.mkdir()

    def run(name, declared):
        body = {"ts": {"functional": "b3lyp", "basis": "def2-svp"}}
        body["ts"].update(declared)
        (projects / f"{name}.yaml").write_text(
            yaml.safe_dump(body), encoding="utf-8"
        )
        runner = CliRunner()
        with patch("chemsmart.jobs.orca.ts.ORCATSJob") as job:
            job.return_value = MagicMock()
            result = runner.invoke(
                orca_cli,
                [
                    "-p",
                    str(projects / name),
                    "-f",
                    str(molecule),
                    "-c",
                    "0",
                    "-m",
                    "1",
                    "ts",
                ],
                obj={},
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        return job.call_args.kwargs["settings"]

    declared = run("declares", {"recalc_hess": 999, "geom_maxiter": 300})
    assert declared.recalc_hess == 999, (
        "the project declared recalc_hess 999 and an option nobody typed "
        f"overwrote it with {declared.recalc_hess}"
    )
    assert declared.geom_maxiter == 300

    silent = run("silent", {})
    assert silent.recalc_hess is None, (
        "a project that declares nothing states no recalculation, not "
        f"{silent.recalc_hess}"
    )

    from chemsmart.io.molecules.structure import Molecule
    from chemsmart.jobs.orca.ts import ORCATSJob
    from chemsmart.jobs.orca.writer import ORCAInputWriter

    job = ORCATSJob(
        molecule=Molecule.from_filepath(str(molecule)),
        settings=silent,
        label="silent_ts",
        jobrunner=orca_jobrunner_no_scratch,
    )
    ORCAInputWriter(job=job).write(target_directory=str(tmp_path))
    written = (tmp_path / "silent_ts.inp").read_text(encoding="utf-8")
    assert (
        "Recalc_Hess 5" in written
    ), "a silent project's OptTS must still be written with Recalc_Hess 5"
