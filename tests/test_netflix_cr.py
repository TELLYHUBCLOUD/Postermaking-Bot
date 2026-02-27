"""Test Netflix Template with Crunchyroll data"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from colorama import init, Fore, Style
init()

def test_netflix_crunchyroll(query: str = "attack on titan"):
    """Test Netflix template with Crunchyroll API data"""
    print(f"\n{Fore.RED}═══ Netflix + Crunchyroll Test ═══{Style.RESET_ALL}\n")
    
    timings = {}
    total_start = time.time()
    
    # Step 1: Import
    start = time.time()
    from crunchyroll import fetch_series_data, login_anonymously
    from curl_cffi import requests as cffi_requests
    from templates.netflix import create_poster
    timings["Import"] = time.time() - start
    
    # Step 2: Login
    print(f"  {Fore.BLUE}•{Style.RESET_ALL} Logging in...")
    start = time.time()
    session = cffi_requests.Session(impersonate="chrome")
    token = login_anonymously(session)
    timings["Login"] = time.time() - start
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Token ready")
    
    # Step 3: Fetch Data
    print(f"  {Fore.BLUE}•{Style.RESET_ALL} Fetching '{query}'...")
    start = time.time()
    data = fetch_series_data(session, token, query)
    timings["API Fetch"] = time.time() - start
    
    if not data or 'error' in data:
        print(f"  {Fore.RED}✗ Failed: {data.get('error', 'Unknown')}{Style.RESET_ALL}")
        return False
    
    title = data.get('title', 'Unknown')
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Fetched: {title}")
    
    # Debug: show available images
    images = data.get('images', {})
    bg_url = images.get('landscape_poster') or images.get('banner_backdrop') or images.get('portrait_poster')
    if bg_url:
        print(f"  {Fore.CYAN}  Background: {bg_url[:70]}...{Style.RESET_ALL}")
    else:
        print(f"  {Fore.YELLOW}  Available images: {', '.join(images.keys()) if images else 'None'}{Style.RESET_ALL}")
    
    # Step 4: Generate Poster
    print(f"  {Fore.BLUE}•{Style.RESET_ALL} Generating poster...")
    start = time.time()
    poster_bio = create_poster(data)
    timings["Generate Poster"] = time.time() - start
    
    # Step 5: Save
    start = time.time()
    slug = query.lower().replace(" ", "-")
    output = Path("output") / f"netflix_cr_{slug}.jpg"
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
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "attack on titan"
    test_netflix_crunchyroll(query)
