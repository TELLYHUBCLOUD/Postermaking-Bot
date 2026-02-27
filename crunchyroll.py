"""
Crunchyroll API Client (Worker Version)
=======================================
Fetches series metadata by delegating to the Blaze Crunchyroll Edge Worker.
"""

import requests
from config import Config

def fetch_series_data(query):
    """
    Fetch series data from the Crunchyroll Edge Worker.
    
    Args:
        query (str): Series ID or search query.
        
    Returns:
        Dictionary containing series data or None.
    """
    params = {"q": query}
    
    try:
        # Note: Worker defaults to the same logic as the previous local implementation
        response = requests.get(Config.CRUNCHYROLL_WORKER_URL, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Crunchyroll Worker Error: {e}")
        
    return None