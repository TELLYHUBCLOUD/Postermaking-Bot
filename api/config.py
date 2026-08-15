"""
Configuration loader for the TMDB Flask micro-service (`api/tmdb_service.py`).

All values are actually owned by the root ``config.py`` module. This file just
re-exports them so that ``api/tmdb_service.py`` (which imports
``from api.config import ...``) stays clean and all links/IDs live in one place.

Run the service from the project root:
    python -m api.tmdb_service
"""
import os
import sys

# Make the project root importable when this module is loaded as `api.config`.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import Config  # noqa: E402

# Re-exported as module-level names so `from api.config import ...` works.
TMDB_BEARER_TOKEN = Config.TMDB_BEARER_TOKEN
TMDB_API_KEY = Config.TMDB_API_KEY
TMDB_BASE_URL = Config.TMDB_BASE_URL
TMDB_IMAGE_BASE_URL = Config.TMDB_IMAGE_BASE_URL
MIN_RUNTIME = Config.MIN_RUNTIME
HOST = Config.HOST
PORT = Config.PORT
DEBUG = Config.DEBUG

__all__ = [
    "TMDB_BEARER_TOKEN",
    "TMDB_API_KEY",
    "TMDB_BASE_URL",
    "TMDB_IMAGE_BASE_URL",
    "MIN_RUNTIME",
    "HOST",
    "PORT",
    "DEBUG",
]
