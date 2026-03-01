from typing import Any, Optional, get_args, get_origin
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Settings class for application configuration.
    """

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

    PROMPT_TEMPLATE: str = (
        "You are a strict Git commit message generator. Generate exactly one commit message based on the user's intent and staged changes.\n"
        + "User intent: {{user_input}}\n"
        + "Staged changes: {{diff_content}}\n"
        + "Output language: {{language}}\n"
        + "You must follow the commit specification rules provided later. If there is any conflict, those rules take highest priority.\n"
        + "Return only the final commit message text. Do not add explanations, code fences, prefixes, suffixes, or multiple lines.\n"
    )

    MAX_DIFF_LENGTH: int = 8000
    MAX_DIFF_FILE_LINES: int = 50
    MAX_DIFF_FILES_FOR_AI: int = 30
    ENABLE_SPLIT_SUGGESTION: bool = True
    SPLIT_CONFIDENCE_THRESHOLD: float = 0.75
    DIFF_SUMMARY_CONCURRENCY: int = 5
    RETRY_MAX_ATTEMPTS: int = 5
    RETRY_BASE_DELAY_SECONDS: float = 2.0
    RETRY_MAX_DELAY_SECONDS: float = 30.0

    class Config:
        """
        Configuration for Pydantic settings.
        """

        env_file = str(Path.home() / ".config" / "cmai" / "settings.env")
        if not Path(env_file).exists():
            Path(env_file).parent.mkdir(parents=True, exist_ok=True)
            Path(env_file).touch()
        env_file_encoding = "utf-8"
        case_sensitive = False
        use_enum_values = True
        extra = "ignore"

    def load_from_env(self, env_file: Optional[str] = None):
        if env_file:
            self.Config.env_file = env_file
        self._load_env_file()

    def _parse_value(self, key: str, raw_value: str) -> Any:
        field = self.__class__.model_fields.get(key)
        if field is None:
            return raw_value

        annotation = field.annotation
        origin = get_origin(annotation)
        args = get_args(annotation)

        target_type = annotation
        if origin is not None and type(None) in args:
            non_none_types = [arg for arg in args if arg is not type(None)]
            if len(non_none_types) == 1:
                target_type = non_none_types[0]

        if target_type is bool:
            return raw_value.lower() in {"1", "true", "yes", "on"}
        if target_type is int:
            return int(raw_value)
        if target_type is float:
            return float(raw_value)

        return raw_value

    def _load_env_file(self):
        env_file = Path(self.Config.env_file)
        if env_file.exists():
            with env_file.open(encoding=self.Config.env_file_encoding) as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        key, value = line.strip().split("=", 1)
                        parsed = self._parse_value(key.strip(), value.strip())
                        setattr(self, key.strip(), parsed)


settings = Settings()
