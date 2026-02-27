"""Test Manga Cruise Template with timing metrics"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from colorama import init, Fore, Style
init()

def test_mangacruise(query: str = "solo leveling", media_type: str = "ANIME"):
    """Test Manga Cruise template with detailed timing"""
    print(f"\n{Fore.MAGENTA}═══ Manga Cruise Template Test ═══{Style.RESET_ALL}\n")
    
    timings = {}
    total_start = time.time()
    
    # Step 1: Import
    start = time.time()
    from anilist import get_anime_data
    from templates.mangacruise import create_poster
    timings["Import"] = time.time() - start
    
    # Step 2: Fetch Data
    print(f"  {Fore.BLUE}•{Style.RESET_ALL} Fetching '{query}'...")
    start = time.time()
    # Explicitly request media type
    data = get_anime_data(query, media_type=media_type) 
    timings["API Fetch"] = time.time() - start
    
    if not data:
        print(f"  {Fore.RED}✗ Failed{Style.RESET_ALL}")
        return False
    
    title = data.get('title', {}).get('english') or data.get('title', {}).get('romaji')
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Fetched: {title}")
    
    # Step 3: Generate Poster
    print(f"  {Fore.BLUE}•{Style.RESET_ALL} Generating poster...")
    start = time.time()
    poster_bio = create_poster(data)
    timings["Generate Poster"] = time.time() - start
    
    # Step 4: Save
    start = time.time()
    output = Path("output") / f"mangacruise_{media_type}_{query.replace(' ', '-')}.jpg"
    output.parent.mkdir(exist_ok=True)
    with open(output, "wb") as f:
        f.write(poster_bio.read())
    timings["Save File"] = time.time() - start
    
    total_time = time.time() - total_start
    
    # Print timing report
    print(f"\n{Fore.YELLOW}⏱  Timing Report:{Style.RESET_ALL}")
    slowest = max(timings, key=timings.get)
    for step, duration in timings.items():
        bar = "█" * int(duration / total_time * 20)
        marker = f" {Fore.RED}← SLOWEST{Style.RESET_ALL}" if step == slowest else ""
        print(f"  {step:20} {duration:6.3f}s  {Fore.CYAN}{bar}{Style.RESET_ALL}{marker}")
    
    print(f"\n  {Fore.GREEN}Total: {total_time:.3f}s{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}✓ Saved: {output}{Style.RESET_ALL}")
    return True

if __name__ == "__main__":
    # Parse -m flag
    args = sys.argv[1:]
    media_type = "ANIME"
    if "-m" in args:
        media_type = "MANGA"
        args.remove("-m")
    
    query = " ".join(args) if args else "solo leveling"
    test_mangacruise(query, media_type)

