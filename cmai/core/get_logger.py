import logging
from logging import Logger
from pathlib import Path

from cmai.config.settings import settings


class LoggerFactory:
    _instance: "LoggerFactory"
    _loggers: dict[str, Logger]
    _log_file: Path

    def __new__(cls, *args, **kwargs) -> "LoggerFactory":
        if not hasattr(cls, "_instance"):
            cls._instance = super(LoggerFactory, cls).__new__(cls, *args, **kwargs)
            cls._loggers = {}
            if not settings.LOG_FILE_PATH:
                log_file_path = Path.home() / ".logs" / "cmai" / "cmai.log"
            elif Path.exists(Path(settings.LOG_FILE_PATH)):
                log_file_path = Path(settings.LOG_FILE_PATH)
            else:
                log_file_path = Path.home() / ".logs" / "cmai" / "cmai.log"
            cls._log_file = Path(log_file_path).resolve()
        return cls._instance

    def get_logger(self, name: str) -> Logger:
        if not self._log_file.exists():
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            self._log_file.touch()

        if name not in self._loggers:
            logger = logging.getLogger(name)
            logger.setLevel(settings.LOG_LEVEL)

            formatter = logging.Formatter(
                settings.LOG_FORMAT, datefmt=settings.LOG_DATE_FORMAT
            )

            file_handler = logging.FileHandler(LoggerFactory._log_file, mode="a")
            file_handler.setLevel(settings.LOG_LEVEL)
            file_handler.setFormatter(formatter)

            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(settings.LOG_LEVEL)
            stream_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            logger.addHandler(stream_handler)

            self._loggers[name] = logger

        return self._loggers[name]
