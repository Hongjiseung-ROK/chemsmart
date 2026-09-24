"""Pure validation for requested and completed PySCF calculations.

The functions in this module never launch a solver, import an optional
dependency, or mutate an artifact.  Optional-package and GPU facts are
supplied as an ``environment`` mapping, which makes preflight deterministic
and lets an agent collect every known blocker in one pass.

Recognised environment evidence is intentionally small and permissive.  The
following keys may be flat or nested under ``dependencies`` / ``gpu``:

``solver_callables``
    A mapping from ``geometric``, ``berny`` or ``ase`` to the probed Python
    entry point (or ``{"callable": True}`` for an external-env attestation).
``solvent_ids`` / ``solvent_db``
    Valid PySCF solvent names as a collection or mapping.
``pyscf_dispersion``
    Whether the dispersion extra is available.
``dispersion_conformance``
    Target-PySCF observation for the exact requested dispersion literal and
    mean-field method. Missing or mismatched evidence fails closed.
``gpu4pyscf``, ``cupy``, ``cuda_available``, ``cutensor_compatible``
    Required GPU runtime evidence.  ``basis_max_l`` and
    ``aux_basis_max_l`` optionally carry pre-probed angular momenta.

No availability conclusion is inferred by importing from the current
ChemSmart interpreter: the generated calculation may run in a different
``CONDA_ENV``.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Any

import numpy as np
from ase.data import atomic_masses as ASE_ATOMIC_MASSES
from ase.data import atomic_numbers as ASE_ATOMIC_NUMBERS

from chemsmart.jobs.pyscf.settings import (
    PYSCF_AB_INITIO_METHODS,
    PYSCF_ANALYTIC_HESSIAN_STAGES,
    PYSCF_COUPLED_CLUSTER_METHODS,
    PYSCF_DEFGRIDS,
    PYSCF_ENGINES,
    PYSCF_EXCITED_SURFACE_JOBTYPES,
    PYSCF_FROZEN_CORE_AUTO,
    PYSCF_IRC_DIRECTIONS,
    PYSCF_JOBTYPES,
    PYSCF_MOVING_STAGES,
    PYSCF_OPT_SOLVERS,
    PYSCF_RESPONSE_METHODS,
    PYSCF_SOLVENT_MODELS,
    PYSCF_STATE_MANIFOLDS,
    PYSCF_TWO_BLOCK_MANIFOLD,
    PYSCF_UNRESTRICTED_MANIFOLD,
    is_double_hybrid_functional,
    pyscf_correlated_method,
    pyscf_native_functional,
    pyscf_stages,
)


@dataclass(frozen=True, slots=True)
class PySCFViolation:
    """One stable, machine-repairable PySCF validation finding."""

    rule_id: str
    field: str
    expected: Any
    observed: Any
    evidence_ref: str


RULE_UNSUPPORTED_SETTING = "pyscf.settings.unsupported"
RULE_INVALID_SETTING = "pyscf.settings.invalid_value"
RULE_SOLVENT_MODEL = "pyscf.solvent.model_unsupported"
RULE_SOLVENT_ID_REQUIRED = "pyscf.solvent.id_required"
RULE_SOLVENT_DATABASE = "pyscf.solvent.database_unavailable"
RULE_SOLVENT_ID_UNKNOWN = "pyscf.solvent.id_unknown"
RULE_SOLVER_UNCALLABLE = "pyscf.solver.uncallable"
RULE_DISPERSION_MISSING = "pyscf.dispersion.dependency_missing"
RULE_DISPERSION_UNVERIFIED = "pyscf.dispersion.literal_unverified"
RULE_DISPERSION_INVALID = "pyscf.dispersion.literal_invalid"
RULE_DISPERSION_METHOD = "pyscf.dispersion.method_incompatible"
RULE_GPU_DEPENDENCY = "pyscf.gpu.dependency_missing"
RULE_GPU_CUDA = "pyscf.gpu.cuda_unavailable"
RULE_GPU_TENSOR = "pyscf.gpu.cutensor_incompatible"
RULE_GPU_BASIS = "pyscf.gpu.basis_angular_momentum"
RULE_GPU_AUX_BASIS = "pyscf.gpu.aux_basis_angular_momentum"
RULE_GPU_DOUBLE_HYBRID = "pyscf.gpu.double_hybrid"
RULE_GPU_LAPLACIAN = "pyscf.gpu.laplacian_meta_gga"
RULE_GPU_FUNCTIONAL_EVIDENCE = "pyscf.gpu.functional_unverified"
RULE_GPU_SOLVENT = "pyscf.gpu.solvent_unsupported"
RULE_GPU_TD_HESSIAN = "pyscf.gpu.tddft_hessian"
RULE_CHARGE_INVALID = "pyscf.electrons.charge_invalid"
RULE_MULTIPLICITY_INVALID = "pyscf.electrons.multiplicity_invalid"
RULE_STATE_OVERRIDE_PAIR = "pyscf.electrons.override_pair"
RULE_ATOMIC_NUMBERS = "pyscf.electrons.atomic_numbers_unavailable"
RULE_ELECTRON_COUNT = "pyscf.electrons.count_inconsistent"
RULE_SPIN_PARITY = "pyscf.electrons.spin_parity"
RULE_SPIN_EXCEEDS = "pyscf.electrons.spin_exceeds_count"
RULE_SPIN_MISMATCH = "pyscf.electrons.spin_mismatch"
RULE_PREFLIGHT_INPUT = "pyscf.preflight.invalid_input"
RULE_PROVENANCE_READ = "pyscf.provenance.artifact_unreadable"
RULE_PROVENANCE_INCOMPLETE = "pyscf.provenance.incomplete_calculation"
RULE_PROVENANCE_SPEC = "pyscf.provenance.spec_mismatch"
RULE_PROVENANCE_ENGINE = "pyscf.provenance.engine_mismatch"
RULE_PROVENANCE_DIGEST = "pyscf.provenance.digest_mismatch"
RULE_PROVENANCE_PROJECT_DIGEST = (
    "pyscf.provenance.project_yaml_digest_mismatch"
)
RULE_PROVENANCE_RECEIPT = "pyscf.provenance.receipt_mismatch"
RULE_PROVENANCE_APPLIED_DIGEST = (
    "pyscf.provenance.applied_settings_digest_mismatch"
)
RULE_PROVENANCE_MATERIALIZATION = "pyscf.provenance.materialization_invalid"
RULE_RESULT_UNIT = "pyscf.result.unit_missing_or_mismatched"
RULE_HESSIAN_REFERENCE = "pyscf.hessian.reference_unsupported"
RULE_HESSIAN_NLC_OPEN_SHELL = "pyscf.hessian.nlc_open_shell_unsupported"
RULE_TD_GPU_UNSUPPORTED = "pyscf.td.gpu_preview_unsupported"
#: The response stage runs on a Kohn-Sham reference whose manifold matches
#: its spin: singlet/triplet on a closed shell, ``unrestricted`` on an open
#: shell.  A mismatch is a contract about what PySCF computes, not a grade.
RULE_TD_REFERENCE = "pyscf.td.reference_unsupported"
#: PySCF 2.14 raises NotImplementedError for PCM/SMD excited-state
#: gradients; an excited-root optimisation is gas phase only.
RULE_TD_GRADIENT_SOLVENT = "pyscf.td.gradient_solvent_unsupported"
#: Correlated methods: what this driver has audited, each with its route.
RULE_CORRELATION_HESSIAN = "pyscf.correlation.hessian_unsupported"
RULE_CORRELATION_CCSDT_GRADIENT = "pyscf.correlation.ccsd_t_gradient_unaudited"
RULE_CORRELATION_DENSITY_FIT = "pyscf.correlation.density_fit_unsupported"
RULE_CORRELATION_SOLVENT = "pyscf.correlation.solvent_unaudited"
RULE_CORRELATION_DISPERSION = "pyscf.correlation.dispersion_unaudited"
#: An excited or correlated surface is optimised with geomeTRIC only; the
#: other backends are not installed here and were never exercised on a
#: gradient scanner.
RULE_SOLVER_UNAUDITED_SURFACE = "pyscf.solver.unaudited_surface"
#: Excited-state and correlated result arrays: finite, aligned, ordered.
RULE_RESULT_EXCITED = "pyscf.result.excited_state_invalid"
RULE_RESULT_CORRELATION = "pyscf.result.correlation_invalid"
#: The decomposition of the total (contract v10): the settings that
#: produce a term and the terms recorded agree.  A solvated run whose
#: artifact carries no continuum term reads, through the selector plane,
#: exactly like a gas-phase one -- which is the reading this rule exists
#: to prevent -- and a term recorded by a run that applied no such model
#: is a number belonging to nothing.
RULE_RESULT_DECOMPOSITION = "pyscf.result.energy_decomposition_invalid"
#: An IRC walks one branch from the saddle it was handed, on an HF or DFT
#: surface PySCF differentiates twice analytically; each refusal names what
#: answers the question instead.
RULE_IRC_SETTING = "pyscf.irc.setting_unsupported"
#: The IRC's arrays: the start's spectrum, the path and its endpoint.
RULE_RESULT_IRC = "pyscf.result.irc_invalid"
#: The start of an IRC is a first-order saddle of the surface it walks: one
#: imaginary mode past the 20 cm-1 noise convention in that surface's own
#: Hessian. The suffix is the one the program-neutral terminal derivation
#: already reads as a wrong stationary point.
RULE_RESULT_IRC_START_ORDER = "pyscf.result.irc_start_imaginary_mode_count"
#: The branch the first step took, measured, disagrees with the one asked.
RULE_RESULT_IRC_DIRECTION = "pyscf.result.irc_direction_not_followed"
#: The saddle search's arrays: the seed's curvature and the climb.
RULE_RESULT_TS = "pyscf.result.ts_invalid"
#: A number the artifact records *about* its path disagrees with the same
#: number re-derived from the arrays the driver derived it from. Every
#: scalar an IRC stage writes beside its frames -- the start's spectrum,
#: the mass-weighted arc length, the energy statistics -- is a summary of
#: those arrays, and a summary nothing re-derives is a claim the bytes
#: need not support.
RULE_RESULT_IRC_ACCOUNT = "pyscf.result.irc_account_inconsistent"
RULE_FREQUENCY_GEOMETRY = "pyscf.frequency.geometry_invalid"
RULE_FREQUENCY_MODE_COUNT = "pyscf.frequency.mode_count"
RULE_FREQUENCY_NONFINITE = "pyscf.frequency.nonfinite"
RULE_FREQUENCY_IMAGINARY = "pyscf.frequency.imaginary_modes"
RULE_RESULT_READ = "pyscf.result.artifact_unreadable"
RULE_RESULT_STAGE = "pyscf.result.stage_mismatch"
RULE_RESULT_STATE = "pyscf.result.electronic_state_mismatch"
RULE_RESULT_IDENTITY = "pyscf.result.atom_identity_mismatch"
RULE_RESULT_GEOMETRY = "pyscf.result.geometry_invalid"
RULE_RESULT_SHAPE = "pyscf.result.shape_invalid"
RULE_RESULT_NONFINITE = "pyscf.result.nonfinite"
RULE_RESULT_HESSIAN = "pyscf.result.hessian_invalid"
RULE_RESULT_HESSIAN_CONSISTENCY = "pyscf.result.hessian_frequency_inconsistent"
RULE_RESULT_HESSIAN_CONSISTENCY_UNVERIFIED = (
    "pyscf.result.hessian_consistency_unverified"
)
RULE_RESULT_SETTINGS = "pyscf.result.settings_identity_invalid"
RULE_RESULT_DTYPE = "pyscf.result.nonnumeric_physical_array"
RULE_RESULT_OCCUPATION = "pyscf.result.orbital_occupation_invalid"
RULE_RESULT_SPIN_DIAGNOSTIC = "pyscf.result.spin_diagnostic_invalid"
RULE_RESULT_CONTRACT = "pyscf.result.contract_incomplete"
RULE_RESULT_REFERENCE = "pyscf.result.reference_family_mismatch"

FREQUENCY_VALIDATION_SCHEMA_VERSION = "chemsmart.pyscf-frequency-validation.v1"
RESULT_VALIDATION_SCHEMA_VERSION = "chemsmart.pyscf-result-validation.v1"
# Geometry optimizers do not preserve exact collinearity at machine precision.
# A relative transverse spread of 1e-4 is still a conservative linear-rotor
# classification (about 0.01 degrees for a triatomic), while admitting the
# small residual displacement left by ordinary geometry convergence.
_LINEARITY_RELATIVE_TOLERANCE = 1.0e-4
# Analytic PySCF Hessians can retain micro-Hartree/Bohr^2 antisymmetric
# numerical noise.  These tolerances admit the archived water result while
# still rejecting chemically material asymmetry.
_HESSIAN_SYMMETRY_RTOL = 2.0e-5
_HESSIAN_SYMMETRY_ATOL = 1.0e-7
_FIXED_GEOMETRY_ATOL_ANGSTROM = 1.0e-8
#: The job types held to the geometry they were handed: supplied and final
#: coincide by construction and the validator checks it. One authority for
#: every organ that must supply the expected geometry -- the host evaluation
#: once passed it for sp and hess alone while this set had grown to td, so
#: every td under the goal driver failed geometry_invalid with an expected
#: geometry of shape None (PySCF round 2 E1, 2026-09-13).
FIXED_GEOMETRY_JOBTYPES = frozenset({"sp", "hess", "td"})
_OCCUPATION_ATOL = 1.0e-7
_SPIN_DIAGNOSTIC_NUMERICAL_ATOL = 1.0e-7
# Independent CODATA-2018 SI constants.  The child uses PySCF's constants;
# keeping a separate literal set here makes Hessian/frequency comparison a
# genuine cross-check rather than a second call into the producing routine.
_HARTREE_J = 4.3597447222071e-18
_ATOMIC_MASS_KG = 1.66053906660e-27
_BOHR_M = 5.29177210903e-11
_LIGHT_SPEED_M_S = 299792458.0
_HESSIAN_FREQUENCY_ATOL_CM1 = 0.5
_HESSIAN_FREQUENCY_RTOL = 5.0e-4


def _linearity_metrics(coordinates):
    """Return scale, transverse spread, and effective linearity.

    The dimensionless singular-value ratio is invariant to translation,
    rotation, and uniform coordinate scaling.  The same classification is
    used for both the 3N-5 mode-count rule and the independent removal of
    translations and rotations from a Cartesian Hessian.
    """

    values = np.asarray(coordinates, dtype=float)
    centered = values - values.mean(axis=0)
    singular_values = np.linalg.svd(centered, compute_uv=False)
    scale = float(singular_values[0]) if singular_values.size else 0.0
    second = float(singular_values[1]) if singular_values.size > 1 else 0.0
    if not math.isfinite(scale) or scale <= 0.0:
        return scale, second, None
    return (
        scale,
        second,
        second <= _LINEARITY_RELATIVE_TOLERANCE * scale,
    )


_MISSING = object()

_SUPPORTED_FIELDS = frozenset(
    {
        "ab_initio",
        "functional",
        "dispersion",
        "basis",
        "aux_basis",
        "defgrid",
        "scf_tol",
        "scf_maxiter",
        "charge",
        "multiplicity",
        "freq",
        "density_fit",
        "opt_solver",
        "opt_maxsteps",
        "engine",
        "jobtype",
        "title",
        "solvent_model",
        "solvent_id",
        "project_yaml_digest",
        "response_method",
        "state_manifold",
        "nstates",
        "excited_state_root",
        "td_max_cycle",
        "frozen_core",
        "cc_max_cycle",
        "hessian_derivative",
        "fd_step_angstrom",
        "scf_stability",
        "irc_direction",
    }
)

# Defaults distinguish inherited-but-unrequested fields from requests that the
# generated PySCF driver would otherwise ignore.
_UNSUPPORTED_DEFAULTS = {
    "semiempirical": None,
    "numfreq": False,
    "additional_route_parameters": None,
    "route_to_be_written": None,
    "modred": None,
    "gen_genecp_file": None,
    "heavy_elements": None,
    "heavy_elements_basis": None,
    "light_elements_basis": None,
    "custom_solvent": None,
    "forces": False,
    "input_string": None,
}

_SOLVER_ENTRYPOINTS = {
    "geometric": "pyscf.geomopt.geometric_solver.kernel",
    "berny": "pyscf.geomopt.berny_solver.kernel",
    "ase": "pyscf.geomopt.ase_solver.kernel",
}

_ANGULAR_MOMENTA = {
    "s": 0,
    "p": 1,
    "d": 2,
    "f": 3,
    "g": 4,
    "h": 5,
    "i": 6,
    "j": 7,
}

_GPU_SOLVENT_MODELS = frozenset(
    {"pcm", "iefpcm", "cpcm", "cosmo", "ssvpe", "smd"}
)


def preflight(settings, molecule, environment) -> list[PySCFViolation]:
    """Return every known pre-compute violation without running chemistry.

    ``environment`` is evidence gathered for the interpreter that will run
    the generated script.  Solver objects are inspected with ``callable`` but
    never invoked.  Missing evidence fails closed only for a requested
    optional feature (optimization, dispersion, solvent lookup, or GPU).
    """

    violations: list[PySCFViolation] = []
    checks = (
        _check_unsupported_settings,
        _check_setting_values,
        _check_solvent,
        _check_solver,
        _check_dispersion,
        _check_gpu,
        _check_electrons,
        _check_hessian_support,
        _check_irc_settings,
    )
    for check in checks:
        try:
            violations.extend(check(settings, molecule, environment))
        except Exception as exc:  # validation must enumerate, never raise
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PREFLIGHT_INPUT,
                    field=check.__name__,
                    expected="valid preflight input",
                    observed=type(exc).__name__,
                    evidence_ref="preflight:input",
                )
            )
    return violations


def verify_provenance(
    settings, h5_path, *, expected_receipt=None
) -> list[PySCFViolation]:
    """Compare requested settings with the receipt stored in ``label.h5``.

    Both the historical schema-1 JSON datasets and schema-2 HDF5 groups are
    accepted.  Artifact/read errors are returned as typed violations rather
    than raised, preserving the same bounded-repair interface as preflight.
    This verifies receipt agreement and completion, not target-object
    introspection; the current digest is the controller-side requested-settings
    identity.
    """

    try:
        spec, provenance, status = _read_artifact_contract(h5_path)
    except Exception as exc:  # corrupt/missing artifacts are findings
        return [
            PySCFViolation(
                rule_id=RULE_PROVENANCE_READ,
                field="h5_path",
                expected="readable PySCF HDF5 provenance",
                observed=type(exc).__name__,
                evidence_ref="h5:/",
            )
        ]

    if not isinstance(spec, Mapping):
        return [
            PySCFViolation(
                rule_id=RULE_PROVENANCE_READ,
                field="spec",
                expected="mapping of applied settings",
                observed=type(spec).__name__,
                evidence_ref="h5:/spec",
            )
        ]

    violations: list[PySCFViolation] = []
    normal_termination = (
        status.get("normal_termination", False)
        if isinstance(status, Mapping)
        else False
    )
    if normal_termination is not True:
        failure = (
            status.get("failure") if isinstance(status, Mapping) else None
        )
        violations.append(
            PySCFViolation(
                rule_id=RULE_PROVENANCE_INCOMPLETE,
                field="status.normal_termination",
                expected=True,
                observed=bool(normal_termination),
                evidence_ref=(
                    "h5:/status/failure"
                    if failure is not None
                    else "h5:/status/normal_termination"
                ),
            )
        )
    if expected_receipt and expected_receipt.get("require_engine_complete"):
        engine_complete = (
            status.get("engine_complete", False)
            if isinstance(status, Mapping)
            else False
        )
        if engine_complete is not True:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_INCOMPLETE,
                    field="status.engine_complete",
                    expected=True,
                    observed=bool(engine_complete),
                    evidence_ref="h5:/status/engine_complete",
                )
            )
    from chemsmart.jobs.pyscf.writer import applied_pyscf_spec_fields

    requested = _requested_spec(settings)
    # A field the artifact's own contract vocabulary never carried cannot
    # be compared against it.  An artifact written under an earlier
    # contract is evidence, not a mismatch, and the day a new applied-spec
    # field is added is the day every archived result would otherwise
    # start failing its own settings check.  A field the contract *does*
    # carry and the spec lacks stays a finding.  So does a request that
    # asked: an artifact that could not carry the answer satisfies only a
    # request that did not ask for one, or the settings check would call a
    # pre-v7 result valid evidence for a run that requested the analysis.
    carried = frozenset(applied_pyscf_spec_fields(spec))
    for field, expected in requested.items():
        observed = spec.get(field, _MISSING)
        if (
            observed is _MISSING
            and field not in carried
            and expected in (None, False)
        ):
            continue
        if observed is _MISSING and expected is None:
            observed = None
        if not _equivalent(field, expected, observed):
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_SPEC,
                    field=field,
                    expected=expected,
                    observed=(
                        "<missing>" if observed is _MISSING else observed
                    ),
                    evidence_ref=f"h5:/spec/{field}",
                )
            )

    if isinstance(provenance, Mapping):
        expected_engine = requested.get("engine", _MISSING)
        observed_engine = provenance.get("engine", _MISSING)
        if expected_engine is not _MISSING and not _equivalent(
            "engine", expected_engine, observed_engine
        ):
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_ENGINE,
                    field="provenance.engine",
                    expected=expected_engine,
                    observed=(
                        "<missing>"
                        if observed_engine is _MISSING
                        else observed_engine
                    ),
                    evidence_ref="h5:/provenance/engine",
                )
            )

        spec_digest = spec.get("settings_digest", _MISSING)
        provenance_digest = provenance.get("settings_digest", _MISSING)
        if (
            spec_digest is _MISSING
            or provenance_digest is _MISSING
            or spec_digest != provenance_digest
        ):
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_DIGEST,
                    field="settings_digest",
                    expected=(
                        "present in both spec and provenance"
                        if spec_digest is _MISSING
                        else spec_digest
                    ),
                    observed=(
                        "<missing>"
                        if provenance_digest is _MISSING
                        else provenance_digest
                    ),
                    evidence_ref="h5:/provenance/settings_digest",
                )
            )

        expected_project_digest = _member(
            settings, "project_yaml_digest", _MISSING
        )
        observed_project_digest = provenance.get(
            "project_yaml_digest", _MISSING
        )
        if (
            expected_project_digest not in (_MISSING, None)
            and expected_project_digest != observed_project_digest
        ):
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_PROJECT_DIGEST,
                    field="project_yaml_digest",
                    expected=expected_project_digest,
                    observed=(
                        "<missing>"
                        if observed_project_digest is _MISSING
                        else observed_project_digest
                    ),
                    evidence_ref="h5:/provenance/project_yaml_digest",
                )
            )
        violations.extend(
            _verify_bound_receipt(
                spec,
                provenance,
                expected_receipt,
            )
        )
    elif expected_receipt:
        violations.append(
            PySCFViolation(
                rule_id=RULE_PROVENANCE_RECEIPT,
                field="provenance",
                expected="mapping with bound receipt hashes",
                observed=type(provenance).__name__,
                evidence_ref="h5:/provenance",
            )
        )
    if expected_receipt:
        violations.extend(_verify_result_units(h5_path))
        if expected_receipt.get("require_applied_settings_sha256"):
            violations.extend(_verify_materializations(spec, provenance))
    return violations


def _verify_result_units(h5_path):
    """Require native real-number arrays and explicit physical units.

    Validation intentionally inspects the HDF5 dtype before using the public
    reader.  Converting ``["-76.0"]`` or ``[True]`` to floats would turn a
    serialization defect into apparently valid chemistry.
    """

    import h5py

    from chemsmart.jobs.pyscf.writer import RESULT_UNITS

    violations = []
    try:
        with h5py.File(os.fspath(h5_path), "r") as handle:
            results = handle["results"]

            def visit(_name, node):
                if not isinstance(node, h5py.Dataset):
                    return
                if bool(node.attrs.get("chemsmart_is_null", False)):
                    return
                leaf = node.name.rsplit("/", 1)[-1]
                expected = RESULT_UNITS.get(leaf)
                if expected is None:
                    if node.dtype.kind in {"b", "i", "u", "f", "c"}:
                        violations.append(
                            PySCFViolation(
                                rule_id=RULE_RESULT_UNIT,
                                field=f"{node.name}.unit",
                                expected="registered physical-result unit",
                                observed="unregistered numeric dataset",
                                evidence_ref=f"h5:{node.name}",
                            )
                        )
                    return
                if node.dtype.kind not in {"i", "u", "f"}:
                    violations.append(
                        PySCFViolation(
                            rule_id=RULE_RESULT_DTYPE,
                            field=node.name,
                            expected="native real integer or floating HDF5 array",
                            observed=str(node.dtype),
                            evidence_ref=f"h5:{node.name}",
                        )
                    )
                observed = node.attrs.get("unit")
                if isinstance(observed, bytes):
                    observed = observed.decode("utf-8")
                if observed != expected:
                    violations.append(
                        PySCFViolation(
                            rule_id=RULE_RESULT_UNIT,
                            field=f"{node.name}.unit",
                            expected=expected,
                            observed=(
                                "<missing>" if observed is None else observed
                            ),
                            evidence_ref=f"h5:{node.name}",
                        )
                    )

            results.visititems(visit)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        violations.append(
            PySCFViolation(
                rule_id=RULE_RESULT_UNIT,
                field="results.units",
                expected="readable unit attributes",
                observed=type(exc).__name__,
                evidence_ref="h5:/results",
            )
        )
    return violations


def _verify_materializations(spec, provenance=None):
    """Verify target-runtime functional and solvent materializations."""

    provenance = provenance if isinstance(provenance, Mapping) else {}

    model = spec.get("solvent_model")
    materializations = spec.get("materializations")
    if materializations in (None, {}):
        materializations = {}
    if not isinstance(materializations, Mapping):
        return [
            PySCFViolation(
                rule_id=RULE_PROVENANCE_MATERIALIZATION,
                field="spec.materializations",
                expected="mapping of registered materialization records",
                observed=materializations,
                evidence_ref="h5:/spec/materializations",
            )
        ]

    violations = []
    allowed = {
        "functional_definition",
        "solvent_dielectric",
        "td_response_plan",
    }
    unknown = tuple(sorted(set(materializations).difference(allowed)))
    if unknown:
        violations.append(
            PySCFViolation(
                rule_id=RULE_PROVENANCE_MATERIALIZATION,
                field="spec.materializations",
                expected=tuple(sorted(allowed)),
                observed=unknown,
                evidence_ref="h5:/spec/materializations",
            )
        )

    solvent_record = materializations.get("solvent_dielectric")
    if model is not None:
        environment_receipt_sha256 = provenance.get(
            "environment_receipt_sha256"
        )
        pyscf_version = provenance.get("pyscf_version")
        if not _is_sha256(environment_receipt_sha256):
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_MATERIALIZATION,
                    field=(
                        "spec.materializations.solvent_dielectric."
                        "environment_receipt_sha256"
                    ),
                    expected="target environment receipt SHA-256",
                    observed=environment_receipt_sha256,
                    evidence_ref="h5:/provenance/environment_receipt_sha256",
                )
            )
        if not isinstance(pyscf_version, str) or not pyscf_version.strip():
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_MATERIALIZATION,
                    field=(
                        "spec.materializations.solvent_dielectric."
                        "pyscf_version"
                    ),
                    expected="observed target PySCF version",
                    observed=pyscf_version,
                    evidence_ref="h5:/provenance/pyscf_version",
                )
            )
        expected = {
            "schema_version": ("chemsmart.pyscf-solvent-materialization.v1"),
            "field": "solvent_eps",
            "source": "pyscf.solvent.smd.solvent_db",
            "source_key": spec.get("solvent_id"),
            "value": spec.get("solvent_eps"),
            "unit": "dimensionless_relative_permittivity",
            "pyscf_version": pyscf_version,
            "environment_receipt_sha256": environment_receipt_sha256,
        }
        if not isinstance(solvent_record, Mapping) or any(
            not _equivalent(field, value, solvent_record.get(field, _MISSING))
            for field, value in expected.items()
        ):
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_MATERIALIZATION,
                    field="spec.materializations.solvent_dielectric",
                    expected=expected,
                    observed=solvent_record,
                    evidence_ref=(
                        "h5:/spec/materializations/solvent_dielectric"
                    ),
                )
            )
        else:
            value = solvent_record.get("value")
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(float(value))
                or float(value) <= 0
            ):
                violations.append(
                    PySCFViolation(
                        rule_id=RULE_PROVENANCE_MATERIALIZATION,
                        field="spec.solvent_eps",
                        expected="finite positive relative permittivity",
                        observed=value,
                        evidence_ref="h5:/spec/solvent_eps",
                    )
                )
    elif solvent_record is not None:
        violations.append(
            PySCFViolation(
                rule_id=RULE_PROVENANCE_MATERIALIZATION,
                field="spec.materializations.solvent_dielectric",
                expected="absent without a solvent model",
                observed=solvent_record,
                evidence_ref="h5:/spec/materializations/solvent_dielectric",
            )
        )

    violations.extend(
        _verify_response_plan(spec, materializations.get("td_response_plan"))
    )

    functional_record = materializations.get("functional_definition")
    xc = spec.get("xc")
    method = str(spec.get("method") or spec.get("ab_initio") or "").lower()
    is_hf = xc is None and method in PYSCF_AB_INITIO_METHODS
    is_dft = xc is not None
    if is_hf and functional_record is not None:
        violations.append(
            PySCFViolation(
                rule_id=RULE_PROVENANCE_MATERIALIZATION,
                field="spec.materializations.functional_definition",
                expected="absent for an HF calculation",
                observed=functional_record,
                evidence_ref=(
                    "h5:/spec/materializations/functional_definition"
                ),
            )
        )
    elif is_dft:
        expected = {
            "field": "xc",
            "source": "pyscf.dft.libxc.parse_xc",
            "source_key": spec.get("xc"),
        }
        record_valid = isinstance(functional_record, Mapping) and all(
            _equivalent(field, value, functional_record.get(field, _MISSING))
            for field, value in expected.items()
        )
        version = (
            functional_record.get("libxc_version")
            if isinstance(functional_record, Mapping)
            else None
        )
        definition_schema = (
            functional_record.get("schema_version")
            if isinstance(functional_record, Mapping)
            else None
        )
        parser_hybrid = (
            functional_record.get("parser_hybrid_decomposition")
            if isinstance(functional_record, Mapping)
            else None
        )
        exact_exchange = (
            functional_record.get("exact_exchange_fraction")
            if isinstance(functional_record, Mapping)
            else None
        )
        range_separation = (
            functional_record.get("range_separation_coefficients")
            if isinstance(functional_record, Mapping)
            else None
        )
        # Old immutable results used a misleading field name for the
        # ``parse_xc`` tuple.  Continue to read them as legacy evidence, but
        # all newly generated artifacts must carry the environment-bound v3
        # fields. V2 remains readable but is qualified below as legacy evidence.
        legacy_parser_hybrid = (
            functional_record.get("hybrid_coefficients")
            if isinstance(functional_record, Mapping)
            else None
        )
        functional_ids = (
            functional_record.get("functional_ids")
            if isinstance(functional_record, Mapping)
            else None
        )
        functional_factors = (
            functional_record.get("functional_factors")
            if isinstance(functional_record, Mapping)
            else None
        )
        common_valid = bool(
            record_valid
            and isinstance(version, str)
            and version.strip()
            and _positive_integer_sequence(functional_ids)
            and _finite_sequence(functional_factors)
            and len(functional_ids) == len(functional_factors)
        )
        if definition_schema == "chemsmart.pyscf-functional-definition.v3":
            pyscf_version = functional_record.get("pyscf_version")
            environment_receipt_sha256 = functional_record.get(
                "environment_receipt_sha256"
            )
            record_valid = bool(
                common_valid
                and _finite_sequence(parser_hybrid)
                and len(parser_hybrid) == 3
                and _finite_number(exact_exchange)
                and _finite_sequence(range_separation)
                and len(range_separation) == 3
                and isinstance(pyscf_version, str)
                and pyscf_version.strip()
                and _is_sha256(environment_receipt_sha256)
                and pyscf_version == provenance.get("pyscf_version")
                and version == provenance.get("libxc_version")
                and environment_receipt_sha256
                == provenance.get("environment_receipt_sha256")
            )
        elif definition_schema == "chemsmart.pyscf-functional-definition.v2":
            record_valid = bool(
                common_valid
                and _finite_sequence(parser_hybrid)
                and len(parser_hybrid) == 3
                and _finite_number(exact_exchange)
                and _finite_sequence(range_separation)
                and len(range_separation) == 3
            )
        elif definition_schema is None:
            record_valid = bool(
                common_valid and _finite_sequence(legacy_parser_hybrid)
            )
        else:
            record_valid = False
        if not record_valid:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_MATERIALIZATION,
                    field="spec.materializations.functional_definition",
                    expected={
                        **expected,
                        "libxc_version": "non-empty string",
                        "schema_version": (
                            "chemsmart.pyscf-functional-definition.v3 "
                            "or readable legacy v2"
                        ),
                        "pyscf_version": (
                            "v3 value equal to provenance.pyscf_version"
                        ),
                        "environment_receipt_sha256": (
                            "v3 value equal to provenance environment receipt"
                        ),
                        "parser_hybrid_decomposition": (
                            "three finite parser coefficients"
                        ),
                        "exact_exchange_fraction": "finite number",
                        "range_separation_coefficients": (
                            "three finite coefficients"
                        ),
                        "functional_ids": "positive integer sequence",
                        "functional_factors": (
                            "same-length finite numeric sequence"
                        ),
                    },
                    observed=functional_record,
                    evidence_ref=(
                        "h5:/spec/materializations/functional_definition"
                    ),
                )
            )
    elif not is_hf:
        violations.append(
            PySCFViolation(
                rule_id=RULE_PROVENANCE_MATERIALIZATION,
                field="spec.materializations.functional_definition",
                expected=(
                    "DFT record for non-null xc, or no record for explicit HF"
                ),
                observed={"xc": xc, "method": method},
                evidence_ref="h5:/spec",
            )
        )
    return violations


def _verify_response_plan(spec, record):
    """The response manifest names exactly what the spec asked for."""

    jobtype = str(spec.get("jobtype") or "").strip().lower()
    excited_root = spec.get("excited_state_root")
    requested = jobtype == "td" or (jobtype == "opt" and excited_root)
    if not requested:
        if record is None:
            return []
        return [
            PySCFViolation(
                rule_id=RULE_PROVENANCE_MATERIALIZATION,
                field="spec.materializations.td_response_plan",
                expected="absent without a response stage",
                observed=record,
                evidence_ref="h5:/spec/materializations/td_response_plan",
            )
        ]
    family = str(spec.get("reference_family") or "").strip().lower()
    module = "uks" if family == "uks" else "rks"
    response_method = str(spec.get("response_method") or "").strip().lower()
    expected = {
        "response_method": response_method,
        "state_manifold": str(spec.get("state_manifold") or "")
        .strip()
        .lower(),
        "nstates": spec.get("nstates"),
        "ground_state_reference_family": module,
        "response_factory_api": (
            f"pyscf.tdscf.{module}.{'TDA' if response_method == 'tda' else 'TDDFT'}"
        ),
        "execution_policy": "executable",
    }
    if not isinstance(record, Mapping) or any(
        not _equivalent(field, value, record.get(field, _MISSING))
        for field, value in expected.items()
    ):
        return [
            PySCFViolation(
                rule_id=RULE_PROVENANCE_MATERIALIZATION,
                field="spec.materializations.td_response_plan",
                expected=expected,
                observed=record,
                evidence_ref="h5:/spec/materializations/td_response_plan",
            )
        ]
    return []


def _result_advisory(rule_id, field, observed, evidence_ref, message):
    """Return one explicit non-blocking scientific qualification."""

    return {
        "schema_version": "chemsmart.pyscf-result-advisory.v1",
        "rule_id": str(rule_id),
        "field": str(field),
        "observed": observed,
        "evidence_ref": str(evidence_ref),
        "message": str(message),
    }


def _functional_materialization_validation(spec, provenance):
    """Classify target XC evidence without upgrading legacy artifacts."""

    xc = spec.get("xc")
    method = str(spec.get("method") or spec.get("ab_initio") or "").lower()
    materializations = spec.get("materializations")
    materializations = (
        materializations if isinstance(materializations, Mapping) else {}
    )
    record = materializations.get("functional_definition")
    if xc is None and method == "hf":
        return {
            "state": "not_applicable",
            "schema_version": None,
            "environment_bound": False,
        }, ()
    if not isinstance(record, Mapping):
        return {
            "state": "invalid",
            "schema_version": None,
            "environment_bound": False,
        }, ()
    schema_version = record.get("schema_version")
    if schema_version == "chemsmart.pyscf-functional-definition.v3":
        environment_bound = bool(
            record.get("pyscf_version") == provenance.get("pyscf_version")
            and record.get("libxc_version") == provenance.get("libxc_version")
            and record.get("environment_receipt_sha256")
            == provenance.get("environment_receipt_sha256")
            and _is_sha256(record.get("environment_receipt_sha256"))
        )
        return {
            "state": "environment_bound" if environment_bound else "invalid",
            "schema_version": schema_version,
            "environment_bound": environment_bound,
            "pyscf_version": record.get("pyscf_version"),
            "libxc_version": record.get("libxc_version"),
            "environment_receipt_sha256": record.get(
                "environment_receipt_sha256"
            ),
        }, ()
    if schema_version in {
        None,
        "chemsmart.pyscf-functional-definition.v2",
    }:
        advisory = _result_advisory(
            "pyscf.functional_definition.legacy_environment_unbound",
            "spec.materializations.functional_definition",
            schema_version or "legacy_v1",
            "h5:/spec/materializations/functional_definition",
            (
                "The functional definition is readable legacy evidence but "
                "does not bind both target PySCF/LibXC versions and the exact "
                "environment receipt."
            ),
        )
        return {
            "state": "legacy_environment_unbound",
            "schema_version": schema_version,
            "environment_bound": False,
        }, (advisory,)
    return {
        "state": "invalid",
        "schema_version": schema_version,
        "environment_bound": False,
    }, ()


def _spin_diagnostic_validation(
    results,
    status,
    *,
    multiplicity,
    representation,
    require_current=False,
):
    """Validate diagnostic integrity without imposing a chemistry cutoff."""

    requested_multiplicity = int(multiplicity)
    target_spin_square = (requested_multiplicity**2 - 1.0) / 4.0
    observation = {
        "state": "not_recorded",
        "requested_multiplicity": requested_multiplicity,
        "target_spin_square": target_spin_square,
        "observed_spin_square": None,
        "effective_multiplicity": None,
        "spin_square_deviation": None,
        "orbital_representation": representation,
        "numerical_equality_tolerance": _SPIN_DIAGNOSTIC_NUMERICAL_ATOL,
        "scientific_threshold_applied": False,
    }
    findings = []
    advisories = []
    properties = status.get("properties")
    properties = properties if isinstance(properties, Mapping) else {}
    property_record = properties.get("spin_square")
    property_status = (
        property_record.get("status")
        if isinstance(property_record, Mapping)
        else None
    )
    has_spin_square = "spin_square" in results
    has_effective = "spin_square_effective_multiplicity" in results
    if require_current and not isinstance(property_record, Mapping):
        findings.append(
            _result_finding(
                RULE_RESULT_CONTRACT,
                "status.properties.spin_square",
                "explicit current-contract property status",
                property_record,
                "h5:/status/properties/spin_square",
            )
        )
    elif require_current and property_status not in {"ok", "unavailable"}:
        findings.append(
            _result_finding(
                RULE_RESULT_CONTRACT,
                "status.properties.spin_square.status",
                ("ok", "unavailable"),
                property_status,
                "h5:/status/properties/spin_square/status",
            )
        )
    if not has_spin_square and not has_effective:
        observation["state"] = (
            "unavailable"
            if property_status == "unavailable"
            else "legacy_not_recorded"
        )
        if require_current:
            findings.append(
                _result_finding(
                    RULE_RESULT_SPIN_DIAGNOSTIC,
                    "results.spin_diagnostic",
                    (
                        "spin_square and "
                        "spin_square_effective_multiplicity datasets"
                    ),
                    {
                        "spin_square": False,
                        "effective_multiplicity": False,
                        "property_status": property_status,
                    },
                    "h5:/results",
                )
            )
        if property_status == "ok":
            findings.append(
                _result_finding(
                    RULE_RESULT_SPIN_DIAGNOSTIC,
                    "status.properties.spin_square",
                    "result datasets when property status is ok",
                    property_record,
                    "h5:/status/properties/spin_square",
                )
            )
        elif requested_multiplicity > 1 or property_status == "unavailable":
            advisories.append(
                _result_advisory(
                    "pyscf.spin_diagnostic.unavailable",
                    "results.spin_square",
                    property_record,
                    "h5:/status/properties/spin_square",
                    (
                        "No finite <S^2> diagnostic is available; the result "
                        "cannot support an unqualified spin-purity claim."
                    ),
                )
            )
        return observation, findings, advisories
    if has_spin_square != has_effective:
        findings.append(
            _result_finding(
                RULE_RESULT_SPIN_DIAGNOSTIC,
                "results.spin_diagnostic",
                "both spin_square and effective multiplicity datasets",
                {
                    "spin_square": has_spin_square,
                    "effective_multiplicity": has_effective,
                },
                "h5:/results",
            )
        )
        observation["state"] = "malformed"
        return observation, findings, advisories

    spin_array = _result_array(results.get("spin_square"))
    effective_array = _result_array(
        results.get("spin_square_effective_multiplicity")
    )
    spin_is_scalar = spin_array is not None and spin_array.size == 1
    effective_is_scalar = (
        effective_array is not None and effective_array.size == 1
    )
    if not spin_is_scalar or not effective_is_scalar:
        findings.append(
            _result_finding(
                RULE_RESULT_SPIN_DIAGNOSTIC,
                "results.spin_diagnostic",
                "two finite numeric scalars",
                {
                    "spin_square": _array_observation(spin_array),
                    "effective_multiplicity": _array_observation(
                        effective_array
                    ),
                },
                "h5:/results",
            )
        )
        observation["state"] = "malformed"
        return observation, findings, advisories
    spin_square = float(spin_array.reshape(-1)[0])
    effective_multiplicity = float(effective_array.reshape(-1)[0])
    observation.update(
        {
            "observed_spin_square": spin_square,
            "effective_multiplicity": effective_multiplicity,
            "spin_square_deviation": spin_square - target_spin_square,
        }
    )
    values_finite = math.isfinite(spin_square) and math.isfinite(
        effective_multiplicity
    )
    expected_effective = (
        math.sqrt(1.0 + 4.0 * max(spin_square, 0.0)) if values_finite else None
    )
    if (
        not values_finite
        or spin_square < -_SPIN_DIAGNOSTIC_NUMERICAL_ATOL
        or expected_effective is None
        or not math.isclose(
            effective_multiplicity,
            expected_effective,
            rel_tol=0.0,
            abs_tol=_SPIN_DIAGNOSTIC_NUMERICAL_ATOL,
        )
        or property_status != "ok"
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_SPIN_DIAGNOSTIC,
                "results.spin_diagnostic",
                {
                    "finite_nonnegative_spin_square": True,
                    "effective_multiplicity_formula": "sqrt(1 + 4 * <S^2>)",
                    "property_status": "ok",
                },
                {
                    "spin_square": spin_square,
                    "effective_multiplicity": effective_multiplicity,
                    "formula_value": expected_effective,
                    "property_status": property_status,
                },
                "h5:/results",
            )
        )
        observation["state"] = "malformed"
        return observation, findings, advisories

    deviation = spin_square - target_spin_square
    observation["state"] = "available"
    observation["interpretation"] = (
        "numerically_matches_target_eigenvalue"
        if math.isclose(
            spin_square,
            target_spin_square,
            rel_tol=0.0,
            abs_tol=_SPIN_DIAGNOSTIC_NUMERICAL_ATOL,
        )
        else "deviation_observed_without_universal_threshold"
    )
    if (
        observation["interpretation"]
        != "numerically_matches_target_eigenvalue"
    ):
        advisories.append(
            _result_advisory(
                "pyscf.spin_diagnostic.deviation_observed",
                "results.spin_square",
                {
                    "target": target_spin_square,
                    "observed": spin_square,
                    "deviation": deviation,
                },
                "h5:/results/spin_square",
                (
                    "A finite <S^2> deviation was observed. No universal "
                    "spin-contamination acceptance threshold was applied."
                ),
            )
        )
    return observation, findings, advisories


def _finite_sequence(value):
    return bool(
        isinstance(value, Collection)
        and not isinstance(value, (str, bytes, Mapping))
        and value
        and all(
            not isinstance(item, bool)
            and isinstance(item, Real)
            and math.isfinite(float(item))
            for item in value
        )
    )


def _finite_number(value):
    return bool(
        not isinstance(value, bool)
        and isinstance(value, Real)
        and math.isfinite(float(value))
    )


def _scalar_number(value):
    """The one finite number a stored result holds, or None.

    ``_finite_number`` beside it is a predicate, and a predicate used as
    a value is how the correlated-component check came to perform no
    check at all: every entry of a ``results`` mapping read back from
    HDF5 is a NumPy array rather than a Python float, so the predicate
    answered False for each component, the sum that followed compared
    ``False + False`` with ``False`` and agreed, and a component that was
    not there at all was never reported because a bool is never None.
    A value question gets a value answer.
    """

    array = _result_array(value)
    if array is None or array.size != 1:
        return None
    number = float(array.reshape(-1)[0])
    return number if math.isfinite(number) else None


def _positive_integer_sequence(value):
    return bool(
        isinstance(value, Collection)
        and not isinstance(value, (str, bytes, Mapping))
        and value
        and all(
            not isinstance(item, bool)
            and isinstance(item, Integral)
            and int(item) > 0
            for item in value
        )
    )


def frequency_validation_receipt(
    *,
    symbols,
    positions,
    frequencies,
    expected_imaginary_modes=None,
    imaginary_mode_cutoff_cm1=None,
):
    """Validate a harmonic-frequency result without running chemistry.

    The mode-count oracle is ``3N-5`` for a linear molecule and ``3N-6`` for
    a nonlinear molecule. A single atom has zero vibrational modes. Linearity
    is classified from the result geometry using a recorded relative singular-
    value tolerance. Mode count, finiteness, and geometry classification are
    invariant checks. Stationary-point classification is separate and occurs
    only when a host-owned policy explicitly supplies an imaginary-mode count
    and cutoff; a bare Hessian request does not imply a local minimum.
    """
    classify_stationary_point = expected_imaginary_modes is not None
    if classify_stationary_point:
        if (
            isinstance(expected_imaginary_modes, bool)
            or not isinstance(expected_imaginary_modes, Integral)
            or int(expected_imaginary_modes) < 0
        ):
            raise ValueError(
                "expected_imaginary_modes must be a non-negative integer"
            )
        if (
            isinstance(imaginary_mode_cutoff_cm1, bool)
            or not isinstance(imaginary_mode_cutoff_cm1, Real)
            or not math.isfinite(float(imaginary_mode_cutoff_cm1))
            or float(imaginary_mode_cutoff_cm1) < 0
        ):
            raise ValueError(
                "imaginary_mode_cutoff_cm1 must be finite and non-negative"
            )
        expected_imaginary_modes = int(expected_imaginary_modes)
        imaginary_mode_cutoff_cm1 = float(imaginary_mode_cutoff_cm1)
    elif imaginary_mode_cutoff_cm1 is not None:
        # A cutoff without an approved target mode count is not a stationary-
        # point policy.  Ignore the default value while keeping explicit
        # policy-free validation possible through ``None, None``.
        imaginary_mode_cutoff_cm1 = None
    symbol_list = list(symbols or [])
    findings = []
    geometry_class = "unknown"
    expected_mode_count = None
    #: For a polyatomic, the two counts a correct harmonic analysis may
    #: carry; the run's own count picks one and everything else follows.
    admissible_mode_counts = None

    try:
        coordinates = np.asarray(positions, dtype=float)
    except (TypeError, ValueError):
        coordinates = np.empty((0, 3), dtype=float)
    geometry_valid = (
        coordinates.shape == (len(symbol_list), 3)
        and len(symbol_list) > 0
        and bool(np.isfinite(coordinates).all())
    )
    if not geometry_valid:
        findings.append(
            PySCFViolation(
                rule_id=RULE_FREQUENCY_GEOMETRY,
                field="results.positions",
                expected=(
                    f"finite ({len(symbol_list)}, 3) Cartesian geometry"
                ),
                observed={
                    "shape": list(coordinates.shape),
                    "all_finite": bool(np.isfinite(coordinates).all()),
                },
                evidence_ref="h5:/results/positions",
            )
        )
    elif len(symbol_list) == 1:
        geometry_class = "atomic"
        expected_mode_count = 0
    elif len(symbol_list) == 2:
        geometry_class = "linear"
        expected_mode_count = 1
    else:
        scale, second, linear = _linearity_metrics(coordinates)
        if linear is None:
            findings.append(
                PySCFViolation(
                    rule_id=RULE_FREQUENCY_GEOMETRY,
                    field="results.positions",
                    expected="non-degenerate molecular geometry",
                    observed={"largest_singular_value": scale},
                    evidence_ref="h5:/results/positions",
                )
            )
        else:
            # Both counts are admissible for a polyatomic, and which one
            # a run carries is the program's own reading of its geometry,
            # not a tolerance this host gets to impose. HNC reached by a
            # live IRC (CUHK g1-hcn-ts, 2026-09-20) is 0.047 degrees from
            # linear; PySCF's harmonic analysis produced 3N-5 = 4 modes
            # and this rule, whose relative transverse tolerance answers
            # about 0.01 degrees for a triatomic, demanded 3 and failed a
            # Hessian that is exactly right. What replaces the tolerance
            # is not a looser one: the count is admitted if it is 3N-6 or
            # 3N-5, the arrays are held to whichever it is, and the
            # independent spectrum reconstruction then runs at the
            # translation-rotation rank that count implies -- so a wrong
            # count no longer passes on a geometric opinion but fails on
            # the physics, because the reconstructed spectrum will not be
            # the reported one. At rank 6 this artifact reconstructs to
            # [551.33, 2133.66, 3801.77]; at rank 5, to PySCF's own four
            # frequencies to 0.0000 cm-1.
            geometry_class = "linear" if linear else "nonlinear"
            admissible_mode_counts = (
                3 * len(symbol_list) - 6,
                3 * len(symbol_list) - 5,
            )

    complex_frequencies = False
    frequency_shape = None
    try:
        raw_frequencies = np.asarray(frequencies)
        frequency_shape = list(raw_frequencies.shape)
        complex_frequencies = bool(np.iscomplexobj(raw_frequencies))
        if complex_frequencies:
            values = np.asarray(raw_frequencies.real, dtype=float).reshape(-1)
        else:
            values = np.asarray(raw_frequencies, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        values = np.asarray([], dtype=float)

    if frequency_shape is None or len(frequency_shape) != 1:
        findings.append(
            PySCFViolation(
                rule_id=RULE_FREQUENCY_MODE_COUNT,
                field="results.vibrational_frequencies",
                expected="one-dimensional frequency vector",
                observed=frequency_shape,
                evidence_ref="h5:/results/vibrational_frequencies",
            )
        )
    if admissible_mode_counts is not None:
        # A polyatomic whose linearity is not a question this host
        # answers: either count stands, and the count the run carries is
        # what every array below and the spectrum reconstruction are then
        # held to.
        if len(values) in admissible_mode_counts:
            expected_mode_count = len(values)
        else:
            findings.append(
                PySCFViolation(
                    rule_id=RULE_FREQUENCY_MODE_COUNT,
                    field="results.vibrational_frequencies",
                    expected={
                        "3N-6": admissible_mode_counts[0],
                        "3N-5 (linear rotor)": admissible_mode_counts[1],
                    },
                    observed=len(values),
                    evidence_ref="h5:/results/vibrational_frequencies",
                )
            )
    elif (
        expected_mode_count is not None and len(values) != expected_mode_count
    ):
        findings.append(
            PySCFViolation(
                rule_id=RULE_FREQUENCY_MODE_COUNT,
                field="results.vibrational_frequencies",
                expected=expected_mode_count,
                observed=len(values),
                evidence_ref="h5:/results/vibrational_frequencies",
            )
        )

    finite_mask = np.isfinite(values)
    nonfinite_count = int((~finite_mask).sum())
    if complex_frequencies or nonfinite_count:
        findings.append(
            PySCFViolation(
                rule_id=RULE_FREQUENCY_NONFINITE,
                field="results.vibrational_frequencies",
                expected="finite real wavenumbers",
                observed={
                    "complex": complex_frequencies,
                    "nonfinite_count": nonfinite_count,
                },
                evidence_ref="h5:/results/vibrational_frequencies",
            )
        )

    finite_values = values[finite_mask]
    imaginary_count = None
    soft_negative_count = None
    if classify_stationary_point:
        imaginary_count = int(
            (finite_values < -imaginary_mode_cutoff_cm1).sum()
        )
        soft_negative_count = int(
            (
                (finite_values < 0.0)
                & (finite_values >= -imaginary_mode_cutoff_cm1)
            ).sum()
        )
    if (
        classify_stationary_point
        and imaginary_count != expected_imaginary_modes
    ):
        findings.append(
            PySCFViolation(
                rule_id=RULE_FREQUENCY_IMAGINARY,
                field="results.vibrational_frequencies",
                expected={
                    "imaginary_mode_count": expected_imaginary_modes,
                    "convention": (
                        "real wavenumber strictly below the negative cutoff"
                    ),
                    "imaginary_mode_cutoff_cm1": (imaginary_mode_cutoff_cm1),
                },
                observed={
                    "imaginary_mode_count": imaginary_count,
                    "soft_negative_mode_count": soft_negative_count,
                },
                evidence_ref="h5:/results/vibrational_frequencies",
            )
        )

    return {
        "schema_version": FREQUENCY_VALIDATION_SCHEMA_VERSION,
        "state": "validated" if not findings else "failed",
        "atom_count": len(symbol_list),
        # Kept as the observation it is: how far from a linear rotor
        # this structure sits, measured but never graded.
        "geometry_class": geometry_class,
        "linearity_relative_tolerance": _LINEARITY_RELATIVE_TOLERANCE,
        "expected_mode_count": expected_mode_count,
        "admissible_mode_counts": (
            list(admissible_mode_counts) if admissible_mode_counts else None
        ),
        "observed_mode_count": len(values),
        "finite_mode_count": int(finite_mask.sum()),
        "stationary_point_classification": (
            "classified" if classify_stationary_point else "unclassified"
        ),
        "expected_imaginary_mode_count": expected_imaginary_modes,
        "observed_imaginary_mode_count": imaginary_count,
        "soft_negative_mode_count": soft_negative_count,
        "imaginary_mode_cutoff_cm1": imaginary_mode_cutoff_cm1,
        "frequency_unit": "cm^-1",
        "findings": findings,
    }


def _result_contract_validation(spec, status):
    """Classify strict current records without upgrading historical HDF5."""

    from chemsmart.jobs.pyscf.writer import (
        RESULT_CONTRACT_VERSION,
        SUPPORTED_RESULT_CONTRACT_VERSIONS,
    )

    observed = spec.get("result_contract_version")
    # A previous supported contract is a superset relation, never a
    # downgrade: its artifacts stay executed evidence and legal geometry
    # sources, and only the datasets the newer contract added are absent.
    observation = {
        "state": (
            "current"
            if observed == RESULT_CONTRACT_VERSION
            else (
                "supported"
                if observed in SUPPORTED_RESULT_CONTRACT_VERSIONS
                else "legacy"
            )
        ),
        "observed_version": observed,
        "current_version": RESULT_CONTRACT_VERSION,
        "supported_versions": list(SUPPORTED_RESULT_CONTRACT_VERSIONS),
        "new_execution_admissible": (
            observed in SUPPORTED_RESULT_CONTRACT_VERSIONS
        ),
    }
    findings = []
    advisories = []
    if observed is not None and observed not in (
        SUPPORTED_RESULT_CONTRACT_VERSIONS
    ):
        observation["state"] = "unsupported"
        observation["new_execution_admissible"] = False
        findings.append(
            _result_finding(
                RULE_RESULT_CONTRACT,
                "spec.result_contract_version",
                RESULT_CONTRACT_VERSION,
                observed,
                "h5:/spec/result_contract_version",
            )
        )
        return observation, False, findings, advisories
    if observed is None:
        advisories.append(
            _result_advisory(
                "pyscf.result.legacy_contract",
                "spec.result_contract_version",
                None,
                "h5:/spec",
                (
                    "The artifact remains readable historical evidence but "
                    "cannot validate a new execution or artifact-producing "
                    "data edge."
                ),
            )
        )
        return observation, False, findings, advisories

    required_spec = {
        "reference_family",
        "charge",
        "multiplicity",
        "spin",
        "num_electrons",
        "nelec",
    }
    required_status = {
        "stages",
        "engine_complete",
        "normal_termination",
        "failure",
        "properties",
    }
    for field in sorted(required_spec):
        if field not in spec:
            findings.append(
                _result_finding(
                    RULE_RESULT_CONTRACT,
                    f"spec.{field}",
                    "explicit current-contract field",
                    "<missing>",
                    f"h5:/spec/{field}",
                )
            )
    for field in sorted(required_status):
        if field not in status:
            findings.append(
                _result_finding(
                    RULE_RESULT_CONTRACT,
                    f"status.{field}",
                    "explicit current-contract field",
                    "<missing>",
                    f"h5:/status/{field}",
                )
            )
    if findings:
        observation["state"] = "invalid"
        observation["new_execution_admissible"] = False
    return observation, True, findings, advisories


_REFERENCE_RUNTIME_CLASSES = {
    "rks": frozenset(
        {
            "pyscf.dft.rks.RKS",
            "gpu4pyscf.dft.rks.RKS",
        }
    ),
    "uks": frozenset(
        {
            "pyscf.dft.uks.UKS",
            "gpu4pyscf.dft.uks.UKS",
        }
    ),
    "rhf": frozenset(
        {
            "pyscf.scf.hf.RHF",
            "gpu4pyscf.scf.hf.RHF",
        }
    ),
    "rohf": frozenset(
        {
            "pyscf.scf.rohf.ROHF",
            "pyscf.scf.rohf.HF1e",
            "gpu4pyscf.scf.rohf.ROHF",
            "gpu4pyscf.scf.rohf.HF1e",
        }
    ),
    "uhf": frozenset(
        {
            "pyscf.scf.uhf.UHF",
            "gpu4pyscf.scf.uhf.UHF",
        }
    ),
}


def _expected_reference_family(spec, *, symbols, charge, multiplicity):
    atomic_numbers = _expected_atomic_numbers(symbols)
    electron_count = sum(atomic_numbers) - int(charge)
    spin = int(multiplicity) - 1
    xc = spec.get("xc")
    if xc is not None:
        return ("rks" if spin == 0 else "uks"), electron_count == 1
    method = str(spec.get("method") or spec.get("ab_initio") or "").lower()
    # Every ab initio method -- HF and the correlated methods computed on
    # an HF reference -- runs the same mean field; only the family of that
    # reference is a runtime fact to check.
    if method not in PYSCF_AB_INITIO_METHODS:
        return None, electron_count == 1
    if spin == 0:
        return "rhf", electron_count == 1
    if electron_count == 1:
        return "rohf", True
    return "uhf", False


def _runtime_reference_family(runtime):
    if not isinstance(runtime, Mapping):
        return None, None, ()
    mean_field_class = runtime.get("mean_field_class")
    mro = runtime.get("mean_field_mro")
    mro = (
        tuple(str(value) for value in mro)
        if isinstance(mro, Collection) and not isinstance(mro, (str, bytes))
        else ()
    )
    if not isinstance(mean_field_class, str) or not mean_field_class:
        return None, mean_field_class, mro
    if not mro or mro[0] != mean_field_class:
        return None, mean_field_class, mro
    observed = frozenset((mean_field_class, *mro))
    for family in ("rks", "uks", "rohf", "uhf", "rhf"):
        if observed.intersection(_REFERENCE_RUNTIME_CLASSES[family]):
            return family, mean_field_class, mro
    return None, mean_field_class, mro


def _validate_reference_family(
    spec,
    provenance,
    *,
    symbols,
    charge,
    multiplicity,
    orbital_representation,
    require_current,
):
    expected, one_electron = _expected_reference_family(
        spec,
        symbols=symbols,
        charge=charge,
        multiplicity=multiplicity,
    )
    declared = spec.get("reference_family")
    runtime = provenance.get("runtime")
    runtime_family, mean_field_class, mean_field_mro = (
        _runtime_reference_family(runtime)
    )
    observation = {
        "state": "verified",
        "expected_family": expected,
        "declared_family": declared,
        "runtime_family": runtime_family,
        "mean_field_class": mean_field_class,
        "mean_field_mro": mean_field_mro,
        "one_electron_semantics": one_electron,
        "orbital_representation": orbital_representation,
    }
    findings = []
    if not require_current:
        observation["state"] = "legacy_not_recorded"
        return observation, findings
    if expected is None or declared != expected:
        findings.append(
            _result_finding(
                RULE_RESULT_REFERENCE,
                "spec.reference_family",
                expected or "registered HF/DFT reference family",
                declared,
                "h5:/spec/reference_family",
            )
        )
    if runtime_family != expected:
        findings.append(
            _result_finding(
                RULE_RESULT_REFERENCE,
                "provenance.runtime.mean_field_class",
                {
                    "reference_family": expected,
                    "known_runtime_classes": tuple(
                        sorted(_REFERENCE_RUNTIME_CLASSES.get(expected, ()))
                    ),
                    "one_electron_semantics": one_electron,
                },
                {
                    "mean_field_class": mean_field_class,
                    "mean_field_mro": mean_field_mro,
                    "derived_family": runtime_family,
                },
                "h5:/provenance/runtime/mean_field_class",
            )
        )
    expected_representation = (
        "unrestricted" if expected in {"uks", "uhf"} else "restricted"
    )
    if (
        expected is not None
        and orbital_representation != expected_representation
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_REFERENCE,
                "results.mo_energy/mo_occ.reference_representation",
                expected_representation,
                orbital_representation,
                "h5:/results",
            )
        )
    if findings:
        observation["state"] = "invalid"
    return observation, findings


def _result_validation_conventions():
    """Return the convention rules that govern how a result is expressed.

    Imported lazily so the program layer keeps no import-time dependency on the
    agent package; the program layer stays usable without it.
    """

    try:
        from chemsmart.agent.skills.conventions import conventions_for_scope
    except ImportError:  # pragma: no cover - agent package always ships today
        return ()
    return conventions_for_scope("result_validation")


def validate_pyscf_result(
    h5_path,
    *,
    settings,
    expected_jobtype,
    expected_charge,
    expected_multiplicity,
    expected_symbols,
    expected_positions=None,
    expected_receipt=None,
):
    """Apply one scientific result contract to CLI and agent executions.

    The validator is intentionally pure: it reads the immutable HDF5 artifact
    and compares it with host-owned expectations, but launches no chemistry and
    mutates no state. Hessian symmetry, finite physical arrays, and result
    identity are engine/artifact invariants; the order of the stationary
    point a Hessian describes is not the runner's word -- the agent host
    judges it on one program-neutral rule -- so a green Hessian is
    ``validated`` here whatever its frequencies say.
    """

    jobtype = _normalize_result_jobtype(expected_jobtype)
    required_stages = tuple(
        _requested_stages(
            {
                "jobtype": jobtype,
                "ab_initio": _member(settings, "ab_initio", None),
                "excited_state_root": _member(
                    settings, "excited_state_root", None
                ),
            }
        )
    )
    expected_symbols = tuple(str(value) for value in expected_symbols or ())
    findings: list[PySCFViolation] = []
    # Convention rules contributed by domain-knowledge skills travel with the
    # receipt so the expression convention in force is auditable.  They are
    # disclosure only: they carry no accuracy or readiness authority and never
    # change ``state`` or ``findings``, so a run with skills disabled produces
    # an identical verdict.
    advisories: list[dict[str, Any]] = [
        item.as_dict() for item in _result_validation_conventions()
    ]
    frequency = {
        "schema_version": FREQUENCY_VALIDATION_SCHEMA_VERSION,
        "state": "not_applicable",
        "findings": [],
    }
    hessian_observation = {
        "required": jobtype == "hess",
        "shape": None,
        "all_finite": None,
        "symmetric": None,
        "symmetry_relative_tolerance": _HESSIAN_SYMMETRY_RTOL,
        "symmetry_absolute_tolerance": _HESSIAN_SYMMETRY_ATOL,
        "raw_max_abs_antisymmetry_eh_per_bohr2": None,
        "raw_antisymmetry_limit_eh_per_bohr2": None,
        "raw_symmetrization_admissible": None,
        "consistency": {
            "state": "not_applicable" if jobtype != "hess" else "pending",
            "algorithm": "independent-mass-weighted-projection-v1",
            "absolute_tolerance_cm1": _HESSIAN_FREQUENCY_ATOL_CM1,
            "relative_tolerance": _HESSIAN_FREQUENCY_RTOL,
        },
    }
    geometry_observation = {
        "fixed_geometry_required": jobtype in FIXED_GEOMETRY_JOBTYPES,
        "unit": "Angstrom",
        "absolute_tolerance_angstrom": _FIXED_GEOMETRY_ATOL_ANGSTROM,
        "matches_input": None,
    }
    electronic_state_observation = {
        "expected_electron_count": None,
        "expected_alpha_beta": None,
        "observed_electron_count": None,
        "observed_alpha_beta": None,
        "orbital_representation": None,
    }
    spin_diagnostic_observation = {
        "state": "not_evaluated",
        "requested_multiplicity": int(expected_multiplicity),
        "scientific_threshold_applied": False,
    }
    materialization_observation = {
        "functional_definition": {
            "state": "not_evaluated",
            "environment_bound": False,
        }
    }
    status_observation = {
        "required_stage_set": tuple(sorted(required_stages)),
        "observed_stage_set": (),
        "stage_set_exact": False,
        "failure_absent": None,
    }
    contract_observation = {
        "state": "not_evaluated",
        "observed_version": None,
        "current_version": None,
        "new_execution_admissible": False,
    }
    reference_observation = {
        "state": "not_evaluated",
        "expected_family": None,
        "declared_family": None,
        "runtime_family": None,
        "mean_field_class": None,
        "one_electron_semantics": False,
    }

    try:
        from chemsmart.io.pyscf.output import read_pyscf_h5

        spec, provenance, status, results = read_pyscf_h5(h5_path)
    except Exception as exc:
        finding = PySCFViolation(
            rule_id=RULE_RESULT_READ,
            field="result_artifact",
            expected="readable ChemSmart PySCF HDF5 result",
            observed=type(exc).__name__,
            evidence_ref="h5:/",
        )
        return {
            "schema_version": RESULT_VALIDATION_SCHEMA_VERSION,
            "state": "failed",
            "jobtype": jobtype,
            "required_stages": required_stages,
            "observed_stages": (),
            "charge": None,
            "multiplicity": None,
            "symbols": (),
            "geometry_validation": geometry_observation,
            "electronic_state_validation": electronic_state_observation,
            "spin_diagnostic_validation": spin_diagnostic_observation,
            "materialization_validation": materialization_observation,
            "contract_validation": contract_observation,
            "reference_validation": reference_observation,
            "status_validation": status_observation,
            "frequency_validation": frequency,
            "hessian_validation": hessian_observation,
            "advisories": advisories,
            "findings": [finding],
        }

    if not isinstance(spec, Mapping):
        spec = {}
    if not isinstance(provenance, Mapping):
        provenance = {}
    if not isinstance(status, Mapping):
        status = {}
    if not isinstance(results, Mapping):
        results = {}

    (
        contract_observation,
        current_result_contract,
        contract_findings,
        contract_advisories,
    ) = _result_contract_validation(spec, status)
    findings.extend(contract_findings)
    advisories.extend(contract_advisories)

    verification_settings = _result_verification_settings(
        settings=settings,
        jobtype=jobtype,
        charge=expected_charge,
        multiplicity=expected_multiplicity,
    )
    findings.extend(
        verify_provenance(
            verification_settings,
            h5_path,
            expected_receipt=expected_receipt,
        )
    )
    if not expected_receipt:
        findings.extend(_verify_result_units(h5_path))
    findings.extend(_verify_materializations(spec, provenance))
    findings.extend(_verify_result_settings_identity(spec, provenance))
    (
        materialization_observation["functional_definition"],
        materialization_advisories,
    ) = _functional_materialization_validation(spec, provenance)
    advisories.extend(materialization_advisories)

    if spec.get("program") != "pyscf":
        findings.append(
            _result_finding(
                RULE_RESULT_IDENTITY,
                "spec.program",
                "pyscf",
                spec.get("program"),
                "h5:/spec/program",
            )
        )
    observed_jobtype = _normalize_result_jobtype(spec.get("jobtype"))
    if observed_jobtype != jobtype:
        findings.append(
            _result_finding(
                RULE_RESULT_STAGE,
                "spec.jobtype",
                jobtype,
                spec.get("jobtype"),
                "h5:/spec/jobtype",
            )
        )
    observed_stages = tuple(str(value) for value in spec.get("stages") or ())
    if observed_stages != required_stages:
        findings.append(
            _result_finding(
                RULE_RESULT_STAGE,
                "spec.stages",
                required_stages,
                observed_stages,
                "h5:/spec/stages",
            )
        )
    stage_statuses = status.get("stages")
    if not isinstance(stage_statuses, Mapping):
        stage_statuses = {}
    observed_status_stages = tuple(sorted(str(key) for key in stage_statuses))
    required_status_stages = tuple(sorted(required_stages))
    status_observation["observed_stage_set"] = observed_status_stages
    status_observation["stage_set_exact"] = (
        observed_status_stages == required_status_stages
    )
    if observed_status_stages != required_status_stages:
        findings.append(
            _result_finding(
                RULE_RESULT_STAGE,
                "status.stages",
                required_status_stages,
                observed_status_stages,
                "h5:/status/stages",
            )
        )
    for stage in required_stages:
        stage_status = stage_statuses.get(stage)
        converged = (
            stage_status.get("converged")
            if isinstance(stage_status, Mapping)
            else None
        )
        if converged is not True:
            findings.append(
                _result_finding(
                    RULE_RESULT_STAGE,
                    f"status.stages.{stage}.converged",
                    True,
                    converged,
                    f"h5:/status/stages/{stage}/converged",
                )
            )
        if stage == "opt":
            optimizer_converged = (
                stage_status.get("optimizer_converged")
                if isinstance(stage_status, Mapping)
                else None
            )
            final_scf_converged = (
                stage_status.get("final_scf_converged")
                if isinstance(stage_status, Mapping)
                else None
            )
            for field, value in (
                ("optimizer_converged", optimizer_converged),
                ("final_scf_converged", final_scf_converged),
            ):
                if value is not True:
                    findings.append(
                        _result_finding(
                            RULE_RESULT_STAGE,
                            f"status.stages.opt.{field}",
                            True,
                            value,
                            f"h5:/status/stages/opt/{field}",
                        )
                    )
            expected_aggregate = bool(
                optimizer_converged is True and final_scf_converged is True
            )
            if type(converged) is not bool or converged != expected_aggregate:
                findings.append(
                    _result_finding(
                        RULE_RESULT_STAGE,
                        "status.stages.opt.converged",
                        {
                            "value": expected_aggregate,
                            "derivation": (
                                "optimizer_converged AND "
                                "final_scf_converged"
                            ),
                        },
                        converged,
                        "h5:/status/stages/opt",
                    )
                )
    ts_observation = None
    if "ts" in required_stages:
        ts_observation, ts_findings = _validate_ts_results(
            results,
            stage_statuses,
            expected_symbols=expected_symbols,
        )
        findings.extend(ts_findings)
    irc_observation = None
    if "irc" in required_stages:
        irc_observation, irc_findings = _validate_irc_results(
            results,
            stage_statuses,
            spec,
            expected_symbols=expected_symbols,
        )
        findings.extend(irc_findings)
    if "td" in required_stages:
        findings.extend(
            _validate_excited_state_results(results, stage_statuses)
        )
    if "corr" in required_stages:
        findings.extend(
            _validate_correlated_results(results, stage_statuses, spec)
        )
    # The decomposition is read off every completed run, whatever stages
    # it ran, because what the SCF put into its own total is a property
    # of the reference and not of a stage.  A run whose engine did not
    # finish never reached the property block and is not held to it.
    if (
        status.get("engine_complete") is True
        and contract_observation.get("state") == "current"
    ):
        findings.extend(_validate_energy_decomposition(results, spec))
    if status.get("engine_complete") is not True:
        findings.append(
            _result_finding(
                RULE_RESULT_STAGE,
                "status.engine_complete",
                True,
                status.get("engine_complete"),
                "h5:/status/engine_complete",
            )
        )
    if status.get("normal_termination") is not True:
        findings.append(
            _result_finding(
                RULE_RESULT_STAGE,
                "status.normal_termination",
                True,
                status.get("normal_termination"),
                "h5:/status/normal_termination",
            )
        )
    failure = status.get("failure")
    failure_absent = failure is None
    status_observation["failure_absent"] = failure_absent
    if status.get("normal_termination") is True and not failure_absent:
        findings.append(
            _result_finding(
                RULE_RESULT_STAGE,
                "status.normal_termination",
                "incompatible with a recorded failure",
                {"normal_termination": True, "failure": failure},
                "h5:/status/failure",
            )
        )

    observed_charge = spec.get("charge")
    observed_multiplicity = spec.get("multiplicity")
    observed_state = (observed_charge, observed_multiplicity)
    expected_state = (int(expected_charge), int(expected_multiplicity))
    state_types_valid = bool(
        not isinstance(observed_charge, bool)
        and isinstance(observed_charge, Integral)
        and not isinstance(observed_multiplicity, bool)
        and isinstance(observed_multiplicity, Integral)
    )
    if (
        not state_types_valid
        or tuple(
            int(value)
            for value in observed_state
            if isinstance(value, Integral)
        )
        != expected_state
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_STATE,
                "spec.electronic_state",
                {
                    "charge": expected_state[0],
                    "multiplicity": expected_state[1],
                    "types": "integer, never boolean",
                },
                observed_state,
                "h5:/spec",
            )
        )

    observed_symbols = tuple(str(value) for value in spec.get("symbols") or ())
    if not expected_symbols or observed_symbols != expected_symbols:
        findings.append(
            _result_finding(
                RULE_RESULT_IDENTITY,
                "spec.symbols",
                expected_symbols or "non-empty host-bound atom order",
                observed_symbols,
                "h5:/spec/symbols",
            )
        )
    if str(spec.get("unit") or "").strip().lower() != "angstrom":
        findings.append(
            _result_finding(
                RULE_RESULT_GEOMETRY,
                "spec.unit",
                "Angstrom",
                spec.get("unit"),
                "h5:/spec/unit",
            )
        )

    positions = _result_array(results.get("positions"))
    input_positions = _result_array(expected_positions)
    if positions is None or positions.shape != (len(expected_symbols), 3):
        findings.append(
            _result_finding(
                RULE_RESULT_GEOMETRY,
                "results.positions",
                (len(expected_symbols), 3),
                _array_observation(positions),
                "h5:/results/positions",
            )
        )
    elif jobtype in FIXED_GEOMETRY_JOBTYPES:
        input_valid = bool(
            input_positions is not None
            and input_positions.shape == (len(expected_symbols), 3)
            and np.isfinite(input_positions).all()
        )
        if not input_valid:
            findings.append(
                _result_finding(
                    RULE_RESULT_GEOMETRY,
                    "expected_positions",
                    (
                        f"finite ({len(expected_symbols)}, 3) input geometry "
                        "in Angstrom"
                    ),
                    _array_observation(input_positions),
                    "host:input_config.positions",
                )
            )
        else:
            matches_input = bool(
                np.allclose(
                    positions,
                    input_positions,
                    rtol=0.0,
                    atol=_FIXED_GEOMETRY_ATOL_ANGSTROM,
                )
            )
            geometry_observation["matches_input"] = matches_input
            if not matches_input:
                findings.append(
                    _result_finding(
                        RULE_RESULT_GEOMETRY,
                        "results.positions",
                        {
                            "input_positions": input_positions.tolist(),
                            "absolute_tolerance_angstrom": (
                                _FIXED_GEOMETRY_ATOL_ANGSTROM
                            ),
                        },
                        positions.tolist(),
                        "h5:/results/positions",
                    )
                )
    elif jobtype in PYSCF_MOVING_STAGES:
        # An optimisation and an IRC branch are the stages allowed to change
        # coordinates.  The final geometry remains shape/finite checked above
        # and atom order is independently bound by symbols and atomic
        # numbers; an IRC's path is held to both ends below.
        geometry_observation["matches_input"] = f"not_required_for_{jobtype}"
    elif not bool(np.isfinite(positions).all()):
        findings.append(
            _result_finding(
                RULE_RESULT_NONFINITE,
                "results.positions",
                "finite Cartesian geometry",
                _array_observation(positions),
                "h5:/results/positions",
            )
        )

    atomic_numbers = _result_array(results.get("atomic_numbers"))
    expected_atomic_numbers = _expected_atomic_numbers(expected_symbols)
    if (
        atomic_numbers is None
        or atomic_numbers.shape != (len(expected_symbols),)
        or not bool(np.isfinite(atomic_numbers).all())
        or not np.array_equal(
            atomic_numbers,
            np.asarray(expected_atomic_numbers, dtype=float),
        )
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_IDENTITY,
                "results.atomic_numbers",
                expected_atomic_numbers,
                _array_observation(atomic_numbers),
                "h5:/results/atomic_numbers",
            )
        )

    energies = _result_array(results.get("energies"))
    if energies is None or energies.ndim != 1 or energies.size < 1:
        findings.append(
            _result_finding(
                RULE_RESULT_SHAPE,
                "results.energies",
                "non-empty one-dimensional energy history",
                _array_observation(energies),
                "h5:/results/energies",
            )
        )
    elif not bool(np.isfinite(energies).all()):
        findings.append(
            _result_finding(
                RULE_RESULT_NONFINITE,
                "results.energies",
                "finite energies",
                _array_observation(energies),
                "h5:/results/energies",
            )
        )

    _validate_orbital_arrays(
        results,
        findings,
        symbols=expected_symbols,
        charge=int(expected_charge),
        multiplicity=int(expected_multiplicity),
        observation=electronic_state_observation,
    )
    reference_observation, reference_findings = _validate_reference_family(
        spec,
        provenance,
        symbols=expected_symbols,
        charge=int(expected_charge),
        multiplicity=int(expected_multiplicity),
        orbital_representation=electronic_state_observation[
            "orbital_representation"
        ],
        require_current=current_result_contract,
    )
    findings.extend(reference_findings)
    _validate_result_electron_metadata(
        spec,
        findings,
        symbols=expected_symbols,
        charge=int(expected_charge),
        multiplicity=int(expected_multiplicity),
    )
    (
        spin_diagnostic_observation,
        spin_findings,
        spin_advisories,
    ) = _spin_diagnostic_validation(
        results,
        status,
        multiplicity=int(expected_multiplicity),
        representation=electronic_state_observation["orbital_representation"],
        require_current=current_result_contract,
    )
    findings.extend(spin_findings)
    advisories.extend(spin_advisories)

    if jobtype == "hess":
        hessian = _result_array(results.get("hessian"))
        matrix = _hessian_matrix(hessian, len(expected_symbols))
        hessian_observation["shape"] = (
            list(hessian.shape) if hessian is not None else None
        )
        hessian_observation["all_finite"] = bool(
            matrix is not None and np.isfinite(matrix).all()
        )
        if matrix is None:
            findings.append(
                _result_finding(
                    RULE_RESULT_HESSIAN,
                    "results.hessian",
                    (
                        (len(expected_symbols), len(expected_symbols), 3, 3),
                        (len(expected_symbols), 3, len(expected_symbols), 3),
                        (3 * len(expected_symbols), 3 * len(expected_symbols)),
                    ),
                    _array_observation(hessian),
                    "h5:/results/hessian",
                )
            )
        elif not bool(np.isfinite(matrix).all()):
            findings.append(
                _result_finding(
                    RULE_RESULT_NONFINITE,
                    "results.hessian",
                    "finite Cartesian Hessian",
                    _array_observation(hessian),
                    "h5:/results/hessian",
                )
            )
        else:
            hessian_stage = status.get("stages", {}).get("hess", {})
            raw_antisymmetry = hessian_stage.get(
                "raw_max_abs_antisymmetry_eh_per_bohr2"
            )
            matrix_scale = float(np.max(np.abs(matrix)))
            raw_limit = float(
                _HESSIAN_SYMMETRY_ATOL + _HESSIAN_SYMMETRY_RTOL * matrix_scale
            )
            # A Hessian differenced from independent displacements is
            # not symmetric to analytic precision and was never meant to
            # be: its two mixed derivatives differ by the truncation
            # error of the step, which is a property of the third
            # derivative and the molecule, not of the integration grid
            # this limit was calibrated against.  Analytic DFT Hessians
            # likewise contain numerical quadrature over their integration
            # grid; the writer records that raw mismatch before it
            # symmetrises the stored matrix.  No limit has been calibrated
            # for either source of numerical antisymmetry, so both remain
            # evidence rather than an invalidity verdict.  The size of the
            # correction and the independent frequency check stay sealed for
            # a reader to weigh.
            numerical = (
                str(hessian_stage.get("derivative") or "")
                .strip()
                .lower()
                .endswith("finite_difference")
            )
            # Whether this is a DFT Hessian is a fact the artifact states
            # about itself -- the driver writes the applied functional to
            # ``spec/xc`` -- so it is read there rather than from the
            # caller's settings. Asking the caller made one Hessian get
            # two verdicts: the runner, which holds the project settings,
            # recorded the archived hcn_hnc_ts_hess as admissible
            # ungraded evidence, and the host evaluator, called with the
            # settings it verifies (which do not include the functional),
            # graded the same bytes against the analytic limit and
            # refused them.
            dft = bool(
                str(spec.get("xc") or "").strip()
                or str(_member(settings, "functional", "") or "").strip()
            )
            finite_value = bool(
                isinstance(raw_antisymmetry, (int, float))
                and not isinstance(raw_antisymmetry, bool)
                and np.isfinite(raw_antisymmetry)
                and float(raw_antisymmetry) >= 0.0
            )
            raw_admissible = bool(
                finite_value
                and (numerical or dft or float(raw_antisymmetry) <= raw_limit)
            )
            hessian_observation["raw_max_abs_antisymmetry_eh_per_bohr2"] = (
                raw_antisymmetry
            )
            hessian_observation["raw_antisymmetry_graded"] = not (
                numerical or dft
            )
            hessian_observation["raw_antisymmetry_limit_eh_per_bohr2"] = (
                raw_limit
            )
            hessian_observation["raw_symmetrization_admissible"] = (
                raw_admissible
            )
            if not raw_admissible:
                findings.append(
                    _result_finding(
                        RULE_RESULT_HESSIAN,
                        "status.stages.hess.raw_max_abs_antisymmetry_eh_per_bohr2",
                        {
                            "finite_nonnegative": True,
                            "maximum": raw_limit,
                            "scale": matrix_scale,
                        },
                        raw_antisymmetry,
                        "h5:/status/stages/hess/raw_max_abs_antisymmetry_eh_per_bohr2",
                    )
                )
            # The stored matrix is the symmetrised one either way; this
            # asks that the symmetrisation actually happened.
            symmetric = bool(
                np.allclose(
                    matrix,
                    matrix.T,
                    rtol=_HESSIAN_SYMMETRY_RTOL,
                    atol=_HESSIAN_SYMMETRY_ATOL,
                )
            )
            hessian_observation["symmetric"] = symmetric
            if not symmetric:
                findings.append(
                    _result_finding(
                        RULE_RESULT_HESSIAN,
                        "results.hessian.symmetry",
                        True,
                        False,
                        "h5:/results/hessian",
                    )
                )

        frequency = frequency_validation_receipt(
            symbols=observed_symbols,
            positions=results.get("positions"),
            frequencies=results.get("vibrational_frequencies"),
        )
        findings.extend(frequency["findings"])
        expected_modes = frequency.get("expected_mode_count")
        for field, expected_shape in (
            (
                "normal_modes",
                (expected_modes, len(expected_symbols), 3),
            ),
            ("reduced_masses", (expected_modes,)),
            ("force_constants", (expected_modes,)),
        ):
            values = _result_array(results.get(field))
            if (
                expected_modes is None
                or values is None
                or values.shape != expected_shape
            ):
                findings.append(
                    _result_finding(
                        RULE_RESULT_SHAPE,
                        f"results.{field}",
                        expected_shape,
                        _array_observation(values),
                        f"h5:/results/{field}",
                    )
                )
            elif not bool(np.isfinite(values).all()):
                findings.append(
                    _result_finding(
                        RULE_RESULT_NONFINITE,
                        f"results.{field}",
                        "finite numerical array",
                        _array_observation(values),
                        f"h5:/results/{field}",
                    )
                )

        hessian_consistency, consistency_findings = (
            _validate_hessian_frequency_consistency(
                matrix=matrix,
                symbols=observed_symbols,
                positions=positions,
                frequencies=_result_array(
                    results.get("vibrational_frequencies")
                ),
                mode_count=expected_modes,
            )
        )
        hessian_observation["consistency"] = hessian_consistency
        findings.extend(consistency_findings)

    findings = _deduplicate_result_findings(findings)
    if findings:
        contract_observation["new_execution_admissible"] = False
        if contract_observation["state"] == "current":
            contract_observation["state"] = "invalid"
    legacy_evidence = bool(
        not current_result_contract
        or materialization_observation["functional_definition"]["state"]
        == "legacy_environment_unbound"
    )
    if legacy_evidence:
        contract_observation["new_execution_admissible"] = False
        if contract_observation["state"] == "current":
            contract_observation["state"] = "qualified_legacy"
    validation_state = (
        "failed"
        if findings
        else ("qualified_legacy" if legacy_evidence else "validated")
    )
    receipt = {
        "schema_version": RESULT_VALIDATION_SCHEMA_VERSION,
        "state": validation_state,
        "jobtype": jobtype,
        "required_stages": required_stages,
        "observed_stages": observed_stages,
        "charge": spec.get("charge"),
        "multiplicity": spec.get("multiplicity"),
        "symbols": observed_symbols,
        "requested_settings_sha256": spec.get("requested_settings_sha256"),
        "applied_settings_sha256": spec.get("applied_settings_sha256"),
        "geometry_validation": geometry_observation,
        "electronic_state_validation": electronic_state_observation,
        "spin_diagnostic_validation": spin_diagnostic_observation,
        "materialization_validation": materialization_observation,
        "contract_validation": contract_observation,
        "reference_validation": reference_observation,
        "status_validation": status_observation,
        "frequency_validation": frequency,
        "hessian_validation": hessian_observation,
        "advisories": advisories,
        "findings": findings,
    }
    if irc_observation is not None:
        # Present only on an IRC, so every receipt of every other job
        # type keeps the exact shape it has always had.
        receipt["irc_validation"] = irc_observation
    if ts_observation is not None:
        receipt["ts_validation"] = ts_observation
    return receipt


#: How far a path's first frame may sit from the geometry the run was
#: handed, and its last frame from ``results/positions``: the two are the
#: same numbers passed through geomeTRIC's Bohr/Angstrom round trip, so
#: anything past round-off means the path is not the path of this result.
_IRC_FRAME_ATOL_ANGSTROM = 1.0e-6


def _irc_first_step_projection(positions, mode, masses):
    """Cosine of the first accepted step with the recorded transition
    vector, the step superposed on the start (mass-weighted Kabsch)."""

    frames = np.asarray(positions, dtype=float)
    weights = np.asarray(masses, dtype=float)
    first, second = frames[0], frames[1]
    total = float(weights.sum())
    first_centre = (weights[:, None] * first).sum(axis=0) / total
    second_centre = (weights[:, None] * second).sum(axis=0) / total
    covariance = (weights[:, None] * (second - second_centre)).T @ (
        first - first_centre
    )
    left, _values, right = np.linalg.svd(covariance)
    handed = float(np.sign(np.linalg.det(right.T @ left.T))) or 1.0
    rotation = right.T @ np.diag([1.0, 1.0, handed]) @ left.T
    step = (
        (second - second_centre) @ rotation.T - (first - first_centre)
    ).ravel()
    vector = np.asarray(mode, dtype=float).ravel()
    if not (np.linalg.norm(step) and np.linalg.norm(vector)):
        return None
    return float(
        step @ vector / (np.linalg.norm(step) * np.linalg.norm(vector))
    )


def _irc_steepest_descent_alignment(positions, gradients, masses, *, switch):
    """How far each recorded step is from steepest descent on its surface.

    An intrinsic reaction coordinate is the steepest-descent path in
    mass-weighted coordinates, and a Gonzalez-Schlegel step is the chord of
    an arc tangent to the gradient at both of its ends, so each accepted
    step -- the later frame superposed on the earlier by the mass-weighted
    Kabsch rotation -- should lie along the mean of the two unit negative
    mass-weighted gradients. geomeTRIC finds each next point from a
    quadratic model of the gradient rather than the gradient itself, so
    where the valley turns sharply a recorded step can cut the corner: the
    walk still reaches its basin while those steps are not the surface's
    steepest descent. The cosines are stated, never graded -- no threshold
    has been earned -- and the steps after a switch to minimisation are not
    path steps and are left out. Shares no code with the integrator.
    """

    frames = np.asarray(positions, dtype=float)
    grads = np.asarray(gradients, dtype=float)
    weights = np.asarray(masses, dtype=float)
    root = np.sqrt(np.repeat(weights, 3))
    last = len(frames) - 1
    switch_values = np.asarray(
        switch if switch is not None else [], dtype=float
    ).ravel()
    if switch_values.size:
        last = min(last, int(switch_values[0]))
    cosines = []
    for index in range(last):
        before = frames[index]
        after = frames[index + 1]
        total = float(weights.sum())
        before_centre = (weights[:, None] * before).sum(axis=0) / total
        after_centre = (weights[:, None] * after).sum(axis=0) / total
        covariance = (weights[:, None] * (after - after_centre)).T @ (
            before - before_centre
        )
        left, _values, right = np.linalg.svd(covariance)
        handed = float(np.sign(np.linalg.det(right.T @ left.T))) or 1.0
        rotation = right.T @ np.diag([1.0, 1.0, handed]) @ left.T
        step = (
            (after - after_centre) @ rotation.T - (before - before_centre)
        ).ravel() * root
        start = grads[index].ravel() / root
        end = (grads[index + 1] @ rotation.T).ravel() / root
        if not (
            np.linalg.norm(step)
            and np.linalg.norm(start)
            and np.linalg.norm(end)
        ):
            continue
        descent = -(start / np.linalg.norm(start) + end / np.linalg.norm(end))
        if not np.linalg.norm(descent):
            continue
        cosines.append(
            float(
                step
                @ descent
                / (np.linalg.norm(step) * np.linalg.norm(descent))
            )
        )
    # The first step leaves the saddle along the transition vector, where
    # the gradient is near zero and its direction is noise.
    later = cosines[1:]
    return {
        "steepest_descent_cosines": [round(value, 4) for value in cosines],
        "steepest_descent_cosine_median": (
            float(np.median(cosines)) if cosines else None
        ),
        "steepest_descent_cosine_min_after_first_step": (
            float(min(later)) if later else None
        ),
        "steepest_descent_steps_compared": len(cosines),
    }


#: How far a re-derived mass-weighted arc length may sit from the one the
#: driver recorded, in its own unit (amu^1/2 bohr).  Both are the same
#: Kabsch superposition of the same frames under the same masses, so the
#: difference is float summation order; a real divergence is orders of
#: magnitude larger.
_IRC_ARC_ATOL_AMU_HALF_BOHR = 1.0e-8
#: Likewise for the energy statistics, in hartree: the recorded drop and
#: largest rise are differences of the recorded energies.
_IRC_ENERGY_ATOL_EH = 1.0e-10


#: What a path stage's primitive arrays and derived scalars are called.
#: One entry per stage, because an IRC's branch and a saddle search's
#: climb are the same shape of evidence under different names, and the
#: arithmetic that re-derives one re-derives the other.
_IRC_ACCOUNT_NAMES = {
    "stage": "irc",
    "hessian": "start_hessian",
    "frequencies": "start_frequencies",
    "positions": "path_positions",
    "masses": "path_masses",
    "energies": "path_energies",
    "distance": "path_arc_lengths",
    # (status key -> how the energies give it).  A stage is checked on
    # exactly the scalars it records, so adding one to a driver without
    # a derivation here is caught by the coverage check below rather
    # than silently unverified.
    "energy_statistics": {
        "energy_drop_eh": "first_minus_last",
        "energy_rises_along_path": "count_of_rises",
        "largest_energy_rise_eh": "largest_rise",
    },
}
_TS_ACCOUNT_NAMES = {
    "stage": "ts",
    "hessian": "seed_hessian",
    "frequencies": "seed_frequencies",
    "positions": "search_positions",
    "masses": "search_masses",
    "energies": "search_energies",
    "distance": "search_displacements",
    "energy_statistics": {"energy_rise_eh": "last_minus_first"},
}


def _validate_path_account(*, arrays, stage, symbols, findings, names):
    """Re-derive every number a path stage records about its own frames.

    A derived summary written beside the arrays it came from, with
    nothing re-deriving it, is a claim the bytes need not support.  Real
    archived v8 artifacts proved it: the start's spectrum rewritten to
    all-real values, the mass table set to 1.0, two interior frames
    swapped, the energies reversed, the whole path appended to itself
    walked back to the saddle, and the start Hessian replaced by a
    different symmetric matrix of the same shape -- each of the six came
    back ``validated``, because the Hessian was checked for shape alone
    and every scalar was read rather than recomputed.

    So each is derived again from the primitives it is a summary of, by
    arithmetic that shares no code with the driver:

    * the start's spectrum from the start Hessian at the start geometry,
      through the *same* independent reconstruction a ``hess`` stage is
      already held to -- which weighs by its own isotope-averaged mass
      table, so it is an authority and not an echo;
    * the mass-weighted arc lengths from the frames and ``path_masses``,
      which is the one number that ties frames, masses and order
      together: a step inserted, removed, reordered or re-weighted moves
      it;
    * the energy statistics from ``path_energies``.

    Nothing here judges the chemistry of the path.  It judges whether the
    artifact's account of itself is the account its own arrays give.
    """

    import numpy as np

    stage_name = names["stage"]
    observation = {"state": "unverified", "checks": {}}

    def _record(name, expected, observed, tolerance, evidence):
        agreed = (
            expected is not None
            and observed is not None
            and abs(float(expected) - float(observed)) <= tolerance
        )
        observation["checks"][name] = {
            "recomputed": None if expected is None else float(expected),
            "recorded": None if observed is None else float(observed),
            "agrees": agreed if observed is not None else None,
        }
        if observed is not None and not agreed:
            findings.append(
                _result_finding(
                    RULE_RESULT_IRC_ACCOUNT,
                    name,
                    {
                        "recomputed": (
                            None if expected is None else float(expected)
                        ),
                        "absolute_tolerance": tolerance,
                    },
                    float(observed),
                    evidence,
                )
            )

    atoms = len(symbols)
    hessian = _result_array(arrays.get(names["hessian"]))
    frames = _result_array(arrays.get(names["positions"]))
    frequencies = _result_array(arrays.get(names["frequencies"]))
    masses = _result_array(arrays.get(names["masses"]))
    energies = _result_array(arrays.get(names["energies"]))
    arc = _result_array(arrays.get(names["distance"]))
    positions_field = f"h5:/results/{stage_name}/{names['positions']}"
    energies_field = f"h5:/results/{stage_name}/{names['energies']}"
    distance_field = f"results.{stage_name}.{names['distance']}"
    distance_evidence = f"h5:/results/{stage_name}/{names['distance']}"
    hessian_evidence = f"h5:/results/{stage_name}/{names['hessian']}"

    # 1. the start's spectrum belongs to the start's Hessian, taken at the
    #    geometry the path starts from.
    if (
        hessian is not None
        and hessian.shape == (atoms, atoms, 3, 3)
        and frames is not None
        and frames.ndim == 3
        and frames.shape[1:] == (atoms, 3)
        and frames.shape[0] >= 1
    ):
        matrix = hessian.transpose(0, 2, 1, 3).reshape(3 * atoms, 3 * atoms)
        consistency, consistency_findings = (
            _validate_hessian_frequency_consistency(
                matrix=matrix,
                symbols=symbols,
                positions=frames[0],
                frequencies=frequencies,
            )
        )
        # The finding's field names this stage's own spectrum, not a
        # ``hess`` stage's ``results.vibrational_frequencies`` which this
        # artifact has not got.
        for finding in consistency_findings:
            findings.append(
                _result_finding(
                    finding.rule_id,
                    f"results.{stage_name}.{names['frequencies']}",
                    finding.expected,
                    finding.observed,
                    hessian_evidence,
                )
            )
        observation["start_frequency_consistency"] = consistency

    # 2. the arc length is the mass-weighted path of these frames.
    if (
        frames is not None
        and masses is not None
        and arc is not None
        and frames.ndim == 3
        and frames.shape[1:] == (atoms, 3)
        and masses.shape == (atoms,)
        and arc.shape == (frames.shape[0],)
        and bool(np.isfinite(frames).all())
        and bool(np.isfinite(masses).all())
        and bool((masses > 0.0).all())
    ):
        recomputed = _mass_weighted_arc_lengths(frames, masses)
        difference = float(np.max(np.abs(recomputed - arc)))
        observation["checks"][distance_field] = {
            "max_absolute_difference_amu_half_bohr": difference,
            "absolute_tolerance": _IRC_ARC_ATOL_AMU_HALF_BOHR,
            "agrees": difference <= _IRC_ARC_ATOL_AMU_HALF_BOHR,
        }
        if difference > _IRC_ARC_ATOL_AMU_HALF_BOHR:
            findings.append(
                _result_finding(
                    RULE_RESULT_IRC_ACCOUNT,
                    distance_field,
                    {
                        "recomputed_from": (
                            f"{names['positions']} and {names['masses']}"
                        ),
                        "max_absolute_difference_amu_half_bohr": difference,
                        "absolute_tolerance": _IRC_ARC_ATOL_AMU_HALF_BOHR,
                    },
                    arc.tolist(),
                    distance_evidence,
                )
            )

    # 3. the energy statistics are statistics of these energies.
    if energies is not None and energies.ndim == 1 and energies.size:
        rises = np.diff(energies)
        derivations = {
            "first_minus_last": (
                lambda: float(energies[0] - energies[-1]),
                _IRC_ENERGY_ATOL_EH,
            ),
            "last_minus_first": (
                lambda: float(energies[-1] - energies[0]),
                _IRC_ENERGY_ATOL_EH,
            ),
            "count_of_rises": (
                lambda: float(int((rises > 0.0).sum())),
                0.0,
            ),
            "largest_rise": (
                (lambda: float(rises.max())) if rises.size else None,
                _IRC_ENERGY_ATOL_EH,
            ),
        }
        for key, derivation in names["energy_statistics"].items():
            compute, tolerance = derivations[derivation]
            if compute is None:
                continue
            _record(
                f"status.stages.{stage_name}.{key}",
                compute(),
                stage.get(key),
                tolerance,
                energies_field,
            )
    if frames is not None and frames.ndim == 3:
        _record(
            f"status.stages.{stage_name}.frames",
            float(frames.shape[0]),
            stage.get("frames"),
            0.0,
            positions_field,
        )
    observation["state"] = (
        "verified"
        if not any(
            item.get("agrees") is False
            for item in observation["checks"].values()
        )
        and observation.get("start_frequency_consistency", {}).get("state")
        in (None, "verified")
        else "refused"
    )
    return observation


def _mass_weighted_arc_lengths(frames, masses):
    """Cumulative mass-weighted path length, rigid motion removed.

    The driver's own arithmetic, written again rather than shared, so the
    check is an authority: consecutive frames superposed by the
    mass-weighted Kabsch rotation, the displacement weighted by sqrt(m),
    and the Bohr conversion the driver applies.
    """

    import numpy as np

    #: PySCF's own ``lib.param.BOHR``, the literal the driver divides by.
    bohr = 0.52917721092
    weights = np.asarray(masses, dtype=float)
    total = float(weights.sum())
    lengths = [0.0]
    for index in range(1, len(frames)):
        before = np.asarray(frames[index - 1], dtype=float)
        after = np.asarray(frames[index], dtype=float)
        before_centred = (
            before - (weights[:, None] * before).sum(axis=0) / total
        )
        after_centred = after - (weights[:, None] * after).sum(axis=0) / total
        covariance = (weights[:, None] * after_centred).T @ before_centred
        left, _values, right = np.linalg.svd(covariance)
        handed = float(np.sign(np.linalg.det(right.T @ left.T))) or 1.0
        rotation = right.T @ np.diag([1.0, 1.0, handed]) @ left.T
        displacement = after_centred @ rotation.T - before_centred
        norm = float(np.sqrt((weights[:, None] * displacement**2).sum()))
        lengths.append(lengths[-1] + norm / bohr)
    return np.asarray(lengths, dtype=float)


def _validate_ts_results(results, stage_statuses, *, expected_symbols):
    """The saddle search's invariants, and the facts a reader weighs.

    Identity and shape, never chemistry: that the climb starts at the
    geometry the run was handed, ends at the structure every property
    belongs to, that the arrays are finite and aligned, and that every
    number the stage records about its own frames is the number those
    frames give.

    What is deliberately not checked is the order of the structure the
    search reached.  This artifact carries no Hessian there -- geomeTRIC's
    updated curvature is a quasi-Newton estimate of it and is recorded
    under a name that says so -- and a validator that read that estimate
    as a spectrum would certify a saddle from an approximation.  A
    ``hess`` node on the reached geometry is what answers it.
    """

    findings = []
    ts = results.get("ts")
    ts = ts if isinstance(ts, Mapping) else {}
    stage = stage_statuses.get("ts")
    stage = stage if isinstance(stage, Mapping) else {}
    atoms = len(expected_symbols)
    observation = {
        "frames": None,
        "end_matches_positions": None,
        "seed_frequencies_cm1": None,
        "seed_max_abs_gradient_eh_per_bohr": (
            (stage.get("seed") or {}).get("max_abs_gradient_eh_per_bohr")
            if isinstance(stage.get("seed"), Mapping)
            else None
        ),
        "end_max_abs_gradient_eh_per_bohr": stage.get(
            "end_max_abs_gradient_eh_per_bohr"
        ),
        "search_converged": stage.get("search_converged"),
        "iterations": stage.get("iterations"),
        "maxsteps": stage.get("maxsteps"),
        # How far the structure travelled and what that cost in energy.
        # A search seeded at a minimum of the same surface converges at
        # once and moves nowhere -- the direct-CLI reference run
        # h2co_ts_from_minimum (CUHK 2141124) did exactly that, one
        # iteration, all-real seed spectrum, and a green receipt -- and
        # these two numbers beside that spectrum are how a reader sees it.
        "displacement_amu_half_bohr": stage.get("displacement_amu_half_bohr"),
        "energy_rise_eh": stage.get("energy_rise_eh"),
    }

    def _array(name, shape):
        values = _result_array(ts.get(name))
        if values is None or values.shape != shape:
            findings.append(
                _result_finding(
                    RULE_RESULT_TS,
                    f"results.ts.{name}",
                    shape,
                    _array_observation(values),
                    f"h5:/results/ts/{name}",
                )
            )
            return None
        if not bool(np.isfinite(values).all()):
            findings.append(
                _result_finding(
                    RULE_RESULT_NONFINITE,
                    f"results.ts.{name}",
                    "finite values",
                    _array_observation(values),
                    f"h5:/results/ts/{name}",
                )
            )
            return None
        return values

    frequencies = _result_array(ts.get("seed_frequencies"))
    if frequencies is None or frequencies.ndim != 1 or not frequencies.size:
        findings.append(
            _result_finding(
                RULE_RESULT_TS,
                "results.ts.seed_frequencies",
                "the seed's harmonic spectrum on the climbed surface",
                _array_observation(frequencies),
                "h5:/results/ts/seed_frequencies",
            )
        )
    else:
        observation["seed_frequencies_cm1"] = [
            float(value) for value in frequencies[:3]
        ]
    _array("seed_hessian", (atoms, atoms, 3, 3))
    _array("search_masses", (atoms,))
    positions = _result_array(ts.get("search_positions"))
    frames = (
        int(positions.shape[0])
        if positions is not None
        and positions.ndim == 3
        and positions.shape[1:] == (atoms, 3)
        else None
    )
    observation["frames"] = frames
    if frames is None or frames < 1:
        findings.append(
            _result_finding(
                RULE_RESULT_TS,
                "results.ts.search_positions",
                ("frames >= 1", atoms, 3),
                _array_observation(positions),
                "h5:/results/ts/search_positions",
            )
        )
        return observation, findings
    positions = _array("search_positions", (frames, atoms, 3))
    _array("search_energies", (frames,))
    _array("search_gradients", (frames, atoms, 3))
    displacements = _array("search_displacements", (frames,))
    if displacements is not None and (
        abs(float(displacements[0])) > 0.0
        or bool((np.diff(displacements) < 0.0).any())
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_TS,
                "results.ts.search_displacements",
                "zero at the seed and never decreasing",
                displacements.tolist(),
                "h5:/results/ts/search_displacements",
            )
        )
    final = _result_array(results.get("positions"))
    if positions is not None and final is not None:
        ends = bool(
            final.shape == (atoms, 3)
            and np.allclose(
                positions[-1],
                final,
                rtol=0.0,
                atol=_IRC_FRAME_ATOL_ANGSTROM,
            )
        )
        observation["end_matches_positions"] = ends
        if not ends:
            findings.append(
                _result_finding(
                    RULE_RESULT_TS,
                    "results.positions",
                    {
                        "last_search_frame": positions[-1].tolist(),
                        "absolute_tolerance_angstrom": (
                            _IRC_FRAME_ATOL_ANGSTROM
                        ),
                    },
                    final.tolist(),
                    "h5:/results/ts/search_positions",
                )
            )
    observation["account"] = _validate_path_account(
        arrays=ts,
        stage=stage,
        symbols=list(expected_symbols),
        findings=findings,
        names=_TS_ACCOUNT_NAMES,
    )
    for field in ("search_converged", "final_scf_converged"):
        if stage.get(field) is not True:
            findings.append(
                _result_finding(
                    RULE_RESULT_STAGE,
                    f"status.stages.ts.{field}",
                    True,
                    stage.get(field),
                    f"h5:/status/stages/ts/{field}",
                )
            )
    return observation, findings


def _validate_irc_results(results, stage_statuses, spec, *, expected_symbols):
    """The IRC artifact's invariants, and the facts a reader weighs.

    What is checked is identity and shape, never chemistry: that the path
    starts at the geometry the run was handed and ends at the structure
    every property belongs to, that the arrays are finite and aligned,
    that the arc length never runs backwards, and that the branch the
    first step took is the branch that was asked for.  Whether the start
    was a first-order saddle of this surface is the host's program-neutral
    stationary-point rule, read from ``start_frequencies``; whether the
    endpoint is a minimum is a Hessian's question, and this artifact
    carries none at the endpoint.
    """

    findings = []
    irc = results.get("irc")
    irc = irc if isinstance(irc, Mapping) else {}
    stage = stage_statuses.get("irc")
    stage = stage if isinstance(stage, Mapping) else {}
    atoms = len(expected_symbols)
    observation = {
        "frames": None,
        "start_matches_supplied": None,
        "end_matches_positions": None,
        "path_start_minus_scf_energy_eh": None,
        "requested_direction": spec.get("irc_direction"),
        "direction_followed": stage.get("direction_followed"),
        "first_step_projection": stage.get("first_step_projection"),
        "start_frequencies_cm1": None,
        "start_max_abs_gradient_eh_per_bohr": (
            (stage.get("start") or {}).get("max_abs_gradient_eh_per_bohr")
            if isinstance(stage.get("start"), Mapping)
            else None
        ),
        "path_converged": stage.get("path_converged"),
        "switched_to_minimisation": stage.get("switched_to_minimisation"),
        # Where the walk stopped stepping along the path and started
        # minimising, and the ceiling it was given: a reader that knows
        # only the frame count cannot tell a branch that reached its
        # basin from one that ran out of steps, nor an endpoint the path
        # arrived at from one a minimisation from the path's tail did.
        "switch_after_iteration": stage.get("switch_after_iteration"),
        "maxsteps": stage.get("maxsteps"),
        "energy_rises_along_path": stage.get("energy_rises_along_path"),
        "largest_energy_rise_eh": stage.get("largest_energy_rise_eh"),
        "arc_length_amu_half_bohr": stage.get("arc_length_amu_half_bohr"),
        "energy_drop_eh": stage.get("energy_drop_eh"),
    }

    def _array(name, shape):
        values = _result_array(irc.get(name))
        if values is None or values.shape != shape:
            findings.append(
                _result_finding(
                    RULE_RESULT_IRC,
                    f"results.irc.{name}",
                    shape,
                    _array_observation(values),
                    f"h5:/results/irc/{name}",
                )
            )
            return None
        if not bool(np.isfinite(values).all()):
            findings.append(
                _result_finding(
                    RULE_RESULT_NONFINITE,
                    f"results.irc.{name}",
                    "finite values",
                    _array_observation(values),
                    f"h5:/results/irc/{name}",
                )
            )
            return None
        return values

    frequencies = _result_array(irc.get("start_frequencies"))
    if frequencies is None or frequencies.ndim != 1 or not frequencies.size:
        findings.append(
            _result_finding(
                RULE_RESULT_IRC,
                "results.irc.start_frequencies",
                "the start's harmonic spectrum on the walked surface",
                _array_observation(frequencies),
                "h5:/results/irc/start_frequencies",
            )
        )
    else:
        observation["start_frequencies_cm1"] = [
            float(value) for value in frequencies[:3]
        ]
    _array("start_hessian", (atoms, atoms, 3, 3))
    _array("path_masses", (atoms,))
    positions = _result_array(irc.get("path_positions"))
    frames = (
        int(positions.shape[0])
        if positions is not None
        and positions.ndim == 3
        and positions.shape[1:] == (atoms, 3)
        else None
    )
    observation["frames"] = frames
    if frames is None or frames < 1:
        findings.append(
            _result_finding(
                RULE_RESULT_IRC,
                "results.irc.path_positions",
                ("frames >= 1", atoms, 3),
                _array_observation(positions),
                "h5:/results/irc/path_positions",
            )
        )
        return observation, findings
    positions = _array("path_positions", (frames, atoms, 3))
    energies = _array("path_energies", (frames,))
    _array("path_gradients", (frames, atoms, 3))
    arc = _array("path_arc_lengths", (frames,))
    if frames > 1:
        _array("transition_mode", (atoms, 3))
    if arc is not None and (
        abs(float(arc[0])) > 0.0 or bool((np.diff(arc) < 0.0).any())
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_IRC,
                "results.irc.path_arc_lengths",
                "zero at the start and never decreasing",
                arc.tolist(),
                "h5:/results/irc/path_arc_lengths",
            )
        )
    supplied = _result_array(spec.get("positions"))
    if positions is not None and supplied is not None:
        starts = bool(
            supplied.shape == (atoms, 3)
            and np.allclose(
                positions[0],
                supplied,
                rtol=0.0,
                atol=_IRC_FRAME_ATOL_ANGSTROM,
            )
        )
        observation["start_matches_supplied"] = starts
        if not starts:
            findings.append(
                _result_finding(
                    RULE_RESULT_IRC,
                    "results.irc.path_positions[0]",
                    {
                        "supplied_positions": supplied.tolist(),
                        "absolute_tolerance_angstrom": (
                            _IRC_FRAME_ATOL_ANGSTROM
                        ),
                    },
                    positions[0].tolist(),
                    "h5:/results/irc/path_positions",
                )
            )
    final = _result_array(results.get("positions"))
    if positions is not None and final is not None:
        ends = bool(
            final.shape == (atoms, 3)
            and np.allclose(
                positions[-1],
                final,
                rtol=0.0,
                atol=_IRC_FRAME_ATOL_ANGSTROM,
            )
        )
        observation["end_matches_positions"] = ends
        if not ends:
            findings.append(
                _result_finding(
                    RULE_RESULT_IRC,
                    "results.positions",
                    {
                        "last_path_frame": positions[-1].tolist(),
                        "absolute_tolerance_angstrom": (
                            _IRC_FRAME_ATOL_ANGSTROM
                        ),
                    },
                    final.tolist(),
                    "h5:/results/positions",
                )
            )
    # Every number this stage records *about* its arrays, derived again
    # from those arrays.  Placed after the shape and finiteness checks so
    # the arithmetic below runs on arrays that are already known to be
    # arrays, and before the branch and stage checks so a finding about
    # the account arrives with them.
    observation["account"] = _validate_path_account(
        arrays=irc,
        stage=stage,
        symbols=list(expected_symbols),
        findings=findings,
        names=_IRC_ACCOUNT_NAMES,
    )
    gradients = _result_array(irc.get("path_gradients"))
    masses = _result_array(irc.get("path_masses"))
    if (
        positions is not None
        and gradients is not None
        and masses is not None
        and gradients.shape == positions.shape
        and masses.shape == (atoms,)
    ):
        observation.update(
            _irc_steepest_descent_alignment(
                positions,
                gradients,
                masses,
                switch=stage.get("switch_after_iteration"),
            )
        )
    scf_trace = _result_array(results.get("energies"))
    if energies is not None and scf_trace is not None and scf_trace.size:
        # Stated, never graded: the saddle's SCF and the path's first
        # energy are one geometry on one method, so a difference here is
        # two SCF solutions, which a reader should see.
        observation["path_start_minus_scf_energy_eh"] = float(
            energies[0] - scf_trace[0]
        )
    requested = str(spec.get("irc_direction") or "").strip().lower()
    followed = str(stage.get("direction_followed") or "").strip().lower()
    # The branch is measured here again from the recorded arrays rather
    # than read from the driver's own word: the first accepted step,
    # superposed on the start, against the transition vector the artifact
    # says was followed.
    mode = _result_array(irc.get("transition_mode"))
    if (
        frames > 1
        and positions is not None
        and mode is not None
        and mode.shape == (atoms, 3)
        and masses is not None
        and masses.shape == (atoms,)
    ):
        measured = _irc_first_step_projection(positions, mode, masses)
        observation["first_step_projection_measured"] = measured
        if measured is not None:
            observed_branch = "forward" if measured > 0 else "backward"
            if observed_branch != followed:
                findings.append(
                    _result_finding(
                        RULE_RESULT_IRC_DIRECTION,
                        "status.stages.irc.direction_followed",
                        {
                            "measured_from_path": observed_branch,
                            "first_step_projection": measured,
                        },
                        followed or None,
                        "h5:/results/irc/path_positions",
                    )
                )
            followed = observed_branch
    if frames > 1 and requested != followed:
        findings.append(
            _result_finding(
                RULE_RESULT_IRC_DIRECTION,
                "status.stages.irc.direction_followed",
                {
                    "requested": requested,
                    "rule": stage.get("direction_rule"),
                },
                {
                    "followed": followed or None,
                    "first_step_projection": stage.get(
                        "first_step_projection"
                    ),
                },
                "h5:/status/stages/irc",
            )
        )
    for field in ("path_converged", "final_scf_converged"):
        if stage.get(field) is not True:
            findings.append(
                _result_finding(
                    RULE_RESULT_STAGE,
                    f"status.stages.irc.{field}",
                    True,
                    stage.get(field),
                    f"h5:/status/stages/irc/{field}",
                )
            )
    return observation, findings


def _validate_excited_state_results(results, stage_statuses):
    """Roots are finite, ascending, and every per-root array is aligned."""

    findings = []
    excitations = _result_array(results.get("excitation_energies"))
    if excitations is None or excitations.ndim != 1 or excitations.size == 0:
        findings.append(
            _result_finding(
                RULE_RESULT_EXCITED,
                "results.excitation_energies",
                "non-empty 1-d array of excitation energies",
                _array_observation(excitations),
                "h5:/results/excitation_energies",
            )
        )
        return findings
    if not bool(np.isfinite(excitations).all()):
        findings.append(
            _result_finding(
                RULE_RESULT_EXCITED,
                "results.excitation_energies",
                "finite excitation energies",
                _array_observation(excitations),
                "h5:/results/excitation_energies",
            )
        )
    if excitations.size > 1 and bool((np.diff(excitations) < 0).any()):
        findings.append(
            _result_finding(
                RULE_RESULT_EXCITED,
                "results.excitation_energies",
                "ascending roots within the manifold",
                excitations.tolist(),
                "h5:/results/excitation_energies",
            )
        )
    count = int(excitations.size)
    for name in (
        "oscillator_strengths",
        "excited_state_converged",
        "excited_state_multiplicities",
    ):
        if name not in results:
            continue
        values = _result_array(results.get(name))
        if values is None or values.shape[:1] != (count,):
            findings.append(
                _result_finding(
                    RULE_RESULT_EXCITED,
                    f"results.{name}",
                    f"one entry per root ({count})",
                    _array_observation(values),
                    f"h5:/results/{name}",
                )
            )
    dipoles = results.get("transition_dipole_moments")
    if dipoles is not None:
        values = _result_array(dipoles)
        if values is None or values.shape != (count, 3):
            findings.append(
                _result_finding(
                    RULE_RESULT_EXCITED,
                    "results.transition_dipole_moments",
                    (count, 3),
                    _array_observation(values),
                    "h5:/results/transition_dipole_moments",
                )
            )
    td_status = stage_statuses.get("td")
    obtained = (
        td_status.get("nstates_obtained")
        if isinstance(td_status, Mapping)
        else None
    )
    if obtained != count:
        findings.append(
            _result_finding(
                RULE_RESULT_EXCITED,
                "status.stages.td.nstates_obtained",
                count,
                obtained,
                "h5:/status/stages/td/nstates_obtained",
            )
        )
    return findings


def _validate_correlated_results(results, stage_statuses, spec):
    """The components are finite and sum to the total the artifact states."""

    findings = []
    method = pyscf_correlated_method(spec.get("ab_initio"))
    names = ["reference_energy", "correlation_energy", "total_energy"]
    if method in PYSCF_COUPLED_CLUSTER_METHODS:
        names.append("ccsd_correlation_energy")
    if method == "ccsd(t)":
        names.append("triples_correction")
    values = {}
    for name in names:
        value = _scalar_number(results.get(name))
        if value is None:
            findings.append(
                _result_finding(
                    RULE_RESULT_CORRELATION,
                    f"results.{name}",
                    "finite scalar in Eh",
                    _array_observation(_result_array(results.get(name))),
                    f"h5:/results/{name}",
                )
            )
        values[name] = value
    if all(values.get(name) is not None for name in names):
        total = values["reference_energy"] + values["correlation_energy"]
        if abs(total - values["total_energy"]) > 1.0e-8:
            findings.append(
                _result_finding(
                    RULE_RESULT_CORRELATION,
                    "results.total_energy",
                    {"reference_plus_correlation": total},
                    values["total_energy"],
                    "h5:/results/total_energy",
                )
            )
        if method == "ccsd(t)":
            parts = (
                values["ccsd_correlation_energy"]
                + values["triples_correction"]
            )
            if abs(parts - values["correlation_energy"]) > 1.0e-8:
                findings.append(
                    _result_finding(
                        RULE_RESULT_CORRELATION,
                        "results.correlation_energy",
                        {"ccsd_plus_triples": parts},
                        values["correlation_energy"],
                        "h5:/results/correlation_energy",
                    )
                )
        elif method == "ccsd":
            # PySCF's own meaning makes these one number: the driver
            # writes ``float(obj.e_corr)`` to both, with no triples
            # between them, so a plain-CCSD artifact serving two
            # different values is serving one quantity twice and
            # disagreeing with itself. Nothing said so, and the
            # component was tied to the total only through the
            # ccsd(t) sum, so a perturbed ``ccsd_correlation_energy``
            # validated. The bound is exact rather than the 1e-8 the
            # sums carry, because no arithmetic stands between them.
            if (
                abs(
                    values["ccsd_correlation_energy"]
                    - values["correlation_energy"]
                )
                > 1.0e-12
            ):
                findings.append(
                    _result_finding(
                        RULE_RESULT_CORRELATION,
                        "results.ccsd_correlation_energy",
                        {
                            "equals_correlation_energy": values[
                                "correlation_energy"
                            ]
                        },
                        values["ccsd_correlation_energy"],
                        "h5:/results/ccsd_correlation_energy",
                    )
                )
    corr_status = stage_statuses.get("corr")
    applied = (
        corr_status.get("method") if isinstance(corr_status, Mapping) else None
    )
    if applied != method:
        findings.append(
            _result_finding(
                RULE_RESULT_CORRELATION,
                "status.stages.corr.method",
                method,
                applied,
                "h5:/status/stages/corr/method",
            )
        )
    return findings


def _validate_energy_decomposition(results, spec):
    """The terms the applied settings produce are the terms recorded.

    Two directions, and only one of them holds both ways.  A continuum
    model always gives PySCF an ``e_solvent`` and SMD always gives an
    ``e_cds``, so their absence under those settings is a defective
    record, and either term on a run that attached no such model is a
    number belonging to nothing.  Dispersion is checked forwards only: a
    functional whose *name* carries a correction (``wb97x-d3bj``) makes
    ``do_disp()`` true with no ``dispersion`` setting at all, so a term
    beside an unset field is a fact about the functional rather than a
    contradiction.
    """

    findings = []
    solvent_model = str(spec.get("solvent_model") or "").strip().lower()
    solvated = bool(spec.get("solvent_call")) or bool(solvent_model)
    expectations = (
        ("solvation_electrostatic_energy", solvated, True),
        ("solvation_nonelectrostatic_energy", solvent_model == "smd", True),
        ("dispersion_energy", bool(spec.get("dispersion")), False),
    )
    for name, expected, exclusive in expectations:
        stored = results.get(name)
        value = _scalar_number(stored)
        present = stored is not None
        if expected and value is None:
            findings.append(
                _result_finding(
                    RULE_RESULT_DECOMPOSITION,
                    f"results.{name}",
                    "finite scalar in Eh",
                    _array_observation(_result_array(stored)),
                    f"h5:/results/{name}",
                )
            )
        elif not expected and present and exclusive:
            findings.append(
                _result_finding(
                    RULE_RESULT_DECOMPOSITION,
                    f"results.{name}",
                    "absent: the applied settings produce no such term",
                    _array_observation(_result_array(stored)),
                    f"h5:/results/{name}",
                )
            )
        elif present and value is None:
            findings.append(
                _result_finding(
                    RULE_RESULT_DECOMPOSITION,
                    f"results.{name}",
                    "finite scalar in Eh",
                    _array_observation(_result_array(stored)),
                    f"h5:/results/{name}",
                )
            )
    return findings


def _normalize_result_jobtype(value):
    """Return the bare job-type word a spec or a request spells.

    Both branches of the membership test this replaced returned the same
    value, so the vocabulary copy inside it decided nothing; the callers
    compare the normalised words to each other and the vocabulary is
    checked where a setting is validated.
    """

    return str(value or "").strip().lower().replace("pyscf_", "")


def _result_verification_settings(*, settings, jobtype, charge, multiplicity):
    if isinstance(settings, Mapping):
        resolved = dict(settings)
        resolved.setdefault("jobtype", jobtype)
        resolved.setdefault("charge", int(charge))
        resolved.setdefault("multiplicity", int(multiplicity))
        return resolved
    return settings


def _verify_result_settings_identity(spec, provenance):
    findings = []
    for field in ("requested_settings_sha256", "applied_settings_sha256"):
        observed = spec.get(field)
        if not _is_sha256(observed):
            findings.append(
                _result_finding(
                    RULE_RESULT_SETTINGS,
                    f"spec.{field}",
                    "64-character SHA-256",
                    observed,
                    f"h5:/spec/{field}",
                )
            )
        provenance_value = provenance.get(field)
        if provenance_value != observed:
            findings.append(
                _result_finding(
                    RULE_RESULT_SETTINGS,
                    f"provenance.{field}",
                    observed,
                    provenance_value,
                    f"h5:/provenance/{field}",
                )
            )
    applied = spec.get("applied_settings_sha256")
    if _is_sha256(applied):
        from chemsmart.jobs.pyscf.writer import (
            PySCFScriptWriter,
            applied_pyscf_spec_fields,
        )

        fields = applied_pyscf_spec_fields(spec)
        payload = {field: spec.get(field) for field in fields}
        reconstructed = PySCFScriptWriter.settings_digest(payload)
        if reconstructed != applied:
            findings.append(
                _result_finding(
                    RULE_RESULT_SETTINGS,
                    "spec.applied_settings_sha256",
                    reconstructed,
                    applied,
                    "h5:/spec/applied_settings_sha256",
                )
            )
    return findings


def _hessian_matrix(values, atom_count):
    if values is None:
        return None
    if values.shape == (atom_count, atom_count, 3, 3):
        return values.transpose(0, 2, 1, 3).reshape(3 * atom_count, -1)
    if values.shape == (atom_count, 3, atom_count, 3):
        return values.reshape(3 * atom_count, 3 * atom_count)
    if values.shape == (3 * atom_count, 3 * atom_count):
        return values
    return None


def _validate_hessian_frequency_consistency(
    *, matrix, symbols, positions, frequencies, mode_count=None
):
    observation = {
        "state": "unverified",
        "algorithm": "independent-mass-weighted-projection-v1",
        "absolute_tolerance_cm1": _HESSIAN_FREQUENCY_ATOL_CM1,
        "relative_tolerance": _HESSIAN_FREQUENCY_RTOL,
        "translation_rotation_rank": None,
        "recomputed_frequencies_cm1": None,
        "maximum_absolute_difference_cm1": None,
    }
    prerequisites = bool(
        matrix is not None
        and matrix.ndim == 2
        and matrix.shape[0] == matrix.shape[1]
        and np.isfinite(matrix).all()
        and np.allclose(
            matrix,
            matrix.T,
            rtol=_HESSIAN_SYMMETRY_RTOL,
            atol=_HESSIAN_SYMMETRY_ATOL,
        )
        and positions is not None
        and positions.shape == (len(symbols), 3)
        and np.isfinite(positions).all()
        and frequencies is not None
        and frequencies.ndim == 1
        and np.isfinite(frequencies).all()
    )
    if not prerequisites:
        return observation, [
            _result_finding(
                RULE_RESULT_HESSIAN_CONSISTENCY_UNVERIFIED,
                "results.hessian_frequency_consistency",
                "finite symmetric Hessian, geometry, and real frequency vector",
                "one or more prerequisites failed",
                "h5:/results",
            )
        ]
    try:
        recomputed, tr_rank = _independent_mass_weighted_frequencies(
            matrix=matrix,
            symbols=symbols,
            positions=positions,
            mode_count=mode_count,
        )
    except (
        ArithmeticError,
        KeyError,
        TypeError,
        ValueError,
        np.linalg.LinAlgError,
    ) as exc:
        observation["failure"] = type(exc).__name__
        return observation, [
            _result_finding(
                RULE_RESULT_HESSIAN_CONSISTENCY_UNVERIFIED,
                "results.hessian_frequency_consistency",
                "deterministic independent spectrum reconstruction",
                type(exc).__name__,
                "h5:/results/hessian",
            )
        ]

    observation["translation_rotation_rank"] = tr_rank
    observation["recomputed_frequencies_cm1"] = recomputed.tolist()
    if recomputed.shape != frequencies.shape:
        return observation, [
            _result_finding(
                RULE_RESULT_HESSIAN_CONSISTENCY,
                "results.vibrational_frequencies",
                {"shape_from_hessian": tuple(recomputed.shape)},
                {"reported_shape": tuple(frequencies.shape)},
                "h5:/results/vibrational_frequencies",
            )
        ]

    recomputed_sorted = np.sort(recomputed)
    reported_sorted = np.sort(frequencies)
    absolute_difference = np.abs(recomputed_sorted - reported_sorted)
    maximum_difference = (
        float(absolute_difference.max()) if absolute_difference.size else 0.0
    )
    observation["maximum_absolute_difference_cm1"] = maximum_difference
    if not np.allclose(
        recomputed_sorted,
        reported_sorted,
        rtol=_HESSIAN_FREQUENCY_RTOL,
        atol=_HESSIAN_FREQUENCY_ATOL_CM1,
    ):
        return observation, [
            _result_finding(
                RULE_RESULT_HESSIAN_CONSISTENCY,
                "results.vibrational_frequencies",
                {
                    "recomputed_cm1": recomputed_sorted.tolist(),
                    "absolute_tolerance_cm1": _HESSIAN_FREQUENCY_ATOL_CM1,
                    "relative_tolerance": _HESSIAN_FREQUENCY_RTOL,
                },
                reported_sorted.tolist(),
                "h5:/results/hessian",
            )
        ]
    observation["state"] = "verified"
    return observation, []


def _independent_mass_weighted_frequencies(
    *, matrix, symbols, positions, mode_count=None
):
    """Reconstruct signed harmonic wavenumbers without importing PySCF.

    The Cartesian Hessian (Eh/Bohr^2) is mass weighted with ASE's isotope-
    averaged atomic masses, the translation/rotation span is removed by SVD,
    and the remaining symmetric matrix is diagonalized.  SI conversion uses
    the CODATA-2018 literals declared at module scope.

    ``mode_count`` is how many modes the result being checked carries; the
    translation-rotation rank follows from it (3N minus the count), so the
    reconstruction removes exactly the space the reported spectrum implies
    was removed and the comparison below is a like-for-like one. Without
    it the rank comes from this module's own geometric linearity test,
    which near the linear boundary disagrees with the program and drops a
    real mode: on HNC 0.047 degrees from linear it projected out half of
    a degenerate bending pair and shifted the survivor by 0.33 cm-1,
    while at the reported count it reproduces all four frequencies to
    0.0000 cm-1. The masses and the arithmetic stay this module's own, so
    this is still an independent authority -- it takes only the dimension
    of the question from the artifact.
    """

    atomic_numbers = _expected_atomic_numbers(symbols)
    if len(atomic_numbers) != len(symbols) or not symbols:
        raise ValueError("unknown atomic symbol")
    masses = np.asarray(
        [ASE_ATOMIC_MASSES[number] for number in atomic_numbers], dtype=float
    )
    if not np.isfinite(masses).all() or bool((masses <= 0.0).any()):
        raise ValueError("invalid isotope-averaged atomic mass")

    coordinates = np.asarray(positions, dtype=float)
    center = np.einsum("i,ij->j", masses, coordinates) / masses.sum()
    centered = coordinates - center
    square_root_masses = np.sqrt(masses)
    vectors = []
    for axis in np.eye(3):
        vectors.append((square_root_masses[:, None] * axis).reshape(-1))
    for axis in np.eye(3):
        rotation = np.cross(centered, axis)
        vectors.append((square_root_masses[:, None] * rotation).reshape(-1))
    tr_matrix = np.column_stack(vectors)
    left, _, _ = np.linalg.svd(tr_matrix, full_matrices=True)
    if mode_count is not None and 0 <= int(mode_count) <= 3 * len(symbols):
        tr_rank = 3 * len(symbols) - int(mode_count)
    elif len(symbols) == 1:
        tr_rank = 3
    elif len(symbols) == 2:
        tr_rank = 5
    else:
        _, _, linear = _linearity_metrics(coordinates)
        if linear is None:
            raise ValueError("degenerate molecular geometry")
        tr_rank = 5 if linear else 6
    vibrational_basis = left[:, tr_rank:]

    coordinate_mass = np.repeat(square_root_masses, 3)
    mass_weighted = matrix / np.outer(coordinate_mass, coordinate_mass)
    projected = vibrational_basis.T @ mass_weighted @ vibrational_basis
    projected = 0.5 * (projected + projected.T)
    force_constants = np.linalg.eigvalsh(projected)
    conversion = (
        math.sqrt(_HARTREE_J / (_ATOMIC_MASS_KG * _BOHR_M**2))
        / (2.0 * math.pi * _LIGHT_SPEED_M_S)
        * 1.0e-2
    )
    frequencies = (
        np.sign(force_constants)
        * np.sqrt(np.abs(force_constants))
        * conversion
    )
    return frequencies.astype(float, copy=False), tr_rank


def _validate_orbital_arrays(
    results,
    findings,
    *,
    symbols,
    charge,
    multiplicity,
    observation,
):
    """Validate restricted or unrestricted orbital arrays and occupations."""

    mo_energy = _result_array(results.get("mo_energy"))
    mo_occ = _result_array(results.get("mo_occ"))
    valid_shapes = bool(
        mo_energy is not None
        and mo_occ is not None
        and mo_energy.shape == mo_occ.shape
        and (
            (mo_energy.ndim == 1 and mo_energy.size > 0)
            or (
                mo_energy.ndim == 2
                and mo_energy.shape[0] == 2
                and mo_energy.shape[1] > 0
            )
        )
    )
    if not valid_shapes:
        findings.append(
            _result_finding(
                RULE_RESULT_SHAPE,
                "results.mo_energy/mo_occ",
                "matching non-empty (N,) restricted or (2,N) unrestricted arrays",
                {
                    "mo_energy": _array_observation(mo_energy),
                    "mo_occ": _array_observation(mo_occ),
                },
                "h5:/results",
            )
        )
        return
    for field, values in (("mo_energy", mo_energy), ("mo_occ", mo_occ)):
        if not bool(np.isfinite(values).all()):
            findings.append(
                _result_finding(
                    RULE_RESULT_NONFINITE,
                    f"results.{field}",
                    "finite real orbital array",
                    _array_observation(values),
                    f"h5:/results/{field}",
                )
            )
    if not bool(np.isfinite(mo_occ).all()):
        return

    atomic_numbers = _expected_atomic_numbers(symbols)
    expected_electrons = sum(atomic_numbers) - int(charge)
    expected_spin = int(multiplicity) - 1
    if (
        not atomic_numbers
        or expected_electrons < 0
        or expected_spin < 0
        or expected_spin > expected_electrons
        or (expected_electrons - expected_spin) % 2
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_STATE,
                "expected.electronic_state",
                "non-negative electron count with parity-compatible spin",
                {
                    "electron_count": expected_electrons,
                    "spin": expected_spin,
                },
                "derived:symbols-charge-multiplicity",
            )
        )
        return
    expected_alpha = (expected_electrons + expected_spin) // 2
    expected_beta = (expected_electrons - expected_spin) // 2
    observation["expected_electron_count"] = expected_electrons
    observation["expected_alpha_beta"] = (expected_alpha, expected_beta)

    if mo_occ.ndim == 1:
        observation["orbital_representation"] = "restricted"
        bounds_valid = bool(
            (mo_occ >= -_OCCUPATION_ATOL).all()
            and (mo_occ <= 2.0 + _OCCUPATION_ATOL).all()
        )
        integer_like = bool(
            np.allclose(
                mo_occ,
                np.rint(mo_occ),
                rtol=0.0,
                atol=_OCCUPATION_ATOL,
            )
            and np.isin(np.rint(mo_occ).astype(int), (0, 1, 2)).all()
        )
        if not bounds_valid or not integer_like:
            findings.append(
                _result_finding(
                    RULE_RESULT_OCCUPATION,
                    "results.mo_occ",
                    "restricted occupations in {0, 1, 2}",
                    mo_occ.tolist(),
                    "h5:/results/mo_occ",
                )
            )
        rounded = np.rint(mo_occ)
        observed_electrons = float(mo_occ.sum())
        observed_spin = int(np.count_nonzero(rounded == 1.0))
        observed_alpha = (observed_electrons + observed_spin) / 2.0
        observed_beta = (observed_electrons - observed_spin) / 2.0
    else:
        observation["orbital_representation"] = "unrestricted"
        bounds_valid = bool(
            (mo_occ >= -_OCCUPATION_ATOL).all()
            and (mo_occ <= 1.0 + _OCCUPATION_ATOL).all()
        )
        integer_like = bool(
            np.allclose(
                mo_occ,
                np.rint(mo_occ),
                rtol=0.0,
                atol=_OCCUPATION_ATOL,
            )
            and np.isin(np.rint(mo_occ).astype(int), (0, 1)).all()
        )
        if not bounds_valid or not integer_like:
            findings.append(
                _result_finding(
                    RULE_RESULT_OCCUPATION,
                    "results.mo_occ",
                    "unrestricted alpha/beta occupations in {0, 1}",
                    mo_occ.tolist(),
                    "h5:/results/mo_occ",
                )
            )
        observed_alpha = float(mo_occ[0].sum())
        observed_beta = float(mo_occ[1].sum())
        observed_electrons = observed_alpha + observed_beta
        observed_spin = observed_alpha - observed_beta

    observation["observed_electron_count"] = observed_electrons
    observation["observed_alpha_beta"] = (observed_alpha, observed_beta)
    if not math.isclose(
        observed_electrons,
        float(expected_electrons),
        rel_tol=0.0,
        abs_tol=_OCCUPATION_ATOL,
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_OCCUPATION,
                "results.mo_occ.electron_total",
                expected_electrons,
                observed_electrons,
                "h5:/results/mo_occ",
            )
        )
    if not (
        math.isclose(
            observed_alpha,
            float(expected_alpha),
            rel_tol=0.0,
            abs_tol=_OCCUPATION_ATOL,
        )
        and math.isclose(
            observed_beta,
            float(expected_beta),
            rel_tol=0.0,
            abs_tol=_OCCUPATION_ATOL,
        )
        and math.isclose(
            observed_spin,
            float(expected_spin),
            rel_tol=0.0,
            abs_tol=_OCCUPATION_ATOL,
        )
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_OCCUPATION,
                "results.mo_occ.alpha_beta_spin",
                {
                    "alpha": expected_alpha,
                    "beta": expected_beta,
                    "spin": expected_spin,
                },
                {
                    "alpha": observed_alpha,
                    "beta": observed_beta,
                    "spin": observed_spin,
                },
                "h5:/results/mo_occ",
            )
        )


def _validate_result_electron_metadata(
    spec, findings, *, symbols, charge, multiplicity
):
    atomic_numbers = _expected_atomic_numbers(symbols)
    if not atomic_numbers:
        return
    electron_count = sum(atomic_numbers) - int(charge)
    spin = int(multiplicity) - 1
    if electron_count < 0 or spin < 0 or (electron_count - spin) % 2:
        return
    expected_nelec = (
        (electron_count + spin) // 2,
        (electron_count - spin) // 2,
    )
    observed_count = spec.get("num_electrons")
    if (
        isinstance(observed_count, bool)
        or not isinstance(observed_count, Integral)
        or int(observed_count) != electron_count
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_STATE,
                "spec.num_electrons",
                electron_count,
                observed_count,
                "h5:/spec/num_electrons",
            )
        )
    observed_nelec = spec.get("nelec")
    try:
        observed_pair = tuple(observed_nelec)
    except TypeError:
        observed_pair = ()
    if (
        len(observed_pair) != 2
        or any(
            isinstance(value, bool) or not isinstance(value, Integral)
            for value in observed_pair
        )
        or tuple(int(value) for value in observed_pair) != expected_nelec
    ):
        findings.append(
            _result_finding(
                RULE_RESULT_STATE,
                "spec.nelec",
                expected_nelec,
                observed_pair,
                "h5:/spec/nelec",
            )
        )


def _result_array(value):
    if value is None:
        return None
    try:
        array = np.asarray(value)
        if array.dtype.kind not in {"i", "u", "f"}:
            return None
        return array.astype(float, copy=False)
    except (TypeError, ValueError):
        return None


def _array_observation(value):
    if value is None:
        return {"shape": None, "all_finite": False}
    return {
        "shape": list(value.shape),
        "all_finite": bool(np.isfinite(value).all()),
    }


def _expected_atomic_numbers(symbols):
    try:
        return tuple(int(ASE_ATOMIC_NUMBERS[symbol]) for symbol in symbols)
    except (KeyError, TypeError):
        return ()


def _is_sha256(value):
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _result_finding(rule_id, field, expected, observed, evidence_ref):
    return PySCFViolation(
        rule_id=rule_id,
        field=field,
        expected=expected,
        observed=observed,
        evidence_ref=evidence_ref,
    )


def _deduplicate_result_findings(findings):
    deduplicated = []
    seen = set()
    for finding in findings:
        key = (finding.rule_id, finding.field, finding.evidence_ref)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(finding)
    return deduplicated


def _verify_bound_receipt(spec, provenance, expected_receipt):
    """Verify exact controller-to-child hashes when a runner supplies them.

    ``expected_receipt`` is optional to keep historical V1 artifacts readable.
    A hardened run always supplies it and therefore fails closed on absent or
    substituted script, input, environment, geometry, project, or settings
    evidence.
    """
    if not expected_receipt:
        return []

    violations = []
    expected_fields = (
        "run_id",
        "run_nonce",
        "script_sha256",
        "input_receipt_sha256",
        "environment_receipt_sha256",
        "input_geometry_sha256",
        "input_artifact_kind",
        "input_artifact_sha256",
        "requested_settings_sha256",
        "project_yaml_digest",
    )
    spec_mirrors = frozenset(
        {
            "run_id",
            "run_nonce",
            "input_geometry_sha256",
            "input_artifact_kind",
            "input_artifact_sha256",
            "requested_settings_sha256",
        }
    )
    for field in expected_fields:
        expected = expected_receipt.get(field, _MISSING)
        if expected is _MISSING:
            continue
        observed = provenance.get(field, _MISSING)
        if observed is _MISSING or observed != expected:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_RECEIPT,
                    field=f"provenance.{field}",
                    expected=expected,
                    observed=(
                        "<missing>" if observed is _MISSING else observed
                    ),
                    evidence_ref=f"h5:/provenance/{field}",
                )
            )
        if field in spec_mirrors:
            spec_observed = spec.get(field, _MISSING)
            if spec_observed is _MISSING or spec_observed != expected:
                violations.append(
                    PySCFViolation(
                        rule_id=RULE_PROVENANCE_RECEIPT,
                        field=f"spec.{field}",
                        expected=expected,
                        observed=(
                            "<missing>"
                            if spec_observed is _MISSING
                            else spec_observed
                        ),
                        evidence_ref=f"h5:/spec/{field}",
                    )
                )

    spec_applied = spec.get("applied_settings_sha256", _MISSING)
    provenance_applied = provenance.get("applied_settings_sha256", _MISSING)
    require_applied = bool(
        expected_receipt.get("require_applied_settings_sha256", False)
    )
    expected_applied = expected_receipt.get(
        "applied_settings_sha256", _MISSING
    )
    if expected_applied is not _MISSING:
        for container, observed in (
            ("spec", spec_applied),
            ("provenance", provenance_applied),
        ):
            if observed != expected_applied:
                violations.append(
                    PySCFViolation(
                        rule_id=RULE_PROVENANCE_APPLIED_DIGEST,
                        field=f"{container}.applied_settings_sha256",
                        expected=expected_applied,
                        observed=(
                            "<missing>" if observed is _MISSING else observed
                        ),
                        evidence_ref=(
                            f"h5:/{container}/applied_settings_sha256"
                        ),
                    )
                )
    if require_applied and spec_applied in (_MISSING, None, ""):
        violations.append(
            PySCFViolation(
                rule_id=RULE_PROVENANCE_APPLIED_DIGEST,
                field="spec.applied_settings_sha256",
                expected="non-empty digest of applied settings",
                observed=(
                    "<missing>" if spec_applied is _MISSING else spec_applied
                ),
                evidence_ref="h5:/spec/applied_settings_sha256",
            )
        )
    if spec_applied != provenance_applied:
        violations.append(
            PySCFViolation(
                rule_id=RULE_PROVENANCE_APPLIED_DIGEST,
                field="provenance.applied_settings_sha256",
                expected=(
                    "same value as spec.applied_settings_sha256"
                    if spec_applied is _MISSING
                    else spec_applied
                ),
                observed=(
                    "<missing>"
                    if provenance_applied is _MISSING
                    else provenance_applied
                ),
                evidence_ref="h5:/provenance/applied_settings_sha256",
            )
        )
    if spec_applied not in (_MISSING, None, ""):
        from chemsmart.jobs.pyscf.writer import (
            PySCFScriptWriter,
            applied_pyscf_spec_fields,
        )

        fields = applied_pyscf_spec_fields(spec)
        applied_payload = {field: spec.get(field) for field in fields}
        observed_digest = PySCFScriptWriter.settings_digest(applied_payload)
        if observed_digest != spec_applied:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_PROVENANCE_APPLIED_DIGEST,
                    field="spec.applied_settings_sha256",
                    expected=observed_digest,
                    observed=spec_applied,
                    evidence_ref="h5:/spec/applied_settings_sha256",
                )
            )
    return violations


def _check_unsupported_settings(settings, _molecule, _environment):
    defaults = dict(_UNSUPPORTED_DEFAULTS)
    declared = _member(settings, "UNSUPPORTED", {})
    if isinstance(declared, Mapping):
        defaults.update(declared)

    violations = []
    for field, value in _settings_items(settings):
        if str(field).startswith("_") or field in _SUPPORTED_FIELDS:
            continue
        if field in defaults and _is_unset(value, defaults[field]):
            continue
        violations.append(
            PySCFViolation(
                rule_id=RULE_UNSUPPORTED_SETTING,
                field=str(field),
                expected="supported PySCF setting or its unset default",
                observed=value,
                evidence_ref=f"settings:{field}",
            )
        )
    return violations


def _check_setting_values(settings, _molecule, _environment):
    violations = []
    charge_override = _member(settings, "charge", None)
    multiplicity_override = _member(settings, "multiplicity", None)
    if (charge_override is None) != (multiplicity_override is None):
        violations.append(
            PySCFViolation(
                rule_id=RULE_STATE_OVERRIDE_PAIR,
                field="charge_multiplicity",
                expected=(
                    "both explicit overrides or both inherited from the "
                    "molecular source"
                ),
                observed={
                    "charge": charge_override,
                    "multiplicity": multiplicity_override,
                },
                evidence_ref="settings:charge,multiplicity",
            )
        )
    jobtype = _member(settings, "jobtype", None)
    if jobtype not in PYSCF_JOBTYPES:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="jobtype",
                expected=PYSCF_JOBTYPES,
                observed=jobtype,
                evidence_ref="settings:jobtype",
            )
        )
    freq = _member(settings, "freq", False)
    if type(freq) is not bool:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="freq",
                expected="strict boolean",
                observed=freq,
                evidence_ref="settings:freq",
            )
        )
    elif jobtype != "hess" and freq:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="freq",
                expected=False,
                observed=True,
                evidence_ref="settings:freq",
            )
        )
    elif jobtype == "hess" and not freq:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="freq",
                expected=True,
                observed=False,
                evidence_ref="settings:freq",
            )
        )

    response_method = _member(settings, "response_method", None)
    state_manifold = _member(settings, "state_manifold", None)
    nstates = _member(settings, "nstates", None)
    ab_initio = _member(settings, "ab_initio", None)
    functional = _member(settings, "functional", None)
    excited_root = _member(settings, "excited_state_root", None)
    td_max_cycle = _member(settings, "td_max_cycle", None)
    violations.extend(
        _check_response_settings(
            settings,
            _molecule,
            jobtype=jobtype,
            response_method=response_method,
            state_manifold=state_manifold,
            nstates=nstates,
            ab_initio=ab_initio,
            functional=functional,
            excited_root=excited_root,
            td_max_cycle=td_max_cycle,
        )
    )
    violations.extend(
        _check_correlated_settings(
            settings, jobtype=jobtype, ab_initio=ab_initio
        )
    )
    density_fit = _member(settings, "density_fit", False)
    if type(density_fit) is not bool:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="density_fit",
                expected="strict boolean",
                observed=density_fit,
                evidence_ref="settings:density_fit",
            )
        )
    # An observation, never a gate: the flag decides whether the driver
    # asks PySCF the question, and no value of the answer refuses anything.
    scf_stability = _member(settings, "scf_stability", False)
    if type(scf_stability) is not bool:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="scf_stability",
                expected="strict boolean",
                observed=scf_stability,
                evidence_ref="settings:scf_stability",
            )
        )
    scf_tol = _member(settings, "scf_tol", None)
    if scf_tol is not None and (
        isinstance(scf_tol, bool)
        or not isinstance(scf_tol, Real)
        or not math.isfinite(float(scf_tol))
        or float(scf_tol) <= 0
    ):
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="scf_tol",
                expected="finite positive scalar",
                observed=scf_tol,
                evidence_ref="settings:scf_tol",
            )
        )
    for field in (
        "scf_maxiter",
        "opt_maxsteps",
        "td_max_cycle",
        "cc_max_cycle",
    ):
        value = _member(
            settings, field, 100 if field == "opt_maxsteps" else None
        )
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, Integral)
            or int(value) <= 0
        ):
            violations.append(
                PySCFViolation(
                    rule_id=RULE_INVALID_SETTING,
                    field=field,
                    expected="positive integer",
                    observed=value,
                    evidence_ref=f"settings:{field}",
                )
            )
    engine = _member(settings, "engine", "cpu")
    if engine is not None and str(engine).lower() not in PYSCF_ENGINES:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="engine",
                expected=tuple(PYSCF_ENGINES),
                observed=engine,
                evidence_ref="settings:engine",
            )
        )

    solver = _member(settings, "opt_solver", "geometric")
    if solver is not None and str(solver).lower() not in PYSCF_OPT_SOLVERS:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="opt_solver",
                expected=tuple(PYSCF_OPT_SOLVERS),
                observed=solver,
                evidence_ref="settings:opt_solver",
            )
        )

    if (
        ab_initio is not None
        and str(ab_initio).strip().lower() not in PYSCF_AB_INITIO_METHODS
    ):
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="ab_initio",
                expected=PYSCF_AB_INITIO_METHODS,
                observed=ab_initio,
                evidence_ref="settings:ab_initio",
            )
        )
    if ab_initio is not None and functional is not None:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="method",
                expected="exactly one of ab_initio or functional",
                observed={
                    "ab_initio": ab_initio,
                    "functional": functional,
                },
                evidence_ref="settings:method",
            )
        )

    if is_double_hybrid_functional(functional):
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="functional",
                expected="non-double-hybrid DFT functional",
                observed=functional,
                evidence_ref="settings:functional",
            )
        )

    if ab_initio is None and not functional:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="method",
                expected="ab_initio='hf' or a DFT functional",
                observed=None,
                evidence_ref="settings:method",
            )
        )

    basis = _member(settings, "basis", None)
    if not basis:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="basis",
                expected="non-empty PySCF basis name",
                observed=basis,
                evidence_ref="settings:basis",
            )
        )

    defgrid = _member(settings, "defgrid", None)
    if defgrid is not None and str(defgrid).lower() not in PYSCF_DEFGRIDS:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="defgrid",
                expected=tuple(sorted(PYSCF_DEFGRIDS)),
                observed=defgrid,
                evidence_ref="settings:defgrid",
            )
        )
    elif defgrid is not None and ab_initio is not None:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="defgrid",
                expected="unset for ab_initio HF",
                observed=defgrid,
                evidence_ref="settings:defgrid",
            )
        )

    density_fit = _member(settings, "density_fit", False) is True
    aux_basis = _member(settings, "aux_basis", None)
    if not density_fit and aux_basis is not None:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="aux_basis",
                expected="unset when density_fit is disabled",
                observed=aux_basis,
                evidence_ref="settings:aux_basis",
            )
        )
    return violations


def _check_response_settings(
    settings,
    molecule,
    *,
    jobtype,
    response_method,
    state_manifold,
    nstates,
    ab_initio,
    functional,
    excited_root,
    td_max_cycle,
):
    """The executable TDA/TDDFT contract for ``td`` and an excited opt.

    Mirrors ``PySCFJobSettings._validate_response`` as typed violations,
    so a preview reports every refusal by rule id before an engine is
    spent.  The manifold is checked against the *resolved* multiplicity:
    a closed-shell reference asks for singlet or triplet excitations and an
    open-shell reference has exactly one spin-conserving manifold.
    """

    violations = []
    populated = {
        key: value
        for key, value in (
            ("response_method", response_method),
            ("state_manifold", state_manifold),
            ("nstates", nstates),
            ("td_max_cycle", td_max_cycle),
            ("excited_state_root", excited_root),
        )
        if value is not None
    }
    requested = jobtype == "td" or (
        jobtype in PYSCF_EXCITED_SURFACE_JOBTYPES and excited_root is not None
    )
    if (
        excited_root is not None
        and jobtype not in PYSCF_EXCITED_SURFACE_JOBTYPES
    ):
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="excited_state_root",
                expected=(
                    "unset outside "
                    f"{sorted(PYSCF_EXCITED_SURFACE_JOBTYPES)}"
                ),
                observed={
                    "jobtype": jobtype,
                    "excited_state_root": excited_root,
                },
                evidence_ref="settings:excited_state_root",
            )
        )
        return violations
    if not requested:
        if populated:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_INVALID_SETTING,
                    field="td_settings",
                    expected=(
                        "unset outside the td jobtype or an opt carrying "
                        "excited_state_root"
                    ),
                    observed=populated,
                    evidence_ref="settings:jobtype",
                )
            )
        return violations
    if str(response_method or "").strip().lower() not in (
        PYSCF_RESPONSE_METHODS
    ):
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="response_method",
                expected=PYSCF_RESPONSE_METHODS,
                observed=response_method,
                evidence_ref="settings:response_method",
            )
        )
    manifold = str(state_manifold or "").strip().lower()
    if manifold not in PYSCF_STATE_MANIFOLDS:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="state_manifold",
                expected=PYSCF_STATE_MANIFOLDS,
                observed=state_manifold,
                evidence_ref="settings:state_manifold",
            )
        )
    if (
        isinstance(nstates, bool)
        or not isinstance(nstates, Integral)
        or int(nstates) <= 0
    ):
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="nstates",
                expected="positive integer",
                observed=nstates,
                evidence_ref="settings:nstates",
            )
        )
    if ab_initio is not None or not functional:
        violations.append(
            PySCFViolation(
                rule_id=RULE_TD_REFERENCE,
                field="method",
                expected="a Kohn-Sham reference (functional set, no ab_initio)",
                observed={"ab_initio": ab_initio, "functional": functional},
                evidence_ref="settings:method",
            )
        )
    resolved_multiplicity = _integral_value(
        _resolved_value(settings, molecule, "multiplicity")
    )
    if resolved_multiplicity is not _MISSING and manifold in (
        PYSCF_STATE_MANIFOLDS
    ):
        # One rule for every program: which manifolds a reference has.
        from chemsmart.jobs.settings import td_manifold_reference_refusal

        refusal = td_manifold_reference_refusal(
            manifold, int(resolved_multiplicity)
        )
        if refusal:
            restricted = int(resolved_multiplicity) == 1
            violations.append(
                PySCFViolation(
                    rule_id=RULE_TD_REFERENCE,
                    field="state_manifold",
                    expected=(
                        tuple(
                            word
                            for word in PYSCF_STATE_MANIFOLDS
                            if word != PYSCF_UNRESTRICTED_MANIFOLD
                        )
                        if restricted
                        else PYSCF_UNRESTRICTED_MANIFOLD
                    ),
                    observed={
                        "state_manifold": manifold,
                        "multiplicity": int(resolved_multiplicity),
                        "reason": refusal,
                    },
                    evidence_ref="resolved:multiplicity",
                )
            )
    if excited_root is not None:
        if manifold == PYSCF_TWO_BLOCK_MANIFOLD:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_INVALID_SETTING,
                    field="state_manifold",
                    expected="one manifold (singlet or triplet) for a root",
                    observed={
                        "state_manifold": manifold,
                        "excited_state_root": excited_root,
                        "reason": (
                            "excited_state_root follows one root of one "
                            "manifold; singlet_triplet holds two"
                        ),
                    },
                    evidence_ref="settings:state_manifold",
                )
            )
        if (
            isinstance(excited_root, bool)
            or not isinstance(excited_root, Integral)
            or int(excited_root) <= 0
            or (
                isinstance(nstates, Integral)
                and not isinstance(nstates, bool)
                and int(excited_root) > int(nstates)
            )
        ):
            violations.append(
                PySCFViolation(
                    rule_id=RULE_INVALID_SETTING,
                    field="excited_state_root",
                    expected="positive root index no larger than nstates",
                    observed={
                        "excited_state_root": excited_root,
                        "nstates": nstates,
                    },
                    evidence_ref="settings:excited_state_root",
                )
            )
        if (
            _member(settings, "solvent_model", None) is not None
            or _member(settings, "solvent_id", None) is not None
        ):
            violations.append(
                PySCFViolation(
                    rule_id=RULE_TD_GRADIENT_SOLVENT,
                    field="solvent_model",
                    expected="gas phase for an excited-root optimisation",
                    observed={
                        "solvent_model": _member(
                            settings, "solvent_model", None
                        ),
                        "solvent_id": _member(settings, "solvent_id", None),
                        "reason": (
                            "PySCF 2.14 raises NotImplementedError for "
                            "PCM-TDDFT gradients; solvated td energies at a "
                            "fixed geometry remain available"
                        ),
                    },
                    evidence_ref="settings:solvent_model",
                )
            )
        solver = _member(settings, "opt_solver", "geometric")
        if str(solver).lower() != "geometric":
            violations.append(
                PySCFViolation(
                    rule_id=RULE_SOLVER_UNAUDITED_SURFACE,
                    field="opt_solver",
                    expected="geometric",
                    observed=solver,
                    evidence_ref="settings:opt_solver",
                )
            )
    if _member(settings, "dispersion", None) is not None:
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="dispersion",
                expected="unset for a response calculation",
                observed=_member(settings, "dispersion", None),
                evidence_ref="settings:dispersion",
            )
        )
    if str(_member(settings, "engine", "cpu")).strip().lower() != "cpu":
        violations.append(
            PySCFViolation(
                rule_id=RULE_TD_GPU_UNSUPPORTED,
                field="engine",
                expected="cpu",
                observed=_member(settings, "engine", None),
                evidence_ref="settings:engine",
            )
        )
    return violations


def _check_correlated_settings(settings, *, jobtype, ab_initio):
    """Cross-field rules for ``mp2``/``ccsd``/``ccsd(t)`` as typed violations.

    Each names the route it leaves open; none grades the chemistry.  The
    CCSD(T) gradient exists in PySCF 2.14 (``pyscf.grad.ccsd_t``) and is
    refused here as *unaudited*, never as absent.
    """

    violations = []
    method = pyscf_correlated_method(ab_initio)
    frozen = _member(settings, "frozen_core", None)
    cc_max_cycle = _member(settings, "cc_max_cycle", None)
    if method is None:
        for field, value in (
            ("frozen_core", frozen),
            ("cc_max_cycle", cc_max_cycle),
        ):
            if value is not None:
                violations.append(
                    PySCFViolation(
                        rule_id=RULE_INVALID_SETTING,
                        field=field,
                        expected="unset without a correlated ab_initio method",
                        observed=value,
                        evidence_ref=f"settings:{field}",
                    )
                )
        return violations
    if jobtype == "hess":
        violations.append(
            PySCFViolation(
                rule_id=RULE_CORRELATION_HESSIAN,
                field="jobtype",
                expected="an HF or DFT hess node",
                observed={"jobtype": jobtype, "ab_initio": method},
                evidence_ref="settings:jobtype",
            )
        )
    if jobtype == "opt" and method == "ccsd(t)":
        violations.append(
            PySCFViolation(
                rule_id=RULE_CORRELATION_CCSDT_GRADIENT,
                field="jobtype",
                expected=(
                    "opt at mp2 or ccsd, then a ccsd(t) single point on the "
                    "reached geometry"
                ),
                observed={
                    "jobtype": jobtype,
                    "ab_initio": method,
                    "reason": (
                        "PySCF 2.14 carries pyscf.grad.ccsd_t; this driver "
                        "has not audited it"
                    ),
                },
                evidence_ref="settings:jobtype",
            )
        )
    if _member(settings, "density_fit", False) is True:
        violations.append(
            PySCFViolation(
                rule_id=RULE_CORRELATION_DENSITY_FIT,
                field="density_fit",
                expected=False,
                observed=True,
                evidence_ref="settings:density_fit",
            )
        )
    if (
        _member(settings, "solvent_model", None) is not None
        or _member(settings, "solvent_id", None) is not None
    ):
        violations.append(
            PySCFViolation(
                rule_id=RULE_CORRELATION_SOLVENT,
                field="solvent_model",
                expected="gas phase for a correlated method in this release",
                observed={
                    "solvent_model": _member(settings, "solvent_model", None),
                    "solvent_id": _member(settings, "solvent_id", None),
                },
                evidence_ref="settings:solvent_model",
            )
        )
    if _member(settings, "dispersion", None) is not None:
        violations.append(
            PySCFViolation(
                rule_id=RULE_CORRELATION_DISPERSION,
                field="dispersion",
                expected="unset for a correlated method in this release",
                observed=_member(settings, "dispersion", None),
                evidence_ref="settings:dispersion",
            )
        )
    if jobtype == "opt":
        solver = _member(settings, "opt_solver", "geometric")
        if str(solver).lower() != "geometric":
            violations.append(
                PySCFViolation(
                    rule_id=RULE_SOLVER_UNAUDITED_SURFACE,
                    field="opt_solver",
                    expected="geometric",
                    observed=solver,
                    evidence_ref="settings:opt_solver",
                )
            )
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
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="frozen_core",
                expected=f"non-negative orbital count or {PYSCF_FROZEN_CORE_AUTO!r}",
                observed=frozen,
                evidence_ref="settings:frozen_core",
            )
        )
    if cc_max_cycle is not None and method not in (
        PYSCF_COUPLED_CLUSTER_METHODS
    ):
        violations.append(
            PySCFViolation(
                rule_id=RULE_INVALID_SETTING,
                field="cc_max_cycle",
                expected="unset for mp2 (no amplitude iteration)",
                observed=cc_max_cycle,
                evidence_ref="settings:cc_max_cycle",
            )
        )
    return violations


def _check_solvent(settings, _molecule, environment):
    model = _member(settings, "solvent_model", None)
    solvent_id = _member(settings, "solvent_id", None)
    violations = []

    if model is None:
        if solvent_id is not None:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_SOLVENT_MODEL,
                    field="solvent_model",
                    expected="model for the requested solvent_id",
                    observed=None,
                    evidence_ref="settings:solvent_model",
                )
            )
        return violations

    normal_model = str(model).strip().lower()
    if normal_model not in PYSCF_SOLVENT_MODELS:
        violations.append(
            PySCFViolation(
                rule_id=RULE_SOLVENT_MODEL,
                field="solvent_model",
                expected=tuple(sorted(PYSCF_SOLVENT_MODELS)),
                observed=model,
                evidence_ref="settings:solvent_model",
            )
        )

    if normal_model in PYSCF_SOLVENT_MODELS and not solvent_id:
        violations.append(
            PySCFViolation(
                rule_id=RULE_SOLVENT_ID_REQUIRED,
                field="solvent_id",
                expected="non-empty PySCF solvent name",
                observed=solvent_id,
                evidence_ref="settings:solvent_id",
            )
        )
        return violations

    if solvent_id:
        solvent_keys = _solvent_keys(environment)
        if solvent_keys is _MISSING:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_SOLVENT_DATABASE,
                    field="environment.solvent_db",
                    expected="probed PySCF solvent names",
                    observed="<missing>",
                    evidence_ref="environment:solvent_db",
                )
            )
        elif str(solvent_id).strip().lower() not in solvent_keys:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_SOLVENT_ID_UNKNOWN,
                    field="solvent_id",
                    expected="member of PySCF solvent_db",
                    observed=solvent_id,
                    evidence_ref="environment:solvent_db",
                )
            )
    return violations


def _check_solver(settings, _molecule, environment):
    if not _optimization_requested(settings, environment):
        return []

    solver = str(_member(settings, "opt_solver", "geometric")).lower()
    if solver not in _SOLVER_ENTRYPOINTS:
        return []
    probe = _first_environment(
        environment,
        ("solver_callables", solver),
        ("solver_entrypoints", solver),
        ("solvers", solver),
        ("entrypoints", _SOLVER_ENTRYPOINTS[solver]),
        (_SOLVER_ENTRYPOINTS[solver],),
    )
    if _callable_probe(probe):
        return []
    return [
        PySCFViolation(
            rule_id=RULE_SOLVER_UNCALLABLE,
            field="opt_solver",
            expected=_SOLVER_ENTRYPOINTS[solver],
            observed=_describe_probe(probe),
            evidence_ref=f"environment:solver_callables/{solver}",
        )
    ]


def _check_dispersion(settings, _molecule, environment):
    dispersion = _member(settings, "dispersion", None)
    if not dispersion:
        return []
    probe = _dependency_probe(
        environment,
        "pyscf_dispersion",
        "pyscf-dispersion",
        "dispersion_available",
    )
    if not _available_probe(probe):
        return [
            PySCFViolation(
                rule_id=RULE_DISPERSION_MISSING,
                field="dispersion",
                expected="pyscf-dispersion available",
                observed=_describe_probe(probe),
                evidence_ref="environment:dependencies/pyscf-dispersion",
            )
        ]

    conformance = _first_environment(
        environment,
        ("dispersion_conformance",),
        ("pyscf", "dispersion_conformance"),
        ("capabilities", "dispersion_conformance"),
    )
    expected_method = _member(settings, "xc", _MISSING)
    if expected_method is _MISSING or expected_method is None:
        expected_method = _member(settings, "functional", _MISSING)
    if expected_method is _MISSING or expected_method is None:
        expected_method = _member(settings, "ab_initio", _MISSING)
    if expected_method is _MISSING or expected_method is None:
        expected_method = "hf"
    expected_method = str(expected_method).strip().lower()

    identity_matches = bool(
        isinstance(conformance, Mapping)
        and conformance.get("schema_version")
        == "chemsmart.pyscf-dispersion-conformance.v1"
        and conformance.get("requested_literal") == dispersion
        and str(conformance.get("requested_method") or "").strip().lower()
        == expected_method
    )
    if not identity_matches:
        return [
            PySCFViolation(
                rule_id=RULE_DISPERSION_UNVERIFIED,
                field="dispersion",
                expected={
                    "literal": dispersion,
                    "method": expected_method,
                    "target_probe": "parse_disp + check_disp",
                },
                observed=(
                    _describe_probe(conformance)
                    if not isinstance(conformance, Mapping)
                    else dict(conformance)
                ),
                evidence_ref="environment:dispersion_conformance",
            )
        ]

    status = conformance.get("status")
    if status == "invalid" or conformance.get("supported") is not True:
        return [
            PySCFViolation(
                rule_id=RULE_DISPERSION_INVALID,
                field="dispersion",
                expected="literal accepted by target PySCF parse_disp/check_disp",
                observed=dict(conformance),
                evidence_ref="environment:dispersion_conformance",
            )
        ]
    if (
        status != "supported"
        or conformance.get("method_compatible") is not True
        or not isinstance(conformance.get("parsed_method"), str)
        or not conformance.get("parsed_method")
        or not isinstance(conformance.get("dispersion_version"), str)
        or not conformance.get("dispersion_version")
        or type(conformance.get("with_3body")) is not bool
    ):
        return [
            PySCFViolation(
                rule_id=RULE_DISPERSION_METHOD,
                field="dispersion",
                expected={
                    "method": expected_method,
                    "compatible": True,
                    "supported": True,
                },
                observed=dict(conformance),
                evidence_ref="environment:dispersion_conformance",
            )
        ]
    return []


def _check_gpu(settings, _molecule, environment):
    if str(_member(settings, "engine", "cpu")).lower() != "gpu":
        return []

    violations = []
    for dependency, aliases in (
        ("gpu4pyscf", ("gpu4pyscf", "gpu4pyscf_available")),
        ("cupy", ("cupy", "cupy_available")),
    ):
        probe = _dependency_probe(environment, *aliases)
        if not _available_probe(probe):
            violations.append(
                PySCFViolation(
                    rule_id=RULE_GPU_DEPENDENCY,
                    field=f"environment.{dependency}",
                    expected=f"{dependency} available",
                    observed=_describe_probe(probe),
                    evidence_ref=f"environment:dependencies/{dependency}",
                )
            )

    cuda_probe = _first_environment(
        environment,
        ("cuda_available",),
        ("gpu", "cuda_available"),
        ("gpu", "device_count"),
        ("num_cuda_devices",),
    )
    if not _positive_or_available(cuda_probe):
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_CUDA,
                field="environment.cuda_available",
                expected="at least one visible CUDA device",
                observed=_describe_probe(cuda_probe),
                evidence_ref="environment:gpu/cuda_available",
            )
        )

    tensor_probe = _cutensor_compatibility(environment)
    if tensor_probe is not True:
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_TENSOR,
                field="environment.cutensor_compatible",
                expected="compatible CuPy/cuTENSOR pair using cuTENSOR",
                observed=_describe_probe(tensor_probe),
                evidence_ref="environment:gpu/cutensor_compatible",
            )
        )

    basis = _member(settings, "basis", None)
    basis_l = _basis_max_l(environment, "basis", basis)
    if basis_l is _MISSING:
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_BASIS,
                field="basis",
                expected="probed maximum angular momentum <= g (l=4)",
                observed="<missing>",
                evidence_ref="environment:gpu/basis_max_l",
            )
        )
    elif basis_l > _ANGULAR_MOMENTA["g"]:
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_BASIS,
                field="basis",
                expected="maximum angular momentum <= g (l=4)",
                observed=_angular_label(basis_l),
                evidence_ref="environment:gpu/basis_max_l",
            )
        )

    aux_basis = _member(settings, "aux_basis", None)
    aux_l = _basis_max_l(environment, "aux_basis", aux_basis)
    if aux_basis and aux_l is _MISSING:
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_AUX_BASIS,
                field="aux_basis",
                expected="probed maximum angular momentum <= i (l=6)",
                observed="<missing>",
                evidence_ref="environment:gpu/aux_basis_max_l",
            )
        )
    elif aux_l is not _MISSING and aux_l > _ANGULAR_MOMENTA["i"]:
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_AUX_BASIS,
                field="aux_basis",
                expected="maximum angular momentum <= i (l=6)",
                observed=_angular_label(aux_l),
                evidence_ref="environment:gpu/aux_basis_max_l",
            )
        )

    functional = _member(settings, "functional", None)
    double_hybrid = _functional_evidence(
        environment, functional, "double_hybrid"
    )
    laplacian_meta_gga = _functional_evidence(
        environment, functional, "laplacian_meta_gga"
    )
    name_is_double_hybrid = is_double_hybrid_functional(functional)
    functional_rejected = double_hybrid is True or name_is_double_hybrid
    if functional_rejected:
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_DOUBLE_HYBRID,
                field="functional",
                expected="GPU-supported non-double-hybrid functional",
                observed=functional,
                evidence_ref="environment:functional_metadata/double_hybrid",
            )
        )

    if laplacian_meta_gga is True:
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_LAPLACIAN,
                field="functional",
                expected="meta-GGA not requiring density Laplacian",
                observed=functional,
                evidence_ref=(
                    "environment:functional_metadata/laplacian_meta_gga"
                ),
            )
        )

    if (
        functional is not None
        and not functional_rejected
        and (double_hybrid is _MISSING or laplacian_meta_gga is _MISSING)
    ):
        missing_flags = []
        if double_hybrid is _MISSING:
            missing_flags.append("double_hybrid")
        if laplacian_meta_gga is _MISSING:
            missing_flags.append("laplacian_meta_gga")
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_FUNCTIONAL_EVIDENCE,
                field="functional",
                expected="explicit GPU capability classification",
                observed={"missing": missing_flags},
                evidence_ref="environment:functional_metadata",
            )
        )

    model = _member(settings, "solvent_model", None)
    if model and str(model).lower() not in _GPU_SOLVENT_MODELS:
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_SOLVENT,
                field="solvent_model",
                expected=tuple(sorted(_GPU_SOLVENT_MODELS)),
                observed=model,
                evidence_ref="settings:solvent_model",
            )
        )

    jobtype = str(_member(settings, "jobtype", "")).lower()
    stages = _requested_stages(settings)
    if "td" in jobtype and "hess" in stages:
        violations.append(
            PySCFViolation(
                rule_id=RULE_GPU_TD_HESSIAN,
                field="jobtype",
                expected="no GPU TDDFT Hessian",
                observed=jobtype,
                evidence_ref="settings:jobtype",
            )
        )

    return violations


def _check_hessian_support(settings, molecule, environment):
    """Refuse a Hessian PySCF 2.14 cannot compute, before the engine finds out.

    Two refusals move to where the human decides: PySCF has no analytic
    Hessian for any ROHF reference -- which ``scf.HF`` selects for every
    one-electron system (``HF1e``) -- and none for an open-shell reference
    under a non-local-correlation (VV10-type) functional
    (``pyscf/hessian/uks.py``).  Both died live inside the driver at stage
    ``hess`` after the engine call was spent.  The reference family is the
    writer's own derivation, so this check and the script agree by
    construction; the NLC flag is the target environment's word about the
    functional, absent in a preview.
    """

    # An IRC's first act is the analytic Hessian of its surface at the
    # supplied geometry, so the same two refusals hold for it.
    if not set(PYSCF_ANALYTIC_HESSIAN_STAGES) & set(
        _requested_stages(settings)
    ):
        return []
    from chemsmart.jobs.pyscf.writer import pyscf_reference_family

    charge = _integral_value(_resolved_value(settings, molecule, "charge"))
    multiplicity = _integral_value(
        _resolved_value(settings, molecule, "multiplicity")
    )
    symbols = _first_member(molecule, "chemical_symbols", "symbols")
    if (
        charge is _MISSING
        or multiplicity is _MISSING
        or symbols is _MISSING
        or not symbols
    ):
        # The electron checks name these gaps; nothing to add here.
        return []
    xc = _member(settings, "xc", None)
    try:
        family = pyscf_reference_family(
            symbols=list(symbols),
            charge=int(charge),
            multiplicity=int(multiplicity),
            xc=xc,
        )
    except (KeyError, TypeError, ValueError):
        return []
    violations = []
    if family == "rohf":
        violations.append(
            PySCFViolation(
                rule_id=RULE_HESSIAN_REFERENCE,
                field="jobtype",
                expected=(
                    "a reference PySCF can differentiate twice: RHF, UHF, "
                    "RKS or UKS"
                ),
                observed={
                    "reference_family": family,
                    "reason": (
                        "PySCF 2.14 has no analytic Hessian for ROHF, which "
                        "scf.HF selects for every one-electron system; "
                        "a DFT functional runs UKS and can be differentiated"
                    ),
                },
                evidence_ref="writer:reference_family",
            )
        )
    if family == "uks" and xc:
        nlc = _functional_evidence(environment, xc, "nlc")
        if nlc is True:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_HESSIAN_NLC_OPEN_SHELL,
                    field="functional",
                    expected=(
                        "a functional without non-local correlation for an "
                        "open-shell Hessian, or a closed-shell reference"
                    ),
                    observed={
                        "reference_family": family,
                        "functional": xc,
                        "reason": (
                            "PySCF 2.14 raises NotImplementedError for a UKS "
                            "Hessian under an NLC functional "
                            "(pyscf/hessian/uks.py)"
                        ),
                    },
                    evidence_ref="environment:functional_metadata/nlc",
                )
            )
    return violations


def _check_irc_settings(settings, _molecule, _environment):
    """The IRC contract as typed violations, each naming its route.

    ``PySCFJobSettings._validate_irc`` raises the same refusals as text for
    the CLI and the project loader; this is the enumeration preflight and
    the review read.
    """

    jobtype = _member(settings, "jobtype", None)
    direction = _member(settings, "irc_direction", None)
    if jobtype != "irc":
        if direction is None:
            return []
        return [
            PySCFViolation(
                rule_id=RULE_IRC_SETTING,
                field="irc_direction",
                expected="unset unless the jobtype is irc",
                observed={"jobtype": jobtype, "irc_direction": direction},
                evidence_ref="settings:irc_direction",
            )
        ]
    violations = []
    if str(direction or "").strip().lower() not in PYSCF_IRC_DIRECTIONS:
        violations.append(
            PySCFViolation(
                rule_id=RULE_IRC_SETTING,
                field="irc_direction",
                expected=PYSCF_IRC_DIRECTIONS,
                observed=direction,
                evidence_ref="settings:irc_direction",
            )
        )
    method = pyscf_correlated_method(_member(settings, "ab_initio", None))
    if method is not None:
        violations.append(
            PySCFViolation(
                rule_id=RULE_IRC_SETTING,
                field="ab_initio",
                expected=(
                    "an HF or DFT surface: the branch starts along the "
                    "imaginary mode of the surface's own analytic Hessian, "
                    "which PySCF has not for a correlated method; take "
                    "correlated single points on the geometries the path "
                    "reaches"
                ),
                observed=method,
                evidence_ref="settings:ab_initio",
            )
        )
    if str(_member(settings, "opt_solver", "geometric")) != "geometric":
        violations.append(
            PySCFViolation(
                rule_id=RULE_IRC_SETTING,
                field="opt_solver",
                expected="geometric",
                observed=_member(settings, "opt_solver", None),
                evidence_ref="settings:opt_solver",
            )
        )
    engine = str(_member(settings, "engine", "cpu") or "cpu").strip().lower()
    if engine != "cpu":
        violations.append(
            PySCFViolation(
                rule_id=RULE_IRC_SETTING,
                field="engine",
                expected="cpu",
                observed=engine,
                evidence_ref="settings:engine",
            )
        )
    if _member(settings, "hessian_derivative", None) is not None:
        violations.append(
            PySCFViolation(
                rule_id=RULE_IRC_SETTING,
                field="hessian_derivative",
                expected="unset: an irc takes its surface's analytic Hessian",
                observed=_member(settings, "hessian_derivative", None),
                evidence_ref="settings:hessian_derivative",
            )
        )
    return violations


def _check_electrons(settings, molecule, _environment):
    violations = []
    charge_raw = _resolved_value(settings, molecule, "charge")
    multiplicity_raw = _resolved_value(settings, molecule, "multiplicity")
    charge = _integral_value(charge_raw)
    multiplicity = _integral_value(multiplicity_raw)

    if charge is _MISSING:
        violations.append(
            PySCFViolation(
                rule_id=RULE_CHARGE_INVALID,
                field="charge",
                expected="integer resolved charge",
                observed=charge_raw,
                evidence_ref="resolved:charge",
            )
        )
    if multiplicity is _MISSING or multiplicity < 1:
        violations.append(
            PySCFViolation(
                rule_id=RULE_MULTIPLICITY_INVALID,
                field="multiplicity",
                expected="integer >= 1",
                observed=multiplicity_raw,
                evidence_ref="resolved:multiplicity",
            )
        )

    numbers = _atomic_numbers(molecule)
    if numbers is _MISSING:
        violations.append(
            PySCFViolation(
                rule_id=RULE_ATOMIC_NUMBERS,
                field="molecule.atomic_numbers",
                expected="valid atomic numbers or chemical symbols",
                observed="<unavailable>",
                evidence_ref="molecule:atomic_numbers",
            )
        )
        return violations
    if charge is _MISSING:
        return violations

    electron_count = sum(numbers) - charge
    if electron_count < 0:
        violations.append(
            PySCFViolation(
                rule_id=RULE_ELECTRON_COUNT,
                field="electron_count",
                expected=">= 0 from sum(Z) - charge",
                observed=electron_count,
                evidence_ref="derived:electron_count",
            )
        )

    declared_count = _declared_electron_count(molecule)
    if declared_count is not _MISSING:
        converted_count = _integral_value(declared_count)
        if converted_count is _MISSING or converted_count != electron_count:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_ELECTRON_COUNT,
                    field="electron_count",
                    expected=electron_count,
                    observed=declared_count,
                    evidence_ref="molecule:electron_count",
                )
            )

    if multiplicity is _MISSING or multiplicity < 1:
        return violations
    spin = multiplicity - 1
    declared_spin = _stored_member(settings, "spin", _MISSING)
    if declared_spin is not _MISSING:
        converted_spin = _integral_value(declared_spin)
        if converted_spin is _MISSING or converted_spin != spin:
            violations.append(
                PySCFViolation(
                    rule_id=RULE_SPIN_MISMATCH,
                    field="spin",
                    expected=spin,
                    observed=declared_spin,
                    evidence_ref="settings:spin",
                )
            )

    if spin > electron_count:
        violations.append(
            PySCFViolation(
                rule_id=RULE_SPIN_EXCEEDS,
                field="multiplicity",
                expected=f"multiplicity <= {electron_count + 1}",
                observed=multiplicity,
                evidence_ref="derived:electron_count",
            )
        )
    elif (electron_count - spin) % 2:
        violations.append(
            PySCFViolation(
                rule_id=RULE_SPIN_PARITY,
                field="multiplicity",
                expected=(
                    "electron count and multiplicity - 1 with equal parity"
                ),
                observed={
                    "electron_count": electron_count,
                    "spin": spin,
                },
                evidence_ref="derived:electron_count",
            )
        )
    return violations


def _requested_spec(settings):
    requested = {}
    direct_fields = (
        "title",
        "engine",
        "basis",
        "ab_initio",
        "charge",
        "multiplicity",
        "dispersion",
        "density_fit",
        "aux_basis",
        "defgrid",
        "scf_stability",
        "scf_tol",
        "scf_maxiter",
        "solvent_model",
        "solvent_id",
        "response_method",
        "state_manifold",
        "nstates",
        "excited_state_root",
        "td_max_cycle",
        "frozen_core",
        "cc_max_cycle",
        "jobtype",
    )
    for field in direct_fields:
        value = _member(settings, field, _MISSING)
        if value is _MISSING:
            continue
        if value is None and field in {
            "charge",
            "multiplicity",
            "jobtype",
        }:
            continue
        requested[field] = value

    functional = _member(settings, "functional", _MISSING)
    ab_initio = _member(settings, "ab_initio", _MISSING)
    # Do not evaluate ``PySCFJobSettings.xc`` here: that property may emit a
    # scientific warning for divergent functional names. Verification is a
    # pure comparison, so only a literally stored override is inspected.
    direct_xc = _stored_member(settings, "xc", _MISSING)
    if direct_xc is not _MISSING:
        requested["xc"] = direct_xc
    elif ab_initio is not _MISSING and str(ab_initio).lower() == "hf":
        requested["xc"] = None
    elif functional is not _MISSING and functional is not None:
        # The writer's own spelling, from the table it spells with, so a
        # literal and its synonyms verify against the xc the driver ran.
        requested["xc"] = pyscf_native_functional(functional)

    if ab_initio not in (_MISSING, None):
        requested["method"] = str(ab_initio).lower()
    elif functional not in (_MISSING, None):
        requested["method"] = str(functional).lower()

    multiplicity = _integral_value(_member(settings, "multiplicity", _MISSING))
    if multiplicity is not _MISSING:
        requested["spin"] = multiplicity - 1

    stages = _requested_stages(settings)
    if stages:
        requested["stages"] = stages
    if set(PYSCF_MOVING_STAGES) & set(stages):
        requested["opt_solver"] = _member(settings, "opt_solver", "geometric")
        requested["opt_maxsteps"] = _member(settings, "opt_maxsteps", 100)
    if "irc" in stages:
        # Only a run that walks a branch asks for one, so no artifact whose
        # contract predates the field is compared against it.
        direction = _member(settings, "irc_direction", None)
        requested["irc_direction"] = (
            str(direction).strip().lower() if direction is not None else None
        )
    return requested


def _requested_stages(settings):
    """The stages a resolved configuration runs -- from the settings' own
    derivation, never from the jobtype word alone."""

    jobtype = _member(settings, "jobtype", None)
    if not jobtype:
        return []
    normal = str(jobtype).lower().replace("pyscf_", "")
    if "freq" in normal:
        normal = "hess"
    return pyscf_stages(
        normal,
        ab_initio=_member(settings, "ab_initio", None),
        excited_state_root=_member(settings, "excited_state_root", None),
    )


def _optimization_requested(settings, environment):
    jobtype = str(_member(settings, "jobtype", "")).lower()
    if "opt" in jobtype:
        return True
    stages = _first_environment(environment, ("required_stages",), ("stages",))
    if isinstance(stages, Collection) and not isinstance(stages, str):
        return "opt" in {str(stage).lower() for stage in stages}
    return False


def _solvent_keys(environment):
    source = _first_environment(
        environment,
        ("solvent_ids",),
        ("solvent_db",),
        ("pyscf", "solvent_ids"),
        ("pyscf", "solvent_db"),
        ("capabilities", "solvent_ids"),
    )
    if source is _MISSING or source is None:
        return _MISSING
    if isinstance(source, Mapping):
        source = source.keys()
    elif isinstance(source, str):
        source = (source,)
    if not isinstance(source, Collection):
        return _MISSING
    return {str(key).strip().lower() for key in source}


def _dependency_probe(environment, *names):
    paths = []
    for name in names:
        paths.extend(
            [
                (name,),
                ("dependencies", name),
                ("packages", name),
                ("modules", name),
                ("gpu", name),
            ]
        )
    return _first_environment(environment, *paths)


def _available_probe(probe):
    if probe is _MISSING or probe is None or probe is False:
        return False
    if isinstance(probe, Mapping):
        for key in ("available", "installed", "importable"):
            if key in probe:
                return bool(probe[key])
        return False
    return bool(probe)


def _callable_probe(probe):
    if callable(probe):
        return True
    if probe is _MISSING or probe is None or probe is False:
        return False
    if isinstance(probe, Mapping):
        value = probe.get("callable", _MISSING)
        return callable(value) or value is True
    # A bool is accepted only as an explicit external-environment
    # attestation in the solver_callables slot.  An importable module object
    # is deliberately not accepted: that is the known false-green mode.
    return probe is True


def _positive_or_available(probe):
    if isinstance(probe, bool):
        return probe
    value = _integral_value(probe)
    if value is not _MISSING:
        return value > 0
    return _available_probe(probe)


def _cutensor_compatibility(environment):
    explicit = _first_environment(
        environment,
        ("cutensor_compatible",),
        ("gpu", "cutensor_compatible"),
    )
    if explicit is not _MISSING:
        return explicit is True

    backend = _first_environment(
        environment, ("tensor_backend",), ("gpu", "tensor_backend")
    )
    if backend is not _MISSING:
        return str(backend).strip().lower() == "cutensor"

    cupy_version = _first_environment(
        environment, ("cupy_version",), ("gpu", "cupy_version")
    )
    cutensor_version = _first_environment(
        environment,
        ("cutensor_version",),
        ("gpu", "cutensor_version"),
    )
    known_pairs = {("13.3.0", "2.0.2"), ("13.4.1", "2.2.0")}
    if cupy_version is not _MISSING and cutensor_version is not _MISSING:
        return (str(cupy_version), str(cutensor_version)) in known_pairs
    return _MISSING


def _basis_max_l(environment, role, basis_name):
    names = {
        "basis": ("basis_max_l", "basis_max_angular_momentum"),
        "aux_basis": (
            "aux_basis_max_l",
            "auxbasis_max_l",
            "aux_basis_max_angular_momentum",
        ),
    }[role]
    paths = []
    for name in names:
        paths.extend(((name,), ("gpu", name)))
    value = _first_environment(environment, *paths)
    if isinstance(value, Mapping):
        value = value.get(
            basis_name,
            value.get(str(basis_name).lower(), value.get("default", _MISSING)),
        )
    if value is _MISSING or value is None:
        return _MISSING
    if isinstance(value, str):
        normal = value.strip().lower()
        if normal in _ANGULAR_MOMENTA:
            return _ANGULAR_MOMENTA[normal]
    converted = _integral_value(value)
    return converted


def _functional_evidence(environment, functional, flag):
    direct = _first_environment(environment, (flag,), ("gpu", flag))
    if direct is not _MISSING:
        return direct is True
    metadata = _first_environment(
        environment,
        ("functional_metadata",),
        ("gpu", "functional_metadata"),
    )
    if not isinstance(metadata, Mapping):
        return _MISSING
    item = metadata.get(
        functional,
        metadata.get(str(functional).lower(), metadata.get("default", {})),
    )
    if not isinstance(item, Mapping) or flag not in item:
        return _MISSING
    return item[flag] is True


def _atomic_numbers(molecule):
    raw = _first_member(molecule, "atomic_numbers", "numbers")
    if raw is not _MISSING:
        try:
            values = list(raw)
            converted = [_integral_value(value) for value in values]
            if converted and all(value is not _MISSING for value in converted):
                return converted
        except (TypeError, ValueError):
            pass

    symbols = _first_member(molecule, "chemical_symbols", "symbols")
    if symbols is _MISSING:
        return _MISSING
    try:
        values = [ASE_ATOMIC_NUMBERS[str(symbol)] for symbol in symbols]
    except (KeyError, TypeError):
        return _MISSING
    return values or _MISSING


def _declared_electron_count(molecule):
    direct = _first_member(
        molecule, "electron_count", "num_electrons", "nelectron"
    )
    if direct is not _MISSING:
        return direct
    info = _member(molecule, "info", {})
    if isinstance(info, Mapping):
        for key in ("electron_count", "num_electrons", "nelectron"):
            if key in info:
                return info[key]
    return _MISSING


def _resolved_value(settings, molecule, field):
    value = _member(settings, field, _MISSING)
    if value is not _MISSING and value is not None:
        return value
    return _member(molecule, field, _MISSING)


def _integral_value(value):
    if value is _MISSING or value is None or isinstance(value, bool):
        return _MISSING
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        return int(value) if float(value).is_integer() else _MISSING
    if isinstance(value, str):
        try:
            converted = int(value.strip())
        except ValueError:
            return _MISSING
        return converted if str(converted) == value.strip() else _MISSING
    return _MISSING


def _angular_label(value):
    for label, number in _ANGULAR_MOMENTA.items():
        if value == number:
            return f"{label} (l={number})"
    return f"l={value}"


def _settings_items(settings):
    if isinstance(settings, Mapping):
        return list(settings.items())
    try:
        return list(vars(settings).items())
    except TypeError:
        return []


def _is_unset(value, unset):
    try:
        comparison = value == unset
        return comparison if isinstance(comparison, bool) else False
    except Exception:
        return False


def _first_member(source, *names):
    for name in names:
        value = _member(source, name, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _member(source, name, default=_MISSING):
    try:
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)
    except Exception:
        return default


def _stored_member(source, name, default=_MISSING):
    """Read mappings/instance storage without evaluating a property."""
    if isinstance(source, Mapping):
        return source.get(name, default)
    try:
        return vars(source).get(name, default)
    except TypeError:
        return default


def _first_environment(environment, *paths):
    for path in paths:
        value = _environment_path(environment, path)
        if value is not _MISSING:
            return value
    return _MISSING


def _environment_path(environment, path):
    current = environment
    for name in path:
        current = _member(current, name, _MISSING)
        if current is _MISSING:
            return _MISSING
    return current


def _describe_probe(probe):
    if probe is _MISSING:
        return "<missing>"
    if callable(probe):
        return "callable"
    if isinstance(probe, Mapping):
        return {
            str(key): ("callable" if callable(value) else bool(value))
            for key, value in probe.items()
            if key in {"available", "installed", "importable", "callable"}
        }
    if isinstance(probe, (str, int, float, bool)) or probe is None:
        return probe
    return type(probe).__name__


def _equivalent(field, expected, observed):
    if observed is _MISSING:
        return False
    expected = _plain_value(expected)
    observed = _plain_value(observed)
    if field in {
        "engine",
        "basis",
        "ab_initio",
        "xc",
        "method",
        "dispersion",
        "defgrid",
        "solvent_model",
        "solvent_id",
        "opt_solver",
        "jobtype",
        "response_method",
        "state_manifold",
    }:
        if isinstance(expected, str) and isinstance(observed, str):
            return expected.strip().lower() == observed.strip().lower()
    return expected == observed


def _plain_value(value):
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _plain_value(item) for key, item in value.items()}
    return value


def _read_artifact_contract(h5_path):
    # Prefer B2's public schema reader when available.  The fallback keeps
    # this module usable against an in-progress Stage-A tree and recognizes
    # the exact schema-2 null marker.
    try:
        from chemsmart.io.pyscf.output import read_pyscf_h5
    except ImportError:
        read_pyscf_h5 = None

    if read_pyscf_h5 is not None:
        payload = read_pyscf_h5(h5_path)
        if isinstance(payload, Mapping):
            return (
                payload["spec"],
                payload.get("provenance", {}),
                payload.get("status", {}),
            )
        if isinstance(payload, tuple) and len(payload) >= 3:
            return payload[0], payload[1], payload[2]

    import h5py

    with h5py.File(os.fspath(h5_path), "r") as handle:
        return (
            _decode_h5_node(handle["spec"]),
            _decode_h5_node(handle["provenance"]),
            _decode_h5_node(handle["status"]),
        )


def _decode_h5_node(node):
    import h5py

    if isinstance(node, h5py.Group):
        return {key: _decode_h5_node(node[key]) for key in node}
    if bool(node.attrs.get("chemsmart_is_null", False)):
        return None
    return _decode_h5_value(node[()])


def _decode_h5_value(value):
    if hasattr(value, "item") and not hasattr(value, "tolist"):
        value = value.item()
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "null" or stripped.startswith(("{", "[", '"')):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
        return value
    if hasattr(value, "tolist"):
        return _plain_value(value.tolist())
    return value


__all__ = [
    "FREQUENCY_VALIDATION_SCHEMA_VERSION",
    "RESULT_VALIDATION_SCHEMA_VERSION",
    "PySCFViolation",
    "frequency_validation_receipt",
    "preflight",
    "validate_pyscf_result",
    "verify_provenance",
]
