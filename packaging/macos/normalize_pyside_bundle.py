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


def normalize_resource_modes(app: Path) -> list[dict[str, Any]]:
    """Remove execute bits only from allowlisted, verified data resources."""
    app = app.resolve()
    if app.suffix != ".app" or not app.is_dir():
        raise ValueError(f"Not an app bundle: {app}")

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        changes = normalize_resource_modes(args.app)
        report = {
            "status": "passed",
            "allowlist": list(ALLOWED_RESOURCE_GLOBS),
            "changes": changes,
        }
        returncode = 0
    except Exception as error:  # retain a bounded CI receipt before failing
        report = {
            "status": "failed",
            "allowlist": list(ALLOWED_RESOURCE_GLOBS),
            "changes": [],
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
            }
        )
    )
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
