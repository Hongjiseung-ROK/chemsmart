from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys

import pytest


_PATH = (
    Path(__file__).resolve().parents[2]
    / "packaging"
    / "macos"
    / "verify_runtime_lock.py"
)
_SPEC = importlib.util.spec_from_file_location("chemsmart_runtime_lock", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
RuntimeLockError = _MODULE.RuntimeLockError
expected_versions = _MODULE.expected_versions
installed_versions = _MODULE.installed_versions
verify_runtime_lock = _MODULE.verify_runtime_lock


@dataclass
class _Distribution:
    name: str
    version: str

    @property
    def metadata(self):
        return {"Name": self.name}


def test_checked_in_runtime_lock_parses_as_exact_requirements() -> None:
    expected = expected_versions(
        _PATH.with_name("runtime-lock-py311-macos14-arm64.txt")
    )

    assert expected["pip"] == "25.3"
    assert expected["setuptools"] == "74.1.1"
    assert expected["wheel"] == "0.46.3"
    assert expected["keyring"] == "25.7.0"


def test_runtime_lock_accepts_exact_environment_and_local_project() -> None:
    installed = installed_versions(
        [
            _Distribution("Example_Dep", "1.2.3"),
            _Distribution("chemsmart", "2.0.1"),
        ]
    )

    receipt = verify_runtime_lock({"example-dep": "1.2.3"}, installed)

    assert receipt["status"] == "green"
    assert receipt["allowed_unlocked"] == ["chemsmart"]


@pytest.mark.parametrize(
    "installed",
    [
        {},
        {"example-dep": "9.9.9"},
        {"example-dep": "1.2.3", "unexpected": "1.0"},
    ],
)
def test_runtime_lock_rejects_missing_mismatched_or_extra(installed) -> None:
    with pytest.raises(RuntimeLockError):
        verify_runtime_lock({"example-dep": "1.2.3"}, installed)
