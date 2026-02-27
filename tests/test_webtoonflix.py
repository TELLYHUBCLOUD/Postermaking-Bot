
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from anilist import get_anime_data
from templates.webtoonflix import create_poster

def test_webtoonflix(query, media_type="ANIME"):
    print(f"\n═══ Webtoon Flix Template Test ═══\n")
    
    start_time = time.time()
    
    # Try AniList first
    print(f"  • Fetching '{query}' from AniList (Manga)...")
    try:
        # Pass media_type
        data = get_anime_data(query, media_type=media_type) 
        if not data:
             print("  ✗ Not found on AniList (Manga).")
    except Exception as e:
        print(f"  ✗ AniList Error: {e}")
        data = None

    if not data:
         # Mock data for layout verification
         print("  Using mock data for layout verification...")
         data = {
             "title": {"english": "Swordmaster's Youngest Son"},
             "genres": ["Action", "Fantasy", "Adventure"],
             "description": "Jin Runcandel was the youngest son of Runcandel, the land's most prestigious swordsman family... And the biggest failure in Runcandel history. He, who was kicked out miserably and came to a meaningless end, was given another chance. \"How do you want to use this power?\" \"I want to use it for myself.\"",
             "images": {
                 "portrait_poster": "https://s4.anilist.co/file/anilistcdn/media/manga/cover/medium/bx148066-5k3Z1k0kk3k.jpg" 
             },
             "coverImage": {
                 "extraLarge": "https://s4.anilist.co/file/anilistcdn/media/manga/cover/extraLarge/bx148066-1d1d1d.jpg" 
             }
         }
         # Mock Image URL (AOT for testing image load)
         data["images"]["portrait_poster"] = "https://imgsrv.crunchyroll.com/cdn-cgi/image/fit=contain,format=auto,quality=85,width=600,height=900/catalog/crunchyroll/323c82257b2f6567fabbb7bd55bfa753.jpg"

    print(f"  ✓ Data ready: {data.get('title')}")
    print("  • Generating poster...")
    
    poster = create_poster(data)
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"webtoonflix_{media_type}_{query.replace(' ', '-')}.jpg"
    with open(output_path, "wb") as f:
        f.write(poster.getbuffer())
        
    end_time = time.time()
    print(f"\n  ✓ Saved: {output_path}")
    print(f"  ⏱ Total Time: {end_time - start_time:.3f}s")

if __name__ == "__main__":
    args = sys.argv[1:]
    media_type = "ANIME"
    if "-m" in args:
        media_type = "MANGA"
        args.remove("-m")
        
    query = " ".join(args) if args else "Swordmaster's Youngest Son"
    test_webtoonflix(query, media_type)