"""
Centralized logging setup.

Every module should use ``get_logger(__name__)`` instead of calling
``logging.basicConfig`` itself, so logs are consistent across the codebase.
"""
import logging

_CONFIGURED = False


def setup_logging(level: int = logging.INFO, verbose: bool = False):
    """Configure root logging once. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    if verbose:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Reduce noisy third-party loggers.
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
