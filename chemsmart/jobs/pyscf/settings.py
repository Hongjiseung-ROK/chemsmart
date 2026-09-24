"""PySCF job settings.

``PySCFJobSettings`` subclasses ``MolecularJobSettings`` so that the project
YAML dialect, the ``keywords`` merge whitelist, and ``modify_solvent`` behave
exactly as they do for Gaussian and ORCA. It reuses the existing option
vocabulary (``functional``, ``ab_initio``, ``basis``, ``aux_basis``,
``defgrid``, ``scf_tol``, ``solvent_model``, ``solvent_id``) rather than
inventing PySCF-specific names, so one normalised vocabulary spans programs.

Fields the base class carries but PySCF cannot honour are listed in
``UNSUPPORTED`` and rejected by :meth:`validate`. A project YAML asking for a
genecp basis must not silently produce a plain def2-SVP calculation.
"""

import logging
import math
from numbers import Integral, Real

from chemsmart.jobs.settings import (
    MolecularJobSettings,
    canonical_functional_literal,
    functional_resolution_record,
)

logger = logging.getLogger(__name__)

#: Solvent models accepted by ``solvent_model``, mapped to the PySCF call and
#: the ``with_solvent.method`` string. Verified against pyscf 2.14.0: the PCM
#: methods are exactly C-PCM, COSMO, IEF-PCM and SS(V)PE.
PYSCF_SOLVENT_MODELS = {
    "pcm": ("PCM", "IEF-PCM"),
    "iefpcm": ("PCM", "IEF-PCM"),
    "cpcm": ("PCM", "C-PCM"),
    "cosmo": ("PCM", "COSMO"),
    "ssvpe": ("PCM", "SS(V)PE"),
    "smd": ("SMD", None),
}

#: ``defgrid`` levels mapped to ``mf.grids.atom_grid`` (radial, angular).
#: Chosen to bracket ORCA's DEFGRID1/2/3 in cost, not to reproduce its exact
#: quadrature, which is not publicly specified.
PYSCF_DEFGRIDS = {
    "defgrid1": (50, 194),
    "defgrid2": (75, 302),
    "defgrid3": (99, 590),
}

#: Geometry-optimisation backends. ``geometric`` is the default because it is
#: what ``gpu4pyscf/drivers/opt_driver.py`` calls and what PySCF's own
#: ``[geomopt]`` extra installs first.
PYSCF_OPT_SOLVERS = ("geometric", "berny", "ase")

#: Execution engines. ``gpu`` routes through gpu4pyscf via ``.to_gpu()``.
PYSCF_ENGINES = ("cpu", "gpu")
PYSCF_JOBTYPES = ("hess", "irc", "opt", "sp", "td", "ts")
#: Which branch of the steepest-descent path an ``irc`` walks from the
#: saddle it was handed. The words have no chemical meaning of their own:
#: the transition vector's sign is fixed by a host rule (the first
#: component within 1e-3 of the largest is positive) and ``forward`` is
#: the branch whose first step has a positive projection on it, so two
#: runs from one geometry walk opposite branches whatever sign the
#: eigensolver returned. Which minimum each reaches is read from the
#: path, never from the word.
PYSCF_IRC_DIRECTIONS = ("backward", "forward")
PYSCF_RESPONSE_METHODS = ("tda", "tddft")
#: How a Hessian's second derivative is obtained. ``analytic`` is
#: PySCF's own second derivative and exists for HF and DFT references
#: only; ``finite_difference`` differences the analytic gradient of
#: whatever surface the job is on, which is the only route to the
#: curvature of an excited root here. The driver would difference a
#: correlated gradient the same way; ``validate()`` still refuses a
#: correlated ``hess``, because that path has never been exercised.
#: Unset resolves to the analytic derivative where PySCF has one.
PYSCF_HESSIAN_DERIVATIVES = ("analytic", "finite_difference")
#: Job types whose own surface can be an excited root: the optimisation
#: that walks it and the Hessian that differentiates it twice. A ``td``
#: is not one of them -- its geometry and total energy are the
#: reference's, and its roots are values computed on that surface.
PYSCF_EXCITED_SURFACE_JOBTYPES = frozenset({"hess", "opt"})
#: The order driver stages run in, declared once. A surface is built
#: before anything differentiates it: the correlated method and the
#: response both come before the Hessian that measures their curvature.
#: Every tuple archived under contract v5 -- scf,opt,td; scf,opt,corr;
#: scf,corr; scf,td; scf,hess -- is unchanged by this ordering. An IRC
#: walks from the supplied geometry and ends where its branch ended, so
#: it sits where an optimisation does and composes with nothing after it;
#: a saddle search is the same kind of thing and sits beside it.
PYSCF_STAGE_ORDER = ("scf", "opt", "ts", "irc", "corr", "td", "hess")
#: Stages that move the geometry they were handed: an optimisation, a
#: saddle search and an IRC branch. ``results/positions`` is where they
#: ended, all are bounded by geomeTRIC's step ceiling, and none is held
#: to its input geometry.
PYSCF_MOVING_STAGES = ("irc", "opt", "ts")
#: Stages whose first act can be PySCF's analytic Hessian of the job's
#: own surface: a Hessian node, an IRC, which takes it at its start, and
#: a saddle search, whose partitioned rational-function step needs the
#: curvature at the seed to know which mode to climb.  The references
#: PySCF 2.14 cannot differentiate twice are refused for all three
#: before the engine is spent.
PYSCF_ANALYTIC_HESSIAN_STAGES = ("hess", "irc", "ts")
#: The displacement a finite-difference Hessian steps by, in Angstrom:
#: the unit the geometry is carried in and the one a scientist reads.
#: ORCA's NumFreq default is 0.005 Bohr, a different convention, and the
#: two are compared on the record rather than conflated in a name.
PYSCF_FD_STEP_ANGSTROM = 0.005
#: The orbital-rotation spaces a PySCF stability analysis searches, named
#: per reference family in PySCF 2.14's own words (``scf/stability.py``
#: ``dump_status``).  ``internal`` asks whether the converged solution is a
#: minimum within the space it was optimised in; ``external`` asks whether
#: a lower solution exists in a *larger* space, and which larger space
#: depends on the reference -- so a bare "externally unstable" is ambiguous
#: across reference classes and the record names the space.  The
#: real -> complex question PySCF also computes inside ``rhf_external`` and
#: ``uhf_external`` is not in this table: those functions return only the
#: R->U / U->G flag, so its answer is recorded under its own question from
#: what PySCF's analysis says (``PYSCF_STABILITY_PRINTED_KINDS``) rather
#: than folded into the returned boolean.
PYSCF_STABILITY_SPACES = {
    "rhf": {"internal": "internal", "external": "RHF/RKS -> UHF/UKS"},
    "rks": {"internal": "internal", "external": "RHF/RKS -> UHF/UKS"},
    "uhf": {"internal": "internal", "external": "UHF/UKS -> GHF/GKS"},
    "uks": {"internal": "internal", "external": "UHF/UKS -> GHF/GKS"},
    # ``pyscf.scf.stability.rohf_external`` raises NotImplementedError in
    # 2.14.0, so an ROHF/ROKS reference has no external answer at all.
    "rohf": {"internal": "internal", "external": None},
    "roks": {"internal": "internal", "external": None},
}

#: The rotation space of the question PySCF solves inside ``rhf_external``
#: and ``uhf_external`` and does not return.  Artifacts written before the
#: driver listened to the analysis record it as not determined, by name;
#: later ones record PySCF's answer to it under ``real_to_complex``.
PYSCF_STABILITY_UNRETURNED_SPACE = "real -> complex"

#: What PySCF's stability analysis says, in its own words
#: (``scf/stability.py``, 2.14): every Davidson it runs logs
#: ``<reference>_<kind>: lowest eigs of H = <array>`` -- the lowest roots of
#: the orbital Hessian for that rotation, in Eh, in PySCF's own
#: normalisation, and PySCF calls the reference unstable when the lowest is
#: below ``PYSCF_STABILITY_THRESHOLD`` -- and ``dump_status`` then notes
#: "wavefunction has an <space> instability" or "wavefunction is stable in
#: the <space> stability analysis".  ``rhf_external`` and ``uhf_external``
#: each run two of these, real -> complex first, so the ``real2complex``
#: kind is the question the returned flag never carried.  Keyed kind ->
#: the question this host records; the driver hears the analysis through
#: this table, and the reader reads an older run's log through the same one.
PYSCF_STABILITY_PRINTED_KINDS = {
    "internal": "internal",
    "real2complex": "real_to_complex",
    "external": "external",
}

#: PySCF's own instability threshold on the lowest eigenvalue, in Eh
#: (``stable = not (e < -1e-5)`` in every analysis of ``scf/stability.py``):
#: an eigenvalue between it and zero is PySCF's "stable".
PYSCF_STABILITY_THRESHOLD = -1e-5

#: Excitation manifolds.  A closed-shell reference asks for singlet or
#: triplet excitations, or both (``singlet_triplet``: the driver solves the
#: singlet and the triplet response on the one converged reference, as
#: ORCA's ``Triplets true`` and Gaussian's ``50-50`` do, ``nstates`` roots
#: of each); an open-shell (UKS) reference has one spin-conserving manifold
#: that PySCF labels neither, so it is named for what it is.  The reference
#: decides which names are admissible, by the one rule every program asks
#: (``td_manifold_reference_refusal``).
PYSCF_STATE_MANIFOLDS = (
    "singlet",
    "singlet_triplet",
    "triplet",
    "unrestricted",
)
PYSCF_UNRESTRICTED_MANIFOLD = "unrestricted"
#: The manifold that is two spin blocks, each solved on its own.
PYSCF_TWO_BLOCK_MANIFOLD = "singlet_triplet"
#: ``ab_initio`` values.  ``hf`` is the mean-field reference; the others
#: are correlated single-reference methods computed on an HF reference
#: (PySCF converts an ROHF reference to UHF for them).
PYSCF_AB_INITIO_METHODS = ("hf", "mp2", "ccsd", "ccsd(t)")
PYSCF_CORRELATED_METHODS = ("mp2", "ccsd", "ccsd(t)")
PYSCF_COUPLED_CLUSTER_METHODS = ("ccsd", "ccsd(t)")
#: ``frozen_core: auto`` asks PySCF's own chemical-core rule
#: (``set_frozen(method="auto")``); an integer is an orbital count; unset
#: keeps PySCF's default, which correlates every electron.  ORCA and
#: Gaussian freeze core by default, and that divergence is declared on the
#: cross-program guide rather than silently matched here.
PYSCF_FROZEN_CORE_AUTO = "auto"

#: Functionals for which the perturbative correlation term is not implemented
#: by this v1 mean-field-only backend.  Passing one of these names to
#: ``dft.KS`` can produce a converged energy that contains only the DFT part of
#: the advertised double hybrid, which is scientifically worse than a hard
#: failure.
PYSCF_DOUBLE_HYBRID_MARKERS = (
    "b2plyp",
    "b2gp-plyp",
    "b2gpplyp",
    "pwpb95",
    "pbe0-2",
    "wb97x-2",
    "qidh",
    "-dh",
    "revdsd",
    "dsd",
    "dhdft",
    "xyg3",
    "xygjos",
    "double-hybrid",
)

#: The PySCF spelling of a ChemSmart functional literal whose meaning
#: (``chemsmart.jobs.settings.FUNCTIONAL_IDENTITIES``) needs one.  In PySCF
#: 2.14 the bare ``B3LYP`` alias follows ``__config__.B3LYP_WITH_VWN5``;
#: ``b3lypg`` is the VWN3 (Gaussian) form whatever that switch says, and it
#: is the form the literal ``b3lyp`` names in every program.  The writer
#: spells from this table and the provenance verifier reads the same one.
PYSCF_FUNCTIONAL_NATIVE = {
    "b3lyp": "b3lypg",
    "b3lyp5": "b3lyp5",
    "pbe0": "pbe0",
    "pbe": "pbe",
    "bp86": "bp86",
}

#: Literals PySCF has no libxc spelling for, with the route a refusal names.
PYSCF_FUNCTIONAL_REFUSED = {
    "bp86-pw92": (
        "libxc's P86 is built on the Perdew-Zunger 81 local correlation (the "
        "literal bp86); the Perdew-Wang 92 form is ORCA's BP86 and has no "
        "libxc spelling here. Request bp86, or run bp86-pw92 in ORCA."
    ),
}

#: Literals whose PySCF spelling is announced when it is applied, because
#: the bare name means something else in another program or configuration.
FUNCTIONAL_DIVERGENCES = {
    "b3lyp": (
        "b3lypg",
        "resolved to PySCF's explicit B3LYPG (VWN3/Gaussian convention) so "
        "target-level B3LYP_WITH_VWN5 configuration cannot change the "
        "calculation. Request b3lyp5 explicitly for the VWN5 variant.",
    ),
}


def pyscf_correlated_method(ab_initio):
    """Return the lower-cased correlated method name, or None for HF/DFT."""
    if ab_initio is None:
        return None
    normal = str(ab_initio).strip().lower()
    return normal if normal in PYSCF_CORRELATED_METHODS else None


def pyscf_stages(jobtype, *, ab_initio=None, excited_state_root=None):
    """Return the ordered driver stages a resolved configuration runs.

    Stages are derived from the resolved settings, never from the jobtype
    word alone: an ``opt`` on an excited root runs ``scf, opt, td`` (the
    spectrum is re-evaluated at the reached geometry, so every excited
    quantity belongs to the one structure the artifact carries) and a
    correlated ``sp``/``opt`` appends a ``corr`` stage that computes the
    method's components at the final geometry.  The job classes, the
    driver, preflight and the result validator all call this function.
    """

    normal = str(jobtype or "").strip().lower().replace("pyscf_", "")
    if normal not in PYSCF_JOBTYPES:
        return []
    running = {"scf"}
    if normal == "opt":
        running.add("opt")
    if normal == "irc":
        running.add("irc")
    if normal == "ts":
        running.add("ts")
    if normal == "hess":
        running.add("hess")
    if normal == "td" or excited_state_root is not None:
        running.add("td")
    if pyscf_correlated_method(ab_initio) is not None:
        running.add("corr")
    return [stage for stage in PYSCF_STAGE_ORDER if stage in running]


def describe_functional_resolution(functional=None, *, ab_initio=None):
    """What PySCF is told for a project functional, as a host record.

    Derived from the resolver :attr:`PySCFJobSettings.xc` calls, in the
    record every program's settings module answers.  It is the host's
    alias resolution, not the execution-time libxc materialisation, which
    the result artifact records separately.
    """

    return functional_resolution_record(
        program="pyscf",
        functional=functional,
        ab_initio=ab_initio,
        native=pyscf_native_functional(functional),
        source="chemsmart.jobs.pyscf.settings.resolve_functional",
    )


def pyscf_native_functional(functional):
    """Return the libxc name PySCF is given for a functional literal.

    Pure: the warning belongs to :func:`resolve_functional`, which the
    writer calls, and the provenance verifier compares through this.
    """

    if functional is None:
        return None
    canonical = canonical_functional_literal(functional)
    if canonical in PYSCF_FUNCTIONAL_NATIVE:
        return PYSCF_FUNCTIONAL_NATIVE[canonical]
    return functional


def resolve_functional(functional):
    """Return the libxc functional name for a ChemSmart functional name.

    Warns when the requested name is known to denote different functionals
    in different programs, because such a mismatch is invisible in the
    output but shifts total energies by tens of kcal/mol.
    """
    if functional is None:
        return None
    key = str(functional).strip().lower()
    if key in FUNCTIONAL_DIVERGENCES:
        _resolved, note = FUNCTIONAL_DIVERGENCES[key]
        logger.warning(f"Functional {functional!r}: {note}")
    return pyscf_native_functional(functional)


def is_double_hybrid_functional(functional):
    """Return whether *functional* names a known double-hybrid family."""
    if functional is None:
        return False
    normal = str(functional).strip().lower().replace("_", "-")
    return any(marker in normal for marker in PYSCF_DOUBLE_HYBRID_MARKERS)


class PySCFJobSettings(MolecularJobSettings):
    """Configuration for a PySCF calculation.

    Attributes beyond the shared molecular vocabulary:
        density_fit (bool): Apply ``.density_fit()`` to the mean-field object.
        opt_solver (str): One of ``PYSCF_OPT_SOLVERS``.
        opt_maxsteps (int): Geometry-optimisation step ceiling.
        engine (str): ``cpu`` or ``gpu``; recorded in the results provenance
            so every number states which engine produced it.
        scf_maxiter (int): ``mf.max_cycle``.
    """

    #: Base-class fields PySCF cannot honour. Mapped to the value that means
    #: "unset", so ``validate`` can tell "absent" from "explicitly requested".
    UNSUPPORTED = {
        "semiempirical": None,
        "gen_genecp_file": None,
        "heavy_elements": None,
        "heavy_elements_basis": None,
        "light_elements_basis": None,
        "numfreq": False,
        "additional_route_parameters": None,
        "route_to_be_written": None,
        "modred": None,
        "input_string": None,
        "custom_solvent": None,
        "forces": False,
    }

    _INHERITED_SETTING_NAMES = frozenset(UNSUPPORTED)

    def __init__(
        self,
        ab_initio=None,
        functional=None,
        dispersion=None,
        basis=None,
        aux_basis=None,
        defgrid=None,
        scf_tol=None,
        scf_maxiter=None,
        response_method=None,
        state_manifold=None,
        nstates=None,
        excited_state_root=None,
        td_max_cycle=None,
        frozen_core=None,
        cc_max_cycle=None,
        hessian_derivative=None,
        fd_step_angstrom=None,
        scf_stability=False,
        irc_direction=None,
        charge=None,
        multiplicity=None,
        freq=False,
        density_fit=False,
        opt_solver="geometric",
        opt_maxsteps=100,
        engine="cpu",
        jobtype=None,
        title=None,
        solvent_model=None,
        solvent_id=None,
        **kwargs,
    ):
        # Internal receipt metadata is deliberately private so it does not
        # become an accepted project-YAML setting. The YAML loader derives it
        # from the source artifact after validating the public settings keys.
        project_yaml_digest = kwargs.pop("_project_yaml_digest", None)
        unknown = sorted(set(kwargs).difference(self._INHERITED_SETTING_NAMES))
        if unknown:
            raise ValueError(
                "Unknown PySCF setting(s): "
                f"{', '.join(unknown)}. Refusing fields that would otherwise "
                "be silently ignored."
            )
        super().__init__(
            ab_initio=ab_initio,
            functional=functional,
            dispersion=dispersion,
            basis=basis,
            defgrid=defgrid,
            charge=charge,
            multiplicity=multiplicity,
            freq=freq,
            jobtype=jobtype,
            title=title,
            solvent_model=solvent_model,
            solvent_id=solvent_id,
            **kwargs,
        )
        self.aux_basis = aux_basis
        self.scf_tol = scf_tol
        self.scf_maxiter = scf_maxiter
        self.response_method = response_method
        self.state_manifold = state_manifold
        self.nstates = nstates
        self.excited_state_root = excited_state_root
        self.td_max_cycle = td_max_cycle
        self.frozen_core = frozen_core
        self.cc_max_cycle = cc_max_cycle
        self.hessian_derivative = hessian_derivative
        self.fd_step_angstrom = fd_step_angstrom
        self.scf_stability = scf_stability
        self.irc_direction = irc_direction
        self.density_fit = density_fit
        self.opt_solver = opt_solver
        self.opt_maxsteps = opt_maxsteps
        self.engine = engine
        if project_yaml_digest is not None:
            self._project_yaml_digest = str(project_yaml_digest)

    @classmethod
    def default(cls):
        """Return settings with every field at its unset default."""
        return cls()

    def copy(self):
        import copy as _copy

        return _copy.deepcopy(self)

    @property
    def project_yaml_digest(self):
        """SHA-256 of the project YAML that produced these settings."""
        return getattr(self, "_project_yaml_digest", None)

    def merge(
        self, other, keywords=("charge", "multiplicity"), merge_all=False
    ):
        """Merge ``other`` into a copy of self.

        Mirrors ``ORCAJobSettings.merge``: without ``merge_all`` only the
        names in ``keywords`` cross over. A CLI override whose name was never
        appended to ``keywords`` is dropped here silently, which is the single
        most common bug in this codebase.
        """
        other_dict = other if isinstance(other, dict) else other.__dict__
        if not merge_all and keywords is not None:
            other_dict = {
                k: other_dict[k] for k in keywords if k in other_dict
            }
        merged_dict = self.__dict__.copy()
        merged_dict.update(other_dict)
        return type(self)(**merged_dict)

    @property
    def spin(self):
        """Return PySCF's ``mol.spin`` (= 2S = Nalpha - Nbeta).

        PySCF's ``spin`` is **not** the multiplicity. Passing a multiplicity
        straight into ``mol.spin`` silently computes a different electronic
        state, so this conversion lives in exactly one place.
        """
        if self.multiplicity is None:
            return None
        return int(self.multiplicity) - 1

    @property
    def is_restricted(self):
        """Return whether an R (True) or U (False) reference is implied.

        Derived from multiplicity rather than exposed as a flag, so the
        reference cannot disagree with the requested electronic state.
        """
        return self.multiplicity in (None, 1)

    @property
    def method_name(self):
        """Return the method label used for provenance and the database."""
        if self.ab_initio:
            return str(self.ab_initio).lower()
        if self.functional:
            return str(self.functional).lower()
        return None

    @property
    def correlated_method(self):
        """Return ``mp2``/``ccsd``/``ccsd(t)`` or None for an HF/DFT job."""
        return pyscf_correlated_method(self.ab_initio)

    @property
    def excited_surface(self):
        """Whether the job follows an excited root (an ``opt`` on it)."""
        return self.excited_state_root is not None

    @property
    def response_requested(self):
        """Whether a TDA/TDDFT response stage runs (``td`` or excited opt)."""
        return self.jobtype == "td" or self.excited_surface

    @property
    def stages(self):
        """Return the driver stages these resolved settings run."""
        return pyscf_stages(
            self.jobtype,
            ab_initio=self.ab_initio,
            excited_state_root=self.excited_state_root,
        )

    @property
    def xc(self):
        """Return the libxc functional string, or None for an HF reference.

        Routed through :func:`resolve_functional`, which warns for names
        that denote different functionals in different programs.  Every
        ``ab_initio`` method -- HF and the correlated methods computed on
        an HF reference -- runs without a functional.
        """
        if self.ab_initio:
            return None
        return resolve_functional(self.functional)

    def _check_solvent(self, solvent_model):
        """Reject a solvent model PySCF has no implementation for."""
        if str(solvent_model).lower() not in PYSCF_SOLVENT_MODELS:
            raise ValueError(
                f"Solvent model {solvent_model!r} is not available in PySCF. "
                f"Available models: {sorted(PYSCF_SOLVENT_MODELS)}"
            )

    def unsupported_requests(self):
        """Return ``[(field, value)]`` for every unsupported field that is set.

        Returns rather than raises so a caller can enumerate every problem at
        once instead of discovering them one exception at a time.
        """
        requested = []
        for field, unset in self.UNSUPPORTED.items():
            value = getattr(self, field, unset)
            if value != unset:
                requested.append((field, value))
        return requested

    def validate(self):
        """Raise if the settings request something PySCF cannot deliver.

        Raises:
            ValueError: If an unsupported field is set, or if a supported
                field holds a value outside its allowed set.
        """
        unsupported = self.unsupported_requests()
        if unsupported:
            details = ", ".join(f"{k}={v!r}" for k, v in unsupported)
            raise ValueError(
                f"These settings are not supported by the PySCF backend: "
                f"{details}.\nRemove them from the project YAML or the "
                f"command line; PySCF would otherwise run a different "
                f"calculation than the one requested."
            )

        if (
            self.ab_initio is not None
            and str(self.ab_initio).strip().lower()
            not in PYSCF_AB_INITIO_METHODS
        ):
            raise ValueError(
                f"Unknown ab_initio method {self.ab_initio!r}; the PySCF "
                f"backend accepts one of {PYSCF_AB_INITIO_METHODS} or a "
                "DFT functional."
            )

        if self.ab_initio is not None and self.functional is not None:
            raise ValueError(
                "Specify either 'ab_initio: hf' or 'functional', not both."
            )

        refused = PYSCF_FUNCTIONAL_REFUSED.get(
            canonical_functional_literal(self.functional)
        )
        if self.ab_initio is None and refused is not None:
            raise ValueError(refused)

        if is_double_hybrid_functional(self.functional):
            raise ValueError(
                f"Double-hybrid functional {self.functional!r} is not "
                "supported by the PySCF v1 backend because its "
                "perturbative correlation term would not be applied."
            )

        if self.solvent_model is None and self.solvent_id is not None:
            raise ValueError(
                "solvent_id cannot be applied without a solvent_model."
            )

        if self.solvent_model is not None:
            self._check_solvent(self.solvent_model)
            if not self.solvent_id:
                raise ValueError(
                    "A solvent_id is required for every PySCF solvent model "
                    "so the applied dielectric/environment is explicit."
                )

        if (self.charge is None) != (self.multiplicity is None):
            raise ValueError(
                "PySCF charge and multiplicity overrides must be supplied "
                "together, or both inherited from the molecular source."
            )

        if self.opt_solver not in PYSCF_OPT_SOLVERS:
            raise ValueError(
                f"Unknown opt_solver {self.opt_solver!r}; "
                f"expected one of {PYSCF_OPT_SOLVERS}."
            )

        if self.engine not in PYSCF_ENGINES:
            raise ValueError(
                f"Unknown engine {self.engine!r}; "
                f"expected one of {PYSCF_ENGINES}."
            )

        if self.jobtype not in PYSCF_JOBTYPES:
            raise ValueError(
                f"Unknown PySCF jobtype {self.jobtype!r}; expected exactly "
                f"one of {PYSCF_JOBTYPES}."
            )
        if type(self.density_fit) is not bool:
            raise ValueError(
                "density_fit must be a strict boolean, got "
                f"{self.density_fit!r}."
            )
        if type(self.freq) is not bool:
            raise ValueError(
                f"freq must be a strict boolean, got {self.freq!r}."
            )
        if self.jobtype != "hess" and self.freq:
            raise ValueError(
                f"PySCF {self.jobtype} requires freq=False; use a separate "
                "hess node so its input geometry is explicit."
            )
        if self.jobtype == "hess" and not self.freq:
            raise ValueError(
                "PySCF hess requires freq=True so the project setting "
                "matches the executed Hessian stage."
            )

        self._validate_correlated_method()
        self._validate_response()
        self._validate_hessian_derivative()
        self._validate_irc()
        self._validate_ts()
        if self.scf_tol is not None and (
            isinstance(self.scf_tol, bool)
            or not isinstance(self.scf_tol, Real)
            or not math.isfinite(float(self.scf_tol))
            or float(self.scf_tol) <= 0
        ):
            raise ValueError(
                f"scf_tol must be finite and > 0, got {self.scf_tol!r}."
            )
        for field in (
            "scf_maxiter",
            "opt_maxsteps",
            "td_max_cycle",
            "cc_max_cycle",
        ):
            value = getattr(self, field)
            if value is None:
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, Integral)
                or int(value) <= 0
            ):
                raise ValueError(
                    f"{field} must be a positive integer, got {value!r}."
                )

        if self.defgrid is not None:
            if str(self.defgrid).lower() not in PYSCF_DEFGRIDS:
                raise ValueError(
                    f"Unknown defgrid {self.defgrid!r}; "
                    f"expected one of {sorted(PYSCF_DEFGRIDS)}."
                )
            if self.ab_initio is not None:
                raise ValueError(
                    "defgrid is a DFT-only setting and cannot be applied to "
                    "an ab_initio HF calculation."
                )

        if not self.density_fit and self.aux_basis is not None:
            raise ValueError(
                "aux_basis cannot be applied when density_fit is disabled."
            )

        if self.multiplicity is not None and int(self.multiplicity) < 1:
            raise ValueError(
                f"Multiplicity must be >= 1, got {self.multiplicity!r}."
            )

        if self.xc is None and not self.ab_initio:
            raise ValueError(
                "No method specified: set 'functional' (DFT) or "
                "'ab_initio: hf' in the project YAML."
            )

        if not self.basis:
            raise ValueError(
                "No basis set specified; PySCF has no default basis."
            )
        return self

    def _validate_correlated_method(self):
        """Cross-field rules for ``mp2``/``ccsd``/``ccsd(t)``.

        Each refusal names the route: these are contracts about what this
        driver has audited, never grades of the chemistry asked for.
        """
        method = self.correlated_method
        if method is None:
            for field in ("frozen_core", "cc_max_cycle"):
                if getattr(self, field) is not None:
                    raise ValueError(
                        f"{field} applies only to a correlated ab_initio "
                        f"method ({PYSCF_CORRELATED_METHODS}); remove it or "
                        "name the method."
                    )
            return
        if self.jobtype == "hess":
            # The driver can difference this method's gradient, and that
            # path has never run on a fixture or in a goal, so it stays
            # refused. The route named here used to be "an HF or DFT hess
            # node", which characterises a different surface -- the
            # pairing the delivery refuses to credit.
            raise ValueError(
                f"PySCF {method} has no Hessian through this driver in this "
                "release: PySCF has no analytic one and differencing the "
                f"{method} gradient is not audited here. A minimum on the "
                f"{method} surface stays uncharacterised; an HF or DFT hess "
                "at that geometry is the Hessian of a different surface, "
                "and the delivery says so rather than crediting it."
            )
        if self.jobtype == "td":
            raise ValueError(
                f"PySCF td runs on a Kohn-Sham reference; {method} has no "
                "response surface here. Set a functional for td."
            )
        if self.jobtype == "opt" and method == "ccsd(t)":
            raise ValueError(
                "A CCSD(T) geometry optimisation is not audited through "
                "this driver in this release (PySCF 2.14 carries "
                "pyscf.grad.ccsd_t, unexercised here); optimise at mp2 or "
                "ccsd and take a ccsd(t) single point on the reached "
                "geometry."
            )
        if self.density_fit:
            raise ValueError(
                f"density_fit with {method} is refused: DF-MP2 has no "
                "gradient in PySCF 2.14 and DF coupled cluster is not "
                "audited here; set density_fit: false."
            )
        if self.solvent_model is not None or self.solvent_id is not None:
            raise ValueError(
                f"An implicit solvent with {method} is not audited in this "
                "release; run the correlated single point in the gas "
                "phase or use a DFT node for the solvated surface."
            )
        if self.dispersion is not None:
            raise ValueError(
                f"A dispersion correction with {method} is not audited in "
                "this release; remove dispersion for the correlated node."
            )
        if self.jobtype == "opt" and str(self.opt_solver) != "geometric":
            raise ValueError(
                f"A {method} optimisation is audited with opt_solver "
                f"geometric only; got {self.opt_solver!r}."
            )
        frozen = self.frozen_core
        if frozen is not None and not (
            (
                isinstance(frozen, str)
                and frozen.strip().lower() == PYSCF_FROZEN_CORE_AUTO
            )
            or (
                not isinstance(frozen, bool)
                and isinstance(frozen, Integral)
                and int(frozen) >= 0
            )
        ):
            raise ValueError(
                "frozen_core must be a non-negative orbital count or "
                f"{PYSCF_FROZEN_CORE_AUTO!r} (PySCF's chemical-core rule), "
                f"got {frozen!r}."
            )
        if self.cc_max_cycle is not None and (
            method not in PYSCF_COUPLED_CLUSTER_METHODS
        ):
            raise ValueError(
                "cc_max_cycle applies only to ccsd or ccsd(t); MP2 has no "
                "amplitude iteration."
            )

    def _validate_response(self):
        """The executable TDA/TDDFT contract for ``td`` and an excited opt."""
        td_fields = {
            "response_method": self.response_method,
            "state_manifold": self.state_manifold,
            "nstates": self.nstates,
            "td_max_cycle": self.td_max_cycle,
            "excited_state_root": self.excited_state_root,
        }
        # A root names the surface a job walks on or differentiates: an
        # optimisation follows it downhill and a Hessian measures its
        # curvature. A td node computes the spectrum at a fixed geometry
        # and names no root, because its own surface is the reference's.
        if self.excited_state_root is not None and self.jobtype not in (
            PYSCF_EXCITED_SURFACE_JOBTYPES
        ):
            raise ValueError(
                "excited_state_root names the root a job walks on or "
                "differentiates; it is valid for "
                f"{sorted(PYSCF_EXCITED_SURFACE_JOBTYPES)}, not "
                f"{self.jobtype!r}. A td node computes the spectrum at a "
                "fixed geometry."
            )
        if not self.response_requested:
            populated = ", ".join(
                key for key, value in td_fields.items() if value is not None
            )
            if populated:
                raise ValueError(
                    f"PySCF {populated} are valid only for the td jobtype "
                    "or an opt carrying excited_state_root."
                )
            return
        what = (
            "td"
            if self.jobtype == "td"
            else f"{self.jobtype} on an excited root"
        )
        response_method = str(self.response_method or "").strip().lower()
        if response_method not in PYSCF_RESPONSE_METHODS:
            raise ValueError(
                f"PySCF {what} requires response_method to be one of "
                f"{PYSCF_RESPONSE_METHODS}, got {self.response_method!r}."
            )
        if (
            isinstance(self.nstates, bool)
            or not isinstance(self.nstates, Integral)
            or int(self.nstates) <= 0
        ):
            raise ValueError(
                f"PySCF {what} requires nstates to be a positive integer, "
                f"got {self.nstates!r}."
            )
        if self.ab_initio is not None or not self.functional:
            raise ValueError(
                f"PySCF {what} runs on a Kohn-Sham reference: set a "
                "functional and do not set ab_initio."
            )
        manifold = str(self.state_manifold or "").strip().lower()
        if manifold not in PYSCF_STATE_MANIFOLDS:
            raise ValueError(
                f"PySCF {what} requires state_manifold to be one of "
                f"{PYSCF_STATE_MANIFOLDS}, got {self.state_manifold!r}."
            )
        # Which manifolds the reference admits is a fact about the resolved
        # electronic state, and one rule for every program.  A project
        # section carries no multiplicity, so the check waits until the
        # molecule's state is bound (the CLI re-validates per molecule and
        # preflight resolves it); a settings object that already knows its
        # multiplicity is held to it here.
        from chemsmart.jobs.settings import td_manifold_reference_refusal

        refusal = td_manifold_reference_refusal(manifold, self.multiplicity)
        if refusal:
            raise ValueError(refusal)
        if self.excited_state_root is not None:
            root = self.excited_state_root
            if manifold == PYSCF_TWO_BLOCK_MANIFOLD:
                raise ValueError(
                    "excited_state_root follows one root of one manifold; "
                    "state_manifold: singlet_triplet holds two. Name the "
                    "manifold the root belongs to (singlet or triplet)."
                )
            if (
                isinstance(root, bool)
                or not isinstance(root, Integral)
                or int(root) <= 0
                or int(root) > int(self.nstates)
            ):
                raise ValueError(
                    "excited_state_root must be a positive root index no "
                    f"larger than nstates ({self.nstates!r}); got {root!r}."
                )
            if self.solvent_model is not None or self.solvent_id is not None:
                raise ValueError(
                    "PySCF 2.14 has no excited-state gradient under PCM/SMD "
                    "(NotImplementedError: PCM-TDDFT Gradients); optimise "
                    "the excited root in the gas phase, or take solvated "
                    "td energies at a fixed geometry."
                )
            if str(self.opt_solver) != "geometric":
                raise ValueError(
                    "An excited-state optimisation is audited with "
                    f"opt_solver geometric only; got {self.opt_solver!r}."
                )
        if self.dispersion is not None:
            raise ValueError(
                f"PySCF {what} does not accept a ground-state dispersion "
                "correction as an excited-state setting; the host also has "
                "no dispersion package installed."
            )
        if str(self.engine or "cpu").strip().lower() != "cpu":
            raise ValueError(
                f"PySCF {what} is a CPU capability; GPU4PySCF response "
                "calculations are not validated here."
            )

    def _validate_hessian_derivative(self):
        """How a Hessian's second derivative is obtained, held to what the
        driver does with each word.

        The driver differences a gradient for every word but ``analytic``,
        so a word outside the vocabulary ran a finite difference and was
        recorded as the derivative behind the frequencies. And ``analytic``
        is ``mf.Hessian()``: on an excited root that is the SCF
        reference's curvature, written into a result whose surface names
        the root -- a real spectrum of the wrong state under green
        receipts.
        """
        derivative = self.hessian_derivative
        if derivative is not None:
            normal = str(derivative).strip().lower()
            if normal not in PYSCF_HESSIAN_DERIVATIVES:
                raise ValueError(
                    "hessian_derivative must be one of "
                    f"{PYSCF_HESSIAN_DERIVATIVES}, got {derivative!r}."
                )
            if normal == "analytic" and self.excited_state_root is not None:
                raise ValueError(
                    "PySCF 2.14 has no analytic Hessian of an excited root: "
                    "an analytic Hessian here would be the SCF reference's "
                    "curvature while the result names the surface of root "
                    f"{self.excited_state_root!r}. Omit hessian_derivative "
                    "(an excited root resolves to finite_difference) or "
                    "name finite_difference."
                )
        step = self.fd_step_angstrom
        if step is not None and (
            isinstance(step, bool)
            or not isinstance(step, Real)
            or not math.isfinite(float(step))
            or float(step) <= 0
        ):
            raise ValueError(
                "fd_step_angstrom must be a finite displacement > 0 in "
                f"Angstrom, got {step!r}."
            )

    def _validate_ts(self):
        """The executable saddle-search contract.

        A ``ts`` climbs to a first-order saddle with geomeTRIC's
        partitioned rational-function step, which needs the curvature at
        the seed to know which mode to climb; the driver gives it PySCF's
        analytic Hessian of the job's own surface there, so the surface
        must be one PySCF differentiates twice analytically -- an HF or
        DFT reference on the CPU engine.  Each refusal names what answers
        the question instead.

        An excited root is refused where every job type outside
        ``PYSCF_EXCITED_SURFACE_JOBTYPES`` is, so there is no branch for
        it here.

        What a ``ts`` node does *not* do is take a Hessian where it
        arrives.  The order of the structure a search reaches is a
        Hessian's question and a ``hess`` node is where this program
        answers it, exactly as an ``opt`` is held: an in-process Hessian
        would put two stage identities in one artifact and hide the
        geometry the curvature belongs to.
        """

        if self.jobtype != "ts":
            return
        method = self.correlated_method
        if method is not None:
            raise ValueError(
                f"A {method} transition-state search is not available "
                "through this driver: the climb needs the surface's own "
                f"Hessian and PySCF has no {method} Hessian. Locate the "
                "saddle on an HF or DFT surface and take correlated "
                "single points on the geometry it reaches."
            )
        if str(self.opt_solver) != "geometric":
            raise ValueError(
                "PySCF ts is geomeTRIC's transition-state optimiser; "
                f"opt_solver must be 'geometric', got {self.opt_solver!r}."
            )
        if str(self.engine or "cpu").strip().lower() != "cpu":
            raise ValueError(
                "PySCF ts is a CPU capability; GPU4PySCF has run no "
                "saddle search here."
            )
        if self.hessian_derivative is not None:
            raise ValueError(
                "A ts takes the analytic Hessian of its own surface at "
                "the seed; hessian_derivative applies to a hess node. "
                "Remove it from the ts section."
            )

    def _validate_irc(self):
        """The executable intrinsic-reaction-coordinate contract.

        An ``irc`` walks one branch of the steepest-descent path in
        mass-weighted coordinates from the geometry it was handed, with
        geomeTRIC's Gonzalez-Schlegel integrator. Its first act is the
        analytic Hessian of its own surface at that geometry, because the
        branch starts along that Hessian's one imaginary mode and a
        saddle of another surface is not a saddle of this one. So the
        surface must be one PySCF differentiates twice analytically: an
        HF or DFT reference on the CPU engine. Each refusal names what
        would answer the question instead.
        """

        if self.jobtype != "irc":
            if self.irc_direction is not None:
                raise ValueError(
                    "irc_direction names the branch an irc walks; it is "
                    f"valid only for the irc jobtype, not {self.jobtype!r}."
                )
            return
        direction = str(self.irc_direction or "").strip().lower()
        if direction not in PYSCF_IRC_DIRECTIONS:
            raise ValueError(
                "PySCF irc walks one branch per node: set irc_direction to "
                f"one of {PYSCF_IRC_DIRECTIONS} (got {self.irc_direction!r}); "
                "the two branches from one saddle are two irc nodes on the "
                "same geometry."
            )
        method = self.correlated_method
        if method is not None:
            raise ValueError(
                f"A {method} IRC is not available through this driver: the "
                "branch starts along the imaginary mode of the surface's "
                f"own Hessian, and PySCF has no {method} Hessian. Walk the "
                "path on an HF or DFT surface and take correlated single "
                "points on the geometries it reaches."
            )
        if str(self.opt_solver) != "geometric":
            raise ValueError(
                "PySCF irc is geomeTRIC's intrinsic reaction coordinate; "
                f"opt_solver must be 'geometric', got {self.opt_solver!r}."
            )
        if str(self.engine or "cpu").strip().lower() != "cpu":
            raise ValueError(
                "PySCF irc is a CPU capability; GPU4PySCF has not run one "
                "here."
            )
        if self.hessian_derivative is not None:
            raise ValueError(
                "An irc takes the analytic Hessian of its own surface at "
                "the supplied geometry; hessian_derivative applies to a "
                "hess node. Remove it from the irc section."
            )
