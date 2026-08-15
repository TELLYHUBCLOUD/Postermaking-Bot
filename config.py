"""
Centralized configuration for the Postermaking Bot.

- Loads values from environment variables (and an optional ``.env`` file).
- Provides startup validation so a missing credential fails fast with a
  clear message instead of a confusing runtime error mid-way.

Every link, ID, worker URL and service endpoint used anywhere in the codebase
is defined here in ONE place.
"""
import os
from pathlib import Path

# Load a local .env file if present (keep env-var override priority).
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass


def _env(name, default=""):
    return os.environ.get(name, default)


class Config:
    """All bot settings. Access as ``Config.NAME``."""

    # ── Telegram API Credentials (https://my.telegram.org) ────────────────
    API_ID = int(_env("API_ID", 0))
    API_HASH = _env("API_HASH", "")
    BOT_TOKEN = _env("BOT_TOKEN", "")

    # ── MongoDB ───────────────────────────────────────────────────────────
    MONGO_URL = _env("MONGO_URL", "")

    # ── Bot Owner ID (from @userinfobot) ──────────────────────────────────
    BOT_OWNER = int(_env("OWNER_ID", 0))

    # ── Task limits per tier ──────────────────────────────────────────────
    TASK_LIMITS = {
        "bronze": int(_env("LIMIT_BRONZE", 30)),
        "silver": int(_env("LIMIT_SILVER", 40)),
        "gold": int(_env("LIMIT_GOLD", 50)),
        "default": int(_env("LIMIT_DEFAULT", 20)),
    }

    # ── Branding ──────────────────────────────────────────────────────────
    BRANDING = {
        "powered_by": _env("POWERED_BY", "@Blaze_Updatez"),
        "created_by": _env("CREATED_BY", "@Bharath_boy"),
    }
    BOT_NAME = _env("BOT_NAME", "Poster Bot")
    WATERMARK = BRANDING["powered_by"]

    # ── Channels / links ──────────────────────────────────────────────────
    UPDATE_CHANNEL_USERNAME = _env("UPDATE_CHANNEL", "Blaze_Updatez")
    UPDATE_CHANNEL_URL = _env("UPDATE_CHANNEL_URL", f"https://t.me/{UPDATE_CHANNEL_USERNAME}")
    OWNER_CONTACT_URL = (
        f"tg://user?id={BOT_OWNER}" if BOT_OWNER else _env("OWNER_CONTACT_URL", UPDATE_CHANNEL_URL)
    )

    # Start / Help welcome image
    START_IMG = _env(
        "START_IMG",
        "https://i.pinimg.com/736x/26/8f/68/268f680f5a32c8d37cad7b28455a1123.jpg",
    )

    # ── Image upload (ImgBB proxy) ────────────────────────────────────────
    IMGBB_UPLOAD_URL = _env("IMGBB_UPLOAD_URL", "https://api-integretion-unblocked.vercel.app/imgbb")

    # ── AniList ───────────────────────────────────────────────────────────
    ANILIST_API_URL = _env("ANILIST_API_URL", "https://graphql.anilist.co")
    ANILIST_WORKER_URL = _env("ANILIST_WORKER_URL", "https://anilist.blaze-updatez.workers.dev/")

    # ── Crunchyroll ───────────────────────────────────────────────────────
    CRUNCHYROLL_WORKER_URL = _env("CRUNCHYROLL_WORKER_URL", "https://crunchyroll.blaze-updatez.workers.dev/")

    # ── TMDB (The Movie Database) ─────────────────────────────────────────
    # Use a v4 Bearer token (preferred) OR a v3 read access key.
    TMDB_BEARER_TOKEN = _env("TMDB_BEARER_TOKEN", "")
    TMDB_API_KEY = _env("TMDB_API_KEY", "")
    TMDB_BASE_URL = _env("TMDB_BASE_URL", "https://api.themoviedb.org/3")
    TMDB_IMAGE_BASE_URL = _env("TMDB_IMAGE_BASE_URL", "https://image.tmdb.org/t/p/original")
    # Movies shorter than this runtime (minutes) are ignored (skips trailers/shorts).
    MIN_RUNTIME = int(_env("MIN_RUNTIME", 40))

    # ── TMDB Flask micro-service ──────────────────────────────────────────
    TMDB_SERVICE_HOST = _env("TMDB_SERVICE_HOST", "0.0.0.0")
    TMDB_SERVICE_PORT = int(_env("TMDB_SERVICE_PORT", 5000))
    TMDB_SERVICE_DEBUG = _env("TMDB_SERVICE_DEBUG", "true").lower() == "true"
    TMDB_WORKER_URL = _env("TMDB_WORKER_URL", "http://127.0.0.1:5000")

    # ── Thumbnail generator branding ──────────────────────────────────────
    THUMBNAIL_BRAND = _env("THUMBNAIL_BRAND", BRANDING["created_by"])
    THUMBNAIL_CHANNEL = _env("THUMBNAIL_CHANNEL", UPDATE_CHANNEL_USERNAME)
    THUMBNAIL_QUALITY_TAGS = [
        t.strip() for t in _env("THUMBNAIL_QUALITY_TAGS", "").split(",") if t.strip()
    ]
    THUMBNAIL_DEFAULT_TEMPLATE = _env("THUMBNAIL_DEFAULT_TEMPLATE", "") or None
    THUMBNAIL_DEFAULT_STYLE = _env("THUMBNAIL_DEFAULT_STYLE", "") or None

    # ── Aliases (kept for backward compatibility with api/ micro-service) ─
    HOST = TMDB_SERVICE_HOST
    PORT = TMDB_SERVICE_PORT
    DEBUG = TMDB_SERVICE_DEBUG


# ── Startup validation ────────────────────────────────────────────────────────
REQUIRED = {
    "API_ID": lambda: Config.API_ID,
    "API_HASH": lambda: Config.API_HASH,
    "BOT_TOKEN": lambda: Config.BOT_TOKEN,
    "MONGO_URL": lambda: Config.MONGO_URL,
    "OWNER_ID": lambda: Config.BOT_OWNER,
}


def validate_config(verbose: bool = True) -> list:
    """Check that every required credential is set.

    Returns a list of missing config names (empty => all good).
    Raises nothing; the caller decides how to handle missing values.
    """
    missing = []
    for name, getter in REQUIRED.items():
        if not getter():
            missing.append(name)
    if verbose and missing:
        print(
            "\n⚠️  Missing required config values: "
            + ", ".join(missing)
            + "\n   Set them via environment variables or a .env file, then restart.\n"
        )
    return missing
