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
    assert "default: both" in workflow
    assert "fromJSON(inputs.candidate == 'both'" in workflow
    assert "pyinstaller\",\"pyside6-deploy" in workflow
    assert "runs-on: macos-14" in workflow
    assert "timeout-minutes: 120" in workflow
    assert 'test "$(uname -m)" = "arm64"' in workflow
    assert 'test "$(sw_vers -productVersion | cut -d. -f1)" = "14"' in workflow
    assert "source-provenance.json" in workflow
    assert "uses: actions/checkout@v6" in workflow
    assert "uses: actions/setup-python@v6" in workflow
    assert workflow.count("uses: actions/upload-artifact@v6") == 2
    assert 'tee "build/p1/${CANDIDATE}/source-tests.txt"' in workflow
    assert "set -o pipefail" in workflow
    assert "uses: actions/cache/restore@v6" in workflow
    assert "uses: actions/cache/save@v6" in workflow
    assert "id: nuitka-cache-restore" in workflow
    assert "steps.nuitka-cache-restore.outputs.cache-primary-key" in workflow
    assert "steps.nuitka-cache-restore.outputs.cache-hit != 'true'" in workflow
    assert "if: ${{ !cancelled() && steps.signing.outcome == 'success' }}" in workflow
    assert "CCACHE_DIR: /tmp/chemsmart-nuitka-ccache" in workflow
    assert "NUITKA_CCACHE_BINARY=$(command -v ccache)" in workflow
    assert "ccache --show-stats" in workflow
    assert '".[gui,agent,agent-tui,test]"' in workflow
    assert "tests/gui \\" in workflow
    assert "--dry-run" in workflow
    assert "/usr/bin/grep -F" in workflow
    assert "rg -F" not in workflow
    assert "resource-mode-fixes.json" in workflow
    assert "normalize_pyside_bundle.py" in workflow
    assert "ccache --max-size=2G" in workflow
    assert "py311-pyside692-nuitka2711" in workflow
    assert "hashFiles('packaging/macos/pysidedeploy.spec'" in workflow
    assert "chemsmart-p1-nuitka-${{ runner.os }}-${{ runner.arch }}-" in workflow
    assert "Apply nested-to-outer ad-hoc candidate signature" in workflow
    assert "id: signing" in workflow
    assert "adhoc_sign_bundle.py" in workflow
    assert "adhoc-signing.json" in workflow
    assert "--archive" in workflow
    assert '--forbidden-path "$GITHUB_WORKSPACE"' in workflow
    assert '--forbidden-path "$RUNNER_TEMP"' in workflow
    assert "--launches 3" in workflow
    assert "verify_status=$?" in workflow
    assert "continue-on-error: true" in workflow
    assert "steps.verify.outcome == 'success'" in workflow
    assert "steps.verify.outcome != 'success'" in workflow
    assert "steps.signing.outcome != 'success'" in workflow
    assert workflow.count("compression-level: 0") == 2
    assert "path: build/p1/${{ matrix.candidate }}/" not in workflow
    assert "candidate }}/launches-*/\n" not in workflow
    assert "launches-*/probe-*/receipt.json" in workflow
    assert "launches-*/shell-*/receipt.json" in workflow
    assert workflow.count("application.*.txt") == 2
    evidence_section, bundle_section = workflow.split(
        "- name: Upload verified candidate bundle"
    )
    assert "ChemSmart-*.zip" not in evidence_section
    assert "ChemSmart-*.zip" in bundle_section
    assert "secrets." not in workflow


def test_packaging_specs_are_explicitly_tracked_despite_global_ignore():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "!packaging/macos/ChemSmart.pyinstaller.spec" in ignore
    assert "!packaging/macos/pysidedeploy.spec" in ignore
