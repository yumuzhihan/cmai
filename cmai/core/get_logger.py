import logging
import sys
from logging import Logger
from pathlib import Path

from cmai.config.settings import settings


class ColoredFormatter(logging.Formatter):
    """自定义日志格式化器，用于添加颜色"""

    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey,
        logging.INFO: green,
        logging.WARNING: yellow,
        logging.ERROR: red,
        logging.CRITICAL: bold_red,
    }

    def format(self, record):
        original_levelname = record.levelname
        if record.levelno in self.FORMATS:
            color = self.FORMATS[record.levelno]
            record.levelname = f"{color}{record.levelname}{self.reset}"

        result = super().format(record)
        record.levelname = original_levelname
        return result


class LoggerFactory:
    _instance: "LoggerFactory"
    _loggers: dict[str, Logger]
    _stream_loggers: dict[str, Logger]
    _log_file: Path

    def __new__(cls, *args, **kwargs) -> "LoggerFactory":
        if not hasattr(cls, "_instance"):
            cls._instance = super(LoggerFactory, cls).__new__(cls, *args, **kwargs)
            cls._loggers = {}
            cls._stream_loggers = {}
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

            colored_formatter = ColoredFormatter(
                settings.LOG_FORMAT, datefmt=settings.LOG_DATE_FORMAT
            )

            file_handler = logging.FileHandler(LoggerFactory._log_file, mode="a")
            file_handler.setLevel(settings.LOG_LEVEL)
            file_handler.setFormatter(formatter)

            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(settings.LOG_LEVEL)
            stream_handler.setFormatter(colored_formatter)

            logger.addHandler(file_handler)
            logger.addHandler(stream_handler)

            self._loggers[name] = logger

        return self._loggers[name]

    def get_stream_logger(self, name: str, level=logging.INFO) -> Logger:
        """获取自定义流处理器的日志记录器"""
        if name in self._stream_loggers:
            return self._stream_loggers[name]

        logger = self.get_logger(name)
        logger.setLevel(level)
        logger.handlers.clear()

        stream_handler = StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(stream_handler)
        logger.propagate = False

        self._stream_loggers[name] = logger

        return logger


class StreamHandler(logging.StreamHandler):
    """自定义流处理器，用于实时输出"""

    def emit(self, record):
        msg = self.format(record)
        stream = self.stream
        stream.write(msg)
        stream.flush()
