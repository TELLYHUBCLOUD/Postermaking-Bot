import os
import io
from core.logger import get_logger
from templates.anilist_poster import create_poster as anilist_poster
from templates.crunchyroll_poster import generate_poster as crunchyroll_poster
from templates.lightsimple import create_poster as lightsimple_poster
from templates.netflix import create_poster as netflix_poster
from templates.darksimple import create_poster as darksimple_poster
from templates.modern import create_poster as modern_poster
from templates.tmdb_poster import create_poster as tmdb_poster

from anilist import get_anime_data
from services.tmdb_client import get_tmdb_media
from crunchyroll import fetch_series_data
from PIL import ImageDraw, ImageFont, Image

from config import Config

WATERMARK = Config.WATERMARK
logger = get_logger(__name__)


def add_watermark(image, text=None):
    if text is None:
        text = WATERMARK
    try:
        # Create a drawing context
        draw = ImageDraw.Draw(image)
        
        # Calculate font size (e.g., 2% of image height)
        font_size = int(image.height * 0.02)
        if font_size < 12: font_size = 12
        
        # Try to load a font, fallback to default
        try:
            # Use a basic font or one from our fonts folder if available
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
            
        # 1. Add "Metadata" (Top Left hidden/small or just visual credit?)
        # User said "add @Blaze_Updatez as metadata".
        # We'll add it visually at the top left as a "tag".
        # And "small watermark with less opacity in all temp genrated in emtp corner".
        
        # Let's add the Watermark in Bottom Right
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        x = image.width - text_width - 20
        y = image.height - text_height - 20
        
        # Draw shadow/outline for visibility
        shadow_color = (0, 0, 0)
        draw.text((x+1, y+1), text, font=font, fill=shadow_color)
        
        # Draw Text with opacity (simulated with color if RGBA not fully supported on draw directly without overlay)
        # Use a faint white
        text_color = (255, 255, 255) 
        draw.text((x, y), text, font=font, fill=text_color)
        
        return image
    except Exception as e:
        logger.error(f"Watermark Failed: {e}")
        return image



# Map command/template names to functions
TEMPLATE_MAP = {
    "ani": anilist_poster,
    "anim": anilist_poster,
    "crun": crunchyroll_poster,
    "light": lightsimple_poster,
    "lightm": lightsimple_poster,
    # "mangc": lightsimple_poster, # Keeping for backward compat if needed, but intended to replace
    "mangc": lightsimple_poster,
    "mangcm": lightsimple_poster,
    "net": netflix_poster,
    "netm": netflix_poster,
    "dark": darksimple_poster,
    "darkm": darksimple_poster,
    # "web": darksimple_poster, # Keeping for backward compat
    "web": darksimple_poster,
    "webm": darksimple_poster,
    "netcr": netflix_poster,
    "mod": modern_poster,
    "modm": modern_poster,
    "tmdb": tmdb_poster,
    "tmdbm": tmdb_poster
}

async def generate_poster_image(template_name, query, media_type="ANIME", is_premium=False):
    """
    Generic function to generate poster.
    
    Args:
        template_name (str): Key from TEMPLATE_MAP (e.g., 'ani', 'net').
        query (str): Anime/Manga name.
        media_type (str): 'ANIME' or 'MANGA'.
        is_premium (bool): If True, skip watermark.
        
    Returns:
        BytesIO: Image buffer or None if failed.
    """
    # 1. Fetch Data
    data = None
    
    if template_name == "tmdb":
        # TMDB (Movies / TV) Fetching Logic
        data = get_tmdb_media(query)
    elif template_name in ("netcr", "crun"):
        try:
            # Crunchyroll Fetching Logic (worker-based)
            data = fetch_series_data(query)
            # Check for errors in CR response
            if isinstance(data, dict) and "error" in data:
                logger.error(f"CR Error: {data['error']}")
                data = None
        except Exception as e:
            logger.error(f"CR Fetch Exception: {e}", exc_info=True)
            data = None
    else:
        # Standard AniList Fetching
        data = get_anime_data(query, media_type)
        
    if not data:
        return None
        
    # 2. Select Template Function
    generator_fn = TEMPLATE_MAP.get(template_name)
    if not generator_fn:
        return None
        
    # 3. Generate
    try:
        # Check signature or just try calling. 
        # Most of our refactored templates take `data` (dict).
        # Crunchyroll might need special handling if it expects more, 
        # but `crunchyroll_poster.py` `generate_poster` takes `anime_data: dict`.
        
        # Note: Some templates return BytesIO, others might return PIL Image or save to disk.
        # We need to standardize.
        
        result = generator_fn(data)
        
        # If result is PIL Image, convert to BytesIO
        if hasattr(result, 'save'): 
            # ADD WATERMARK HERE
            if not is_premium:
                result = add_watermark(result)
            
            img_io = io.BytesIO()
            if result.mode in ("RGBA", "P"):
                result = result.convert("RGB")
            
            # Add basic EXIF/Info if supported by format (JPEG supports limited)
            # We can use 'exif' parameter in save if we constructed bytes, but easier to just save.
            # "Metadata" usually implies EXIF 'Artist' or 'Software'.
            # Pillow allows adding exif.
            exif = result.getexif()
            # 0x0131 is Software, 0x013B is Artist
            exif[0x013B] = WATERMARK 
            
            result.save(img_io, 'JPEG', quality=85, exif=exif)
            img_io.seek(0)
            return img_io
        elif isinstance(result, io.BytesIO):
            
            out_io = io.BytesIO()
            
            if not is_premium:
                # If it's already bytes, we'd have to open it to watermark it
                result.seek(0)
                img = Image.open(result)
                img = add_watermark(img)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                    
                exif = img.getexif()
                exif[0x013B] = WATERMARK
                img.save(out_io, 'JPEG', quality=85, exif=exif)
            else:
                 # Just copy/convert if needed but skip watermark
                 result.seek(0)
                 img = Image.open(result)
                 if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                 
                 exif = img.getexif()
                 exif[0x013B] = WATERMARK
                 img.save(out_io, 'JPEG', quality=85, exif=exif)
            
            out_io.seek(0)
            return out_io
        
        return None 
        
    except Exception as e:
        logger.error(f"Generation Error: {e}", exc_info=True)
        return None
