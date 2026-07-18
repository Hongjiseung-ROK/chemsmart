"""Verify the isolated macOS builder matches the exact desktop lock."""

from __future__ import annotations

import argparse
from importlib import metadata
import json
from pathlib import Path
import platform
from typing import Iterable

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


class RuntimeLockError(RuntimeError):
    """Raised when the builder environment drifts from the reviewed lock."""


def expected_versions(lock_path: Path) -> dict[str, str]:
    """Return marker-applicable exact requirements from ``lock_path``."""
    expected: dict[str, str] = {}
    for line_number, raw in enumerate(
        lock_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        pins = [
            item.version
            for item in requirement.specifier
            if item.operator == "==" and not item.version.endswith(".*")
        ]
        if len(pins) != 1 or len(requirement.specifier) != 1:
            raise RuntimeLockError(
                f"runtime lock line {line_number} is not one exact pin"
            )
        name = canonicalize_name(requirement.name)
        if name in expected:
            raise RuntimeLockError(f"duplicate runtime lock entry: {name}")
        expected[name] = pins[0]
    return expected


def installed_versions(
    distributions: Iterable[metadata.Distribution] | None = None,
) -> dict[str, str]:
    """Return the canonical installed distribution/version mapping."""
    installed: dict[str, str] = {}
    for distribution in distributions or metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        canonical = canonicalize_name(name)
        version = distribution.version
        previous = installed.setdefault(canonical, version)
        if previous != version:
            raise RuntimeLockError(
                f"multiple installed versions for {canonical}: "
                f"{previous}, {version}"
            )
    return installed


def verify_runtime_lock(
    expected: dict[str, str],
    installed: dict[str, str],
    *,
    allowed_unlocked: frozenset[str] = frozenset({"chemsmart"}),
) -> dict[str, object]:
    """Fail on missing, mismatched, or unexpected distributions."""
    missing = sorted(set(expected) - set(installed))
    mismatched = {
        name: {"expected": expected[name], "installed": installed[name]}
        for name in sorted(set(expected) & set(installed))
        if expected[name] != installed[name]
    }
    unexpected = sorted(set(installed) - set(expected) - allowed_unlocked)
    receipt: dict[str, object] = {
        "expected_distribution_count": len(expected),
        "installed_distribution_count": len(installed),
        "allowed_unlocked": sorted(allowed_unlocked & set(installed)),
        "missing": missing,
        "mismatched": mismatched,
        "unexpected": unexpected,
        "status": "green" if not (missing or mismatched or unexpected) else "red",
    }
    if receipt["status"] != "green":
        raise RuntimeLockError(json.dumps(receipt, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--python-version", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    observed_python = platform.python_version()
    common = {
        "lock": str(args.lock),
        "python_version": observed_python,
        "platform": platform.platform(),
    }
    failure: RuntimeLockError | None = None
    try:
        if observed_python != args.python_version:
            raise RuntimeLockError(
                f"expected Python {args.python_version}, "
                f"observed {observed_python}"
            )
        receipt = verify_runtime_lock(
            expected_versions(args.lock),
            installed_versions(),
        )
    except RuntimeLockError as exc:
        failure = exc
        try:
            details = json.loads(str(exc))
        except json.JSONDecodeError:
            details = {"error": str(exc), "status": "red"}
        receipt = details
    receipt.update(common)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, sort_keys=True))
    if failure is not None:
        raise failure
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
