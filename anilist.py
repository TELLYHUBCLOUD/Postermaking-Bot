"""
AniList API Client (Worker Version)
===================================
Fetches anime/manga data by delegating to the Blaze AniList Edge Worker.
"""

import requests
from config import Config

def get_anime_data(query, media_type="ANIME", id=None):
    """
    Fetch media data from the AniList Edge Worker.
    
    Args:
        query (str): The search term or ID.
        media_type (str): 'ANIME' or 'MANGA'. Defaults to 'ANIME'.
        id (int): AniList Media ID (will be used as query).
    """
    params = {
        "q": id or query,
        "type": media_type.lower()
    }
    
    try:
        response = requests.get(Config.ANILIST_WORKER_URL, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"AniList Worker Error: {e}")
        
    return None

def clean_description(desc):
    """
    Basic description cleaning. The worker also performs cleaning.
    """
    if not desc:
        return ""
    return desc.replace("<br>", "").replace("<i>", "").replace("</i>", "")
