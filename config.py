import os

class Config:
    """
    Centralized configuration for the Postermaking Bot.
    All sensitive values are loaded from environment variables.
    """
    
    # Telegram API Credentials
    # Get from https://my.telegram.org
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    
    # Bot Token from @BotFather
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    
    # MongoDB Connection String
    MONGO_URL = os.environ.get("MONGO_URL", "")
    
    # Bot Owner ID for administrative commands
    BOT_OWNER = int(os.environ.get("OWNER_ID", 0))
    
    # Task Limits for different user tiers
    TASK_LIMITS = {
        "bronze": 30,
        "silver": 40,
        "gold": 50,
        "default": 20  # Free user daily limit
    }

    # Branding
    BRANDING = {
        "powered_by": "@Blaze_Updatez",
        "created_by": "@Bharath_boy"
    }

    # AniList Constants
    ANILIST_API_URL = "https://graphql.anilist.co"

    # Edge Worker URLs
    ANILIST_WORKER_URL = "https://anilist.blaze-updatez.workers.dev/"
    CRUNCHYROLL_WORKER_URL = "https://crunchyroll.blaze-updatez.workers.dev/"
