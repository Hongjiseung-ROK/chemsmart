"""Build and verify the ad-hoc-signed ChemSmart internal-alpha DMG.

The input application must already have passed ``verify_bundle.py``.  This
script never changes that bundle: it copies the app into a disposable volume,
creates a read-only DMG, mounts the image, and requires the mounted app to have
the same inventory digest and valid nested signature as the input.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote


APP_NAME = "ChemSmart.app"
RELEASE_LEVEL = "internal-alpha-adhoc"
VOLUME_NAME = "ChemSmart Internal Alpha"
APPLICATIONS_LINK = "/Applications"
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]*$")
BUILD_TOOL_DISTRIBUTIONS = {
    "pip",
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "setuptools",
    "wheel",
}
RELEASE_FORBIDDEN_DISTRIBUTIONS = {
    "coverage",
    "pip",
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "pyperclip",
    "pytest",
    "textual",
    "watchdog",
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


def _load_bundle_verifier():
    path = Path(__file__).with_name("verify_bundle.py")
    spec = importlib.util.spec_from_file_location(
        "chemsmart_release_bundle_verifier",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the bundle verifier.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_VERIFIER = _load_bundle_verifier()
_bundle_inventory = _VERIFIER._bundle_inventory
_sha256 = _VERIFIER._sha256
_tree_size = _VERIFIER._tree_size


def _run(command: list[str], *, timeout: int = 900) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "output": completed.stdout[-12000:],
    }


def _require_command(
    command: list[str],
    *,
    label: str,
    timeout: int = 900,
) -> dict[str, Any]:
    receipt = _run(command, timeout=timeout)
    if receipt["returncode"] != 0:
        raise RuntimeError(
            f"{label} failed with exit {receipt['returncode']}: "
            f"{receipt['output'][-2000:]}"
        )
    return receipt


def _command_status(receipt: dict[str, Any]) -> dict[str, int]:
    """Retain the result without embedding disposable builder paths."""
    return {"returncode": int(receipt["returncode"])}


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _locked_components(lock_path: Path) -> list[dict[str, str]]:
    components: list[dict[str, str]] = []
    seen: set[str] = set()
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
        if name in seen:
            raise ValueError(f"Duplicate runtime-lock distribution: {name}")
        seen.add(name)
        components.append(
            {
                "name": name,
                "version": match.group(2),
                "marker": marker.strip() if separator else "",
            }
        )
    return sorted(components, key=lambda item: item["name"])


def _cyclonedx_sbom(
    *,
    version: str,
    source_sha: str,
    app_inventory_sha256: str,
    components: list[dict[str, Any]],
    build_tools: list[dict[str, str]],
) -> dict[str, Any]:
    seed = f"{source_sha}:{app_inventory_sha256}:{version}"
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"urn:chemsmart:{seed}")
    application_ref = f"pkg:pypi/chemsmart@{quote(version, safe='')}"
    libraries: list[dict[str, Any]] = []
    dependency_refs: list[str] = []
    for component in components:
        purl = (
            f"pkg:pypi/{quote(component['name'], safe='')}@"
            f"{quote(component['version'], safe='')}"
        )
        entry: dict[str, Any] = {
            "bom-ref": purl,
            "name": component["name"],
            "purl": purl,
            "type": "library",
            "version": component["version"],
            "properties": [
                {
                    "name": "chemsmart:pyinstaller-top-level-evidence",
                    "value": ",".join(component["evidence_top_levels"]),
                }
            ],
        }
        if component["marker"]:
            entry["properties"].append(
                {
                    "name": "chemsmart:environment-marker",
                    "value": component["marker"],
                }
            )
        libraries.append(entry)
        dependency_refs.append(purl)
    dependencies = [
        {"dependsOn": dependency_refs, "ref": application_ref},
        *({"dependsOn": [], "ref": ref} for ref in dependency_refs),
    ]
    shipped_names = {component["name"] for component in components}
    tool_components = []
    for component in build_tools:
        if component["name"] in shipped_names:
            scope = "builder tool; also present in shipped component inventory"
        else:
            scope = "builder-only tool; not inferred as shipped"
        tool_components.append(
            {
                "name": component["name"],
                "properties": [
                    {
                        "name": "chemsmart:scope",
                        "value": scope,
                    }
                ],
                "purl": (
                    f"pkg:pypi/{quote(component['name'], safe='')}@"
                    f"{quote(component['version'], safe='')}"
                ),
                "type": "application",
                "version": component["version"],
            }
        )
    return {
        "bomFormat": "CycloneDX",
        "components": libraries,
        "dependencies": dependencies,
        "metadata": {
            "component": {
                "bom-ref": application_ref,
                "name": "chemsmart",
                "properties": [
                    {
                        "name": "chemsmart:source-sha",
                        "value": source_sha,
                    },
                    {
                        "name": "chemsmart:bundle-inventory-sha256",
                        "value": app_inventory_sha256,
                    },
                    {
                        "name": "chemsmart:release-level",
                        "value": RELEASE_LEVEL,
                    },
                ],
                "purl": application_ref,
                "type": "application",
                "version": version,
            },
            "tools": {"components": tool_components},
        },
        "serialNumber": f"urn:uuid:{serial}",
        "specVersion": "1.5",
        "version": 1,
    }


def _readme_text(*, version: str, source_sha: str) -> str:
    return f"""ChemSmart {version} — INTERNAL ALPHA

This build is for controlled Zhang Lab evaluation on Apple Silicon Macs.
It is ad-hoc signed, not Developer ID signed or notarized. macOS Gatekeeper is
therefore expected to require an explicit user override.

Install
1. Drag ChemSmart.app onto the Applications shortcut in this window.
2. Open Applications, Control-click ChemSmart, and choose Open.
3. If macOS still blocks it, use System Settings > Privacy & Security >
   Open Anyway. Do not disable Gatekeeper globally.

Safety
- The desktop app generates fake/no-scratch inputs only.
- It does not run Gaussian, ORCA, or xTB calculations or submit HPC jobs.
- AI setup is optional; provider secrets are never included in this image.

Build receipt
- Version: {version}
- Architecture: arm64
- Minimum declared macOS: 14.0
- Source SHA: {source_sha}

Verify the downloaded DMG against SHA256SUMS.txt before opening it. See the
separate macOS internal-alpha guide for upgrade, removal, retained user data,
and support-bundle instructions.
"""


def _inventory_summary(inventory: dict[str, Any]) -> dict[str, Any]:
    return {
        "absolute_symlink_count": len(inventory["absolute_symlinks"]),
        "broken_symlink_count": len(inventory["broken_symlinks"]),
        "directory_count": inventory["directory_count"],
        "escaping_symlink_count": len(inventory["escaping_symlinks"]),
        "file_count": inventory["file_count"],
        "sha256": inventory["sha256"],
        "symlink_count": inventory["symlink_count"],
    }


def _validate_input_receipts(
    *,
    app: Path,
    metrics: dict[str, Any],
    runtime_receipt: dict[str, Any],
    source: dict[str, Any],
    locked_components: list[dict[str, str]],
    bundle_components: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    if metrics.get("status") != "passed":
        raise ValueError("Bundle metrics are not green.")
    mandatory = metrics.get("mandatory")
    if not isinstance(mandatory, dict) or not mandatory:
        raise ValueError("Bundle metrics have no mandatory gate receipt.")
    failed = sorted(key for key, value in mandatory.items() if value is not True)
    if failed:
        raise ValueError(f"Bundle metrics contain failed gates: {failed}")
    if runtime_receipt.get("status") != "green":
        raise ValueError("Runtime-lock receipt is not green.")
    if runtime_receipt.get("expected_distribution_count") != len(
        locked_components
    ):
        raise ValueError("Runtime-lock component count does not match receipt.")
    if bundle_components.get("status") != "passed":
        raise ValueError("PyInstaller component inventory is not green.")
    if bundle_components.get("mandatory_distributions_missing") not in (
        None,
        [],
    ):
        raise ValueError("PyInstaller component inventory misses mandatory items.")
    if bundle_components.get("forbidden_release_distributions_present") not in (
        None,
        [],
    ):
        raise ValueError("PyInstaller component inventory contains excluded items.")
    components = bundle_components.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("PyInstaller component inventory is empty.")
    locked_by_name = {item["name"]: item for item in locked_components}
    component_names: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("Invalid PyInstaller component entry.")
        name = str(component.get("name") or "")
        if name in component_names:
            raise ValueError("Duplicate PyInstaller component entry.")
        component_names.add(name)
        locked = locked_by_name.get(name)
        if (
            locked is None
            or locked["version"] != component.get("version")
            or locked["marker"] != component.get("marker")
        ):
            raise ValueError(
                "PyInstaller component is absent from the exact runtime lock."
            )
        evidence = component.get("evidence_top_levels")
        if (
            not isinstance(evidence, list)
            or not evidence
            or not all(isinstance(item, str) and item for item in evidence)
        ):
            raise ValueError("PyInstaller component has no module evidence.")
    if bundle_components.get("component_count") not in (None, len(components)):
        raise ValueError("PyInstaller component count does not match receipt.")
    missing = REQUIRED_DISTRIBUTIONS - component_names
    if missing:
        raise ValueError(f"Mandatory PyInstaller components are missing: {sorted(missing)}")
    forbidden = RELEASE_FORBIDDEN_DISTRIBUTIONS & component_names
    if forbidden:
        raise ValueError(
            f"Excluded PyInstaller components are present: {sorted(forbidden)}"
        )
    source_sha = str(source.get("commit") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("Source provenance has no full commit SHA.")
    if source.get("workflow_sha") != source_sha:
        raise ValueError("Source and workflow SHAs differ.")

    inventory = _bundle_inventory(app)
    expected_inventory = (
        (metrics.get("bundle") or {}).get("inventory_after") or {}
    )
    if inventory["sha256"] != expected_inventory.get("sha256"):
        raise ValueError("Input app does not match the verified inventory.")
    if (
        inventory["broken_symlinks"]
        or inventory["absolute_symlinks"]
        or inventory["escaping_symlinks"]
    ):
        raise ValueError("Input app contains unsafe symlinks.")
    return inventory, source_sha


def _verify_mounted_image(
    *,
    dmg: Path,
    mountpoint: Path,
    expected_inventory: dict[str, Any],
    expected_readme: str,
) -> dict[str, Any]:
    verify_receipt = _require_command(
        ["/usr/bin/hdiutil", "verify", str(dmg)],
        label="DMG verification",
    )
    mountpoint.mkdir()
    attach_receipt = _require_command(
        [
            "/usr/bin/hdiutil",
            "attach",
            "-readonly",
            "-nobrowse",
            "-mountpoint",
            str(mountpoint),
            str(dmg),
        ],
        label="DMG mount",
    )
    mounted = True
    try:
        mounted_app = mountpoint / APP_NAME
        applications = mountpoint / "Applications"
        readme = mountpoint / "READ ME - INTERNAL ALPHA.txt"
        if not mounted_app.is_dir() or mounted_app.is_symlink():
            raise RuntimeError("Mounted image has no regular ChemSmart.app.")
        if not applications.is_symlink():
            raise RuntimeError("Mounted image has no Applications shortcut.")
        if os.readlink(applications) != APPLICATIONS_LINK:
            raise RuntimeError("Applications shortcut target changed.")
        if readme.read_text(encoding="utf-8") != expected_readme:
            raise RuntimeError("Mounted internal-alpha notice changed.")
        mounted_inventory = _bundle_inventory(mounted_app)
        if mounted_inventory["sha256"] != expected_inventory["sha256"]:
            raise RuntimeError("Mounted app inventory differs from input app.")
        codesign = _require_command(
            [
                "/usr/bin/codesign",
                "--verify",
                "--deep",
                "--strict",
                "--verbose=2",
                str(mounted_app),
            ],
            label="Mounted app code-signature verification",
        )
        gatekeeper = _run(
            [
                "/usr/sbin/spctl",
                "--assess",
                "--type",
                "execute",
                "-vv",
                str(mounted_app),
            ]
        )
        if (
            gatekeeper["returncode"] != 3
            or "rejected" not in gatekeeper["output"].lower()
        ):
            raise RuntimeError(
                "Gatekeeper did not produce the expected ad-hoc rejection."
            )
        return {
            "applications_link": APPLICATIONS_LINK,
            "attach": _command_status(attach_receipt),
            "codesign": _command_status(codesign),
            "gatekeeper_expected_rejection": _command_status(gatekeeper),
            "inventory": _inventory_summary(mounted_inventory),
            "readme_matches": True,
            "verify": _command_status(verify_receipt),
        }
    finally:
        if mounted:
            detach = _run(
                ["/usr/bin/hdiutil", "detach", str(mountpoint)],
                timeout=120,
            )
            if detach["returncode"] != 0:
                raise RuntimeError(
                    "DMG detach failed: " + detach["output"][-2000:]
                )


def build_internal_alpha(
    *,
    app: Path,
    output_dir: Path,
    version: str,
    bundle_metrics_path: Path,
    runtime_lock_path: Path,
    runtime_lock_receipt_path: Path,
    pip_freeze_path: Path,
    source_provenance_path: Path,
    bundle_components_path: Path,
) -> dict[str, Any]:
    if platform.system() != "Darwin":
        raise RuntimeError("Internal-alpha DMG creation requires macOS.")
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Unsafe release version: {version!r}")
    raw_app = app.expanduser().absolute()
    if raw_app.is_symlink():
        raise ValueError(f"Application input must not be a symlink: {raw_app}")
    app = raw_app.resolve()
    if app.name != APP_NAME or not app.is_dir():
        raise ValueError(f"Expected a regular {APP_NAME} directory: {app}")
    output_dir = output_dir.expanduser().resolve(strict=False)
    if output_dir == app or app in output_dir.parents:
        raise ValueError("Release output must be outside the input application.")
    if output_dir in app.parents:
        raise ValueError("Release output must not contain the input application.")
    if output_dir.exists():
        raise FileExistsError(f"Release output already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    metrics = _read_json(bundle_metrics_path, label="bundle metrics")
    runtime_receipt = _read_json(
        runtime_lock_receipt_path,
        label="runtime-lock receipt",
    )
    source = _read_json(source_provenance_path, label="source provenance")
    locked_components = _locked_components(runtime_lock_path)
    bundle_components = _read_json(
        bundle_components_path,
        label="PyInstaller component inventory",
    )
    input_inventory, source_sha = _validate_input_receipts(
        app=app,
        metrics=metrics,
        runtime_receipt=runtime_receipt,
        source=source,
        locked_components=locked_components,
        bundle_components=bundle_components,
    )
    components = bundle_components["components"]
    build_tools = [
        component
        for component in locked_components
        if component["name"] in BUILD_TOOL_DISTRIBUTIONS
    ]

    release_name = f"ChemSmart-{version}-macos14-arm64-internal-alpha"
    work_root = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent)
    )
    try:
        volume = work_root / "volume"
        volume.mkdir()
        staged_app = volume / APP_NAME
        _require_command(
            ["/usr/bin/ditto", str(app), str(staged_app)],
            label="Application staging",
        )
        (volume / "Applications").symlink_to(APPLICATIONS_LINK)
        readme_text = _readme_text(version=version, source_sha=source_sha)
        (volume / "READ ME - INTERNAL ALPHA.txt").write_text(
            readme_text,
            encoding="utf-8",
        )
        staged_inventory = _bundle_inventory(staged_app)
        if staged_inventory["sha256"] != input_inventory["sha256"]:
            raise RuntimeError("Staging changed the verified app inventory.")

        dmg_path = work_root / f"{release_name}.dmg"
        create_receipt = _require_command(
            [
                "/usr/bin/hdiutil",
                "create",
                "-fs",
                "HFS+",
                "-format",
                "UDZO",
                "-volname",
                VOLUME_NAME,
                "-srcfolder",
                str(volume),
                str(dmg_path),
            ],
            label="DMG creation",
            timeout=1800,
        )
        shutil.rmtree(volume)
        mounted_receipt = _verify_mounted_image(
            dmg=dmg_path,
            mountpoint=work_root / "mounted",
            expected_inventory=input_inventory,
            expected_readme=readme_text,
        )
        if _bundle_inventory(app)["sha256"] != input_inventory["sha256"]:
            raise RuntimeError("Release build mutated the input application.")

        readme_path = work_root / "INTERNAL-ALPHA-README.txt"
        readme_path.write_text(readme_text, encoding="utf-8")
        sbom_path = work_root / f"{release_name}.sbom.cdx.json"
        _write_json(
            sbom_path,
            _cyclonedx_sbom(
                version=version,
                source_sha=source_sha,
                app_inventory_sha256=input_inventory["sha256"],
                components=components,
                build_tools=build_tools,
            ),
        )

        receipt_path = work_root / f"{release_name}.release-receipt.json"
        receipt = {
            "app": {
                "bytes": _tree_size(app),
                "inventory": _inventory_summary(input_inventory),
                "name": APP_NAME,
            },
            "artifacts": {
                "dmg": {
                    "bytes": dmg_path.stat().st_size,
                    "name": dmg_path.name,
                    "sha256": _sha256(dmg_path),
                },
                "readme": {
                    "bytes": readme_path.stat().st_size,
                    "name": readme_path.name,
                    "sha256": _sha256(readme_path),
                },
                "sbom": {
                    "bytes": sbom_path.stat().st_size,
                    "component_count": len(components),
                    "name": sbom_path.name,
                    "sha256": _sha256(sbom_path),
                    "shipped_component_count": len(components),
                    "builder_tool_count": len(build_tools),
                },
            },
            "build": {
                "content_contract_reproducible": True,
                "dmg_bytes_reproducible": False,
                "dmg_reproducibility_note": (
                    "hdiutil/HFS+ image metadata is not normalized; verify the "
                    "recorded content inventory and per-build DMG checksum."
                ),
                "release_level": RELEASE_LEVEL,
                "version": version,
                "volume_name": VOLUME_NAME,
            },
            "dmg_create": _command_status(create_receipt),
            "input_receipts": {
                "bundle_metrics_sha256": _sha256(bundle_metrics_path),
                "bundle_components_sha256": _sha256(bundle_components_path),
                "pip_freeze_sha256": _sha256(pip_freeze_path),
                "runtime_lock_receipt_sha256": _sha256(
                    runtime_lock_receipt_path
                ),
                "runtime_lock_sha256": _sha256(runtime_lock_path),
                "source_provenance_sha256": _sha256(
                    source_provenance_path
                ),
            },
            "mounted_verification": mounted_receipt,
            "schema_version": 1,
            "source": {
                "repository": source.get("repository"),
                "run_id": source.get("run_id"),
                "sha": source_sha,
                "workflow_sha": source.get("workflow_sha"),
            },
            "status": "passed",
        }
        _write_json(receipt_path, receipt)

        checksum_path = work_root / "SHA256SUMS.txt"
        checksum_targets = sorted(
            (dmg_path, readme_path, receipt_path, sbom_path),
            key=lambda path: path.name,
        )
        checksum_path.write_text(
            "".join(
                f"{_sha256(path)}  {path.name}\n" for path in checksum_targets
            ),
            encoding="utf-8",
        )
        os.replace(work_root, output_dir)
        return receipt
    except BaseException:
        shutil.rmtree(work_root, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--bundle-metrics", type=Path, required=True)
    parser.add_argument("--runtime-lock", type=Path, required=True)
    parser.add_argument("--runtime-lock-receipt", type=Path, required=True)
    parser.add_argument("--pip-freeze", type=Path, required=True)
    parser.add_argument("--source-provenance", type=Path, required=True)
    parser.add_argument("--bundle-components", type=Path, required=True)
    parser.add_argument("--failure-receipt", type=Path)
    args = parser.parse_args()
    try:
        receipt = build_internal_alpha(
            app=args.app,
            output_dir=args.output_dir,
            version=args.version,
            bundle_metrics_path=args.bundle_metrics,
            runtime_lock_path=args.runtime_lock,
            runtime_lock_receipt_path=args.runtime_lock_receipt,
            pip_freeze_path=args.pip_freeze,
            source_provenance_path=args.source_provenance,
            bundle_components_path=args.bundle_components,
        )
    except BaseException as exc:
        if args.failure_receipt is not None:
            failure_path = args.failure_receipt.resolve()
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            _write_json(
                failure_path,
                {
                    "error": f"{type(exc).__name__}: {exc}",
                    "schema_version": 1,
                    "status": "failed",
                },
            )
        raise
    print(
        json.dumps(
            {
                "dmg": receipt["artifacts"]["dmg"],
                "status": receipt["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
