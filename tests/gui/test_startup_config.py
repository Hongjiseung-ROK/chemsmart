"""Desktop startup must create config templates without shell mutation."""

from __future__ import annotations

import pytest


pytest.importorskip("PySide6")


def test_non_mutating_config_creation_copies_templates_only(
    tmp_path, monkeypatch
) -> None:
    from chemsmart.cli.config import Config

    destination = tmp_path / ".chemsmart"
    config = Config()
    monkeypatch.setattr(
        Config,
        "chemsmart_dest",
        property(lambda _self: destination),
    )

    result = config.ensure_user_config_tree()

    assert result == destination
    assert (destination / "agent" / "agent.yaml.template").is_file()
    assert not (tmp_path / ".zshrc").exists()
    assert not (tmp_path / ".bashrc").exists()


def test_gui_environment_setup_uses_non_mutating_config_path(
    tmp_path, monkeypatch
) -> None:
    from chemsmart.cli.config import Config
    from chemsmart.gui.__main__ import _ensure_environment

    calls: list[str] = []
    destination = tmp_path / ".chemsmart"

    monkeypatch.setattr(
        Config,
        "chemsmart_dest",
        property(lambda _self: destination),
    )
    monkeypatch.setattr(
        Config,
        "ensure_user_config_tree",
        lambda _self: calls.append("safe"),
        raising=False,
    )

    def fail_setup(_self, *args, **kwargs) -> None:
        raise AssertionError("GUI startup must not register shell state")

    monkeypatch.setattr(Config, "setup_environment", fail_setup)

    _ensure_environment()

    assert calls == ["safe"]


def test_config_template_uses_packaged_nonhidden_fallback(
    tmp_path, monkeypatch
) -> None:
    from chemsmart.cli import config as config_module

    templates = tmp_path / "templates" / "chemsmart_defaults"
    templates.mkdir(parents=True)
    monkeypatch.setattr(
        config_module.resources,
        "files",
        lambda package: tmp_path,
    )

    assert config_module.Config().chemsmart_template == templates


def test_partial_legacy_config_tree_gains_missing_defaults_without_overwrite(
    tmp_path, monkeypatch
) -> None:
    from chemsmart.cli.config import Config

    destination = tmp_path / ".chemsmart"
    destination.mkdir()
    existing = destination / "agent" / "agent.yaml.template"
    existing.parent.mkdir()
    existing.write_text("user-owned\n", encoding="utf-8")
    config = Config()
    monkeypatch.setattr(
        Config,
        "chemsmart_dest",
        property(lambda _self: destination),
    )

    config.ensure_user_config_tree()

    assert existing.read_text(encoding="utf-8") == "user-owned\n"
    assert (destination / "server").is_dir()
    assert any((destination / "server").glob("*.yaml"))
