"""
Custom exceptions shared across the codebase.
"""
from config import Config


class BotError(Exception):
    """Base class for expected, user-facing errors."""

    def user_message(self) -> str:
        return str(self)


class TMDBAuthError(BotError):
    """Raised when TMDB rejects our credentials (401/403)."""

    def user_message(self) -> str:
        return (
            "🔑 **TMDB API error.**\n"
            "The bot's TMDB token is invalid or expired. Please ask the admin "
            "to set a valid `TMDB_BEARER_TOKEN` / `TMDB_API_KEY` in the environment."
        )


class ConfigError(BotError):
    """Raised when required config is missing at startup."""
