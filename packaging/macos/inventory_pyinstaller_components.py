"""Derive shipped Python distributions from the PyInstaller analysis graph."""

from __future__ import annotations

import argparse
import ast
from email.parser import Parser
import hashlib
from importlib import metadata
import json
import re
from pathlib import Path
import sys
from typing import Any, Iterable


MAX_TOC_BYTES = 64 * 1024 * 1024
TOC_TYPES = {
    "BINARY",
    "DATA",
    "DEPENDENCY",
    "EXECUTABLE",
    "EXTENSION",
    "PYMODULE",
    "PYSOURCE",
    "SYMLINK",
}
REQUIRED_DISTRIBUTIONS = {
    "anthropic",
    "ase",
    "keyring",
    "matplotlib",
    "numpy",
    "openai",
    "pymatgen",
    "pyside6",
    "rdkit",
    "scipy",
}
FORBIDDEN_RELEASE_DISTRIBUTIONS = {
    "coverage",
    "pip",
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "pyperclip",
    "pytest",
    "textual",
    "watchdog",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _locked_components(lock_path: Path) -> dict[str, dict[str, str]]:
    components: dict[str, dict[str, str]] = {}
    for line_number, raw_line in enumerate(
        lock_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        requirement, separator, marker = stripped.partition(";")
        match = re.fullmatch(
            r"([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s]+)",
            requirement.strip(),
        )
        if match is None:
            raise ValueError(
                f"Runtime lock line {line_number} is not exact: {stripped}"
            )
        name = _normalize_distribution_name(match.group(1))
        if name in components:
            raise ValueError(f"Duplicate runtime-lock distribution: {name}")
        components[name] = {
            "marker": marker.strip() if separator else "",
            "name": name,
            "version": match.group(2),
        }
    return components


def _toc_entries(value: Any) -> Iterable[tuple[str, str, str]]:
    if isinstance(value, (list, tuple)):
        toc_type = (
            value[2].partition("-")[0]
            if len(value) >= 3 and isinstance(value[2], str)
            else ""
        )
        if (
            len(value) >= 3
            and isinstance(value[0], str)
            and isinstance(value[2], str)
            and toc_type in TOC_TYPES
        ):
            yield value[0], str(value[1] or ""), toc_type
            return
        for item in value:
            yield from _toc_entries(item)


def _top_level(entry_name: str) -> str:
    return re.split(r"[./\\]", entry_name, maxsplit=1)[0]


def _metadata_distributions(app: Path) -> list[dict[str, str]]:
    observed: dict[str, dict[str, str]] = {}
    for path in app.rglob("*.dist-info/METADATA"):
        if path.is_symlink() or not path.is_file():
            continue
        message = Parser().parsestr(
            path.read_text(encoding="utf-8", errors="replace")
        )
        raw_name = str(message.get("Name") or "").strip()
        version = str(message.get("Version") or "").strip()
        if not raw_name or not version:
            continue
        name = _normalize_distribution_name(raw_name)
        observed[name] = {"name": name, "version": version}
    return [observed[name] for name in sorted(observed)]


def build_component_inventory(
    *,
    toc: Any,
    package_map: dict[str, list[str]],
    locked: dict[str, dict[str, str]],
    metadata_distributions: list[dict[str, str]],
) -> dict[str, Any]:
    normalized_package_map = {
        package.casefold(): distributions
        for package, distributions in package_map.items()
    }
    top_levels = sorted(
        {
            _top_level(name)
            for name, _source, toc_type in _toc_entries(toc)
            if toc_type in TOC_TYPES and _top_level(name)
        }
    )
    evidence: dict[str, set[str]] = {}
    ambiguous: dict[str, list[str]] = {}
    unmapped: list[str] = []
    stdlib = set(sys.stdlib_module_names) | {"chemsmart"}
    for top_level in top_levels:
        raw_distributions = (
            package_map.get(top_level)
            or normalized_package_map.get(top_level.casefold())
            or []
        )
        distributions = sorted(
            {
                _normalize_distribution_name(name)
                for name in raw_distributions
                if _normalize_distribution_name(name) in locked
            }
        )
        if len(distributions) > 1:
            ambiguous[top_level] = distributions
        if not distributions and top_level not in stdlib:
            unmapped.append(top_level)
        for distribution in distributions:
            evidence.setdefault(distribution, set()).add(top_level)

    components = [
        {
            **locked[name],
            "evidence_top_levels": sorted(evidence[name]),
        }
        for name in sorted(evidence)
    ]
    component_names = set(evidence)
    missing_required = sorted(REQUIRED_DISTRIBUTIONS - component_names)
    forbidden_present = sorted(
        FORBIDDEN_RELEASE_DISTRIBUTIONS & component_names
    )
    metadata_names = {item["name"] for item in metadata_distributions}
    metadata_only = sorted(metadata_names - component_names)
    status = (
        "passed"
        if not missing_required and not forbidden_present
        else "failed"
    )
    return {
        "ambiguous_top_level_mappings": ambiguous,
        "component_count": len(components),
        "components": components,
        "forbidden_release_distributions_present": forbidden_present,
        "mandatory_distributions": sorted(REQUIRED_DISTRIBUTIONS),
        "mandatory_distributions_missing": missing_required,
        "metadata_only_distributions": metadata_only,
        "observed_top_level_count": len(top_levels),
        "schema_version": 1,
        "status": status,
        "unmapped_nonstdlib_top_levels": sorted(unmapped),
    }


def _read_toc(path: Path, *, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"PyInstaller {label} TOC must be a regular file.")
    if path.stat().st_size > MAX_TOC_BYTES:
        raise ValueError(f"PyInstaller {label} TOC exceeds the 64 MiB limit.")
    try:
        return ast.literal_eval(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
        raise ValueError(f"PyInstaller {label} TOC is invalid.") from exc


def inventory_pyinstaller_components(
    *,
    app: Path,
    analysis_toc: Path,
    pyz_toc: Path,
    runtime_lock: Path,
) -> dict[str, Any]:
    if app.is_symlink() or not app.is_dir():
        raise ValueError("ChemSmart app must be a regular directory.")
    toc = (
        _read_toc(analysis_toc, label="analysis"),
        _read_toc(pyz_toc, label="PYZ"),
    )
    report = build_component_inventory(
        toc=toc,
        package_map=metadata.packages_distributions(),
        locked=_locked_components(runtime_lock),
        metadata_distributions=_metadata_distributions(app),
    )
    report["analysis_toc_sha256"] = _sha256(analysis_toc)
    report["pyz_toc_sha256"] = _sha256(pyz_toc)
    report["runtime_lock_sha256"] = _sha256(runtime_lock)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--analysis-toc", type=Path, required=True)
    parser.add_argument("--pyz-toc", type=Path, required=True)
    parser.add_argument("--runtime-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inventory_pyinstaller_components(
        app=args.app.resolve(),
        analysis_toc=args.analysis_toc.resolve(),
        pyz_toc=args.pyz_toc.resolve(),
        runtime_lock=args.runtime_lock.resolve(),
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "component_count": report["component_count"],
                "status": report["status"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
