"""Centralized logging configuration for Paste Beans."""

import logging
import sys
from typing import Optional


def setup_logging(name: Optional[str] = None) -> logging.Logger:
    """Configure and return a logger instance.

    Args:
        name: Logger name (typically __name__ of calling module)

    Returns:
        Configured logger instance
    """
    # Import settings here to avoid circular imports
    from config import settings

    logger = logging.getLogger(name or 'paste_beans')

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # Set log level based on debug setting
    log_level = logging.DEBUG if settings.debug else logging.INFO
    logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Formatter
    if settings.debug:
        # Verbose format with file/line info in debug mode
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - '
            '[%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        # Simpler format for production
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Set log levels for third-party libraries
    if not settings.debug:
        # Reduce noise from third-party libraries in production
        logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
        logging.getLogger('chromadb').setLevel(logging.WARNING)
        logging.getLogger('openai').setLevel(logging.WARNING)

    return logger


# Global logger instance for application-level logging
app_logger = setup_logging('paste_beans')


def log_exception(logger: logging.Logger, e: Exception, context: str = ""):
    """Log exception with appropriate level of detail.

    Args:
        logger: Logger instance to use
        e: Exception to log
        context: Additional context about where the error occurred
    """
    from config import settings

    if settings.debug:
        # Full stack trace in debug mode
        logger.exception(f"{context}: {str(e)}" if context else str(e))
    else:
        # Just the error message in production
        logger.error(f"{context}: {str(e)}" if context else str(e))
