"""
Font Manager - Uses local font files from the fonts directory
"""
import os
from pathlib import Path

FONT_DIR = Path(__file__).parent / "fonts"

# Store font name (normalized) to its full Path object
_LOCAL_FONTS_MAP = {}

def _initialize_fonts():
    """Initializes the _LOCAL_FONTS_MAP by scanning the FONT_DIR."""
    if not FONT_DIR.exists() or not FONT_DIR.is_dir():
        print(f"✗ Font directory not found: {FONT_DIR}")
        return

    for font_file in FONT_DIR.iterdir():
        if font_file.is_file():
            # Normalize the font name for consistent lookup: lowercase, replace spaces/underscores with hyphens
            key = font_file.stem.lower().replace(" ", "-").replace("_", "-")
            _LOCAL_FONTS_MAP[key] = font_file

_initialize_fonts() # Initialize fonts on module load

def get_font(name: str) -> str | None:
    """
    Get a local font path by its normalized name.

    Args:
        name: The name of the font to retrieve (e.g., "Open Sans Bold").
              It will be normalized for lookup.

    Returns:
        The string path to the font file if found, otherwise None.
    """
    # Normalize the input name to match the keys in _LOCAL_FONTS_MAP
    normalized_name = name.lower().replace(" ", "-").replace("_", "-")

    font_path = _LOCAL_FONTS_MAP.get(normalized_name)

    if font_path:
        if font_path.exists():
            return str(font_path)
        else:
            print(f"✗ Font file found in map but not on disk: {font_path}")
            return None
    else:
        print(f"✗ Font '{name}' (normalized to '{normalized_name}') not found.")
        return None

def get_fonts() -> dict[str, str]:
    """
    Get all available local fonts and return their paths.

    Returns:
        A dictionary where keys are normalized font names and values are their
        string paths. Only includes fonts that exist on disk.
    """
    available_fonts = {}
    for normalized_name, font_path in _LOCAL_FONTS_MAP.items():
        if font_path.exists():
            available_fonts[normalized_name] = str(font_path)
        else:
            print(f"✗ Missing font file for '{normalized_name}': {font_path}")
    return available_fonts

if __name__ == "__main__":
    # Test initialization and retrieval
    print(f"Initialized with {len(_LOCAL_FONTS_MAP)} font entries.")

    # Example of how to add dummy font files for testing:
    # (Commented out to avoid creating files if not desired)
    # FONT_DIR.mkdir(exist_ok=True)
    # (FONT_DIR / "Open Sans Regular.ttf").touch()
    # (FONT_DIR / "My_Custom_Font.otf").touch()
    # (FONT_DIR / "AnotherFont-Bold.woff2").touch()
    # _initialize_fonts() # Re-initialize if you add files dynamically

    fonts = get_fonts()
    print(f"\nAvailable fonts on disk: {list(fonts.keys())}")
