"""Settings shared by the xTB command-line jobs."""

from __future__ import annotations

import copy
XTB_METHODS = ("gfn0", "gfn1", "gfn2", "gfnff")
XTB_OPT_LEVELS = (
    "crude",
    "sloppy",
    "loose",
    "lax",
    "normal",
    "tight",
    "vtight",
    "extreme",
)
XTB_JOB_TYPES = ("sp", "opt", "hess")
XTB_SOLVENT_MODELS = ("gbsa", "alpb", "cosmo", "tmcosmo", "cpcmx")


class XTBJobSettings:
    """Small, serializable settings object for xTB input generation."""

    def __init__(
        self,
        gfn_version="gfn2",
        optimization_level="vtight",
        charge=0,
        multiplicity=1,
        jobtype=None,
        title=None,
        grad=False,
        solvent_model=None,
        solvent_id=None,
        **kwargs,
    ):
        if kwargs:
            unknown = ", ".join(sorted(kwargs))
            raise ValueError(f"Unknown xTB project setting(s): {unknown}.")
        self.gfn_version = _lower(gfn_version)
        self.optimization_level = _lower(optimization_level)
        self.charge = charge
        self.multiplicity = multiplicity
        self.jobtype = _lower(jobtype)
        self.title = title
        self.grad = bool(grad)
        self.solvent_model = _lower(solvent_model)
        self.solvent_id = _lower(solvent_id)
        if (self.solvent_model is None) != (self.solvent_id is None):
            raise ValueError(
                "xTB solvation requires both solvent_model and solvent_id."
            )
        self._require_known(self.gfn_version, XTB_METHODS, "GFN version")
        self._require_known(
            self.optimization_level,
            XTB_OPT_LEVELS,
            "optimization level",
        )
        self._require_known(self.jobtype, XTB_JOB_TYPES, "job type")
        self._require_known(
            self.solvent_model,
            XTB_SOLVENT_MODELS,
            "solvent model",
        )

    @staticmethod
    def _require_known(value, known_values, label):
        if value is not None and value not in known_values:
            allowed = ", ".join(known_values)
            raise ValueError(
                f"Unknown xTB {label} {value!r}; expected one of: {allowed}."
            )

    @classmethod
    def default(cls):
        return cls()

    @classmethod
    def from_dict(cls, settings_dict):
        return cls(**settings_dict)

    def copy(self):
        return copy.deepcopy(self)

    def merge(
        self,
        other,
        keywords=("charge", "multiplicity", "title"),
        merge_all=False,
    ):
        source = other if isinstance(other, dict) else other.__dict__
        selected = dict(source)
        if not merge_all and keywords is not None:
            selected = {
                key: source[key]
                for key in keywords
                if key in source and source[key] is not None
            }
        merged = self.__dict__.copy()
        merged.update(selected)
        return type(self)(**merged)

    @classmethod
    def from_filepath(cls, filepath, **kwargs):
        """Reuse charge/spin metadata when importing Gaussian or ORCA files."""
        del kwargs
        lower = str(filepath).lower()
        if lower.endswith((".com", ".gjf")):
            from chemsmart.io.gaussian.input import Gaussian16Input

            parsed = Gaussian16Input(filename=filepath).read_settings()
        elif lower.endswith(".log"):
            from chemsmart.io.gaussian.output import Gaussian16Output

            parsed = Gaussian16Output(filename=filepath).read_settings()
        elif lower.endswith(".inp"):
            from chemsmart.io.orca.input import ORCAInput

            parsed = ORCAInput(filename=filepath).read_settings()
        elif lower.endswith(".out"):
            from chemsmart.io.orca.output import ORCAOutput

            parsed = ORCAOutput(filename=filepath).read_settings()
        else:
            return cls.default()
        return cls.default().merge(
            parsed,
            keywords=("charge", "multiplicity", "title"),
        )

    def __eq__(self, other):
        if type(self) is not type(other):
            return NotImplemented
        return self.__dict__ == other.__dict__


def _lower(value):
    return value.lower() if isinstance(value, str) else value
