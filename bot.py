"""
Main Bot Entry Point
====================
Initializes the Pyrogram client, registers commands, starts the health server
and the background scheduler for premium account management.

Run:
    python bot.py
"""
import asyncio
import sys

from pyrogram import Client, idle
from pyrogram.types import BotCommand

from config import Config, validate_config
from core.logger import setup_logging, get_logger
from core.health import start_health_server
from core.database import db

setup_logging(verbose=bool(getattr(sys, "setrecursionlimit", None) and "--debug" in sys.argv))
logger = get_logger(__name__)

# Initialize Client
app = Client(
    "poster_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins"),
)

COMMANDS = [
    BotCommand("start", "Start the bot"),
    BotCommand("help", "See available commands"),
    BotCommand("ani", "AniList Anime Poster"),
    BotCommand("anim", "AniList Manga Poster"),
    BotCommand("crun", "Crunchyroll Anime Poster"),
    BotCommand("net", "Netflix Anime Poster"),
    BotCommand("netm", "Netflix Manga Poster"),
    BotCommand("light", "Light Simple Anime Poster"),
    BotCommand("lightm", "Light Simple Manga Poster"),
    BotCommand("dark", "Dark Simple Anime Poster"),
    BotCommand("darkm", "Dark Simple Manga Poster"),
    BotCommand("netcr", "Netflix x Crunchyroll"),
    BotCommand("mod", "Modern Poster"),
    BotCommand("modm", "Modern Manga Poster"),
    BotCommand("tmdb", "TMDB Movie / TV Poster"),
    BotCommand("movie", "TMDB Movie Poster"),
    BotCommand("tv", "TMDB TV Poster"),
    BotCommand("magic", "Magic Thumbnail (20 templates)"),
    BotCommand("premiere", "Premiere Thumbnail (12 styles)"),
    BotCommand("settings", "Your personal settings (buttons)"),
    BotCommand("my_plan", "Check Premium Status"),
    BotCommand("plans", "View Premium Plans"),
    BotCommand("broadcast", "Broadcast Message (Owner)"),
    BotCommand("add_premium", "Add Premium (Owner)"),
    BotCommand("remove_premium", "Remove Premium (Owner)"),
    BotCommand("authorize", "Authorize a group/user (Owner)"),
    BotCommand("unauthorize", "Revoke access (Owner)"),
    BotCommand("authorized", "List authorized targets (Owner)"),
]


async def check_expired_premiums(client):
    """Periodically remove expired premium plans and notify the users."""
    while True:
        try:
            expired = await db.get_and_remove_expired_users()
            for user_id in expired:
                try:
                    await asyncio.sleep(1)
                    await client.send_message(
                        user_id,
                        "😢 **Your premium plan has expired.** 😢\n\n"
                        "You have been reverted to the **Free** plan. To upgrade again, "
                        "please contact the bot owner.",
                    )
                    logger.info(f"Sent expiration notice to user {user_id}")
                except Exception as e:
                    logger.warning(f"Could not notify user {user_id}: {e}")
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Error in background premium check: {e}", exc_info=True)
            await asyncio.sleep(300)


async def main():
    try:
        # Bind a port so Render/PaaS detect a live service (bot + health port).
        start_health_server()

        await app.start()
        logger.info("Bot Started!")

        await app.set_bot_commands(COMMANDS)
        logger.info("Bot commands registered.")

        asyncio.create_task(check_expired_premiums(app))

        await idle()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await app.stop()
        logger.info("Bot Stopped.")


if __name__ == "__main__":
    # Fail fast with a clear message if required credentials are missing.
    missing = validate_config()
    if missing:
        sys.exit(
            "Cannot start: missing required config → "
            + ", ".join(missing)
            + "\nSet them via environment variables or a .env file."
        )
    app.run(main())
