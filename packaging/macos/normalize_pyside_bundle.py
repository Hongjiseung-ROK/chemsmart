"""Normalize the known Nuitka QtWebEngine resource-mode defect on macOS."""

from __future__ import annotations

import argparse
import hashlib
import json
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
    template_plan = _template_relocation_plan(app)
    return {
        "changes": _apply_resource_modes(app, resource_candidates),
        "template_relocation": _apply_template_relocation(app, template_plan),
    }


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
                "template_relocated": report["template_relocation"] is not None,
            }
        )
    )
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
