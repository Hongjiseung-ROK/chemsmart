"""Canonical, path-free identities for the narrow M2 geometry boundary.

The command-compiled frontier path accepts a single-frame XYZ geometry as an
opaque, content-addressed artifact.  This module adds the second identity that
the raw file hash alone cannot provide: a stable digest of the ordered atom
symbols and Cartesian coordinates.  Gaussian and ORCA safe previews can be
checked against the same digest after ChemSmart renders their native input.

It deliberately supports only the forms that have an unambiguous M2 parser.
Multi-frame XYZ, periodic cells, Z-matrices, and QM/MM layer syntax remain
outside this validator until their coordinate semantics have a dedicated,
tested manifest format.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_ELEMENT = re.compile(r"^[A-Z][a-z]?$")


@dataclass(frozen=True)
class OrderedGeometryManifest:
    """Path-free ordered Cartesian identity in Angstrom."""

    atom_count: int
    ordered_geometry_sha256: str
    element_counts: tuple[tuple[str, int], ...]
    coordinate_units: str = "angstrom"

    def public_dict(self) -> dict[str, str | int | dict[str, int]]:
        return {
            "atom_count": self.atom_count,
            "coordinate_units": self.coordinate_units,
            "ordered_geometry_sha256": self.ordered_geometry_sha256,
            "element_counts": dict(self.element_counts),
        }


def xyz_geometry_manifest(path: str | Path) -> OrderedGeometryManifest:
    """Return a manifest for one strict XYZ frame or raise ``ValueError``.

    A frame selector is intentionally absent.  Selecting a frame without a
    first-class typed binding would make a geometry hash ambiguous, so M2
    rejects multi-frame XYZ rather than silently taking the first or last one.
    """

    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("geometry artifact could not be read") from exc
    return xyz_text_geometry_manifest(text)


def xyz_text_geometry_manifest(text: str) -> OrderedGeometryManifest:
    """Return the canonical manifest for a strict single-frame XYZ string."""

    lines = text.splitlines()
    if len(lines) < 2:
        raise ValueError("XYZ requires atom count and comment lines")
    try:
        atom_count = int(lines[0].strip())
    except ValueError as exc:
        raise ValueError("XYZ first line must be an integer atom count") from exc
    if atom_count < 1:
        raise ValueError("XYZ atom count must be positive")
    coordinate_lines = lines[2 : 2 + atom_count]
    if len(coordinate_lines) != atom_count:
        raise ValueError("XYZ coordinate count does not match atom count")
    trailing = lines[2 + atom_count :]
    if any(line.strip() for line in trailing):
        raise ValueError("M2 accepts one XYZ frame only")
    symbols: list[str] = []
    coordinates: list[tuple[float, float, float]] = []
    for line in coordinate_lines:
        symbol, xyz = _coordinate_row(line)
        symbols.append(symbol)
        coordinates.append(xyz)
    return ordered_geometry_manifest(symbols, coordinates)


def native_input_geometry_manifest(
    content: str,
    *,
    program: str,
) -> OrderedGeometryManifest | None:
    """Parse the Cartesian block from a Gaussian/ORCA rendered input.

    The returned digest is based only on ordered symbols and coordinates.  It
    does not claim that a job has executed or that an optimization preserved
    geometry; it verifies the safe-preview *input rendering* boundary.
    """

    if program == "gaussian":
        rows = _gaussian_rows(content)
    elif program == "orca":
        rows = _orca_rows(content)
    else:
        return None
    if not rows:
        return None
    symbols, coordinates = zip(*rows)
    return ordered_geometry_manifest(symbols, coordinates)


def ordered_geometry_manifest(
    symbols: Iterable[str],
    coordinates: Iterable[tuple[float, float, float]],
) -> OrderedGeometryManifest:
    """Hash an ordered Cartesian representation with deterministic rounding."""

    normalized_symbols: list[str] = []
    normalized_coordinates: list[list[str]] = []
    for symbol, point in zip(symbols, coordinates, strict=True):
        if not isinstance(symbol, str) or _ELEMENT.fullmatch(symbol) is None:
            raise ValueError("geometry contains an invalid element symbol")
        if len(point) != 3:
            raise ValueError("geometry coordinate row must contain three values")
        values = tuple(float(value) for value in point)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("geometry contains a non-finite coordinate")
        normalized_symbols.append(symbol)
        normalized_coordinates.append([_coordinate_text(value) for value in values])
    if not normalized_symbols:
        raise ValueError("geometry has no atoms")
    payload = {
        "coordinate_units": "angstrom",
        "symbols": normalized_symbols,
        "coordinates": normalized_coordinates,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return OrderedGeometryManifest(
        atom_count=len(normalized_symbols),
        ordered_geometry_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        element_counts=tuple(
            (symbol, normalized_symbols.count(symbol))
            for symbol in sorted(set(normalized_symbols))
        ),
    )


def _coordinate_text(value: float) -> str:
    """Keep 12 decimal places: stable across normal engine input formatting."""

    rendered = f"{value:.12f}"
    return rendered.rstrip("0").rstrip(".") or "0"


def _coordinate_row(line: str) -> tuple[str, tuple[float, float, float]]:
    tokens = line.split()
    if len(tokens) < 4:
        raise ValueError("XYZ coordinate line must contain symbol and x y z")
    symbol = tokens[0]
    if _ELEMENT.fullmatch(symbol) is None:
        raise ValueError("geometry contains an invalid element symbol")
    try:
        values = tuple(float(item) for item in tokens[1:4])
    except ValueError as exc:
        raise ValueError("geometry coordinates must be numeric") from exc
    return symbol, values  # type: ignore[return-value]


def _gaussian_rows(content: str) -> list[tuple[str, tuple[float, float, float]]]:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        tokens = line.split()
        if not tokens or len(tokens) % 2:
            continue
        if not all(re.fullmatch(r"-?\d+", token) for token in tokens):
            continue
        if any(int(token) < 1 for token in tokens[1::2]):
            continue
        rows: list[tuple[str, tuple[float, float, float]]] = []
        for coordinate in lines[index + 1 :]:
            if not coordinate.strip():
                break
            try:
                rows.append(_coordinate_row(coordinate))
            except ValueError:
                return []
        return rows
    return []


def _orca_rows(content: str) -> list[tuple[str, tuple[float, float, float]]]:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^\s*\*\s+xyz\s+-?\d+\s+\d+\s*$", line, re.I) is None:
            continue
        rows: list[tuple[str, tuple[float, float, float]]] = []
        for coordinate in lines[index + 1 :]:
            if coordinate.strip().startswith("*"):
                break
            try:
                rows.append(_coordinate_row(coordinate))
            except ValueError:
                return []
        return rows
    return []


__all__ = [
    "OrderedGeometryManifest",
    "native_input_geometry_manifest",
    "ordered_geometry_manifest",
    "xyz_geometry_manifest",
    "xyz_text_geometry_manifest",
]
