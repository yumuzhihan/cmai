"""Application settings and prompt-template compatibility helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SETTINGS_PATH = Path.home() / ".config" / "cmai" / "settings.env"

PROMPT_TEMPLATE_VARIABLES = ("{user_input}", "{diff_content}", "{language}")
LEGACY_PROMPT_TEMPLATE_VARIABLES = {
    "{{user_input}}": "{user_input}",
    "{{diff_content}}": "{diff_content}",
    "{{language}}": "{language}",
}

DEFAULT_PROMPT_TEMPLATE = (
    "You are a strict Git commit message generator. Generate exactly one commit "
    "message based on the user's intent and staged changes.\n"
    "User intent: {user_input}\n"
    "Staged changes: {diff_content}\n"
    "Output language: {language}\n"
    "You must follow the commit specification rules provided later. If there is any "
    "conflict, those rules take highest priority.\n"
    "Return only the final commit message text. Do not add explanations, code fences, "
    "prefixes, suffixes, or multiple lines.\n"
)


def decode_prompt_template(value: object) -> str:
    """Decode the one-line JSON representation used in ``settings.env``.

    Older configuration files stored a plain value, so a non-JSON string is left
    untouched.  This deliberately does not normalize old double-brace variables:
    callers can detect and migrate them with a user-visible prompt.
    """

    if not isinstance(value, str):
        return str(value)

    candidate = value.strip()
    if not candidate:
        return value

    try:
        decoded = json.loads(candidate)
    except (TypeError, ValueError):
        return value

    return decoded if isinstance(decoded, str) else value


def encode_prompt_template(value: str) -> str:
    """Return a reversible, single-line representation suitable for dotenv."""

    return json.dumps(value, ensure_ascii=False)


def normalize_prompt_template_variables(value: str) -> str:
    """Make legacy ``{{variable}}`` templates usable by the current renderer."""

    normalized = value
    for legacy, current in LEGACY_PROMPT_TEMPLATE_VARIABLES.items():
        normalized = normalized.replace(legacy, current)
    return normalized


def has_legacy_prompt_template_variables(value: str) -> bool:
    return any(variable in value for variable in LEGACY_PROMPT_TEMPLATE_VARIABLES)


def has_required_prompt_template_variables(value: str) -> bool:
    normalized = normalize_prompt_template_variables(value)
    return all(variable in normalized for variable in PROMPT_TEMPLATE_VARIABLES)


class Settings(BaseSettings):
    """Settings loaded from environment variables and the optional global dotenv."""

    model_config = SettingsConfigDict(
        env_file=str(DEFAULT_SETTINGS_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        use_enum_values=True,
        extra="ignore",
    )

    LOG_FILE_PATH: Optional[str] = None
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 5

    PROVIDER: str = "openai"
    API_BASE: str | None = None
    API_KEY: str = ""
    MODEL: str | None = None
    MAX_TOKEN: int = 8192

    OLLAMA_HOST: Optional[str] = None

    RESPONSE_LANGUAGE: str = "English"
    ENABLE_THINKING: bool = True
    THINKING_BUDGET: int = 1024  # Only For Anthropic

    COMMIT_SPEC: str = "conventional"
    COMMIT_STRICT: bool = True
    COMMIT_ALLOWED_TYPES: Optional[str] = None
    COMMIT_SCOPE_POLICY: str = "optional"
    COMMIT_SUBJECT_MAX_LEN: int = 72
    COMMIT_HEADER_MAX_LEN: int = 100
    COMMIT_SUBJECT_CASE: str = "lower"
    COMMIT_ALLOW_BANG: bool = True

    PROMPT_TEMPLATE: str = DEFAULT_PROMPT_TEMPLATE

    MAX_DIFF_LENGTH: int = 8000
    MAX_DIFF_FILE_LINES: int = 50
    MAX_DIFF_FILES_FOR_AI: int = 30
    ENABLE_SPLIT_SUGGESTION: bool = True
    SPLIT_CONFIDENCE_THRESHOLD: float = 0.75
    DIFF_SUMMARY_CONCURRENCY: int = 5
    RETRY_MAX_ATTEMPTS: int = 5
    RETRY_BASE_DELAY_SECONDS: float = 2.0
    RETRY_MAX_DELAY_SECONDS: float = 30.0

    @field_validator("PROMPT_TEMPLATE", mode="before")
    @classmethod
    def _decode_prompt_template(cls, value: object) -> str:
        return decode_prompt_template(value)

    @classmethod
    def from_env_file(cls, env_file: str | Path | None = None) -> "Settings":
        """Load settings from a path without ever creating that path."""

        path = DEFAULT_SETTINGS_PATH if env_file is None else Path(env_file)
        # Pylance synthesizes a field-only Pydantic constructor, while
        # BaseSettings also accepts this runtime-only configuration argument.
        return cls(_env_file=str(path))  # pyright: ignore[reportCallIssue]

    def load_from_env(self, env_file: str | Path | None = None) -> None:
        """Reload this shared instance while preserving references held elsewhere."""

        loaded = self.__class__.from_env_file(env_file)
        for field_name in self.__class__.model_fields:
            setattr(self, field_name, getattr(loaded, field_name))
        self.__pydantic_fields_set__ = set(loaded.model_fields_set)


# Importing this module is intentionally read-only: the parent directory and
# settings file are created only by the interactive configuration save path.
settings = Settings.from_env_file()
