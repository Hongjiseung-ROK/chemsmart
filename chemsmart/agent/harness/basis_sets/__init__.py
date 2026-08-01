"""Basis-set name catalog and validation helpers for agent harnesses."""

from chemsmart.agent.harness.basis_sets.catalog import (
    BasisCatalogIdentityCollisionError,
    BasisElementInspectionResult,
    BasisElementObservation,
    BasisIntentResult,
    BasisProgram,
    check_basis_intent,
    inspect_basis_elements,
    load_basis_catalog,
    normalize_basis_identity,
    resolve_basis_name,
    search_basis_sets,
)

__all__ = [
    "BasisCatalogIdentityCollisionError",
    "BasisElementInspectionResult",
    "BasisElementObservation",
    "BasisIntentResult",
    "BasisProgram",
    "check_basis_intent",
    "inspect_basis_elements",
    "load_basis_catalog",
    "normalize_basis_identity",
    "resolve_basis_name",
    "search_basis_sets",
]
