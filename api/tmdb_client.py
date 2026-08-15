"""
Backward-compatible re-export of the TMDB client.

New code should import from :mod:`services.tmdb_client`:
    from services.tmdb_client import get_tmdb_media, search_media_candidates
"""
from services.tmdb_client import (  # noqa: F401
    tmdb_get,
    get_tmdb_media,
    get_tmdb_media_by_id,
    search_media_candidates,
    search_media_id,
    process_images,
    TMDBAuthError,
)
