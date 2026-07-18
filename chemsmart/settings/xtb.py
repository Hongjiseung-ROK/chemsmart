"""Project YAML adapter for xTB jobs."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from chemsmart.jobs.xtb.settings import XTBJobSettings
from chemsmart.settings.user import ChemsmartUserSettings


class XTBProjectSettings:
    """Three-leaf xTB settings loaded from user or bundled YAML."""

    def __init__(self, sp_settings, opt_settings, hess_settings, name="yaml"):
        self._sp_settings = sp_settings
        self._opt_settings = opt_settings
        self._hess_settings = hess_settings
        self.PROJECT_NAME = name

    def sp_settings(self):
        return self._sp_settings.copy()

    def opt_settings(self):
        return self._opt_settings.copy()

    def hess_settings(self):
        return self._hess_settings.copy()

    @classmethod
    def from_project(cls, project):
        if not str(project or "").strip():
            raise FileNotFoundError("xTB jobs require -p/--project.")
        name = Path(str(project)).stem
        workspace_path = (
            Path.cwd() / ".chemsmart" / "xtb" / f"{name}.yaml"
        ).resolve()
        user_path = Path(ChemsmartUserSettings().user_xtb_settings_dir) / (
            f"{name}.yaml"
        )
        packaged_path = (
            Path(__file__).resolve().parent
            / "templates"
            / ".chemsmart"
            / "xtb"
            / f"{name}.yaml"
        )
        for path in (workspace_path, user_path, packaged_path):
            if path.is_file():
                return cls.from_yaml(path)
        raise FileNotFoundError(
            f"No xTB project settings found for {project!r}. Place a YAML "
            f"file in {user_path.parent}."
        )

    @classmethod
    def from_yaml(cls, filename):
        path = Path(filename).expanduser().resolve()
        with path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}

        def settings(jobtype):
            values = dict(payload.get(jobtype) or {})
            # The selected CLI leaf owns the calculation type. Project YAML
            # may tune it, but must never redirect ``sp`` into ``hess``/``opt``.
            values["jobtype"] = jobtype
            return XTBJobSettings.from_dict(values)

        return cls(
            sp_settings=settings("sp"),
            opt_settings=settings("opt"),
            hess_settings=settings("hess"),
            name=os.path.basename(path).removesuffix(".yaml"),
        )
