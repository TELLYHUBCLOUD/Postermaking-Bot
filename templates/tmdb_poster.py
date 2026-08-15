"""
TMDB Movie / TV Poster Generator
================================
A cinematic, dark "Netflix meets TMDB" style poster built from the data dict
returned by :func:`api.tmdb_client.get_tmdb_media`.
"""
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import textwrap

from fonts import get_fonts
from poster import load_image, sanitize_description

# ─── Configuration ────────────────────────────────────────────────────────────
CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
LEFT_PANEL_WIDTH = 1150
PADDING_X = 110

# Colors
COLOR_WHITE = (255, 255, 255)
COLOR_OFF_WHITE = (245, 245, 245)
COLOR_TEXT_BLACK = (15, 15, 15)
COLOR_TMDB_GREEN = (64, 224, 168)
COLOR_TMDB_GREEN_DARK = (26, 188, 156)
COLOR_RATING_GOLD = (255, 205, 63)
COLOR_TITLE_BG = (255, 255, 255, 38)
COLOR_MUTED = (200, 200, 200)

try:
    GOOGLE_FONTS = get_fonts()
except Exception:
    GOOGLE_FONTS = {}


def get_font(size: int, weight: str = "bold") -> ImageFont.FreeTypeFont:
    mapping = {
        "bold": "Poppins-Bold",
        "extra-bold": "Poppins-ExtraBold",
        "medium": "Poppins-Medium",
        "regular": "Poppins-Regular",
        "black": "Poppins-Black",
        "display": "BebasNeue-Regular",
    }
    key = mapping.get(weight, "Poppins-Regular")
    font_path = GOOGLE_FONTS.get(key, GOOGLE_FONTS.get("Poppins-Regular", "arial.ttf"))
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        return ImageFont.load_default()


def create_gradient_bg(width: int, height: int) -> Image.Image:
    """Deep cinematic spotlight gradient (dark edges, teal center glow)."""
    import numpy as np
    start = (5, 8, 8)
    end = (8, 40, 34)
    y, x = np.ogrid[:height, :width]
    arr = np.zeros((height, width, 3), dtype=float)
    arr[:] = start
    cx, cy = width * 0.5, height * 0.42
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    max_dist = np.sqrt(width ** 2 + height ** 2)
    glow = np.clip(1 - (dist / (max_dist * 0.95)), 0, 1) ** 1.8
    target = np.array(end, dtype=float)
    for c in range(3):
        arr[:, :, c] = arr[:, :, c] * (1 - glow) + target[c] * glow
    return Image.fromarray(np.uint8(arr))


def draw_pill_button(draw, x, y, w, h, text, font, text_color, bg_color):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg_color)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x + (w - tw) // 2
    ty = y + (h - th) // 2 - bbox[1]
    draw.text((tx, ty), text, font=font, fill=text_color)


def _pick_backdrop(data):
    """Return the best backdrop URL (English preferred, fallback to first)."""
    images = data.get("images", {})
    backdrops = images.get("backdrops", {}) or {}
    if backdrops.get("en"):
        return backdrops["en"][0]
    if backdrops.get("all"):
        return backdrops["all"][0]
    # Fall back to the poster itself
    posters = images.get("posters", {}) or {}
    if posters.get("all"):
        return posters["all"][0]
    return data.get("poster_url")


def _pick_poster(data):
    """Return the best poster URL (English preferred)."""
    images = data.get("images", {})
    posters = images.get("posters", {}) or {}
    if posters.get("en"):
        return posters["en"][0]
    if posters.get("all"):
        return posters["all"][0]
    return data.get("poster_url")


def create_poster(data: dict) -> BytesIO:
    """Create a cinematic TMDB-style movie/TV poster.

    Args:
        data: dict from :func:`api.tmdb_client.get_tmdb_media`.

    Returns:
        BytesIO containing the generated JPEG image.
    """
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0))

    # ─── 1. Background (backdrop image when available) ────────────────────
    bg_url = _pick_backdrop(data)
    if bg_url:
        bg = load_image(bg_url)
        if bg:
            target_w = CANVAS_WIDTH
            target_h = CANVAS_HEIGHT
            img_ratio = bg.width / bg.height
            target_ratio = target_w / target_h
            if img_ratio > target_ratio:
                new_h = target_h
                new_w = int(new_h * img_ratio)
            else:
                new_w = target_w
                new_h = int(new_w / img_ratio)
            bg = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
            crop_x = (new_w - target_w) // 2
            crop_y = 0
            bg = bg.crop((crop_x, crop_y, crop_x + target_w, crop_y + target_h)).convert("RGB")
            canvas.paste(bg, (0, 0))
            # Dark overlay
            overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 150))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
        else:
            canvas.paste(create_gradient_bg(CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0))
    else:
        canvas.paste(create_gradient_bg(CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0))

    # Darken the left panel region for text readability
    panel_overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    _pd = ImageDraw.Draw(panel_overlay)
    _pd.rectangle([0, 0, LEFT_PANEL_WIDTH, CANVAS_HEIGHT], fill=(0, 0, 0, 160))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), panel_overlay).convert("RGB")

    # ─── 2. Right-side poster image ───────────────────────────────────────
    poster_url = _pick_poster(data)
    if poster_url:
        img = load_image(poster_url)
        if img:
            target_w = CANVAS_WIDTH - LEFT_PANEL_WIDTH
            target_h = CANVAS_HEIGHT
            img_ratio = img.width / img.height
            target_ratio = target_w / target_h
            if img_ratio > target_ratio:
                new_h = target_h
                new_w = int(new_h * img_ratio)
            else:
                new_w = target_w
                new_h = int(new_w / img_ratio)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            crop_x = (new_w - target_w) // 2
            crop_y = 0
            img = img.crop((crop_x, crop_y, crop_x + target_w, crop_y + target_h))
            canvas.paste(img, (LEFT_PANEL_WIDTH, 0))

    draw = ImageDraw.Draw(canvas, "RGBA")

    # ─── 3. Header: TMDB-style wordmark ───────────────────────────────────
    logo_font = get_font(78, weight="display")
    draw.text((PADDING_X, 40), "T M D B", font=logo_font, fill=COLOR_TMDB_GREEN)
    # Accent underline under the wordmark
    draw.rounded_rectangle(
        [PADDING_X, 130, PADDING_X + 220, 138],
        radius=4,
        fill=(COLOR_TMDB_GREEN + (255,)),
    )

    media_label = "M O V I E" if data.get("media_type") == "movie" else "T V   S E R I E S"
    tag_font = get_font(22, weight="medium")
    draw.text((PADDING_X + 240, 62), media_label, font=tag_font, fill=COLOR_OFF_WHITE)

    # ─── 4. Meta bar (rating • year • runtime • certificate) ──────────────
    rating = data.get("rating")
    rating_text = f"{rating:.1f}/10" if rating else "N/A"
    year = data.get("year") or "—"
    runtime = data.get("runtime") or "—"
    cert = data.get("certificates")

    meta_parts = []
    if rating:
        meta_parts.append(f"★ {rating_text}")
    meta_parts.append(str(year))
    meta_parts.append(str(runtime))
    if cert:
        meta_parts.append(cert)
    if data.get("media_type") == "tv":
        meta_parts.append(f"{data.get('seasons','?')} S")

    meta_font = get_font(34, weight="bold")
    meta_text = "  |  ".join(meta_parts)
    draw.text((PADDING_X, 190), meta_text, font=meta_font, fill=COLOR_OFF_WHITE)

    # ─── 5. Title ──────────────────────────────────────────────────────────
    title_text = (data.get("title") or data.get("localized_title") or "Unknown Title").upper()
    title_font = get_font(96, weight="extra-bold")
    if len(title_text) > 26:
        title_text = title_text[:26] + "..."
    wrapper = textwrap.TextWrapper(width=18, max_lines=2, placeholder="...")
    lines = wrapper.wrap(title_text) or [title_text]

    title_y = 270
    for line in lines:
        draw.text((PADDING_X, title_y), line, font=title_font, fill=COLOR_WHITE)
        title_y += 106

    # ─── 6. Tagline ────────────────────────────────────────────────────────
    tagline = data.get("tagline")
    if tagline:
        tag_font = get_font(26, weight="medium")
        draw.text((PADDING_X, title_y + 8), f"“{tagline}”", font=tag_font, fill=COLOR_MUTED)
        title_y += 55

    # ─── 7. Genre pills ────────────────────────────────────────────────────
    genres = [g.strip().upper() for g in (data.get("genres") or "").split(",") if g.strip()][:4]
    if not genres:
        genres = ["DRAMA", "ACTION"]
    pill_h = 60
    pill_w = 205
    spacing = 22
    pill_font = get_font(20, weight="extra-bold")
    px = PADDING_X
    for g in genres:
        draw_pill_button(draw, px, title_y + 25, pill_w, pill_h, g,
                         pill_font, COLOR_TEXT_BLACK, COLOR_TMDB_GREEN)
        px += pill_w + spacing

    # ─── 8. Synopsis ───────────────────────────────────────────────────────
    syn_y = title_y + 130
    syn_font = get_font(44, weight="extra-bold")
    draw.text((PADDING_X, syn_y), "SYNOPSIS", font=syn_font, fill=COLOR_TMDB_GREEN)

    body_font = get_font(28, weight="medium")
    plot = sanitize_description(data.get("plot") or "")
    body_wrapper = textwrap.TextWrapper(width=68)
    body_lines = body_wrapper.wrap(plot)[:5]
    current_y = syn_y + 60
    for line in body_lines:
        draw.text((PADDING_X, current_y), line, font=body_font, fill=(232, 232, 232))
        current_y += 40

    # ─── 9. Credits row ────────────────────────────────────────────────────
    cred_font = get_font(22, weight="bold")
    credit_y = current_y + 20
    if data.get("director"):
        draw.text((PADDING_X, credit_y), f"DIRECTOR  {data['director']}",
                  font=cred_font, fill=COLOR_OFF_WHITE)
        credit_y += 36
    if data.get("cast"):
        cast_short = data["cast"]
        if len(cast_short) > 60:
            cast_short = cast_short[:60] + "..."
        draw.text((PADDING_X, credit_y), f"CAST  {cast_short}",
                  font=cred_font, fill=COLOR_OFF_WHITE)

    # ─── 10. Bottom action button ──────────────────────────────────────────
    btn_w = 360
    btn_h = 82
    btn_x = (LEFT_PANEL_WIDTH - btn_w) // 2
    btn_y = CANVAS_HEIGHT - 130
    btn_text = "WATCH NOW" if data.get("media_type") == "movie" else "STREAM NOW"
    draw_pill_button(draw, btn_x, btn_y, btn_w, btn_h, btn_text,
                     get_font(30, weight="extra-bold"), COLOR_TEXT_BLACK, COLOR_OFF_WHITE)

    # TMDB rating badge (top right)
    badge_font = get_font(26, weight="black")
    badge = f"★ {rating_text}"
    badge_bbox = draw.textbbox((0, 0), badge, font=badge_font)
    bw = badge_bbox[2] - badge_bbox[0] + 60
    bh = 64
    bx = CANVAS_WIDTH - bw - 40
    by = 40
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh // 2, fill=COLOR_RATING_GOLD)
    bt = bx + 30
    ty = by + (bh - (badge_bbox[3] - badge_bbox[1])) // 2 - badge_bbox[1]
    draw.text((bt, ty), badge, font=badge_font, fill=COLOR_TEXT_BLACK)

    # ─── 11. Output ────────────────────────────────────────────────────────
    output = BytesIO()
    canvas.convert("RGB").save(output, "JPEG", quality=88)
    output.seek(0)
    return output


if __name__ == "__main__":
    # Quick standalone test (no network) with a sample data dict.
    sample = {
        "media_type": "movie", "title": "Inception", "year": "2010",
        "rating": 8.8, "votes": 2400000, "runtime": "148 min",
        "certificates": "PG-13", "tagline": "Your mind is the scene of the crime.",
        "genres": "Action, Science Fiction, Thriller",
        "plot": "A thief who steals corporate secrets through the use of dream-sharing "
                "technology is given the inverse task of planting an idea into the mind of a C.E.O.",
        "director": "Christopher Nolan", "cast": "Leonardo DiCaprio, Joseph Gordon-Levitt, Elliot Page",
        "poster_url": None, "images": {"posters": {}, "backdrops": {}},
    }
    buf = create_poster(sample)
    with open("tmdb_sample_poster.jpg", "wb") as f:
        f.write(buf.read())
    print("Sample poster written to tmdb_sample_poster.jpg")
