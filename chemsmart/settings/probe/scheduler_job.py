"""Scheduler job identity and state: what a submission said, what the
scheduler still knows.

``sbatch`` answers a submission with one line naming the job; ``scontrol``
and ``squeue`` answer for a job the scheduler still remembers, which on a
site without accounting storage is only until ``MinJobAge`` has passed.
Every parser here is a pure function over ``(returncode, stdout, stderr)``
in the probe convention, so scheduler behaviour is provable from canned
real outputs without a cluster. A job the scheduler no longer knows is
reported as unknown, never guessed at: after that window the run's own
durable record is the completion evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .units import ProbeUnitError

#: Scheduler states after which a job will not run again.
TERMINAL_JOB_STATES = frozenset(
    {
        "BOOT_FAIL",
        "CANCELLED",
        "COMPLETED",
        "DEADLINE",
        "FAILED",
        "NODE_FAIL",
        "OUT_OF_MEMORY",
        "PREEMPTED",
        "TIMEOUT",
    }
)

#: job id|state|time used|submit|start|end -- pinned, never human default.
_SQUEUE_FORMAT = "%i|%T|%M|%V|%S|%e"

_SBATCH_LINE = re.compile(r"Submitted batch job (\d+)")
_BARE_JOB_ID = re.compile(r"^\d+(?:\.\S+)?$")


@dataclass(frozen=True)
class SchedulerJobStateV1:
    """What the scheduler currently says about one job.

    ``known`` is False when the scheduler no longer has the job at all;
    every other field is then empty, and the caller must read the run's
    own record instead of inferring an outcome from absence.
    """

    job_id: str
    known: bool
    state: str = ""
    exit_code: str = ""
    submit_time: str = ""
    start_time: str = ""
    end_time: str = ""
    run_seconds: int | None = None

    @property
    def terminal(self) -> bool:
        return self.known and self.state.split()[0] in TERMINAL_JOB_STATES


def parse_submission(returncode: int, stdout: str, stderr: str) -> str:
    """The job id a submission command printed.

    Accepts ``Submitted batch job N`` (sbatch), a bare ``N`` (sbatch
    ``--parsable``) and ``N.server`` (qsub). A submission that exited
    nonzero or printed no id is refused with the scheduler's own words.
    """

    if returncode != 0:
        raise ProbeUnitError(
            f"submission exited {returncode}: {stderr.strip() or 'no output'}"
        )
    match = _SBATCH_LINE.search(stdout)
    if match:
        return match.group(1)
    for line in stdout.splitlines():
        token = line.strip().split(";")[0]
        if _BARE_JOB_ID.match(token):
            return token
    raise ProbeUnitError(
        "submission printed no job id: "
        f"{stdout.strip() or stderr.strip() or 'no output'}"
    )


def scontrol_job_command(job_id: str) -> tuple[str, ...]:
    return ("scontrol", "show", "job", str(job_id))


def squeue_job_command(job_id: str) -> tuple[str, ...]:
    return (
        "squeue",
        "-h",
        "-t",
        "all",
        "-j",
        str(job_id),
        "-o",
        _SQUEUE_FORMAT,
    )


def parse_elapsed_seconds(text: str) -> int | None:
    """Seconds from a Slurm elapsed field: ``[D-]HH:MM:SS`` or the shortened
    ``M:SS`` / ``H:MM:SS`` that ``squeue %M`` prints."""

    cleaned = text.strip()
    if not cleaned or cleaned in {"N/A", "INVALID", "UNLIMITED"}:
        return None
    days = 0
    if "-" in cleaned:
        day_text, cleaned = cleaned.split("-", 1)
        days = int(day_text)
    parts = cleaned.split(":")
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
    elif len(numbers) == 2:
        hours, (minutes, seconds) = 0, numbers
    elif len(numbers) == 1:
        hours, minutes, seconds = 0, 0, numbers[0]
    else:
        return None
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


def _unknown(job_id: str) -> SchedulerJobStateV1:
    return SchedulerJobStateV1(job_id=str(job_id), known=False)


def parse_scontrol_job(
    returncode: int, stdout: str, stderr: str, *, job_id: str
) -> SchedulerJobStateV1:
    """State from ``scontrol show job``; unknown when the scheduler has
    forgotten the job (``Invalid job id specified``)."""

    if returncode != 0 or "Invalid job id" in stderr:
        return _unknown(job_id)
    fields: dict[str, str] = {}
    for token in stdout.split():
        key, sep, value = token.partition("=")
        if sep and key not in fields:
            fields[key] = value
    if fields.get("JobId", "") != str(job_id):
        return _unknown(job_id)
    return SchedulerJobStateV1(
        job_id=str(job_id),
        known=True,
        state=fields.get("JobState", ""),
        exit_code=fields.get("ExitCode", ""),
        submit_time=fields.get("SubmitTime", ""),
        start_time=fields.get("StartTime", ""),
        end_time=fields.get("EndTime", ""),
        run_seconds=parse_elapsed_seconds(fields.get("RunTime", "")),
    )


def parse_squeue_job(
    returncode: int, stdout: str, stderr: str, *, job_id: str
) -> SchedulerJobStateV1:
    """State from ``squeue -t all`` in the pinned format; unknown when the
    job is absent, whatever the reason."""

    if returncode != 0:
        return _unknown(job_id)
    for line in stdout.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 6 or parts[0] != str(job_id):
            continue
        return SchedulerJobStateV1(
            job_id=str(job_id),
            known=True,
            state=parts[1],
            submit_time=parts[3],
            start_time=parts[4],
            end_time=parts[5],
            run_seconds=parse_elapsed_seconds(parts[2]),
        )
    return _unknown(job_id)


__all__ = [
    "TERMINAL_JOB_STATES",
    "SchedulerJobStateV1",
    "parse_elapsed_seconds",
    "parse_scontrol_job",
    "parse_squeue_job",
    "parse_submission",
    "scontrol_job_command",
    "squeue_job_command",
]
