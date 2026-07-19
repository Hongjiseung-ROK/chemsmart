from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_selected_pyinstaller_has_pinned_qt_boundary():
    constraints = (
        ROOT / "packaging" / "macos" / "constraints.txt"
    ).read_text(encoding="utf-8")
    requirements = (
        ROOT / "packaging" / "macos" / "build-requirements.txt"
    ).read_text(encoding="utf-8")

    assert "pip==25.3" in constraints
    assert "setuptools==74.1.1" in constraints
    assert "wheel==0.46.3" in constraints
    assert "PySide6==6.9.2" in constraints
    assert "PyInstaller==6.21.0" in constraints
    assert "pyinstaller-hooks-contrib==2026.6" in constraints
    assert "PyInstaller==6.21.0" in requirements
    assert "pyinstaller-hooks-contrib==2026.6" in requirements
    assert "Nuitka" not in constraints
    assert "Nuitka" not in requirements
    assert "ordered-set" not in requirements
    assert "zstandard" not in requirements


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
    assert 'collect_submodules("keyring")' in spec
    assert '"textual"' in spec


def test_packaging_workflow_is_manual_pyinstaller_only():
    workflow = (
        ROOT / ".github" / "workflows" / "macos-packaging-spike.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "pull_request:" not in workflow
    assert "CANDIDATE: pyinstaller" in workflow
    assert "inputs:" not in workflow
    assert "matrix.candidate" not in workflow
    assert "pyside6-deploy" not in workflow
    assert "Nuitka" not in workflow
    assert "runs-on: macos-14" in workflow
    assert "timeout-minutes: 120" in workflow
    assert 'test "$(uname -m)" = "arm64"' in workflow
    assert 'test "$(sw_vers -productVersion | cut -d. -f1)" = "14"' in workflow
    assert "source-provenance.json" in workflow
    assert (
        "uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10"
        in workflow
    )
    assert (
        "uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
        in workflow
    )
    assert workflow.count(
        "uses: actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f"
    ) == 2
    assert "actions/checkout@v6" not in workflow
    assert "actions/setup-python@v6" not in workflow
    assert "actions/upload-artifact@v6" not in workflow
    assert 'tee "build/p1/${CANDIDATE}/source-tests.txt"' in workflow
    assert "set -o pipefail" in workflow
    assert "uses: actions/cache/restore@v6" not in workflow
    assert "uses: actions/cache/save@v6" not in workflow
    assert "if: ${{ !cancelled() && steps.signing.outcome == 'success' }}" in workflow
    assert '".[gui,agent,agent-tui,test]"' in workflow
    assert "runtime-lock-py311-macos14-arm64.txt" in workflow
    assert 'python-version: "3.11.9"' in workflow
    assert "--no-build-isolation" in workflow
    assert "pip freeze --all" in workflow
    assert "python -m pip check" in workflow
    assert "verify_runtime_lock.py" in workflow
    assert workflow.count("MPLCONFIGDIR:") == 2
    assert "Matplotlib font-cache prewarm failed" in workflow
    assert "matplotlib-cache.json" in workflow
    assert "runtime-lock-verification.json" in workflow
    assert "tests/gui \\" in workflow
    assert "tests/agent/test_secrets.py \\" in workflow
    assert "Apply nested-to-outer ad-hoc candidate signature" in workflow
    assert workflow.count("app=build/p1/pyinstaller/dist/ChemSmart.app") == 2
    assert "find build chemsmart/gui/deployment" not in workflow
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
    assert "launches-*/probe-*/receipt.json" in workflow
    assert "launches-*/shell-*/receipt.json" in workflow
    assert workflow.count("application.*.txt") == 2
    evidence_section, bundle_section = workflow.split(
        "- name: Upload verified candidate bundle"
    )
    assert "ChemSmart-*.zip" not in evidence_section
    assert "ChemSmart-*.zip" in bundle_section
    assert "${{ secrets." not in workflow


def test_packaging_specs_are_explicitly_tracked_despite_global_ignore():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "!packaging/macos/ChemSmart.pyinstaller.spec" in ignore
    assert "!packaging/macos/pysidedeploy.spec" not in ignore


def test_desktop_runtime_lock_is_exact_and_contains_keychain_boundary():
    lock_path = (
        ROOT
        / "packaging"
        / "macos"
        / "runtime-lock-py311-macos14-arm64.txt"
    )
    lines = [
        line.strip()
        for line in lock_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    assert all("==" in line for line in lines)
    assert "keyring==25.7.0" in lines
    assert "PySide6==6.9.2" in lines
    assert "pyinstaller==6.21.0" in lines
    assert "numpy==1.26.4" in lines
    assert "pip==25.3" in lines
    assert "setuptools==74.1.1" in lines
    assert "wheel==0.46.3" in lines
    assert "Nuitka==2.7.11" not in lines
    assert "ordered-set==4.1.0" not in lines
    assert "zstandard==0.23.0" not in lines
    assert len(lines) == len({line.split("==", 1)[0].lower() for line in lines})


def test_agent_extra_can_resolve_keyring_references() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    agent_section = project.split("agent = [", 1)[1].split("]", 1)[0]
    assert '"keyring>=25.7,<26"' in agent_section
