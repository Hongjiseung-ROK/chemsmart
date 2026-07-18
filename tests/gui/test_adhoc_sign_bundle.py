from __future__ import annotations

import importlib.util
import plistlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "packaging" / "macos" / "adhoc_sign_bundle.py"
SPEC = importlib.util.spec_from_file_location(
    "chemsmart_adhoc_bundle_signer", MODULE_PATH
)
assert SPEC and SPEC.loader
signer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(signer)


def test_signer_orders_helper_framework_and_outer_app(monkeypatch, tmp_path):
    app = tmp_path / "ChemSmart.app"
    framework = app / "Contents" / "Frameworks" / "QtWebEngineCore.framework"
    helper = (
        framework
        / "Versions"
        / "A"
        / "Helpers"
        / "QtWebEngineProcess.app"
    )
    resources = helper / "Contents" / "Resources"
    resources.mkdir(parents=True)
    entitlements = resources / "QtWebEngineProcess.entitlements"
    entitlements.write_bytes(
        plistlib.dumps({"com.apple.security.cs.allow-jit": True})
    )
    commands = []

    def fake_run(command):
        commands.append(command)
        return {"command": command, "returncode": 0, "output": "ok"}

    monkeypatch.setattr(signer, "_run", fake_run)

    report = signer.sign_bundle(app)

    assert commands[0][-1] == str(helper)
    assert "--entitlements" in commands[0]
    assert commands[1][-1] == str(framework)
    assert "--deep" not in commands[1]
    assert commands[2][-1] == str(app)
    assert "--deep" not in commands[2]
    assert commands[3][1:4] == ["--verify", "--deep", "--strict"]
    assert report["helpers"][0]["required_entitlements"] == {
        "com.apple.security.cs.allow-jit": True
    }


def test_signer_rejects_helper_without_entitlement_template(tmp_path):
    app = tmp_path / "ChemSmart.app"
    helper = (
        app
        / "Contents"
        / "Frameworks"
        / "QtWebEngineCore.framework"
        / "Helpers"
        / "QtWebEngineProcess.app"
    )
    helper.mkdir(parents=True)

    try:
        signer.sign_bundle(app)
    except RuntimeError as error:
        assert "Expected one helper entitlement template" in str(error)
    else:
        raise AssertionError("Missing entitlement template was accepted")
