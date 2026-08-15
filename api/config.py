"""
Backward-compatible config loader for the TMDB micro-service.

New code should import directly from :mod:`config`.
"""
from config import Config  # noqa: F401

# Re-exported as module-level names so `from api.config import ...` works.
HOST = Config.HOST
PORT = Config.PORT
DEBUG = Config.DEBUG
MIN_RUNTIME = Config.MIN_RUNTIME
TMDB_API_KEY = Config.TMDB_API_KEY
TMDB_BASE_URL = Config.TMDB_BASE_URL
TMDB_BEARER_TOKEN = Config.TMDB_BEARER_TOKEN
TMDB_IMAGE_BASE_URL = Config.TMDB_IMAGE_BASE_URL

__all__ = [
    "Config",
    "HOST", "PORT", "DEBUG", "MIN_RUNTIME",
    "TMDB_API_KEY", "TMDB_BASE_URL", "TMDB_BEARER_TOKEN", "TMDB_IMAGE_BASE_URL",
]
