from __future__ import annotations

import configparser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_packaging_candidates_share_pinned_qt_boundary():
    constraints = (
        ROOT / "packaging" / "macos" / "constraints.txt"
    ).read_text(encoding="utf-8")
    requirements = (
        ROOT / "packaging" / "macos" / "build-requirements.txt"
    ).read_text(encoding="utf-8")

    assert "PySide6==6.9.2" in constraints
    assert "PyInstaller==6.21.0" in constraints
    assert "pyinstaller-hooks-contrib==2026.6" in constraints
    assert "Nuitka==2.7.11" in constraints
    assert "PyInstaller==6.21.0" in requirements
    assert "pyinstaller-hooks-contrib==2026.6" in requirements
    assert "Nuitka==2.7.11" in requirements


def test_pyside_deploy_candidate_includes_runtime_and_resources():
    config = configparser.ConfigParser()
    config.read(ROOT / "packaging" / "macos" / "pysidedeploy.spec")

    assert config["app"]["input_file"] == "chemsmart/gui/__main__.py"
    assert config["nuitka"]["mode"] == "standalone"
    assert "WebEngineWidgets" in config["qt"]["modules"]
    assert "--include-package=chemsmart" in config["nuitka"]["extra_args"]
    assert "--include-package-data=chemsmart" in config["nuitka"][
        "extra_args"
    ]
    assert "--no-deployment-flag=self-execution" in config["nuitka"][
        "extra_args"
    ]
    assert "--macos-signed-app-name=org.zhanglab.chemsmart" in config[
        "nuitka"
    ]["extra_args"]
    assert "--macos-target-arch=arm64" in config["nuitka"]["extra_args"]
    assert "chemsmart.agent.tui.*" in config["nuitka"]["extra_args"]


def test_pyinstaller_candidate_is_onedir_app_with_no_path_dispatch():
    spec = (
        ROOT / "packaging" / "macos" / "ChemSmart.pyinstaller.spec"
    ).read_text(encoding="utf-8")

    assert "COLLECT(" in spec
    assert "BUNDLE(" in spec
    assert 'bundle_identifier="org.zhanglab.chemsmart"' in spec
    assert '"LSMinimumSystemVersion": "14.0"' in spec
    assert "collect_data_files(\"chemsmart\"" in spec
    assert 'target_arch="arm64"' in spec
    assert 'name.startswith("chemsmart.agent.tui")' in spec
    assert '"textual"' in spec


def test_packaging_workflow_is_manual_and_runs_both_candidates():
    workflow = (
        ROOT / ".github" / "workflows" / "macos-packaging-spike.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "pull_request:" not in workflow
    assert "candidate: [pyinstaller, pyside6-deploy]" in workflow
    assert "runs-on: macos-14" in workflow
    assert 'test "$(uname -m)" = "arm64"' in workflow
    assert 'test "$(sw_vers -productVersion | cut -d. -f1)" = "14"' in workflow
    assert '".[gui,agent,agent-tui,test]"' in workflow
    assert "tests/gui \\" in workflow
    assert "--dry-run" in workflow
    assert "--archive" in workflow
    assert "--launches 3" in workflow
    assert "secrets." not in workflow


def test_packaging_specs_are_explicitly_tracked_despite_global_ignore():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "!packaging/macos/ChemSmart.pyinstaller.spec" in ignore
    assert "!packaging/macos/pysidedeploy.spec" in ignore
