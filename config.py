import os


class Config:
    """
    Centralized configuration for the Postermaking Bot.

    All sensitive values are loaded from environment variables so that no
    secret is committed to the repository. Every public link, worker URL,
    channel ID and external service endpoint used anywhere in the codebase
    is defined here in one place.
    """

    # ── Telegram API Credentials ────────────────────────────────────────────
    # Get from https://my.telegram.org
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")

    # Bot Token from @BotFather
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

    # MongoDB Connection String
    MONGO_URL = os.environ.get("MONGO_URL", "")

    # Bot Owner ID for administrative commands (from @userinfobot)
    BOT_OWNER = int(os.environ.get("OWNER_ID", 0))

    # ── Task Limits for different user tiers ────────────────────────────────
    TASK_LIMITS = {
        "bronze": 30,
        "silver": 40,
        "gold": 50,
        "default": 20,  # Free user daily limit
    }

    # ── Branding ────────────────────────────────────────────────────────────
    BRANDING = {
        "powered_by": "@Blaze_Updatez",
        "created_by": "@Bharath_boy",
    }
    BOT_NAME = "Poster Bot"
    WATERMARK = BRANDING["powered_by"]

    # ── Official Channels / Groups / Links ──────────────────────────────────
    UPDATE_CHANNEL_USERNAME = "Blaze_Updatez"
    UPDATE_CHANNEL_URL = "https://t.me/Blaze_Updatez"
    OWNER_CONTACT_URL = f"tg://user?id={BOT_OWNER}" if BOT_OWNER else "https://t.me/Blaze_Updatez"

    # Start / Help welcome image (hosted externally so Telegram can load it)
    START_IMG = "https://i.pinimg.com/736x/26/8f/68/268f680f5a32c8d37cad7b28455a1123.jpg"

    # ── Image Upload (ImgBB proxy) ──────────────────────────────────────────
    IMGBB_UPLOAD_URL = "https://api-integretion-unblocked.vercel.app/imgbb"

    # ── AniList ─────────────────────────────────────────────────────────────
    ANILIST_API_URL = "https://graphql.anilist.co"
    ANILIST_WORKER_URL = "https://anilist.blaze-updatez.workers.dev/"

    # ── Crunchyroll ─────────────────────────────────────────────────────────
    CRUNCHYROLL_WORKER_URL = "https://crunchyroll.blaze-updatez.workers.dev/"

    # ── TMDB (The Movie Database) ───────────────────────────────────────────
    # API settings. Use a v4 Bearer token (preferred) or a v3 read access key.
    TMDB_BEARER_TOKEN = os.environ.get(
        "TMDB_BEARER_TOKEN",
        "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJiYjFhYjI5YTA2ZGI2MTBjOGY3Y2Y1NWYyN2VmZWI5YyIsInN1YiI6IjYxMjBhNjZlYjBmMGRhMDA0M2QxNmZiZiIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ"
    )
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
    TMDB_BASE_URL = os.environ.get("TMDB_BASE_URL", "https://api.themoviedb.org/3")
    TMDB_IMAGE_BASE_URL = os.environ.get(
        "TMDB_IMAGE_BASE_URL", "https://image.tmdb.org/t/p/original"
    )
    # Movies shorter than this runtime (minutes) are ignored (excludes trailers / shorts).
    MIN_RUNTIME = 40

    # ── TMDB Flask micro-service ────────────────────────────────────────────
    TMDB_SERVICE_HOST = os.environ.get("TMDB_SERVICE_HOST", "0.0.0.0")
    TMDB_SERVICE_PORT = int(os.environ.get("TMDB_SERVICE_PORT", 5000))
    TMDB_SERVICE_DEBUG = os.environ.get("TMDB_SERVICE_DEBUG", "true").lower() == "true"

    # Public URL of the running TMDB service (used by /tmdb_worker command)
    TMDB_WORKER_URL = os.environ.get("TMDB_WORKER_URL", "http://127.0.0.1:5000")

    # ── Thumbnail Generator branding ────────────────────────────────────────
    # Default brand shown on generated magic/premiere thumbnails.
    # NOTE: every user can override this for themselves via /settings —
    # values are stored per-user in MongoDB (see utils/db.py user_settings).
    THUMBNAIL_BRAND = os.environ.get("THUMBNAIL_BRAND", BRANDING["created_by"])
    THUMBNAIL_CHANNEL = os.environ.get("THUMBNAIL_CHANNEL", UPDATE_CHANNEL_USERNAME)
    # Optional quality tags baked into thumbnails (e.g. ["1080p", "HD"])
    THUMBNAIL_QUALITY_TAGS = [t.strip() for t in
                              os.environ.get("THUMBNAIL_QUALITY_TAGS", "").split(",") if t.strip()]
    # Default magic template / premiere style to auto-use for a user.
    # None => the bot always shows the template/style picker.
    THUMBNAIL_DEFAULT_TEMPLATE = os.environ.get("THUMBNAIL_DEFAULT_TEMPLATE", "") or None
    THUMBNAIL_DEFAULT_STYLE = os.environ.get("THUMBNAIL_DEFAULT_STYLE", "") or None

    # ── Aliases so the api/ micro-service can reuse the same values ─────────
    # Kept for backwards compatibility with `api/config.py`.
    HOST = TMDB_SERVICE_HOST
    PORT = TMDB_SERVICE_PORT
    DEBUG = TMDB_SERVICE_DEBUG
