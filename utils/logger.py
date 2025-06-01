import logging
from pathlib import Path
from typing import Any

import colorlog

_lib_path = Path(__file__).parents[1]
_leng_path = len(_lib_path.as_posix())


def filter(record: logging.LogRecord) -> bool:
    # Define `package` attribute with the relative path.
    record.package = record.pathname[_leng_path + 1 :].replace(".py", "")
    record.emoji = (
        "🔍"
        if record.levelno == logging.DEBUG
        else "ℹ︎"
        if record.levelno == logging.INFO
        else "🚧"
        if record.levelno == logging.WARNING
        else "❌"
        if record.levelno == logging.ERROR
        else "🧨"
        if record.levelno == logging.CRITICAL
        else ""
    )
    return True


# Define the color scheme
color_scheme = {
    "DEBUG": "light_black",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red,bg_white",
}

# Define secondary log colors
secondary_colors = {
    "log_name": {"DEBUG": "blue"},
    "asctime": {"DEBUG": "cyan"},
    "process": {"DEBUG": "purple"},
    "module": {"DEBUG": "light_black,bg_blue"},
    "funcName": {"DEBUG": "light_white,bg_blue"},  # Add this line
}

# Define the log format string
fmt_string = "%(emoji)s%(log_color)s%(package)s.%(funcName)s%(reset)s %(white)s%(message)s"

# Define formatting configuration
fmt_config = {
    "log_colors": color_scheme,
    "secondary_log_colors": secondary_colors,
    "style": "%",
    "reset": True,
}


class MultilineColoredFormatter(colorlog.ColoredFormatter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.log_colors = kwargs.pop("log_colors", {})
        self.secondary_log_colors = kwargs.pop("secondary_log_colors", {})

    def format(self, record: logging.LogRecord) -> str:
        # Add default emoji if not present
        if not hasattr(record, "emoji"):
            record.emoji = "📝"

        # Add default package if not present
        if not hasattr(record, "package"):
            record.package = getattr(record, "name", "unknown")

        # Format the first line normally
        formatted_first_line = super().format(record)

        # Check if the message has multiple lines
        lines = formatted_first_line.split("\n")
        if len(lines) > 1:
            # For multiple lines, only apply colors to the first line
            # Keep subsequent lines without color formatting
            formatted_lines = [formatted_first_line]
            formatted_lines.extend(lines[1:])
            return "\n".join(formatted_lines)
        return super().format(record)


# Create a MultilineColoredFormatter object for colorized logging
formatter = MultilineColoredFormatter(fmt_string, **fmt_config)

# Create a stream handler for logging output
stream = logging.StreamHandler()
stream.setFormatter(formatter)


def get_colorful_logger(name: str = "main") -> logging.Logger:
    # Create and configure the logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(stream)
    logger.addFilter(filter)

    return logger


# Set up the root logger with the same formatting
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(stream)
root_logger.addFilter(filter)

ignore_logs = ["_trace", "httpx", "_client", "atrace", "aiohttp", "_client"]
for lgr in ignore_logs:
    loggr = logging.getLogger(lgr)
    loggr.setLevel(logging.INFO)
