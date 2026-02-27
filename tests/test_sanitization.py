
import sys
import os

# Add parent dir to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anilist import get_anime_data
from poster import sanitize_description
import re

def test_sanitization(anime_list):
    print(f"{'='*60}")
    print(f"TESTING DESCRIPTION SANITIZATION")
    print(f"{'='*60}\n")

    for anime_name in anime_list:
        print(f"Fetching: {anime_name}...")
        data = get_anime_data(anime_name)
        
        if not data:
            print(f"❌ Could not verify '{anime_name}'\n")
            continue
            
        # Get Main Character Description
        desc = ""
        char_edges = data.get('characters', {}).get('edges', [])
        char_name = "Unknown"
        
        if char_edges:
            char_node = char_edges[0].get('node', {})
            char_name = char_node.get('name', {}).get('full', 'Unknown')
            desc = char_node.get('description', '')

        if not desc:
            print(f"⚠️ No description found for {char_name} ({anime_name})\n")
            continue
            
        print(f"--- {char_name} ({anime_name}) ---")
        
        # 1. Show First 300 chars of RAW (to see metadata)
        print(f"[RAW START]:\n{desc[:300].replace(chr(10), ' ')}...\n")
        
        # 2. Clean
        cleaned = sanitize_description(desc)
        
        # 3. Show Cleaned
        print(f"[CLEANED]:\n{cleaned[:300]}...\n")
        
        # Check for colon-based metadata that might have leaked
        lines = cleaned.split('\n')
        leaked_metadata = [line for line in lines[:3] if ':' in line and len(line) < 50]
        if leaked_metadata:
             print(f"⚠️ POTENTIAL LEAK: {leaked_metadata}")
             
        print(f"{'-'*60}\n")

if __name__ == "__main__":
    test_anime = [
        "One Piece",       # Complex metadata (Devil Fruit, Bounty)
        "Naruto",          # Rank, Age, etc.
        "Bleach",          # Zanpakuto, etc.
        "Attack on Titan", # Status, Rank
        "Solo Leveling",   # Class, Guild
        "Kimetsu no Yaiba",    # Breathing Style
        "Dragon Ball",     # Race
    ]
    test_sanitization(test_anime)
