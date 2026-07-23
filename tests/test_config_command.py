import os
import stat
from pathlib import Path

import pytest
from click.testing import CliRunner

import cmai.cli.commands.config as config_module
from cmai.config.settings import Settings, settings


class FakeProviderFactory:
    def __init__(self, providers: dict[str, str]):
        self.providers = providers

    def list_providers(self) -> dict[str, str]:
        return self.providers


@pytest.fixture(autouse=True)
def restore_shared_settings():
    snapshot = settings.model_copy(deep=True)
    yield
    for field_name in settings.__class__.model_fields:
        setattr(settings, field_name, getattr(snapshot, field_name))


@pytest.fixture
def config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / ".config" / "cmai" / "settings.env"
    monkeypatch.setattr(config_module, "DEFAULT_SETTINGS_PATH", path)
    return path


@pytest.fixture
def providers(monkeypatch: pytest.MonkeyPatch):
    available = {"openai": "OpenAIProvider", "ollama": "OllamaProvider"}
    monkeypatch.setattr(
        config_module,
        "ProviderFactory",
        lambda: FakeProviderFactory(available),
    )
    return available


def _complete_wizard_input(*, api_key: str = "test-secret", save: str = "y") -> str:
    return "\n".join(
        [
            "openai",  # Provider
            "",  # API base
            api_key,  # API key
            "",  # Model default
            "",  # Strict default
            "",  # Commit spec default
            "",  # Commit rules default
            "",  # Language default
            "",  # Template keep
            save,
            "",
        ]
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_first_run_waits_for_confirmation_before_creating_file(
    config_path: Path, providers
):
    result = CliRunner().invoke(
        config_module.config_command,
        input=_complete_wizard_input(save="n"),
    )

    assert result.exit_code == 0
    assert "Nothing is written until you confirm" in result.output
    assert "Configuration cancelled" in result.output
    assert not config_path.exists()
    assert not config_path.parent.exists()


def test_first_run_saves_secure_configuration_and_reloads_settings(
    config_path: Path, providers
):
    secret = "super-secret-api-key"
    result = CliRunner().invoke(
        config_module.config_command,
        input=_complete_wizard_input(api_key=secret),
    )

    assert result.exit_code == 0
    assert config_path.exists()
    assert secret not in result.output
    assert "updated (hidden)" in result.output
    assert "The new settings will be used" in result.output
    assert settings.API_KEY == secret
    assert settings.MODEL == "qwen-turbo-latest"
    if os.name != "nt":
        assert stat.S_IMODE(config_path.stat().st_mode) == 0o600


def test_existing_provider_edit_preserves_other_content_and_hides_key(
    config_path: Path, providers
):
    secret = "existing-secret"
    _write(
        config_path,
        "# hand-written comment\n"
        "UNMANAGED_SETTING=keep-me\n"
        "PROVIDER=openai\n"
        "API_BASE=https://old.example/v1\n"
        f"API_KEY={secret}\n"
        "MODEL=old-model\n"
        "COMMIT_STRICT=false\n"
        "# keep this blank line too\n\n",
    )

    result = CliRunner().invoke(
        config_module.config_command,
        input="2\nollama\nhttp://localhost:22444\n\nqwen3:8b\ny\n",
    )

    assert result.exit_code == 0
    assert secret not in result.output
    content = config_path.read_text(encoding="utf-8")
    assert "# hand-written comment\n" in content
    assert "UNMANAGED_SETTING=keep-me\n" in content
    assert "COMMIT_STRICT=false\n" in content
    assert f"API_KEY={secret}\n" in content
    assert "PROVIDER=ollama\n" in content
    assert "API_BASE=http://localhost:22444\n" in content
    assert "OLLAMA_HOST=http://localhost:22444\n" in content


def test_commit_detail_configuration_and_blank_allowed_types_fallback(
    config_path: Path, providers
):
    _write(
        config_path,
        "PROVIDER=openai\n" "COMMIT_ALLOWED_TYPES=feat,fix\n" "COMMIT_STRICT=true\n",
    )
    detailed_input = "\n".join(
        [
            "3",
            "n",
            "angular",
            "detailed",
            "",  # Blank deletes the type override.
            "required",
            "80",
            "90",
            "sentence",
            "n",
            "y",
            "",
        ]
    )

    result = CliRunner().invoke(config_module.config_command, input=detailed_input)

    assert result.exit_code == 0
    configured = Settings.from_env_file(config_path)
    assert configured.COMMIT_STRICT is False
    assert configured.COMMIT_SPEC == "angular"
    assert configured.COMMIT_ALLOWED_TYPES is None
    assert configured.COMMIT_SCOPE_POLICY == "required"
    assert configured.COMMIT_SUBJECT_MAX_LEN == 80
    assert configured.COMMIT_HEADER_MAX_LEN == 90
    assert configured.COMMIT_SUBJECT_CASE == "sentence"
    assert configured.COMMIT_ALLOW_BANG is False
    assert "Allowed types: build, chore, ci" in result.output


def test_optional_template_migrates_legacy_variables_and_round_trips_newlines(
    config_path: Path, providers, monkeypatch: pytest.MonkeyPatch
):
    legacy = "Intent: {{user_input}}; Diff: {{diff_content}}; Language: {{language}}"
    _write(
        config_path,
        "PROVIDER=openai\n" f"PROMPT_TEMPLATE={legacy}\n" "RESPONSE_LANGUAGE=English\n",
    )
    edited = "Intent: {user_input}\nDiff: {diff_content}\nLanguage: {language}\n"
    monkeypatch.setattr(config_module.click, "edit", lambda *_args, **_kwargs: edited)

    result = CliRunner().invoke(
        config_module.config_command,
        input="4\nChinese\nedit\ny\ny\n",
    )

    assert result.exit_code == 0
    content = config_path.read_text(encoding="utf-8")
    template_line = next(
        line for line in content.splitlines() if line.startswith("PROMPT_TEMPLATE=")
    )
    assert "\\n" in template_line
    assert "{{user_input}}" not in template_line
    configured = Settings.from_env_file(config_path)
    assert configured.RESPONSE_LANGUAGE == "Chinese"
    assert configured.PROMPT_TEMPLATE == edited


def test_template_editor_cancel_does_not_modify_file(
    config_path: Path, providers, monkeypatch: pytest.MonkeyPatch
):
    original = (
        "PROVIDER=openai\n"
        "PROMPT_TEMPLATE=Intent:{user_input}:{diff_content}:{language}\n"
        "RESPONSE_LANGUAGE=English\n"
    )
    _write(config_path, original)
    monkeypatch.setattr(config_module.click, "edit", lambda *_args, **_kwargs: None)

    result = CliRunner().invoke(
        config_module.config_command,
        input="4\nEnglish\nedit\ny\n",
    )

    assert result.exit_code == 0
    assert "Template was not changed" in result.output
    assert "No settings changed" in result.output
    assert config_path.read_text(encoding="utf-8") == original


def test_malformed_existing_file_is_not_overwritten(config_path: Path, providers):
    original = "this is not dotenv\n"
    _write(config_path, original)

    result = CliRunner().invoke(config_module.config_command)

    assert result.exit_code != 0
    assert "Malformed dotenv entry" in result.output
    assert config_path.read_text(encoding="utf-8") == original


def test_no_registered_provider_exits_without_creating_configuration(
    config_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        config_module, "ProviderFactory", lambda: FakeProviderFactory({})
    )

    result = CliRunner().invoke(config_module.config_command)

    assert result.exit_code != 0
    assert "No AI providers are available" in result.output
    assert not config_path.exists()


def test_provider_choices_come_from_factory(
    config_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        config_module,
        "ProviderFactory",
        lambda: FakeProviderFactory(
            {"zeta": "OpenAIProvider", "acme": "OpenAIProvider"}
        ),
    )

    result = CliRunner().invoke(
        config_module.config_command,
        input="acme\n\n\n\n\n\n\n\n\nn\n",
    )

    assert result.exit_code == 0
    assert "Provider (acme, zeta)" in result.output
    assert not config_path.exists()


def test_interrupt_does_not_create_configuration(
    config_path: Path, providers, monkeypatch
):
    monkeypatch.setattr(
        config_module,
        "_edit_provider",
        lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    result = CliRunner().invoke(config_module.config_command)

    assert result.exit_code != 0
    assert "Configuration cancelled" in result.output
    assert not config_path.exists()


def test_settings_load_missing_file_without_creating_it(tmp_path: Path):
    path = tmp_path / "not-created" / "settings.env"

    configured = Settings.from_env_file(path)

    assert configured.PROVIDER
    assert not path.exists()
    assert not path.parent.exists()


def test_ollama_uses_api_base_when_legacy_host_is_absent(
    monkeypatch: pytest.MonkeyPatch,
):
    from cmai.providers import ollama_provider

    captured: dict[str, str] = {}

    class FakeAsyncClient:
        def __init__(self, *, host: str):
            captured["host"] = host

    class FakeLoggerFactory:
        def get_logger(self, _name):
            return object()

        def get_stream_logger(self, _name):
            return object()

    monkeypatch.setattr(ollama_provider, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(ollama_provider, "LoggerFactory", lambda: FakeLoggerFactory())
    monkeypatch.setattr(ollama_provider.settings, "OLLAMA_HOST", None)
    monkeypatch.setattr(
        ollama_provider.settings, "API_BASE", "http://ollama.example:11434"
    )

    ollama_provider.OllamaProvider(model="test-model")

    assert captured["host"] == "http://ollama.example:11434"

    monkeypatch.setattr(
        ollama_provider.settings, "OLLAMA_HOST", "http://legacy.example:11434"
    )
    ollama_provider.OllamaProvider(model="test-model")

    assert captured["host"] == "http://legacy.example:11434"
