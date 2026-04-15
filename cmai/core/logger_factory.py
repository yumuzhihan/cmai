import logging
import sys
from logging import Logger
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from cmai.config.settings import settings


class RichStreamHandler(logging.Handler):
    """
    Output log messages with rich formatting to a console,
    suitable for streaming real-time updates.
    """

    def __init__(self, console: Console) -> None:
        super().__init__()
        self.console = console

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self.console.print(message, end="", soft_wrap=True, highlight=False)
        except Exception:
            self.handleError(record)


class LoggerFactory:
    _instance: "LoggerFactory"
    _loggers: dict[str, Logger]
    _stream_loggers: dict[str, Logger]
    _log_file: Path
    _console: Console
    _stream_console: Console

    def __new__(cls, *args, **kwargs) -> "LoggerFactory":
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
            cls._loggers = {}
            cls._stream_loggers = {}
            cls._log_file = cls._resolve_log_file()
            cls._console = Console(stderr=True)
            cls._stream_console = Console(file=sys.stdout, soft_wrap=True)
        return cls._instance

    @classmethod
    def _resolve_log_file(cls) -> Path:
        configured_path = settings.LOG_FILE_PATH
        if configured_path:
            return Path(configured_path).resolve()
        return (Path.home() / ".logs" / "cmai" / "cmai.log").resolve()

    @classmethod
    def _ensure_log_file(cls) -> None:
        if cls._log_file.exists():
            return
        cls._log_file.parent.mkdir(parents=True, exist_ok=True)
        cls._log_file.touch()

    @staticmethod
    def _build_file_handler() -> logging.FileHandler:
        formatter = logging.Formatter(
            settings.LOG_FORMAT,
            datefmt=settings.LOG_DATE_FORMAT,
        )
        handler = logging.FileHandler(LoggerFactory._log_file, mode="a")
        handler.setLevel(settings.LOG_LEVEL)
        handler.setFormatter(formatter)
        return handler

    @classmethod
    def _build_rich_handler(cls) -> RichHandler:
        handler = RichHandler(
            console=cls._console,
            rich_tracebacks=True,
            markup=False,
            show_path=False,
            omit_repeated_times=False,
            log_time_format=settings.LOG_DATE_FORMAT,
        )
        handler.setLevel(settings.LOG_LEVEL)
        handler.setFormatter(logging.Formatter("%(message)s"))
        return handler

    def get_logger(self, name: str) -> Logger:
        self._ensure_log_file()

        if name not in self._loggers:
            logger = logging.getLogger(name)
            logger.setLevel(settings.LOG_LEVEL)
            logger.handlers.clear()
            logger.propagate = False

            logger.addHandler(self._build_file_handler())
            logger.addHandler(self._build_rich_handler())

            self._loggers[name] = logger

        return self._loggers[name]

    def get_stream_logger(self, name: str, level: int = logging.INFO) -> Logger:
        """
        Get a logger that outputs to the console for streaming real-time updates.
        This logger is separate from the main loggers to allow different formatting
        and log levels suitable for streaming.
        """
        if name in self._stream_loggers:
            return self._stream_loggers[name]

        logger = logging.getLogger(f"{name}.stream")
        logger.setLevel(level)
        logger.handlers.clear()
        logger.propagate = False

        stream_handler = RichStreamHandler(self._stream_console)
        stream_handler.setLevel(level)
        stream_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(stream_handler)

        self._stream_loggers[name] = logger
        return logger
