"""Tests for agent provider YAML configuration."""

from __future__ import annotations

import pytest

from chemsmart.agent.provider_config import (
    AgentProviderConfig,
    AgentProviderConfigError,
    load_active_provider_config,
    migrate_plaintext_provider_secret,
)


def _write_agent_yaml(path, text: str):
    path.write_text(text, encoding="utf-8")
    return path


def test_load_active_provider_config_valid_yaml(tmp_path):
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: main
providers:
  main:
    type: openai
    api_key_env: OPENAI_API_KEY
    api_key: literal-key
    model: gpt-test
    base_url: https://example.test/v1
    extra_headers:
      X-Test: value
""",
    )

    config = load_active_provider_config(yaml_path)

    assert config == AgentProviderConfig(
        name="main",
        type="openai",
        api_key="literal-key",
        model="gpt-test",
        base_url="https://example.test/v1",
        extra_headers={"X-Test": "value"},
    )
    assert "literal-key" not in repr(config)


def test_load_active_provider_config_missing_yaml_returns_none(tmp_path):
    assert load_active_provider_config(tmp_path / "missing.yaml") is None


@pytest.mark.parametrize(
    "text",
    [
        "active: [broken\n",
        "providers: {}\n",
    ],
)
def test_load_active_provider_config_rejects_malformed_or_missing_active(
    tmp_path, text
):
    yaml_path = _write_agent_yaml(tmp_path / "agent.yaml", text)

    with pytest.raises(AgentProviderConfigError):
        load_active_provider_config(yaml_path)


def test_load_active_provider_config_rejects_unknown_type(tmp_path):
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: localish
providers:
  localish:
    type: localish
    api_key: key
    model: model
    base_url: ""
    extra_headers: {}
""",
    )

    with pytest.raises(AgentProviderConfigError):
        load_active_provider_config(yaml_path)


def test_load_active_provider_config_accepts_local_provider(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("HF_TOKEN", "hf-test")
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: local_chemsmart_v13_1
providers:
  local_chemsmart_v13_1:
    type: local
    model: chemsmart-qwen2.5-coder-3b-instruct-v13_1
    base_model_id: Smilesjs/chemsmart-qwen2.5-coder-3b-instruct-v13_1
    hf_token_env: HF_TOKEN
    hf_token: ""
    runtime: ""
""",
    )

    config = load_active_provider_config(yaml_path)

    assert config is not None
    assert config.type == "local"
    assert config.hf_token == "hf-test"
    assert (
        config.base_model_id
        == "Smilesjs/chemsmart-qwen2.5-coder-3b-instruct-v13_1"
    )


def test_load_active_provider_config_accepts_mlx_runtime(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("HF_TOKEN", "hf-test")
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: local_chemsmart_v13_1_mlx4
providers:
  local_chemsmart_v13_1_mlx4:
    type: local
    model: chemsmart-qwen2.5-coder-3b-instruct-v13_1-mlx-4bit
    base_model_id: Smilesjs/chemsmart-qwen2.5-coder-3b-instruct-v13_1-mlx-4bit
    hf_token_env: HF_TOKEN
    hf_token: ""
    runtime: mlx
    project: test
""",
    )

    config = load_active_provider_config(yaml_path)

    assert config is not None
    assert config.type == "local"
    assert config.runtime == "mlx"
    assert (
        config.base_model_id
        == "Smilesjs/chemsmart-qwen2.5-coder-3b-instruct-v13_1-mlx-4bit"
    )
    assert config.project == "test"


def test_load_active_provider_config_resolves_api_key_env(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: claude
providers:
  claude:
    type: anthropic
    api_key_env: ANTHROPIC_API_KEY
    api_key: ""
    model: claude-test
    base_url: ""
    extra_headers: {}
""",
    )

    config = load_active_provider_config(yaml_path)

    assert config is not None
    assert config.api_key == "env-key"
    assert config.type == "anthropic"


def test_load_active_provider_config_resolves_credential_reference(tmp_path):
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: main
providers:
  main:
    type: openai
    api_key_ref: keyring:test.service:main
    api_key: stale-legacy-value
    model: gpt-test
    base_url: https://api.openai.com/v1
    extra_headers: {}
""",
    )

    class FakeStore:
        def resolve(self, reference):
            assert reference == "keyring:test.service:main"
            return "resolved-test-value"

    config = load_active_provider_config(yaml_path, secret_store=FakeStore())

    assert config is not None
    assert config.api_key == "resolved-test-value"


def test_plaintext_secret_migration_is_atomic_private_and_resolvable(tmp_path):
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: main
providers:
  main:
    type: openai
    api_key: plaintext-test-value
    api_key_env: OPENAI_API_KEY
    model: gpt-test
    base_url: https://api.openai.com/v1
    extra_headers: {}
""",
    )

    class FakeStore:
        def __init__(self):
            self.values = {}

        def store(self, account, secret):
            self.values[account] = secret
            return f"keyring:test.service:{account}"

        def resolve(self, reference):
            return self.values[reference.rsplit(":", 1)[1]]

        def delete(self, reference):
            self.values.pop(reference.rsplit(":", 1)[1], None)

    store = FakeStore()
    receipt = migrate_plaintext_provider_secret(
        yaml_path,
        secret_store=store,
    )
    text = yaml_path.read_text(encoding="utf-8")

    assert receipt.status == "migrated"
    assert "plaintext-test-value" not in text
    assert receipt.reference in text
    assert yaml_path.stat().st_mode & 0o777 == 0o600
    config = load_active_provider_config(yaml_path, secret_store=store)
    assert config is not None
    assert config.api_key == "plaintext-test-value"


def test_secret_migration_does_not_rewrite_environment_only_config(tmp_path):
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: main
providers:
  main:
    type: openai
    api_key: ""
    api_key_env: OPENAI_API_KEY
    model: gpt-test
""",
    )
    before = yaml_path.read_bytes()

    receipt = migrate_plaintext_provider_secret(yaml_path, secret_store=object())

    assert receipt.status == "no_plaintext_secret"
    assert yaml_path.read_bytes() == before


def test_secret_migration_readback_failure_preserves_yaml_and_rolls_back(
    tmp_path,
):
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: main
providers:
  main:
    type: openai
    api_key: plaintext-test-value
    model: gpt-test
""",
    )
    before = yaml_path.read_bytes()

    class MismatchedStore:
        deleted = []

        def store(self, account, secret):
            return "keyring:test.service:main"

        def resolve(self, reference):
            return "different-value"

        def delete(self, reference):
            self.deleted.append(reference)

    store = MismatchedStore()

    with pytest.raises(AgentProviderConfigError, match="different value"):
        migrate_plaintext_provider_secret(yaml_path, secret_store=store)

    assert yaml_path.read_bytes() == before
    assert store.deleted == ["keyring:test.service:main"]


def test_load_active_provider_config_rejects_legacy_peft_adapter(tmp_path):
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: local
providers:
  local:
    type: local
    model: old-adapter
    base_model_id: Qwen/base
    adapter_repo_id: lab/adapter
""",
    )

    with pytest.raises(AgentProviderConfigError, match="merged model"):
        load_active_provider_config(yaml_path)


def test_load_active_provider_config_loads_api_env_before_yaml(
    monkeypatch, tmp_path
):
    env_path = tmp_path / "api.env"
    env_path.write_text("DEEPSEEK-api-key=deepseek-key\n", encoding="utf-8")
    yaml_path = _write_agent_yaml(
        tmp_path / "agent.yaml",
        """
active: deepseek
providers:
  deepseek:
    type: openai
    api_key_env: DEEPSEEK-api-key
    model: deepseek-v4-pro
    base_url: https://api.deepseek.com
    extra_headers: {}
""",
    )
    monkeypatch.setenv("CHEMSMART_API_ENV", str(env_path))
    monkeypatch.delenv("DEEPSEEK-api-key", raising=False)

    with pytest.warns(DeprecationWarning, match="api.env credential"):
        config = load_active_provider_config(yaml_path)

    assert config is not None
    assert config.name == "deepseek"
    assert config.api_key == "deepseek-key"
    assert config.model == "deepseek-v4-pro"
