"""Job model for xTB command-line calculations."""

from __future__ import annotations

import logging
import os

from chemsmart.io.molecules.structure import Molecule
from chemsmart.jobs.job import Job
from chemsmart.jobs.xtb.settings import XTBJobSettings

logger = logging.getLogger(__name__)


class XTBJob(Job):
    """Base xTB job whose input artifact is an XYZ geometry."""

    PROGRAM = "xtb"

    def __init__(
        self,
        molecule,
        settings=None,
        label=None,
        jobrunner=None,
        **kwargs,
    ):
        if not isinstance(molecule, Molecule):
            raise ValueError("xTB jobs require a Molecule instance.")
        if not isinstance(settings, XTBJobSettings):
            raise ValueError("xTB jobs require XTBJobSettings.")
        label = label or molecule.get_chemical_formula(empirical=True)
        super().__init__(
            molecule=molecule.copy(),
            label=label,
            jobrunner=jobrunner,
            **kwargs,
        )
        self.settings = settings.copy()

    @classmethod
    def settings_class(cls):
        return XTBJobSettings

    @property
    def xyzfile(self):
        return os.path.join(self.folder, f"{self.label}.xyz")

    @property
    def inputfile(self):
        return self.xyzfile

    @property
    def outputfile(self):
        return os.path.join(self.folder, f"{self.label}.out")

    @property
    def errfile(self):
        return os.path.join(self.folder, f"{self.label}.err")

    def _backup_files(self, **kwargs):
        folder = self._create_backup_folder_name()
        for path in (self.xyzfile, self.outputfile, self.errfile):
            self.backup_file(path, folder=folder, **kwargs)

    def _output(self):
        """Return minimal completion evidence without importing old parsers."""
        if not os.path.isfile(self.outputfile):
            return None
        return _XTBCompletion(self.outputfile)

    def _run(self, **kwargs):
        self.jobrunner.run(self, **kwargs)


class _XTBCompletion:
    def __init__(self, outputfile):
        self.outputfile = outputfile

    @property
    def normal_termination(self):
        with open(self.outputfile, encoding="utf-8", errors="replace") as handle:
            tail = handle.read()[-16384:].lower()
        return "finished run" in tail or "normal termination of xtb" in tail

    @property
    def optimized_structure(self):
        return None

    @property
    def all_structures(self):
        return []
