"""
TMDB API Client
===============
Pure Python client for The Movie Database API.

No Flask dependency so the bot can import it safely. The Flask micro-service
(:mod:`services.tmdb_service`) re-uses :func:`get_tmdb_media` / the candidate
search to expose an HTTP endpoint.
"""
import re
import sys
import os

from datetime import datetime
from functools import lru_cache
from difflib import SequenceMatcher

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Project imports (single source of truth = root config.py)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import Config  # noqa: E402
from core.errors import TMDBAuthError  # noqa: E402

TMDB_BEARER_TOKEN = Config.TMDB_BEARER_TOKEN
TMDB_API_KEY = Config.TMDB_API_KEY
TMDB_BASE_URL = Config.TMDB_BASE_URL
TMDB_IMAGE_BASE_URL = Config.TMDB_IMAGE_BASE_URL
MIN_RUNTIME = Config.MIN_RUNTIME

sys.setrecursionlimit(10000)

# ── HTTP session with retries ────────────────────────────────────────────────
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=0.3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.mount("http://", adapter)


def tmdb_get(path: str, params: dict = None, api_key: str = None):
    """GET a TMDB endpoint, raising :class:`TMDBAuthError` on 401/403."""
    url = f"{TMDB_BASE_URL}/{path.lstrip('/')}"
    _params = params.copy() if params else {}
    _headers = None

    if api_key:
        _params["api_key"] = api_key
    elif TMDB_BEARER_TOKEN:
        _headers = {
            "Authorization": f"Bearer {TMDB_BEARER_TOKEN}",
            "Content-Type": "application/json;charset=utf-8",
        }
    elif TMDB_API_KEY:
        _params["api_key"] = TMDB_API_KEY

    resp = session.get(url, params=_params, headers=_headers)
    if resp.status_code in (401, 403):
        raise TMDBAuthError()
    resp.raise_for_status()
    return resp


def list_to_str(data_list: list, limit: int = 10, key: str = None):
    if not data_list or not isinstance(data_list, list):
        return None
    items = data_list[:limit]
    if key:
        return ", ".join(str(item.get(key, "")) for item in items if item)
    return ", ".join(str(item) for item in items if item)


@lru_cache(maxsize=128)
def extract_title_and_year(query: str):
    match = re.search(r"^(.*?)(?:\s+(\d{4}))?$", query.strip())
    if match:
        title, year_str = match.groups()
        year = int(year_str) if year_str and year_str.isdigit() else None
        return title.strip(), year
    return query.strip(), None


@lru_cache(maxsize=128)
def fetch_media_details(media_type: str, media_id: int, api_key: str = None):
    params = {"append_to_response": "credits,external_ids,alternative_titles,release_dates,images"}
    return tmdb_get(f"{media_type}/{media_id}", params=params, api_key=api_key).json()


@lru_cache(maxsize=128)
def search_media_id(query: str, api_key: str = None):
    """Find the best matching (media_type, media_id) for a query."""
    title, year = extract_title_and_year(query)
    params = {"query": title, "language": "en-US", "page": 1, "include_adult": False}
    multi_results = tmdb_get("search/multi", params=params, api_key=api_key).json().get("results", [])

    def get_ratio(s1, s2):
        if not s1 or not s2:
            return 0
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

    scored_results = []
    for r in multi_results:
        ratio = get_ratio(r.get("title") or r.get("name"), title)
        if ratio >= 0.85:
            scored_results.append((r, ratio))
    if not scored_results:
        scored_results = [(r, get_ratio(r.get("title") or r.get("name"), title)) for r in multi_results]

    today = datetime.utcnow().date()
    candidates_past, candidates_upcoming = [], []
    for r, ratio in scored_results:
        mtype = r.get("media_type")
        rd_str = r.get("release_date") or r.get("first_air_date")
        if not (rd_str and mtype in ["movie", "tv"]):
            continue
        try:
            rd_date = datetime.strptime(rd_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if year and rd_date.year != year:
            continue
        if mtype == "movie":
            try:
                details = fetch_media_details(mtype, r["id"], api_key=api_key)
                runtime = details.get("runtime")
                is_video = details.get("video", False)
                if is_video or (runtime and runtime < MIN_RUNTIME):
                    continue
            except requests.exceptions.HTTPError:
                continue
        candidate = {"type": mtype, "id": r["id"], "date": rd_date,
                     "score": r.get("popularity", 0), "ratio": ratio}
        (candidates_upcoming if rd_date > today else candidates_past).append(candidate)

    candidates_past.sort(key=lambda x: (x["ratio"], x["date"], x["score"]), reverse=True)
    candidates_upcoming.sort(key=lambda x: (x["ratio"], x["date"], x["score"]), reverse=True)
    final = candidates_past or candidates_upcoming
    if not final:
        return None, None
    top = final[0]
    return top["type"], top["id"]


def process_images(images_data):
    posters_by_lang, backdrops_by_lang = {}, {}
    for img in images_data.get("posters", []):
        lang = img.get("iso_639_1") or "no_lang"
        posters_by_lang.setdefault(lang, []).append(f"{TMDB_IMAGE_BASE_URL}{img['file_path']}")
    for img in images_data.get("backdrops", []):
        lang = img.get("iso_639_1") or "no_lang"
        backdrops_by_lang.setdefault(lang, []).append(f"{TMDB_IMAGE_BASE_URL}{img['file_path']}")
    posters_by_lang["all"] = [f"{TMDB_IMAGE_BASE_URL}{i['file_path']}" for i in images_data.get("posters", [])]
    backdrops_by_lang["all"] = [f"{TMDB_IMAGE_BASE_URL}{i['file_path']}" for i in images_data.get("backdrops", [])]
    languages = sorted(set(posters_by_lang) | set(backdrops_by_lang))
    return {"posters": posters_by_lang, "backdrops": backdrops_by_lang,
            "available_languages": languages}


def search_media_candidates(query: str, limit: int = 5, api_key: str = None) -> list:
    """Return lightweight search matches for a "pick the correct one" picker."""
    title, year = extract_title_and_year(query)
    params = {"query": title, "language": "en-US", "page": 1, "include_adult": False}
    results = tmdb_get("search/multi", params=params, api_key=api_key).json().get("results", [])

    def get_ratio(s1, s2):
        if not s1 or not s2:
            return 0
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

    scored = []
    for r in results:
        mtype = r.get("media_type")
        if mtype not in ("movie", "tv"):
            continue
        name = r.get("title") or r.get("name")
        rd = r.get("release_date") or r.get("first_air_date")
        y = rd[:4] if rd else None
        if year and y and str(year) != str(y):
            continue
        scored.append({
            "media_type": mtype,
            "media_id": r.get("id"),
            "title": name or "Unknown",
            "year": y,
            "poster_url": f"{TMDB_IMAGE_BASE_URL}{r.get('poster_path')}" if r.get("poster_path") else None,
            "backdrop_url": f"{TMDB_IMAGE_BASE_URL}{r.get('backdrop_path')}" if r.get("backdrop_path") else None,
            "overview": r.get("overview") or "",
            "score": r.get("popularity", 0),
            "ratio": get_ratio(name, title),
        })

    scored.sort(key=lambda x: (x["ratio"], x["score"]), reverse=True)
    return scored[:limit]


def _build_media_data(media_type: str, media_id: int, query: str = "", api_key: str = None) -> dict:
    details = fetch_media_details(media_type, media_id, api_key=api_key)
    crew = details.get("credits", {}).get("crew", [])
    certificates = None
    if media_type == "movie" and "release_dates" in details:
        us = [r for r in details["release_dates"]["results"] if r["iso_3166_1"] == "US"]
        if us and us[0]["release_dates"]:
            certificates = us[0]["release_dates"][0].get("certification")

    runtime_display = None
    if media_type == "movie":
        runtime = details.get("runtime")
        runtime_display = f"{runtime} min" if runtime else None
    else:
        er = list_to_str(details.get("episode_run_time", []))
        runtime_display = f"{er} min" if er else None

    images_structured = process_images(details.get("images", {}))
    images_structured["original_language"] = details.get("original_language")

    output_data = {
        "query": query, "media_type": media_type, "media_id": media_id,
        "title": details.get("title") or details.get("name"),
        "localized_title": details.get("original_title") or details.get("original_name"),
        "aka": list_to_str(details.get("alternative_titles", {}).get("titles", []), key="title"),
        "kind": media_type,
        "year": (details.get("release_date") or details.get("first_air_date", ""))[:4],
        "release_date": details.get("release_date") or details.get("first_air_date"),
        "imdb_id": details.get("external_ids", {}).get("imdb_id"),
        "tmdb_id": details.get("id"),
        "rating": details.get("vote_average"), "votes": details.get("vote_count"),
        "runtime": runtime_display, "certificates": certificates,
        "genres": list_to_str(details.get("genres", []), key="name"),
        "languages": list_to_str(details.get("spoken_languages", []), key="english_name"),
        "countries": list_to_str(details.get("production_countries", []), key="name"),
        "director": list_to_str([p for p in crew if p.get("job") == "Director"], key="name"),
        "writer": list_to_str([p for p in crew if p.get("job") in ["Screenplay", "Writer", "Story"]], key="name"),
        "producer": list_to_str([p for p in crew if p.get("job") == "Producer"], key="name"),
        "composer": list_to_str([p for p in crew if p.get("job") == "Original Music Composer"], key="name"),
        "cinematographer": list_to_str([p for p in crew if p.get("job") == "Director of Photography"], key="name"),
        "cast": list_to_str(details.get("credits", {}).get("cast", []), key="name", limit=15),
        "plot": details.get("overview"), "tagline": details.get("tagline"),
        "box_office": details.get("revenue") if details.get("revenue", 0) > 0 else "N/A",
        "distributors": list_to_str(details.get("production_companies", []), key="name"),
        "poster_url": f"{TMDB_IMAGE_BASE_URL}{details.get('poster_path')}" if details.get("poster_path") else None,
        "url": f"https://www.themoviedb.org/{media_type}/{details.get('id')}",
        "images": images_structured,
    }
    if media_type == "tv":
        output_data.update({"seasons": details.get("number_of_seasons"),
                            "episodes": details.get("number_of_episodes")})
    return output_data


def get_tmdb_media_by_id(media_type: str, media_id: int, api_key: str = None) -> dict:
    return _build_media_data(media_type, media_id, query="", api_key=api_key)


def get_tmdb_media(query: str, api_key: str = None) -> dict:
    media_type, media_id = search_media_id(query, api_key=api_key)
    if not media_id:
        return None
    return _build_media_data(media_type, media_id, query=query, api_key=api_key)
