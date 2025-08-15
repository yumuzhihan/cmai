from typing import Optional
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
    API_BASE: str = "https://api.openai.com/v1"
    API_KEY: str = ""
    MODEL: str | None = None

    OLLAMA_HOST: Optional[str] = None

    RESPONSE_LANGUAGE: str = "English"

    PROMPT_TEMPLATE: str = (
        "请你根据用户的描述{{user_input}}，生成一个规范化的commit信息。请确保信息简洁明了，符合常规的commit规范。\n"
        + "修改的信息包括：{{diff_content}}。你的回复应该只包含规范化的commit信息，不需要其他内容。\n"
        + "请用{{language}}回答，不要包含任何其他语言或注释。\n"
    )

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

    def _load_env_file(self):
        env_file = Path(self.Config.env_file)
        if env_file.exists():
            with env_file.open(encoding=self.Config.env_file_encoding) as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        key, value = line.strip().split("=", 1)
                        setattr(self, key.strip(), value.strip())


settings = Settings()
