"""
Main Bot Entry Point
====================
This module initializes the Pyrogram client, registers commands, 
and starts the background scheduler for premium account management.
"""

import logging
import os
import asyncio
import threading

from pyrogram import Client, idle
from pyrogram.types import BotCommand
from config import Config
from utils.db import db

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Initialize Client
app = Client(
    "poster_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins")
)


def _start_health_server():
    """
    Start a tiny HTTP server bound to the port Render/PaaS expects.

    A Telegram bot is a long-running process that never opens an HTTP port by
    itself, so Render reports "No open ports detected" and marks a *web*
    service unhealthy. Binding a health-check port makes Render detect a live
    service while the bot runs normally in the same process.

    Port resolution order:
      1. $PORT (set by Render / Heroku)
      2. Config.TMDB_SERVICE_PORT (default 5000)
    """
    port = int(os.environ.get("PORT", Config.TMDB_SERVICE_PORT or 5000))

    def _run():
        try:
            from flask import Flask, jsonify
            health = Flask("health")

            @health.get("/")
            def _index():
                return "Poster Bot is running 🎨"

            @health.get("/health")
            def _health():
                return jsonify({"status": "ok", "bot": Config.BOT_NAME})

            logger.info(f"Health server listening on 0.0.0.0:{port}")
            health.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
        except Exception as e:
            logger.warning(f"Health server could not start on port {port}: {e}")

    t = threading.Thread(target=_run, daemon=True, name="health-server")
    t.start()
    return t

async def check_expired_premiums(client):
    """
    Periodically checks for and removes expired premium plans, notifying users.
    Runs every hour.
    """
    while True:
        try:
            expired_user_ids = await db.get_and_remove_expired_users()
            for user_id in expired_user_ids:
                try:
                    await asyncio.sleep(1)
                    await client.send_message(
                        user_id,
                        "😢 **Your premium plan has expired.** 😢\n\n"
                        "You have been reverted to the **Free** plan. To upgrade again, please contact the bot owner."
                    )
                    logger.info(f"Sent expiration notice to user {user_id}")
                except Exception as e:
                    logger.warning(f"Could not send expiration notice to user {user_id}: {e}")
            
            await asyncio.sleep(3600)  # Check every hour
        except Exception as e:
            logger.error(f"Error in background premium check: {e}", exc_info=True)
            await asyncio.sleep(300) # Wait 5 min on error

async def main():
    """
    Starts the bot, registers commands, and initializes background tasks.
    """
    try:
        # Bind a port so Render/PaaS detect a live service (worker + health port).
        _start_health_server()

        await app.start()
        logger.info("Bot Started!")
        
        # Register Bot Commands
        commands = [
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
        await app.set_bot_commands(commands)
        logger.info("Bot commands registered.")
        
        # Start Background Scheduler
        asyncio.create_task(check_expired_premiums(app))
        
        await idle()
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await app.stop()
        logger.info("Bot Stopped.")

if __name__ == "__main__":
    asyncio.run(main())
