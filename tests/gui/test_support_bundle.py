from __future__ import annotations

import json
import os
import stat
import zipfile

import pytest

from chemsmart.gui.application import desktop_logging
from chemsmart.gui.application import support_bundle as support_module
from chemsmart.gui.application.support_bundle import (
    MAX_LOG_BYTES,
    create_support_bundle,
)


def test_support_bundle_is_bounded_redacted_and_excludes_private_state(
    tmp_path,
) -> None:
    home = tmp_path / "Researcher Home"
    logs = tmp_path / "logs"
    logs.mkdir()
    secret = "sk-ant-abcdefghijklmnop"
    (logs / "desktop.log").write_text(
        f"workspace={home}/confidential\n"
        f"api_key={secret}\n"
        "OPENAI_API_KEY=sk-proj-abcdefghijklmnop\n"
        'provider={"api_key": "AIzaabcdefghijklmnopqrstuvwxyz123"}\n'
        "Authorization: Bearer abcdefghijklmnop\n",
        encoding="utf-8",
    )
    private_config = home / ".chemsmart" / "agent" / "agent.yaml"
    private_config.parent.mkdir(parents=True)
    private_config.write_text("api_key: never-copy-me", encoding="utf-8")
    output = tmp_path / "support.zip"

    receipt = create_support_bundle(output, log_root=logs, home=home)

    assert receipt.output_path == output
    assert receipt.included_log_count == 1
    assert receipt.redaction_count >= 3
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == [
            "manifest.json",
            "README.txt",
            "logs/desktop-0.log",
        ]
        manifest = json.loads(archive.read("manifest.json"))
        log = archive.read("logs/desktop-0.log").decode()
        combined = b"".join(archive.read(name) for name in archive.namelist())
    assert manifest["collection"]["config_contents_included"] is False
    assert "$HOME/confidential" in log
    assert secret not in log
    assert "abcdefghijklmnop" not in log
    assert "AIza" not in log
    assert "never-copy-me" not in combined.decode()
    assert "[REDACTED]" in log


def test_support_bundle_caps_logs_and_skips_symlinks(tmp_path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "desktop.log").write_bytes(b"x" * (MAX_LOG_BYTES + 1000))
    outside = tmp_path / "outside.log"
    outside.write_text("must not enter bundle", encoding="utf-8")
    (logs / "desktop.log.1").symlink_to(outside)
    output = tmp_path / "support.zip"

    receipt = create_support_bundle(output, log_root=logs, home=tmp_path)

    assert receipt.included_log_count == 1
    with zipfile.ZipFile(output) as archive:
        payload = archive.read("logs/desktop-0.log")
        assert b"Earlier log content omitted" in payload
        assert b"must not enter bundle" not in payload
        assert len(payload) <= MAX_LOG_BYTES + 100


def test_support_bundle_drops_partial_secret_line_at_tail_boundary(
    tmp_path,
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    secret_suffix = b"s" * MAX_LOG_BYTES
    (logs / "desktop.log").write_bytes(
        b"api_key=" + secret_suffix + b"\nvisible=complete-line\n"
    )
    output = tmp_path / "support.zip"

    create_support_bundle(output, log_root=logs, home=tmp_path)

    with zipfile.ZipFile(output) as archive:
        payload = archive.read("logs/desktop-0.log")
    assert b"Earlier log content omitted" in payload
    assert b"visible=complete-line" in payload
    assert b"s" * 32 not in payload


def test_support_bundle_single_overlong_line_never_exports_a_fragment(
    tmp_path,
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "desktop.log").write_bytes(
        b"token=" + b"private-fragment-" * MAX_LOG_BYTES
    )
    output = tmp_path / "support.zip"

    create_support_bundle(output, log_root=logs, home=tmp_path)

    with zipfile.ZipFile(output) as archive:
        payload = archive.read("logs/desktop-0.log")
    assert payload == (
        b"[Earlier log content omitted by support-bundle limit.]\n"
    )
    assert b"private-fragment" not in payload


def test_support_bundle_fails_closed_without_overwrite(tmp_path) -> None:
    output = tmp_path / "support.zip"
    output.write_bytes(b"user-owned")

    with pytest.raises(FileExistsError, match="already exists"):
        create_support_bundle(output, log_root=tmp_path)

    assert output.read_bytes() == b"user-owned"
    with pytest.raises(ValueError, match="end in .zip"):
        create_support_bundle(tmp_path / "support.txt", log_root=tmp_path)


def test_support_bundle_atomic_publish_loses_race_without_clobber(
    tmp_path, monkeypatch
) -> None:
    output = tmp_path / "support.zip"
    original_link = support_module.os.link

    def racing_link(source, destination, **kwargs):
        destination.write_bytes(b"user-won-race")
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(support_module.os, "link", racing_link)

    with pytest.raises(FileExistsError):
        create_support_bundle(output, log_root=tmp_path)

    assert output.read_bytes() == b"user-won-race"
    assert not list(tmp_path.glob(".support.zip.*.tmp"))


def test_desktop_logging_is_private_bounded_and_idempotent(
    tmp_path,
) -> None:
    import logging

    root = tmp_path / "desktop-logs"
    root_logger = logging.getLogger()
    before = list(root_logger.handlers)
    before_level = root_logger.level
    try:
        first = desktop_logging.configure_desktop_logging(root)
        second = desktop_logging.configure_desktop_logging(root)

        assert first == second == root / "desktop.log"
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE(first.stat().st_mode) == 0o600
        handlers = [
            handler
            for handler in logging.getLogger().handlers
            if getattr(handler, "_chemsmart_desktop_path", None) == first
        ]
        assert len(handlers) == 1
        assert handlers[0].maxBytes == desktop_logging.MAX_LOG_BYTES
        assert handlers[0].backupCount == desktop_logging.BACKUP_COUNT
    finally:
        root_logger = logging.getLogger()
        for handler in list(root_logger.handlers):
            if handler not in before:
                handler.close()
                root_logger.removeHandler(handler)
        root_logger.setLevel(before_level)


def test_desktop_logging_rejects_symlink_root(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="must not be a symlink"):
        desktop_logging.configure_desktop_logging(linked)

    assert os.path.islink(linked)


def test_desktop_logging_rejects_symlink_file_without_touching_target(
    tmp_path,
) -> None:
    import logging

    root = tmp_path / "logs"
    root.mkdir()
    outside = tmp_path / "outside.log"
    outside.write_text("user-owned", encoding="utf-8")
    outside.chmod(0o644)
    (root / "desktop.log").symlink_to(outside)
    root_logger = logging.getLogger()
    before = list(root_logger.handlers)
    before_level = root_logger.level
    try:
        with pytest.raises(ValueError, match="file must not be a symlink"):
            desktop_logging.configure_desktop_logging(root)
    finally:
        for handler in list(root_logger.handlers):
            if handler not in before:
                handler.close()
                root_logger.removeHandler(handler)
        root_logger.setLevel(before_level)

    assert outside.read_text(encoding="utf-8") == "user-owned"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o644


def test_desktop_diagnostics_never_blocks_launch_on_log_failure(
    monkeypatch,
) -> None:
    import chemsmart.gui.__main__ as gui_main

    installed: list[bool] = []
    monkeypatch.setattr(
        desktop_logging,
        "configure_desktop_logging",
        lambda: (_ for _ in ()).throw(PermissionError("read only")),
    )
    monkeypatch.setattr(
        desktop_logging,
        "install_exception_logging",
        lambda: installed.append(True),
    )

    gui_main._configure_desktop_diagnostics()

    assert installed == [True]
