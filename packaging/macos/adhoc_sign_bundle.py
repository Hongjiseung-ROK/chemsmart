"""Apply the P1 ad-hoc macOS signature from nested WebEngine code outward."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import subprocess
from pathlib import Path
from typing import Any


PRESERVED_METADATA = "identifier,entitlements,requirements,flags,runtime"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    result = {
        "command": command,
        "returncode": completed.returncode,
        "output": completed.stdout[-8000:],
    }
    return result


def _containing_framework(path: Path, app: Path) -> Path:
    for parent in path.parents:
        if parent.suffix == ".framework":
            return parent
        if parent == app:
            break
    raise RuntimeError(f"QtWebEngineProcess is not inside a framework: {path}")


def sign_bundle(app: Path) -> dict[str, Any]:
    """Sign WebEngine helpers, containing frameworks, then the outer app."""
    app = app.resolve()
    if app.suffix != ".app" or not app.is_dir():
        raise ValueError(f"Not an app bundle: {app}")

    helper_apps = sorted(
        path
        for path in app.rglob("QtWebEngineProcess.app")
        if path.is_dir() and not path.is_symlink()
    )
    if not helper_apps:
        raise RuntimeError("QtWebEngineProcess.app was not found.")

    report: dict[str, Any] = {
        "status": "running",
        "app": str(app),
        "helpers": [],
        "frameworks": [],
        "outer_signing": None,
        "verification": None,
        "failed_stage": None,
    }
    frameworks = set()
    for helper_app in helper_apps:
        entitlement_files = list(
            helper_app.rglob("QtWebEngineProcess.entitlements")
        )
        if len(entitlement_files) != 1:
            raise RuntimeError(
                f"Expected one helper entitlement template: {helper_app}"
            )
        entitlements = entitlement_files[0]
        parsed = plistlib.loads(entitlements.read_bytes())
        if not isinstance(parsed, dict) or not parsed:
            raise RuntimeError(f"Invalid helper entitlements: {entitlements}")
        signing_result = _run(
            [
                "/usr/bin/codesign",
                "--force",
                "--deep",
                "--sign",
                "-",
                "--timestamp=none",
                "--entitlements",
                str(entitlements),
                str(helper_app),
            ]
        )
        report["helpers"].append(
            {
                "path": str(helper_app.relative_to(app)),
                "entitlements_path": str(entitlements.relative_to(app)),
                "entitlements_sha256": _sha256(entitlements),
                "required_entitlements": parsed,
                "signing": signing_result,
            }
        )
        if report["helpers"][-1]["signing"]["returncode"]:
            report["status"] = "failed"
            report["failed_stage"] = "helper_signing"
            return report
        frameworks.add(_containing_framework(helper_app, app))

    for framework in sorted(frameworks, key=lambda path: len(path.parts), reverse=True):
        signing_result = _run(
            [
                "/usr/bin/codesign",
                "--force",
                "--sign",
                "-",
                "--timestamp=none",
                f"--preserve-metadata={PRESERVED_METADATA}",
                str(framework),
            ]
        )
        report["frameworks"].append(
            {
                "path": str(framework.relative_to(app)),
                "signing": signing_result,
            }
        )
        if report["frameworks"][-1]["signing"]["returncode"]:
            report["status"] = "failed"
            report["failed_stage"] = "framework_signing"
            return report

    outer = _run(
        [
            "/usr/bin/codesign",
            "--force",
            "--sign",
            "-",
            "--timestamp=none",
            f"--preserve-metadata={PRESERVED_METADATA}",
            str(app),
        ]
    )
    report["outer_signing"] = outer
    if outer["returncode"]:
        report["status"] = "failed"
        report["failed_stage"] = "outer_signing"
        return report
    verification = _run(
        [
            "/usr/bin/codesign",
            "--verify",
            "--deep",
            "--strict",
            "--verbose=2",
            str(app),
        ]
    )
    report["verification"] = verification
    report["status"] = "passed" if verification["returncode"] == 0 else "failed"
    if report["status"] == "failed":
        report["failed_stage"] = "strict_verification"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = sign_bundle(args.app)
    except Exception as error:  # retain validation failures as CI evidence
        report = {
            "status": "failed",
            "app": str(args.app.resolve()),
            "helpers": [],
            "frameworks": [],
            "outer_signing": None,
            "verification": None,
            "failed_stage": "preflight",
            "error": {
                "type": type(error).__name__,
                "message": str(error)[-4000:],
            },
        }
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "signed_helpers": len(report["helpers"]),
            }
        )
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
