"""Real and fake xTB job runners."""

from __future__ import annotations

from contextlib import suppress
from functools import lru_cache
from glob import glob
import logging
import os
import shlex
from shutil import copy
import subprocess

from chemsmart.jobs.runner import JobRunner
from chemsmart.settings.executable import XTBExecutable

logger = logging.getLogger(__name__)


class XTBJobRunner(JobRunner):
    """Run xTB using one command renderer shared by real and fake paths."""

    JOBTYPES = ["xtbopt", "xtbsp", "xtbhess"]
    PROGRAM = "xtb"
    FAKE = False
    SCRATCH = True

    def __init__(self, server, scratch=None, fake=False, **kwargs):
        if scratch is None:
            scratch = self.SCRATCH
        super().__init__(server=server, scratch=scratch, fake=fake, **kwargs)

    @property
    @lru_cache(maxsize=12)
    def executable(self):
        return XTBExecutable.from_servername(servername=self.server.name)

    def _prerun(self, job):
        os.makedirs(job.folder, exist_ok=True)
        self.job_outputfile = os.path.abspath(job.outputfile)
        if self.scratch and self.scratch_dir:
            self._set_up_variables_in_scratch(job)
        else:
            self._set_up_variables_in_job_directory(job)
        if self.executable.local_run is not None:
            job.local = self.executable.local_run

    def _set_up_variables_in_scratch(self, job):
        self.running_directory = os.path.join(self.scratch_dir, job.label)
        os.makedirs(self.running_directory, exist_ok=True)
        self.job_xyzfile = os.path.abspath(
            os.path.join(self.running_directory, f"{job.label}.xyz")
        )
        self.job_errfile = os.path.abspath(job.errfile)

    def _set_up_variables_in_job_directory(self, job):
        self.running_directory = job.folder
        self.job_xyzfile = os.path.abspath(job.xyzfile)
        self.job_outputfile = os.path.abspath(job.outputfile)
        self.job_errfile = os.path.abspath(job.errfile)

    def _write_input(self, job):
        job.molecule.write_xyz(self.job_xyzfile, mode="w")

    def _get_command(self, job):
        executable = self.executable.get_executable()
        if not executable:
            executable = "xtb"
        return [executable, self.job_xyzfile, *self._settings_args(job.settings)]

    @staticmethod
    def _settings_args(settings):
        args: list[str] = []
        if settings.gfn_version == "gfnff":
            args.append("--gfnff")
        elif settings.gfn_version and settings.gfn_version[-1:].isdigit():
            args.extend(("--gfn", settings.gfn_version[-1]))
        elif settings.gfn_version:
            args.append(f"--{settings.gfn_version}")

        if settings.jobtype == "opt":
            args.extend(("--opt", settings.optimization_level))
        elif settings.jobtype == "hess":
            args.append("--hess")
        elif settings.jobtype != "sp":
            raise ValueError(f"Unsupported xTB job type: {settings.jobtype}")

        args.extend(("--chrg", str(settings.charge)))
        args.extend(("--uhf", str(settings.multiplicity - 1)))
        if settings.solvent_model and settings.solvent_id:
            args.extend((f"--{settings.solvent_model}", settings.solvent_id))
        if settings.grad:
            args.append("--grad")
        return args

    def _create_process(self, job, command, env):
        del job
        with (
            open(self.job_outputfile, "w", encoding="utf-8") as out,
            open(self.job_errfile, "w", encoding="utf-8") as err,
        ):
            return subprocess.Popen(
                command,
                stdout=out,
                stderr=err,
                env=env,
                cwd=self.running_directory,
            )

    def _postrun(self, job, **kwargs):
        del kwargs
        if not self.scratch:
            return
        for filepath in glob(os.path.join(self.running_directory, "*")):
            destination = os.path.join(job.folder, os.path.basename(filepath))
            if os.path.abspath(filepath) == os.path.abspath(destination):
                continue
            with suppress(IsADirectoryError):
                copy(filepath, job.folder)


class FakeXTBJobRunner(XTBJobRunner):
    """Generate xTB artifacts without invoking an xTB executable."""

    FAKE = True

    def __init__(self, server, scratch=None, fake=True, **kwargs):
        super().__init__(server=server, scratch=scratch, fake=fake, **kwargs)

    @property
    @lru_cache(maxsize=12)
    def executable(self):
        return XTBExecutable(executable_folder=None, local_run=True)

    def run(self, job, **kwargs):
        del kwargs
        self._prerun(job)
        self._append_suffix_to_job_label(job, "_fake")
        if not self.scratch:
            self._set_up_variables_in_job_directory(job)
        else:
            self.job_xyzfile = os.path.join(
                self.running_directory,
                f"{job.label}.xyz",
            )
            self.job_outputfile = os.path.abspath(
                os.path.join(self.running_directory, f"{job.label}.out")
            )
            self.job_errfile = os.path.abspath(
                os.path.join(self.running_directory, f"{job.label}.err")
            )
        self._write_input(job)
        command = self._get_command(job)
        with open(self.job_outputfile, "w", encoding="utf-8") as out:
            out.write("* xtb version 0.0.0 (Fake)\n")
            out.write(f"program call : {shlex.join(command)}\n")
            out.write("* finished run (fake xtb)\n")
        with open(self.job_errfile, "w", encoding="utf-8"):
            pass
        self._postrun(job)
        self._postrun_cleanup(job)
        return 0
