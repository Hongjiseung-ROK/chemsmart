"""Normalize the known Nuitka QtWebEngine resource-mode defect on macOS."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any


ALLOWED_RESOURCE_GLOBS = (
    "qtwebengine_resources*.pak",
    "qtwebengine_devtools_resources.pak",
)
HIDDEN_TEMPLATE_RELATIVE = Path(
    "Contents/MacOS/chemsmart/settings/templates/.chemsmart"
)
PACKAGED_TEMPLATE_DIRNAME = "chemsmart_defaults"
QTWEBENGINE_ROOT_RESOURCE_FILES = (
    "Info.plist",
    "PrivacyInfo.xcprivacy",
    "icudtl.dat",
    "qtwebengine_devtools_resources.pak",
    "qtwebengine_resources.pak",
    "qtwebengine_resources_100p.pak",
    "qtwebengine_resources_200p.pak",
    "v8_context_snapshot.arm64.bin",
    "v8_context_snapshot.x86_64.bin",
)
QTWEBENGINE_LOCALES_DIRNAME = "qtwebengine_locales"
MACHO_MAGICS = {
    b"\xca\xfe\xba\xbe",
    b"\xce\xfa\xed\xfe",
    b"\xcf\xfa\xed\xfe",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_allowed_resource(path: Path) -> bool:
    return any(path.match(pattern) for pattern in ALLOWED_RESOURCE_GLOBS)


def _resource_mode_candidates(
    app: Path,
) -> list[tuple[Path, int, str]]:
    candidates = []
    for path in sorted(app.rglob("*")):
        if not path.is_file() or path.is_symlink() or not _is_allowed_resource(path):
            continue
        before = stat.S_IMODE(path.stat().st_mode)
        if before & 0o111 == 0:
            continue
        with path.open("rb") as handle:
            prefix = handle.read(4)
        if prefix in MACHO_MAGICS or prefix[:2] == b"#!":
            raise RuntimeError(f"Refusing to chmod executable content: {path}")
        candidates.append((path, before, _sha256(path)))
    return candidates


def _apply_resource_modes(
    app: Path, candidates: list[tuple[Path, int, str]]
) -> list[dict[str, Any]]:

    changes = []
    for path, before, before_hash in candidates:
        path.chmod(before & ~0o111)
        after = stat.S_IMODE(path.stat().st_mode)
        after_hash = _sha256(path)
        if before_hash != after_hash:
            raise RuntimeError(f"Content changed while normalizing mode: {path}")
        changes.append(
            {
                "path": str(path.relative_to(app)),
                "before_mode": oct(before),
                "after_mode": oct(after),
                "sha256_before": before_hash,
                "sha256_after": after_hash,
            }
        )
    return changes


def _template_tree_receipt(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = 0
    directories = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Refusing symlinked configuration template: {path}")
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            directories += 1
            digest.update(f"directory\0{relative}\0".encode())
            continue
        if not path.is_file():
            raise RuntimeError(f"Unsupported configuration template entry: {path}")
        files += 1
        digest.update(f"file\0{relative}\0".encode())
        digest.update(bytes.fromhex(_sha256(path)))
    return {
        "files": files,
        "directories": directories,
        "tree_sha256": digest.hexdigest(),
    }


def _flat_file_set_receipt(root: Path, names: list[str]) -> dict[str, Any]:
    digest = hashlib.sha256()
    for name in sorted(names):
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Invalid flat QtWebEngine resource: {path}")
        digest.update(f"file\0{name}\0".encode())
        digest.update(bytes.fromhex(_sha256(path)))
    return {"files": len(names), "tree_sha256": digest.hexdigest()}


def _tree_inventory_receipt(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    counts = {"files": 0, "directories": 0, "symlinks": 0}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            counts["symlinks"] += 1
            digest.update(f"symlink\0{relative}\0{os.readlink(path)}\0".encode())
        elif path.is_dir():
            counts["directories"] += 1
            digest.update(f"directory\0{relative}\0".encode())
        elif path.is_file():
            counts["files"] += 1
            digest.update(f"file\0{relative}\0".encode())
            digest.update(bytes.fromhex(_sha256(path)))
        else:
            raise RuntimeError(f"Unsupported framework entry: {path}")
    return {**counts, "tree_sha256": digest.hexdigest()}


def _framework_inventory(app: Path) -> list[dict[str, Any]]:
    frameworks = sorted(
        path
        for path in app.rglob("QtWebEngineCore.framework")
        if path.is_dir() and not path.is_symlink()
    )
    return [
        {"path": str(path.relative_to(app)), **_tree_inventory_receipt(path)}
        for path in frameworks
    ]


def _outer_info_plist_receipt(app: Path) -> dict[str, Any]:
    path = app / "Contents" / "Info.plist"
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Outer application Info.plist was not found: {path}")
    return {
        "path": str(path.relative_to(app)),
        "sha256": _sha256(path),
        "mode": oct(stat.S_IMODE(path.stat().st_mode)),
    }


def _qtwebengine_resource_relocation_plan(
    app: Path,
) -> tuple[
    list[tuple[Path, Path, str]],
    tuple[Path, list[tuple[Path, Path, str]], dict[str, Any]],
    list[dict[str, Any]],
]:
    source_root = app / "Contents" / "MacOS"
    destination_root = app / "Contents" / "Resources"
    if not destination_root.is_dir() or destination_root.is_symlink():
        raise RuntimeError(
            f"Safe application resource directory was not found: {destination_root}"
        )

    files = []
    planned_destinations: set[Path] = set()
    for name in QTWEBENGINE_ROOT_RESOURCE_FILES:
        source = source_root / name
        destination = destination_root / name
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"QtWebEngine root resource was not found: {source}")
        if destination.exists() or destination.is_symlink():
            raise RuntimeError(
                f"QtWebEngine resource destination already exists: {destination}"
            )
        if destination in planned_destinations:
            raise RuntimeError(
                f"Duplicate QtWebEngine resource destination: {destination}"
            )
        planned_destinations.add(destination)
        files.append((source, destination, _sha256(source)))

    locale_source = source_root / QTWEBENGINE_LOCALES_DIRNAME
    if not locale_source.is_dir() or locale_source.is_symlink():
        raise RuntimeError(
            f"QtWebEngine locale resource directory was not found: {locale_source}"
        )
    locale_entries = sorted(locale_source.iterdir())
    if not locale_entries:
        raise RuntimeError(f"QtWebEngine locale directory is empty: {locale_source}")
    locale_names = []
    locale_files = []
    for source in locale_entries:
        if source.suffix != ".pak" or not source.is_file() or source.is_symlink():
            raise RuntimeError(f"Unsupported QtWebEngine locale entry: {source}")
        destination = destination_root / source.name
        if destination.exists() or destination.is_symlink():
            raise RuntimeError(
                f"QtWebEngine locale destination already exists: {destination}"
            )
        if destination in planned_destinations:
            raise RuntimeError(
                f"Duplicate QtWebEngine resource destination: {destination}"
            )
        planned_destinations.add(destination)
        locale_names.append(source.name)
        locale_files.append((source, destination, _sha256(source)))
    locale_receipt = _flat_file_set_receipt(locale_source, locale_names)

    planned_sources = {source for source, _, _ in files}
    remaining_code = []
    for path in sorted(source_root.iterdir()):
        if path in planned_sources or path == locale_source:
            continue
        if path.is_symlink():
            raise RuntimeError(f"Unsupported direct Contents/MacOS entry: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError(f"Unsupported direct Contents/MacOS entry: {path}")
        with path.open("rb") as handle:
            magic = handle.read(4)
        if magic not in MACHO_MAGICS:
            raise RuntimeError(
                f"Non-code file would remain directly in Contents/MacOS: {path}"
            )
        remaining_code.append(
            {
                "path": str(path.relative_to(app)),
                "magic": magic.hex(),
                "sha256": _sha256(path),
            }
        )
    if not remaining_code:
        raise RuntimeError("No direct Mach-O application executable was found.")
    locales = (locale_source, locale_files, locale_receipt)
    return files, locales, remaining_code


def _apply_qtwebengine_resource_relocation(
    app: Path,
    plan: tuple[
        list[tuple[Path, Path, str]],
        tuple[Path, list[tuple[Path, Path, str]], dict[str, Any]],
        list[dict[str, Any]],
    ],
) -> dict[str, Any]:
    files, locales, remaining_code = plan
    file_receipts = []
    for source, destination, before_hash in files:
        before_mode = stat.S_IMODE(source.stat().st_mode)
        source.rename(destination)
        after_hash = _sha256(destination)
        after_mode = stat.S_IMODE(destination.stat().st_mode)
        if before_hash != after_hash or before_mode != after_mode:
            raise RuntimeError(
                f"QtWebEngine resource changed during relocation: {destination}"
            )
        file_receipts.append(
            {
                "from_path": str(source.relative_to(app)),
                "to_path": str(destination.relative_to(app)),
                "mode_before": oct(before_mode),
                "mode_after": oct(after_mode),
                "sha256_before": before_hash,
                "sha256_after": after_hash,
            }
        )

    locale_source, locale_files, before = locales
    locale_names = []
    for source, destination, before_hash in locale_files:
        before_mode = stat.S_IMODE(source.stat().st_mode)
        source.rename(destination)
        if _sha256(destination) != before_hash:
            raise RuntimeError(
                f"QtWebEngine locale changed during relocation: {destination}"
            )
        if stat.S_IMODE(destination.stat().st_mode) != before_mode:
            raise RuntimeError(
                f"QtWebEngine locale mode changed during relocation: {destination}"
            )
        locale_names.append(destination.name)
    locale_source.rmdir()
    after = _flat_file_set_receipt(
        app / "Contents" / "Resources", locale_names
    )
    if before != after:
        raise RuntimeError(
            "QtWebEngine locale content changed during bundle relocation."
        )
    for index, (_, destination, before_hash) in enumerate(files):
        final_hash = _sha256(destination)
        if final_hash != before_hash:
            raise RuntimeError(
                "QtWebEngine root resource changed after locale relocation: "
                f"{destination}"
            )
        file_receipts[index]["sha256_final"] = final_hash
    return {
        "files": file_receipts,
        "locales": {
            "from_path": str(locale_source.relative_to(app)),
            "to_path": "Contents/Resources",
            "files": before["files"],
            "tree_sha256_before": before["tree_sha256"],
            "tree_sha256_after": after["tree_sha256"],
        },
        "remaining_direct_macho": remaining_code,
    }


def _template_relocation_plan(
    app: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    source = app / HIDDEN_TEMPLATE_RELATIVE
    destination = source.with_name(PACKAGED_TEMPLATE_DIRNAME)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError(
            f"Packaged template destination already exists: {destination}"
        )
    if not source.is_dir() or source.is_symlink():
        raise RuntimeError(f"Hidden configuration template was not found: {source}")
    return source, destination, _template_tree_receipt(source)


def _apply_template_relocation(
    app: Path,
    plan: tuple[Path, Path, dict[str, Any]],
) -> dict[str, Any]:
    source, destination, before = plan
    source.rename(destination)
    after = _template_tree_receipt(destination)
    if before != after:
        raise RuntimeError(
            "Configuration template content changed during bundle relocation."
        )
    return {
        "from_path": str(source.relative_to(app)),
        "to_path": str(destination.relative_to(app)),
        "files": before["files"],
        "directories": before["directories"],
        "tree_sha256_before": before["tree_sha256"],
        "tree_sha256_after": after["tree_sha256"],
    }


def normalize_resource_modes(app: Path) -> list[dict[str, Any]]:
    """Remove execute bits only from allowlisted, verified data resources."""
    app = app.resolve()
    if app.suffix != ".app" or not app.is_dir():
        raise ValueError(f"Not an app bundle: {app}")
    return _apply_resource_modes(app, _resource_mode_candidates(app))


def normalize_bundle(app: Path) -> dict[str, Any]:
    """Preflight and apply all exact pyside6/Nuitka bundle repairs."""
    app = app.resolve()
    if app.suffix != ".app" or not app.is_dir():
        raise ValueError(f"Not an app bundle: {app}")
    resource_candidates = _resource_mode_candidates(app)
    outer_info_before = _outer_info_plist_receipt(app)
    frameworks_before = _framework_inventory(app)
    qtwebengine_plan = _qtwebengine_resource_relocation_plan(app)
    template_plan = _template_relocation_plan(app)
    report = {
        "changes": _apply_resource_modes(app, resource_candidates),
        "qtwebengine_resource_relocation": (
            _apply_qtwebengine_resource_relocation(app, qtwebengine_plan)
        ),
        "template_relocation": _apply_template_relocation(app, template_plan),
    }
    outer_info_after = _outer_info_plist_receipt(app)
    frameworks_after = _framework_inventory(app)
    if outer_info_before != outer_info_after:
        raise RuntimeError("Outer application Info.plist changed during normalization.")
    if frameworks_before != frameworks_after:
        raise RuntimeError("Nested QtWebEngine framework changed during normalization.")
    report["outer_info_plist"] = {
        "before": outer_info_before,
        "after": outer_info_after,
    }
    report["qtwebengine_frameworks"] = {
        "before": frameworks_before,
        "after": frameworks_after,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        normalization = normalize_bundle(args.app)
        report = {
            "status": "passed",
            "allowlist": list(ALLOWED_RESOURCE_GLOBS),
            **normalization,
        }
        returncode = 0
    except Exception as error:  # retain a bounded CI receipt before failing
        report = {
            "status": "failed",
            "allowlist": list(ALLOWED_RESOURCE_GLOBS),
            "changes": [],
            "outer_info_plist": None,
            "qtwebengine_frameworks": None,
            "qtwebengine_resource_relocation": None,
            "template_relocation": None,
            "error": {
                "type": type(error).__name__,
                "message": str(error)[-4000:],
            },
        }
        returncode = 1
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "normalized_resources": len(report["changes"]),
                "relocated_qtwebengine_resources": len(
                    (report.get("qtwebengine_resource_relocation") or {}).get(
                        "files", []
                    )
                ),
                "template_relocated": report["template_relocation"] is not None,
            }
        )
    )
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
