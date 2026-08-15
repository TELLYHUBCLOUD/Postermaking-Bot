"""
Backward-compatible re-export of the TMDB Flask micro-service.

New code should import from :mod:`services.tmdb_service`.
Run with: python -m services.tmdb_service
"""
from services.tmdb_service import app  # noqa: F401

if __name__ == "__main__":
    from config import Config
    app.run(host=Config.TMDB_SERVICE_HOST, port=Config.TMDB_SERVICE_PORT,
            debug=Config.TMDB_SERVICE_DEBUG)
