"""Test Crunchyroll Template with timing metrics"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from colorama import init, Fore, Style
init()

def test_crunchyroll_poster(query: str = "Spy x Family"):
    """Test Crunchyroll template with detailed timing"""
    print(f"\n{Fore.CYAN}═══ Crunchyroll Template Test ═══{Style.RESET_ALL}\n")
    
    timings = {}
    total_start = time.time()
    
    # Step 1: Import
    start = time.time()
    from crunchyroll import fetch_series_data, login_anonymously
    from templates.crunchyroll_poster import generate_poster
    from curl_cffi import requests as cffi_requests
    timings["Import"] = time.time() - start
    
    # Step 2: Login
    print(f"  {Fore.BLUE}•{Style.RESET_ALL} Logging in...")
    start = time.time()
    session = cffi_requests.Session(impersonate="chrome")
    session.headers.update({"User-Agent": "Crunchyroll/ANDROIDTV/3.50.0"})
    token = login_anonymously(session)
    timings["Login (cached)"] = time.time() - start
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Token ready")
    
    # Step 3: Fetch Data
    print(f"  {Fore.BLUE}•{Style.RESET_ALL} Fetching '{query}'...")
    start = time.time()
    anime_data = fetch_series_data(session, token, query)
    timings["API Fetch"] = time.time() - start
    
    if "error" in anime_data:
        print(f"  {Fore.RED}✗ {anime_data['error']}{Style.RESET_ALL}")
        session.close()
        return False
    
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Fetched: {anime_data.get('title')}")
    
    # Step 4: Generate Poster
    print(f"  {Fore.BLUE}•{Style.RESET_ALL} Generating poster...")
    start = time.time()
    slug = anime_data.get("slug", query.lower().replace(" ", "-"))
    output_path = Path(__file__).parent.parent / "output" / f"crunchyroll_{slug}.jpg"
    poster = generate_poster(anime_data)
    poster = poster.convert("RGB")
    poster.save(output_path, "JPEG", quality=85)
    print(f"Poster saved to: {output_path}")
    timings["Generate Poster"] = time.time() - start
    
    session.close()
    total_time = time.time() - total_start
    
    # Print timing report
    print(f"\n{Fore.YELLOW}⏱  Timing Report:{Style.RESET_ALL}")
    slowest = max(timings, key=timings.get)
    for step, duration in timings.items():
        bar = "█" * int(duration / total_time * 20)
        marker = f" {Fore.RED}← SLOWEST{Style.RESET_ALL}" if step == slowest else ""
        print(f"  {step:20} {duration:6.3f}s  {Fore.CYAN}{bar}{Style.RESET_ALL}{marker}")
    
    print(f"\n  {Fore.GREEN}Total: {total_time:.3f}s{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}✓ Dimensions: {poster.size[0]}x{poster.size[1]}{Style.RESET_ALL}")
    return True

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Spy x Family"
    test_crunchyroll_poster(query)
