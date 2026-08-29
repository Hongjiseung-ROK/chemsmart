"""Every result scanner drops a non-normally-terminated output before it
can be named, so the session that most needed to read a failure could
not even ask about it: a live relaxed scan died at step 2 of 12 and the
next session's context held no trace of the file. The failure is now
admitted as its own artifact class, ``failed_result``, carrying the
typed terminal facts a revision needs -- and nothing else: the class
matches no reader's artifact_kind, so quantity extraction and geometry
handoff stay refused by construction.
"""

from pathlib import Path

from chemsmart.agent.live_session import _scan_failed_result_artifacts


def _truncated_scan(tmp_path: Path) -> Path:
    target = tmp_path / "fluoro_scan_scan.out"
    target.write_text(
        "\n".join(
            (
                "                                 * O   R   C   A *",
                "|  1> ! Opt B3LYP def2-SVP",
                "|  5> %geom",
                "|  6>   Scan",
                "|  7>     D 3 2 1 0 = 40.0, -125.0, 12",
                "|  8>   end",
                "|  9> end",
                "* xyz 0 1",
                "Total Charge           Charge          ....    0",
                " Multiplicity           Mult            ....    1",
                "        Dihedral (  3,   2,   1,   0):   "
                "range=  40.00 .. -125.00 steps = 12",
                "         *               RELAXED SURFACE SCAN STEP   1",
                "         *** THE OPTIMIZATION HAS CONVERGED ***",
                "         *               RELAXED SURFACE SCAN STEP   2",
                "       The optimization did not converge but reached the"
                " maximum number of",
                "       optimization cycles.",
                "ERROR (SHARK): Failed to read input file"
                " (/scratch/job.SHARKINP.tmp)",
                "ORCA finished by error termination in PROPERTIES",
            )
        )
    )
    return target


def test_the_truncated_scan_is_admitted_with_its_terminal_facts(tmp_path):
    _truncated_scan(tmp_path)
    observations = _scan_failed_result_artifacts(tmp_path)
    assert len(observations) == 1
    record = observations[0].public_record()
    assert record["artifact_class"] == "failed_result"
    assert record["program"] == "orca"
    assert record["jobtype"] == "scan"
    assert record["normal_termination"] is False
    assert record["converged"] is False
    assert record["scan_steps_reached"] == 2
    assert record["scan_steps_planned"] == 12
    assert record["native_failure_class"]
    assert "not admissible for quantity extraction" in (
        record["admissibility"]
    )
    joined = " ".join(record["engine_lines"])
    assert "SHARK" in joined
    assert "/scratch" not in joined, "engine lines must arrive redacted"


def test_a_normally_terminated_output_is_not_a_failed_result(tmp_path):
    healthy = tmp_path / "water_opt.out"
    healthy.write_text(
        "\n".join(
            (
                "                                 * O   R   C   A *",
                "*** THE OPTIMIZATION HAS CONVERGED ***",
                "FINAL SINGLE POINT ENERGY       -76.000000000000",
                "                    ***ORCA TERMINATED NORMALLY***",
            )
        )
    )
    assert _scan_failed_result_artifacts(tmp_path) == ()


def test_arbitrary_text_is_not_sniffed_as_a_program(tmp_path):
    (tmp_path / "notes.out").write_text(
        "meeting notes: the run failed, ask for more cores\n"
    )
    assert _scan_failed_result_artifacts(tmp_path) == ()
