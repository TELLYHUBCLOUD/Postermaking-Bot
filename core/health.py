"""
Health-check HTTP server.

A Telegram bot never opens an HTTP port by itself, so platforms like Render /
Heroku report "No open ports detected" and mark a *web* service unhealthy.
This tiny Flask server binds to ``$PORT`` (or a configured default) so the
platform detects a live service while the bot runs in the same process.
"""
import os
import threading

from core.logger import get_logger
from config import Config

logger = get_logger(__name__)


def start_health_server() -> threading.Thread:
    """Start a health server bound to 0.0.0.0:$PORT in a daemon thread."""
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
