"""
TMDB Flask Micro-Service
========================
Exposes the TMDB client as an HTTP API so it can be hosted on a VPS / worker.

The heavy lifting lives in :mod:`api.tmdb_client` (shared with the bot).
This module only wraps it with Flask routes.

Run from the project root:
    python -m api.tmdb_service
"""
import json
import sys

import requests
from flask import Flask, request, make_response

# Internal imports (single source of truth for all links/IDs is root config)
from api.config import HOST, PORT, DEBUG
from api.tmdb_client import get_tmdb_media

sys.setrecursionlimit(10000)

app = Flask(__name__)


def pretty_json(data: dict, status: int = 200):
    """Return a formatted JSON response with proper headers."""
    response = make_response(json.dumps(data, indent=2, ensure_ascii=False), status)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


# ── Flask Routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return ("<h1>Movie Details API</h1>"
            "<p>Use the <code>/api/movie-posters?query=...</code> endpoint "
            "to search for a movie.</p>")


@app.route("/api/movie-posters")
def media_posters_handler():
    query = request.args.get("query")
    api_key = request.args.get("api_key")

    if not query:
        return pretty_json({"error": "Missing query parameter"}, 400)

    try:
        data = get_tmdb_media(query, api_key=api_key)
        if not data:
            return pretty_json({"error": f"Media not found for '{query}'"}, 404)
        return pretty_json(data)
    except requests.exceptions.HTTPError as e:
        return pretty_json({"error": "TMDB API error", "details": str(e)}, 502)
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return pretty_json({"error": "An internal server error occurred", "details": str(e)}, 500)


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
