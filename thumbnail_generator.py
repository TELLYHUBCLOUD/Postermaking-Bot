"""
Thumbnail Generator Library
===========================
A high-quality thumbnail / poster engine for movies & TV.

Exposes several async entry points (all run the heavy work on a worker thread):

* :func:`make_landscape`            - landscape title-card over a backdrop
* :func:`portrait_to_landscape`     - convert a portrait poster into a landscape card
* :func:`make_thumbnail_with_logo`  - thumbnail with a channel/brand logo
* :func:`make_magic_thumbnail`      - 20 "Magic" templates (2560x1440)
* :func:`make_premiere_thumbnail`   - 12 "Premiere" styles

Fonts are loaded from the Postermaking-Bot ``fonts/`` directory via the shared
:mod:`fonts` manager, with sensible system fallbacks.
"""
import asyncio
import colorsys
import gc
import math
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

try:
    _LANCZOS = Image.Resampling.LANCZOS
    _BILINEAR = Image.Resampling.BILINEAR
    _BICUBIC = Image.Resampling.BICUBIC
except AttributeError:
    _LANCZOS = Image.LANCZOS
    _BILINEAR = Image.BILINEAR
    _BICUBIC = Image.BICUBIC

try:
    _MEDIANCUT = Image.Quantize.MEDIANCUT
except AttributeError:
    _MEDIANCUT = Image.MEDIANCUT

# ── Font paths (this project keeps fonts in ./fonts) ─────────────────────────
_ASSETS_FONT_DIR = Path(__file__).resolve().parent / "fonts"

_FONT_BOLD_CANDIDATES = [
    str(_ASSETS_FONT_DIR / "Poppins-Bold.ttf"),
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/seguiemj.ttf",
]
_FONT_MEDIUM_CANDIDATES = [
    str(_ASSETS_FONT_DIR / "Poppins-Medium.ttf"),
    "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_FONT_LIGHT_CANDIDATES = [
    str(_ASSETS_FONT_DIR / "Poppins-Regular.ttf"),
    str(_ASSETS_FONT_DIR / "DMSans-Medium.ttf"),
    "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

_FONT_BOLD = _FONT_BOLD_CANDIDATES[0]
_FONT_MEDIUM = _FONT_MEDIUM_CANDIDATES[0]
_FONT_LIGHT = _FONT_LIGHT_CANDIDATES[0]

_font_cache: dict = {}
_resolved_path_cache: dict = {}


def _resolve_font_path(path: str) -> str:
    if path in _resolved_path_cache:
        return _resolved_path_cache[path]
    for candidates in (_FONT_BOLD_CANDIDATES, _FONT_MEDIUM_CANDIDATES, _FONT_LIGHT_CANDIDATES):
        if path == candidates[0]:
            for candidate in candidates:
                if Path(candidate).exists():
                    _resolved_path_cache[path] = candidate
                    return candidate
    _resolved_path_cache[path] = path
    return path


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    size_int = int(round(size))
    key = (path, size_int)
    if key in _font_cache:
        return _font_cache[key]
    resolved = _resolve_font_path(path)
    try:
        font = ImageFont.truetype(resolved, size_int)
    except Exception:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def _sharpen_image(img: Image.Image, radius: float = 2, percent: int = 150, threshold: int = 3) -> Image.Image:
    return img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))


def _release_native_memory() -> None:
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


def _finish_and_save(img: Image.Image, output_path: str, quality: int = 95) -> None:
    img.convert("RGB").save(output_path, "JPEG", quality=quality, subsampling=0)


def _open_convert(path: str, mode: str = "RGB") -> Image.Image:
    with Image.open(path) as img:
        return img.convert(mode)


# ══════════════════════════════════════════════════════════════════════════════
# ── Shared Utility Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _truncate(draw, text, font, max_width, max_lines):
    lines = _wrap_text(draw, text, font, max_width)
    if len(lines) <= max_lines:
        return lines
    lines = lines[:max_lines]
    last = lines[-1]

    def fits(sample):
        return draw.textbbox((0, 0), sample + "…", font=font)[2] <= max_width

    while last and not fits(last):
        last = last.rsplit(" ", 1)[0] if " " in last else last[:-1].rstrip()
    while last and not fits(last):
        last = last[:-1].rstrip()
    lines[-1] = f"{last}…" if last else "…"
    return lines


def _cover_crop(img, width, height, resample=_LANCZOS):
    iw, ih = img.size
    target_aspect = width / height
    img_aspect = iw / ih
    if img_aspect > target_aspect:
        new_w = int(ih * target_aspect)
        offset = (iw - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, ih))
    elif img_aspect < target_aspect:
        new_h = int(iw / target_aspect)
        offset = (ih - new_h) // 2
        img = img.crop((0, offset, iw, offset + new_h))
    return img.resize((width, height), resample)


def _aa_rounded_rect(img, box, radius, fill=None, outline=None, width=1, ss=4):
    x0, y0, x1, y1 = box
    w, h = int(round(x1 - x0)), int(round(y1 - y0))
    if w <= 0 or h <= 0:
        return
    patch = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(patch).rounded_rectangle(
        [0, 0, w * ss - 1, h * ss - 1],
        radius=radius * ss,
        fill=fill,
        outline=outline,
        width=max(1, width * ss),
    )
    patch = patch.resize((w, h), _LANCZOS)
    img.alpha_composite(patch, (int(round(x0)), int(round(y0))))


def _draw_badge(img, x, y, label, font, fill=(30, 35, 45, 230),
                text_fill=(240, 197, 24, 255), S=1):
    draw = ImageDraw.Draw(img)
    pad_x, pad_y = 10 * S, 5 * S
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    box_w, box_h = tw + pad_x * 2, th + pad_y * 2
    _aa_rounded_rect(
        img, [x, y, x + box_w, y + box_h],
        radius=box_h // 2, fill=fill,
        outline=(255, 255, 255, 60), width=1,
    )
    draw.text((x + pad_x, y + pad_y - bbox[1]), label, font=font, fill=text_fill)
    return x + box_w + 10 * S


def _draw_info_pill(img, x, cy, label, font, S, fill=(0, 0, 0, 115), text_fill=None):
    if text_fill is None:
        r, g, b = fill[0], fill[1], fill[2]
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        text_fill = (20, 18, 16, 255) if lum > 165 else (255, 255, 255, 255)
    draw = ImageDraw.Draw(img)
    pad_x, pad_y = 14 * S, 7 * S
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    box_w, box_h = tw + pad_x * 2, th + pad_y * 2
    y = cy - box_h // 2
    _aa_rounded_rect(
        img, [x, y, x + box_w, y + box_h],
        radius=box_h // 2, fill=fill,
        outline=(255, 255, 255, 90), width=max(1, S // 2),
    )
    draw.text((x + pad_x, y + pad_y - bbox[1]), label, font=font, fill=text_fill)
    return x + box_w + 10 * S


def _draw_star(draw, cx, cy, r, fill):
    pts = []
    for i in range(10):
        ang = math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append((cx + rad * math.cos(ang), cy - rad * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def _torn_polygon(w, h, jag=11, step=15):
    pts = []
    x = 0
    while x < w:
        pts.append((x, random.randint(0, jag)))
        x += step
    pts.append((w, 0))
    y = 0
    while y < h:
        pts.append((w - random.randint(0, jag), y))
        y += step
    pts.append((w, h))
    x = w
    while x > 0:
        pts.append((x, h - random.randint(0, jag)))
        x -= step
    pts.append((0, h))
    y = h
    while y > 0:
        pts.append((random.randint(0, jag), y))
        y -= step
    pts.append((0, 0))
    return pts


def _torn_photo(img, target_w, target_h, rotate_deg=0.0):
    pad = 24
    photo = _cover_crop(img, target_w, target_h)
    mask = Image.new("L", (target_w, target_h), 0)
    ImageDraw.Draw(mask).polygon(_torn_polygon(target_w, target_h), fill=255)
    paper_mask = mask.filter(ImageFilter.MaxFilter(5))
    canvas_w, canvas_h = target_w + pad * 2, target_h + pad * 2
    layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    paper = Image.new("RGBA", (target_w, target_h), (255, 252, 246, 255))
    paper.putalpha(paper_mask)
    layer.alpha_composite(paper, dest=(pad, pad))
    photo_rgba = photo.convert("RGBA")
    photo_rgba.putalpha(mask)
    layer.alpha_composite(photo_rgba, dest=(pad, pad))
    if rotate_deg:
        layer = layer.rotate(rotate_deg, resample=_BICUBIC, expand=True)
    return layer


def _shadow_from_alpha(layer, blur=18, opacity=165):
    w, h = layer.size
    half_w, half_h = max(1, w // 2), max(1, h // 2)
    alpha = layer.split()[-1].resize((half_w, half_h), _BILINEAR)
    alpha = alpha.point(lambda p: opacity if p > 10 else 0)
    black = Image.new("RGBA", (half_w, half_h), (0, 0, 0, 255))
    empty = Image.new("RGBA", (half_w, half_h), (0, 0, 0, 0))
    shadow = Image.composite(black, empty, alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(1, blur // 2)))
    return shadow.resize((w, h), _BILINEAR)


def _extract_palette(img, n=6):
    small = img.convert("RGB").resize((120, 160), _LANCZOS)
    quant = small.quantize(colors=max(n * 3, 12), method=_MEDIANCUT)
    palette = quant.getpalette()
    counts = quant.getcolors() or []
    counts.sort(reverse=True, key=lambda c: c[0])
    swatches = []
    for _count, idx in counts:
        r, g, b = palette[idx * 3: idx * 3 + 3]
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if v < 0.28 or v > 0.95 or s < 0.22:
            continue
        s = min(1.0, s * 1.35)
        v = min(0.95, max(0.55, v * 1.05))
        r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
        candidate = (int(r2 * 255), int(g2 * 255), int(b2 * 255))
        if all(sum(abs(a - b) for a, b in zip(candidate, ex)) > 90 for ex in swatches):
            swatches.append(candidate)
        if len(swatches) >= n:
            break
    return swatches or [(99, 102, 241)]


_GENRE_DEFAULT_COLOR = (99, 102, 241)
_RUNTIME_PILL_COLOR = (217, 119, 6)
_YEAR_PILL_COLOR = (67, 56, 202)

_tg_icon_cache: dict = {}
_scrim_overlay_cache: dict = {}

_TITLE_ABBREVIATIONS = [
    (r"\bdirector'?s\s+cut\b", "Dir. Cut"),
    (r"\bextended\s+edition\b", "Ext. Ed."),
    (r"\bspecial\s+edition\b", "Spec. Ed."),
    (r"\bcollector'?s\s+edition\b", "Collector's Ed."),
    (r"\banniversary\s+edition\b", "Anniv. Ed."),
    (r"\bunrated\s+edition\b", "Unrated"),
    (r"\btheatrical\s+cut\b", "Theatrical"),
    (r"\bextended\s+cut\b", "Ext. Cut"),
    (r"\bdirector'?s\s+edition\b", "Dir. Ed."),
    (r"\bextended\b", "Ext."),
    (r"\bpart\s+one\b", "Pt. 1"), (r"\bpart\s+two\b", "Pt. 2"),
    (r"\bpart\s+three\b", "Pt. 3"), (r"\bpart\s+four\b", "Pt. 4"),
    (r"\bpart\s+(\d+)\b", r"Pt. \1"),
    (r"\bchapter\s+one\b", "Ch. 1"), (r"\bchapter\s+two\b", "Ch. 2"),
    (r"\bchapter\s+(\d+)\b", r"Ch. \1"),
    (r"\bvolume\s+one\b", "Vol. 1"), (r"\bvolume\s+two\b", "Vol. 2"),
    (r"\bvolume\s+(\d+)\b", r"Vol. \1"),
]
_EDITION_TAIL_RE = re.compile(
    r"[\s:\-–—(]+(?:the\s+)?"
    r"(?:director'?s\s+cut|special\s+edition|unrated(?:\s+edition)?|"
    r"theatrical(?:\s+cut)?|remaster(?:ed)?(?:\s+edition)?|anniversary\s+edition|"
    r"extended(?:\s+(?:cut|edition))?|imax(?:\s+edition)?|4k(?:\s+edition)?|"
    r"uncut|uncensored|redux|definitive\s+edition|ultimate\s+edition|collector'?s\s+edition)"
    r"\)?[.\s]*$",
    re.IGNORECASE,
)


def _abbreviate_title(text):
    upper = text.isupper()
    for pattern, repl in _TITLE_ABBREVIATIONS:
        if upper:
            repl = repl.upper()
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def _strip_edition_tail(text):
    stripped = _EDITION_TAIL_RE.sub("", text).rstrip(" :-–—(")
    return stripped if stripped else text


def _title_fallback_candidates(text):
    candidates = []
    stripped = _strip_edition_tail(text)
    if stripped != text:
        candidates.append(stripped)
    abbreviated = _abbreviate_title(stripped)
    if abbreviated != stripped:
        candidates.append(abbreviated)
    return candidates


def _telegram_icon(size):
    if size in _tg_icon_cache:
        return _tg_icon_cache[size]
    s = size * 4
    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(icon)
    d.ellipse([0, 0, s - 1, s - 1], fill=(41, 168, 228, 255))
    plane = [
        (s * 0.20, s * 0.53), (s * 0.82, s * 0.20), (s * 0.68, s * 0.80),
        (s * 0.47, s * 0.62), (s * 0.36, s * 0.75), (s * 0.40, s * 0.55),
    ]
    d.polygon(plane, fill=(255, 255, 255, 255))
    d.polygon([plane[0], plane[1], plane[4]], fill=(210, 230, 245, 255))
    icon = icon.resize((size, size), _LANCZOS)
    _tg_icon_cache[size] = icon
    return icon


def _get_scrim_overlay(W, H):
    key = (W, H)
    if key in _scrim_overlay_cache:
        return _scrim_overlay_cache[key]
    scrim_col = Image.new("RGBA", (1, H), (0, 0, 0, 0))
    flat_tint = Image.new("RGBA", (1, H), (4, 4, 6, 154))
    bgrad = Image.new("L", (1, H))
    for yy in range(H):
        t = yy / (H - 1)
        bgrad.putpixel((0, yy), int(90 * max(0.0, (t - 0.75) / 0.25)))
    btint = Image.new("RGBA", (1, H), (0, 0, 0, 255))
    btint.putalpha(bgrad)
    scrim_col.alpha_composite(flat_tint)
    scrim_col.alpha_composite(btint)
    overlay = scrim_col.resize((W, H))
    _scrim_overlay_cache[key] = overlay
    return overlay


def _fit_title(draw, title, max_w, S=1.5, max_lines=2):
    for font_size in range(int(46 * S), int(24 * S), -4):
        font = _load_font(_FONT_BOLD, font_size)
        lines = _wrap_text(draw, title.upper(), font, max_w)
        if len(lines) <= max_lines:
            return font, lines
    font = _load_font(_FONT_BOLD, int(24 * S))
    return font, _wrap_text(draw, title.upper(), font, max_w)[:max_lines]


def _wrap_first_line(draw, words, font, max_width):
    line, i = [], 0
    while i < len(words):
        trial = " ".join(line + [words[i]])
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width or not line:
            line.append(words[i])
            i += 1
        else:
            break
    return line, i


def _fit_title_with_badge(draw, text, max_width, reserve_w, max_lines=2,
                           start_size=84, min_size=40, font_path=_FONT_BOLD):
    words = text.split()
    size = start_size
    while size >= min_size:
        font = _load_font(font_path, size)
        first_max = max(40, max_width - reserve_w)
        line1_words, idx = _wrap_first_line(draw, words, font, first_max)
        remaining = words[idx:]
        lines = [" ".join(line1_words)]
        if remaining:
            lines.extend(_wrap_text(draw, " ".join(remaining), font, max_width))
        if len(lines) <= max_lines:
            return font, lines
        size -= 4
    font = _load_font(font_path, min_size)
    first_max = max(40, max_width - reserve_w)
    best_words = words
    for candidate in _title_fallback_candidates(text):
        best_words = candidate.split()
        line1_words, idx = _wrap_first_line(draw, best_words, font, first_max)
        remaining = best_words[idx:]
        lines = [" ".join(line1_words)]
        if remaining:
            lines.extend(_wrap_text(draw, " ".join(remaining), font, max_width))
        if len(lines) <= max_lines:
            return font, lines
    line1_words, idx = _wrap_first_line(draw, best_words, font, first_max)
    remaining = best_words[idx:]
    lines = [" ".join(line1_words)]
    if remaining:
        lines.extend(_truncate(draw, " ".join(remaining), font, max_width, max_lines - 1))
    return font, lines[:max_lines]


def _imdb_badge_width(draw, rating_label, star_r, rating_font, imdb_font, ipad_x, S):
    rbbox = draw.textbbox((0, 0), rating_label, font=rating_font)
    ibbox = draw.textbbox((0, 0), "IMDb", font=imdb_font)
    return (star_r * 2 + 8 * S) + (rbbox[2] - rbbox[0]) + 10 * S + (ibbox[2] - ibbox[0] + ipad_x * 2)


def _draw_imdb_rating_badge(img, x, cy, rating_label, star_r,
                             rating_font, imdb_font, ipad_x, ipad_y, S):
    draw = ImageDraw.Draw(img)
    _draw_star(draw, x + star_r, cy, star_r, (235, 178, 62, 255))
    x += star_r * 2 + 8 * S
    rbbox = draw.textbbox((0, 0), rating_label, font=rating_font)
    rh = rbbox[3] - rbbox[1]
    draw.text((x, cy - rh // 2 - rbbox[1]), rating_label, font=rating_font, fill=(255, 255, 255, 255))
    x += (rbbox[2] - rbbox[0]) + 10 * S
    ibbox = draw.textbbox((0, 0), "IMDb", font=imdb_font)
    iw, ih = ibbox[2] - ibbox[0], ibbox[3] - ibbox[1]
    pill_h = ih + ipad_y * 2
    pill_top = cy - pill_h // 2
    _aa_rounded_rect(img, [x, pill_top, x + iw + ipad_x * 2, pill_top + pill_h],
                     radius=5 * S, fill=(14, 14, 14, 255))
    draw.text((x + ipad_x, pill_top + ipad_y - ibbox[1]), "IMDb",
              font=imdb_font, fill=(240, 197, 24, 255))
    return x + iw + ipad_x * 2


def _draw_tomato_icon(draw, cx, cy, r, fresh):
    if fresh:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(224, 44, 38, 255))
        stem_w = max(2, int(r * 0.35))
        draw.polygon(
            [(cx - stem_w, cy - int(r * 0.85)),
             (cx + stem_w, cy - int(r * 0.85)),
             (cx, cy - int(r * 1.5))],
            fill=(69, 140, 60, 255),
        )
    else:
        pts = []
        for i in range(8):
            ang = i * math.pi / 4
            rad = r * (0.7 + 0.3 * (i % 2))
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        draw.polygon(pts, fill=(107, 142, 35, 255))


def _draw_rt_badge(draw, x, cy, score_label, fresh, r, font, S):
    _draw_tomato_icon(draw, x + r, cy, r, fresh)
    x += r * 2 + 8 * S
    color = (235, 90, 80, 255) if fresh else (150, 190, 90, 255)
    bbox = draw.textbbox((0, 0), score_label, font=font)
    th = bbox[3] - bbox[1]
    draw.text((x, cy - th // 2 - bbox[1]), score_label, font=font, fill=color)
    return x + (bbox[2] - bbox[0])


def _draw_age_rating_chip(img, x, y, label, font, S):
    draw = ImageDraw.Draw(img)
    pad_x, pad_y = 9 * S, 5 * S
    bbox = draw.textbbox((0, 0), label, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    box_w, box_h = w + pad_x * 2, h + pad_y * 2
    _aa_rounded_rect(img, [x, y, x + box_w, y + box_h],
                     radius=4 * S, outline=(255, 255, 255, 220), width=2 * S)
    draw.text((x + pad_x, y + pad_y - bbox[1]), label, font=font, fill=(255, 255, 255, 255))
    return x + box_w, box_h


def _draw_leaf(draw, cx, cy, dx, dy, length, width, color, shadow=True):
    px, py = -dy, dx

    def _poly(ox, oy):
        return [
            (cx - dx * length * 0.25 + ox, cy - dy * length * 0.25 + oy),
            (cx + px * width + ox, cy + py * width + oy),
            (cx + dx * length + ox, cy + dy * length + oy),
            (cx - px * width + ox, cy - py * width + oy),
        ]

    if shadow:
        draw.polygon(_poly(1.5, 1.5), fill=(0, 0, 0, 110))
    draw.polygon(_poly(0, 0), fill=color)


def _draw_laurel_branch(draw, base_x, cy, height, side, n_leaves, color, S, shadow=True):
    bow = 16 * S
    bottom_y = cy + height / 2
    for i in range(n_leaves):
        t = i / max(1, n_leaves - 1)
        y = bottom_y - height * t
        x = base_x + side * bow * math.sin(t * math.pi * 0.9)
        leaf_len = (17 - 9 * t) * S
        leaf_w = (6.5 - 3 * t) * S
        ang = math.radians(35 + 45 * t)
        dx, dy = side * math.cos(ang), -math.sin(ang)
        _draw_leaf(draw, x, y, dx, dy, leaf_len, leaf_w, color, shadow=shadow)


def _horizontal_scrim(w, h, dark_end=0.32, clear_start=0.52):
    tail, peak = 12, 165
    grad = Image.new("L", (w, 1), 0)
    for x in range(w):
        frac = x / max(1, w - 1)
        if frac <= dark_end:
            a = peak
        elif frac >= clear_start:
            a = tail
        else:
            t = (frac - dark_end) / (clear_start - dark_end)
            s = t * t * (3 - 2 * t)
            a = int(peak + (tail - peak) * s)
        grad.putpixel((x, 0), a)
    grad = grad.resize((w, h))
    scrim = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    scrim.putalpha(grad)
    return scrim


def _draw_glow_text(canvas, draw, x, y, text, font, color, glow_color, glow_radius, W, H):
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(gl).text((x, y), text, font=font, fill=glow_color)
    gl = gl.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    canvas.alpha_composite(gl)
    draw.text((x, y), text, font=font, fill=color)


def _scatter_particles(canvas, W, H, count, color, min_r, max_r, seed=42, y_range=None):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rng = random.Random(seed)
    y_min = y_range[0] if y_range else 0
    y_max = y_range[1] if y_range else H
    for _ in range(count):
        px = rng.randint(0, W)
        py = rng.randint(y_min, y_max)
        pr = rng.randint(min_r, max_r)
        pa = rng.randint(20, 100)
        d.ellipse([px - pr, py - pr, px + pr, py + pr],
                  fill=(color[0], color[1], color[2], pa))
    canvas.alpha_composite(layer)


def _vertical_gradient_bar(canvas, x, w, H, color, alpha_range=(0, 255)):
    bar = Image.new("RGBA", (w, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    for yy in range(H):
        t = yy / max(1, H - 1)
        a = int(alpha_range[0] + (alpha_range[1] - alpha_range[0]) * (1.0 - abs(2 * t - 1)))
        bd.line([(0, yy), (w, yy)], fill=(color[0], color[1], color[2], a))
    canvas.alpha_composite(bar, dest=(x, 0))


def _draw_18_plus_badge(img, x, y, S):
    draw = ImageDraw.Draw(img)
    r = int(18 * S)
    _aa_rounded_rect(
        img, [x, y, x + r * 2, y + r * 2],
        radius=r, fill=(220, 20, 60, 240),
        outline=(255, 255, 255, 200), width=int(2 * S),
    )
    font = _load_font(_FONT_BOLD, int(14 * S))
    bbox = draw.textbbox((0, 0), "18+", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x + r - tw // 2, y + r - th // 2 - bbox[1]), "18+", font=font, fill=(255, 255, 255, 255))
    return x + r * 2 + int(12 * S)


# ══════════════════════════════════════════════════════════════════════════════
# ── LANDSCAPE / PORTRAIT / LOGO
# ══════════════════════════════════════════════════════════════════════════════

def _make_landscape_sync(input_path, output_path, title="", overview="",
                          year="", quality_tags=None, brand="TELLY_HUB"):
    S = 1.5
    W, H = int(1280 * S), int(720 * S)
    bg_src = _open_convert(input_path, "RGB")
    bg = ImageEnhance.Contrast(_sharpen_image(_cover_crop(bg_src, W, H, resample=_LANCZOS))).enhance(1.04)
    canvas = bg.convert("RGBA")
    if title or overview or quality_tags:
        grad_h = int(420 * S)
        grad = Image.new("RGBA", (W, grad_h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for y in range(grad_h):
            gd.line([(0, y), (W, y)], fill=(0, 0, 0, int(235 * (y / (grad_h - 1)) ** 1.6)))
        canvas.alpha_composite(grad, dest=(0, H - grad_h))
        draw = ImageDraw.Draw(canvas)
        lm, cw = int(48 * S), W - int(48 * S) * 2 - int(100 * S)
        curr_y = H - int(35 * S)
        if quality_tags:
            bx, bf = lm, _load_font(_FONT_BOLD, int(13 * S))
            for tag in reversed((quality_tags or [])[:4]):
                bx = _draw_badge(canvas, bx, curr_y - int(14 * S), tag, bf,
                                 fill=(240, 197, 24, 230), text_fill=(0, 0, 0, 255), S=int(S))
            curr_y -= int(36 * S)
        if overview:
            df = _load_font(_FONT_LIGHT, int(15 * S))
            dl = _truncate(draw, overview, df, cw, max_lines=2)
            dh = len(dl) * int(21 * S)
            curr_y -= dh
            for line in dl:
                draw.text((lm, curr_y), line, font=df, fill=(220, 225, 235, 240))
                curr_y += int(21 * S)
            curr_y -= dh + int(12 * S)
        if year:
            draw.text((lm, curr_y - int(24 * S)), f"Release Year • {year}",
                      font=_load_font(_FONT_MEDIUM, int(16 * S)), fill=(240, 197, 24, 240))
            curr_y -= int(28 * S)
        if title:
            tf = _load_font(_FONT_BOLD, int(42 * S))
            tl = _wrap_text(draw, title, tf, cw)[:2]
            th = len(tl) * int(48 * S)
            curr_y -= th
            for line in tl:
                draw.text((lm + 2, curr_y + 2), line, font=tf, fill=(0, 0, 0, 180))
                draw.text((lm, curr_y), line, font=tf, fill=(255, 255, 255, 255))
                curr_y += int(48 * S)
        if brand:
            _draw_badge(canvas, lm, int(30 * S), f"★  {brand}",
                        _load_font(_FONT_BOLD, int(13 * S)),
                        fill=(240, 197, 24, 220), text_fill=(0, 0, 0, 255), S=int(S))
    _finish_and_save(canvas, output_path, quality=96)


async def make_landscape(input_path, output_path, title="", overview="",
                          year="", quality_tags=None, brand="TELLY_HUB"):
    await asyncio.to_thread(
        _make_landscape_sync, input_path=input_path, output_path=output_path,
        title=title, overview=overview, year=year, quality_tags=quality_tags, brand=brand,
    )


def _portrait_to_landscape_sync(input_path, output_path, title="", overview="",
                                  year="", rating=0.0, genres=None,
                                  quality_tags=None, brand="TELLY_HUB"):
    S = 1.5
    W, H = int(1280 * S), int(720 * S)
    genres, quality_tags = genres or [], quality_tags or []
    poster_img = _open_convert(input_path, "RGB")
    bg = _cover_crop(poster_img, W // 2, H // 2, resample=_BILINEAR)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=20)).resize((W, H), _BILINEAR)
    palette = _extract_palette(poster_img, n=3)
    accent = palette[0] if palette else (20, 30, 50)
    canvas = bg.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), (4, 6, 12, 160)))
    canvas.alpha_composite(Image.new("RGBA", (W, H), (*accent, 45)))
    lg = Image.new("RGBA", (int(W * 0.65), H), (0, 0, 0, 0))
    lgd = ImageDraw.Draw(lg)
    for x in range(int(W * 0.65)):
        lgd.line([(x, 0), (x, H)], fill=(0, 0, 0, int(220 * max(0.0, 1.0 - (x / (W * 0.65)) ** 1.4))))
    canvas.alpha_composite(lg)
    card_h, card_w = int(520 * S), int(520 * S * 2 / 3)
    pc = _torn_photo(poster_img, card_w, card_h)
    si = _shadow_from_alpha(pc, blur=int(24 * S), opacity=190)
    px, py = W - card_w - int(60 * S), (H - card_h) // 2 - 12
    canvas.alpha_composite(si, dest=(px - 24, py - 24))
    canvas.alpha_composite(pc, dest=(px - 24, py - 24))
    draw = ImageDraw.Draw(canvas)
    lm, cw = int(50 * S), px - int(50 * S) - int(30 * S)
    curr_y = int(50 * S)
    if brand:
        _draw_badge(canvas, lm, curr_y, f"★  {brand}", _load_font(_FONT_BOLD, int(13 * S)),
                    fill=(240, 197, 24, 240), text_fill=(0, 0, 0, 255), S=int(S))
        curr_y += int(32 * S)
    tf, tl = _fit_title(draw, title or "Unknown", cw, S)
    for line in tl:
        draw.text((lm + 2, curr_y + 2), line, font=tf, fill=(0, 0, 0, 200))
        draw.text((lm, curr_y), line, font=tf, fill=(255, 255, 255, 255))
        curr_y += int(38 * S if len(tl) > 2 else 46 * S)
    curr_y += int(10 * S)
    parts = []
    if year:
        parts.append(year)
    if rating > 0:
        parts.append(f"IMDb ★ {rating:.1f}")
    if genres:
        parts.append(" • ".join(genres[:2]))
    if parts:
        draw.text((lm, curr_y), "  |  ".join(parts),
                  font=_load_font(_FONT_MEDIUM, int(15 * S)), fill=(240, 197, 24, 240))
        curr_y += int(28 * S)
    if overview:
        df = _load_font(_FONT_LIGHT, int(14 * S))
        for line in _truncate(draw, overview, df, cw, max_lines=3):
            draw.text((lm, curr_y), line, font=df, fill=(215, 220, 230, 240))
            curr_y += int(20 * S)
        curr_y += int(10 * S)
    if quality_tags:
        bx, bf = lm, _load_font(_FONT_BOLD, int(12 * S))
        for tag in quality_tags[:4]:
            bx = _draw_badge(canvas, bx, curr_y, tag, bf,
                             fill=(30, 35, 45, 230), text_fill=(240, 197, 24, 255), S=int(S))
    _finish_and_save(canvas, output_path, quality=96)


async def portrait_to_landscape(input_path, output_path, title="", overview="",
                                  year="", rating=0.0, genres=None,
                                  quality_tags=None, brand="TELLY_HUB"):
    await asyncio.to_thread(
        _portrait_to_landscape_sync, input_path=input_path, output_path=output_path,
        title=title, overview=overview, year=year, rating=rating, genres=genres,
        quality_tags=quality_tags, brand=brand,
    )


def _make_thumbnail_with_logo_sync(backdrop_path, logo_path, output_path,
                                    position="mid-left", gradient=False,
                                    title="", overview="", year="",
                                    quality_tags=None, brand="TELLY_HUB"):
    S = 1.5
    W, H = int(1280 * S), int(720 * S)
    quality_tags = quality_tags or []
    bg = _sharpen_image(_cover_crop(_open_convert(backdrop_path, "RGB"), W, H, resample=_LANCZOS))
    canvas = bg.convert("RGBA")
    lm, cw = int(56 * S), W - int(56 * S) * 2 - int(80 * S)
    if title or overview:
        gh = int(300 * S)
        gr = Image.new("RGBA", (W, gh), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gr)
        for gy in range(gh):
            gd.line([(0, gy), (W, gy)], fill=(0, 0, 0, int(200 * (gy / (gh - 1)) ** 1.6)))
        canvas.alpha_composite(gr, dest=(0, H - gh))
        draw = ImageDraw.Draw(canvas)
        cy = H - int(35 * S)
        if year:
            draw.text((lm, cy - int(20 * S)), f"Release Year • {year}",
                      font=_load_font(_FONT_MEDIUM, int(15 * S)), fill=(240, 197, 24, 240))
            cy -= int(24 * S)
        if overview:
            df = _load_font(_FONT_LIGHT, int(14 * S))
            dl = _truncate(draw, overview, df, cw, max_lines=2)
            dh = len(dl) * int(20 * S)
            cy -= dh
            for line in dl:
                draw.text((lm, cy), line, font=df, fill=(220, 225, 235, 240))
                cy += int(20 * S)
            cy -= dh + int(10 * S)
        if title:
            tf = _load_font(_FONT_BOLD, int(30 * S))
            tl = _wrap_text(draw, title, tf, cw)[:2]
            th = len(tl) * int(36 * S)
            cy -= th
            for line in tl:
                draw.text((lm + 2, cy + 2), line, font=tf, fill=(0, 0, 0, 180))
                draw.text((lm, cy), line, font=tf, fill=(255, 255, 255, 255))
                cy += int(36 * S)
    if brand:
        _draw_badge(canvas, lm, int(30 * S), f"★  {brand}",
                    _load_font(_FONT_BOLD, int(13 * S)),
                    fill=(240, 197, 24, 220), text_fill=(0, 0, 0, 255), S=int(S))
    with Image.open(logo_path) as ls:
        logo = ls.convert("RGBA")
    lw, lh = logo.size
    sc = min(int(W * 0.55) / lw, int(H * 0.30) / lh, 1.0)
    nlw, nlh = int(lw * sc), int(lh * sc)
    logo = logo.resize((nlw, nlh), _LANCZOS)
    px, py = int(72 * S), int(55 * S)
    hp = position.split("-")[-1] if "-" in position else "center"
    lx = px if hp == "left" else (W - nlw - px if hp == "right" else (W - nlw) // 2)
    vp = position.split("-")[0] if "-" in position else "mid"
    ly = py if vp == "top" else (H - nlh - py if vp == "bot" else (H - nlh) // 2)
    if gradient:
        gh2 = nlh + int(140 * S)
        gy = max(0, ly - int(60 * S))
        g2 = Image.new("RGBA", (W, gh2), (0, 0, 0, 0))
        g2d = ImageDraw.Draw(g2)
        mid = gh2 // 2
        for row in range(gh2):
            g2d.line([(0, row), (W, row)],
                     fill=(0, 0, 0, int(185 * max(0.0, 1.0 - (abs(row - mid) / max(mid, 1)) ** 1.5))))
        canvas.alpha_composite(g2, dest=(0, gy))
    sa = logo.split()[-1].point(lambda p: int(p * 0.55))
    bc = Image.new("L", (nlw, nlh), 0)
    si = Image.merge("RGBA", (bc, bc, bc, sa))
    sl = Image.new("RGBA", (nlw + int(20 * S), nlh + int(20 * S)), (0, 0, 0, 0))
    sl.paste(si, (int(10 * S), int(10 * S)))
    sl = sl.filter(ImageFilter.GaussianBlur(radius=int(8 * S)))
    canvas.alpha_composite(sl, dest=(lx - int(10 * S), ly - int(10 * S)))
    canvas.alpha_composite(logo, dest=(lx, ly))
    if quality_tags:
        bx, by, bf = px, H - int(50 * S), _load_font(_FONT_BOLD, int(13 * S))
        for tag in quality_tags[:4]:
            bx = _draw_badge(canvas, bx, by, tag, bf,
                             fill=(240, 197, 24, 230), text_fill=(0, 0, 0, 255), S=int(S))
    _finish_and_save(canvas, output_path, quality=96)


async def make_thumbnail_with_logo(backdrop_path, logo_path, output_path,
                                    position="mid-left", gradient=False,
                                    title="", overview="", year="",
                                    quality_tags=None, brand="TELLY_HUB"):
    await asyncio.to_thread(
        _make_thumbnail_with_logo_sync,
        backdrop_path=backdrop_path, logo_path=logo_path, output_path=output_path,
        position=position, gradient=gradient, title=title, overview=overview,
        year=year, quality_tags=quality_tags, brand=brand,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ── MAGIC THUMBNAIL  (20 Templates)
# ══════════════════════════════════════════════════════════════════════════════

def _magic_data_pack(backdrop_path, poster_path, title, overview, brand, year,
                      rating, genres, runtime, age_rating, rotten_tomatoes,
                      seasons, season, episode, custom_channel, quality_tags, filename,
                      director="", actors="", metascore=""):
    S = 2
    W, H = 1280 * S, 720 * S
    genres, quality_tags = genres or [], quality_tags or []
    bg_src = _open_convert(backdrop_path, "RGB")
    half_bg = _cover_crop(bg_src, W // 2, H // 2, resample=_BILINEAR)
    half_bg = half_bg.filter(ImageFilter.GaussianBlur(radius=max(1.0, 0.6 * S)))
    bg = half_bg.resize((W, H), _BILINEAR)
    canvas = bg.convert("RGBA")
    canvas.alpha_composite(_get_scrim_overlay(W, H))
    poster_img = _open_convert(poster_path, "RGB")
    try:
        palette = _extract_palette(poster_img, n=6)
    except Exception:
        palette = [_GENRE_DEFAULT_COLOR]
    panel_w, panel_h = 300 * S, 452 * S
    ppx = W - panel_w - 44 * S
    ppy = (H - panel_h) // 2
    ep_str = ""
    if season is not None and episode is not None:
        ep_str = f"S{season:02d} E{episode:02d}"
    elif season is not None:
        ep_str = f"Season {season}"
    elif seasons:
        ep_str = f"{seasons} Season{'s' if seasons > 1 else ''}"
    credits = ""
    if director and str(director).strip() and str(director).strip().lower() != "n/a":
        credits = f"Dir. {str(director).strip()}"
    if actors and str(actors).strip() and str(actors).strip().lower() != "n/a":
        cast = str(actors).strip()
        credits = f"{credits}  ·  {cast}" if credits else cast
    desc = overview.strip() if overview else (
        f"File: {filename}" if filename else "No description available for this title."
    )
    brand_text = custom_channel if custom_channel else (
        f"@{brand}" if not brand.startswith("@") else brand
    )
    return dict(
        S=S, W=W, H=H, canvas=canvas, bg=bg, poster_img=poster_img, palette=palette,
        panel_w=panel_w, panel_h=panel_h, ppx=ppx, ppy=ppy, ep_str=ep_str,
        desc=desc, brand_text=brand_text, genres=genres, quality_tags=quality_tags,
        rating=rating, year=year, runtime=runtime, age_rating=age_rating,
        rotten_tomatoes=rotten_tomatoes, title=title, brand=brand,
        credits=credits, metascore=str(metascore or "").strip(),
        director=director or "", actors=actors or "",
    )


def _attach_poster_card(canvas, poster_img, ppx, ppy, panel_w, panel_h, S):
    pc = _sharpen_image(_torn_photo(poster_img, panel_w, panel_h, rotate_deg=0))
    si = _shadow_from_alpha(pc, blur=int(16 * S), opacity=180)
    canvas.alpha_composite(si, dest=(ppx - 24, ppy - 24))
    canvas.alpha_composite(pc, dest=(ppx - 24, ppy - 24))


def _draw_info_row(canvas, draw, rx, cy, dp, S):
    chip_font = _load_font(_FONT_BOLD, 15 * S)
    rt_font = _load_font(_FONT_BOLD, 20 * S)
    dim_font = _load_font(_FONT_MEDIUM, 19 * S)
    rt_r = 10 * S
    if dp["age_rating"]:
        rx, _ = _draw_age_rating_chip(
            canvas, rx, cy - (chip_font.getbbox("Hg")[3] + 10 * S) // 2,
            dp["age_rating"], chip_font, S,
        )
        rx += 14 * S
    if dp["rotten_tomatoes"]:
        rc = dp["rotten_tomatoes"].replace("%", "").strip()
        rx = _draw_rt_badge(
            draw, rx, cy, dp["rotten_tomatoes"],
            int(rc) >= 60 if rc.isdigit() else True, rt_r, rt_font, S,
        )
        rx += 14 * S
    if dp.get("metascore"):
        rx = _draw_info_pill(
            canvas, rx, cy, f"MC {dp['metascore']}", dim_font, S,
            fill=(102, 204, 51, 230), text_fill=(10, 20, 10, 255),
        )
    if dp["ep_str"]:
        rx = _draw_info_pill(canvas, rx, cy, dp["ep_str"], dim_font, S,
                             fill=(16, 185, 129), text_fill=(255, 255, 255, 255))
    if dp["runtime"]:
        rx = _draw_info_pill(canvas, rx, cy, dp["runtime"], dim_font, S, fill=_RUNTIME_PILL_COLOR)
    for idx, g in enumerate(dp["genres"][:3]):
        pc = dp["palette"][idx % len(dp["palette"])] if dp["palette"] else _GENRE_DEFAULT_COLOR
        rx = _draw_info_pill(canvas, rx, cy, g.capitalize(), dim_font, S, fill=pc)
    if dp["year"]:
        rx = _draw_info_pill(canvas, rx, cy, str(dp["year"]), dim_font, S, fill=_YEAR_PILL_COLOR)
    for qt in dp["quality_tags"][:3]:
        rx = _draw_info_pill(canvas, rx, cy, qt, dim_font, S,
                             fill=(240, 197, 24, 230), text_fill=(0, 0, 0, 255))
    return rx


def _build_standard_magic(dp, overlay_color, accent_color, brand_fill, brand_text_fill,
                           title_fill, meta_fill, desc_fill, genre_fill, genre_text,
                           quality_fill, quality_text, glow=False, glow_color=None,
                           particles=None, bar=None, scanlines=None,
                           border_top=None, border_bottom=None,
                           brand_icon="★", badge_18=False):
    S, W, H = dp["S"], dp["W"], dp["H"]
    canvas = dp["canvas"].copy()
    canvas.alpha_composite(Image.new("RGBA", (W, H), overlay_color))

    if scanlines:
        sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sld = ImageDraw.Draw(sl)
        for yy in range(0, H, int(4 * S)):
            sld.line([(0, yy), (W, yy)], fill=scanlines)
        canvas.alpha_composite(sl)

    if bar:
        _vertical_gradient_bar(canvas, bar["x"], bar["w"], H, bar["color"], bar.get("alpha", (0, 255)))

    if particles:
        _scatter_particles(
            canvas, W, H, particles["count"], particles["color"],
            particles.get("min_r", int(2 * S)), particles.get("max_r", int(6 * S)),
            particles.get("seed", 42), particles.get("y_range"),
        )

    if border_top:
        canvas.alpha_composite(
            Image.new("RGBA", (W, int(border_top[1] * S)), border_top[0]), dest=(0, 0)
        )
    if border_bottom:
        canvas.alpha_composite(
            Image.new("RGBA", (W, int(border_bottom[1] * S)), border_bottom[0]),
            dest=(0, H - int(border_bottom[1] * S)),
        )

    draw = ImageDraw.Draw(canvas)
    lm = int(60 * S)
    cw = dp["ppx"] - lm - int(30 * S)
    bf = _load_font(_FONT_BOLD, int(14 * S))
    bx = lm
    if badge_18:
        bx = _draw_18_plus_badge(canvas, bx, int(28 * S), S)
    _draw_badge(canvas, bx, int(30 * S), f"{brand_icon}  {dp['brand_text']}", bf,
                fill=brand_fill, text_fill=brand_text_fill, S=int(S))

    curr_y = int(86 * S)
    tf, tlines = _fit_title_with_badge(
        draw, dp["title"].upper(), cw, 0, max_lines=2, start_size=70 * S, min_size=38 * S
    )
    tlh = tf.getbbox("Hg")[3] + 6 * S
    for line in tlines:
        if glow and glow_color:
            _draw_glow_text(canvas, draw, lm, curr_y, line, tf, title_fill, glow_color, int(6 * S), W, H)
        else:
            draw.text((lm + 2, curr_y + 2), line, font=tf, fill=(0, 0, 0, 140))
            draw.text((lm, curr_y), line, font=tf, fill=title_fill)
        curr_y += tlh
    curr_y += int(10 * S)

    mf = _load_font(_FONT_MEDIUM, int(17 * S))
    parts = []
    if dp["year"]:
        parts.append(str(dp["year"]))
    if dp["rating"]:
        try:
            parts.append(f"★ {float(dp['rating']):.1f}")
        except (TypeError, ValueError):
            parts.append(f"★ {dp['rating']}")
    if dp["ep_str"]:
        parts.append(dp["ep_str"])
    if dp["runtime"]:
        parts.append(dp["runtime"])
    if parts:
        draw.text((lm, curr_y), "  ·  ".join(parts), font=mf, fill=meta_fill)
        curr_y += int(28 * S)
    if dp.get("credits"):
        draw.text((lm, curr_y), dp["credits"], font=mf, fill=meta_fill)
        curr_y += int(26 * S)

    ov_font = _load_font(_FONT_LIGHT, int(18 * S))
    for line in _truncate(draw, dp["desc"], ov_font, cw, 4):
        draw.text((lm, curr_y), line, font=ov_font, fill=desc_fill)
        curr_y += ov_font.getbbox("Hg")[3] + int(6 * S)
    curr_y += int(12 * S)

    dim_font = _load_font(_FONT_MEDIUM, int(15 * S))
    rx = lm
    pill_cy = curr_y + int(18 * S)
    for g in dp["genres"][:3]:
        rx = _draw_info_pill(canvas, rx, pill_cy, g.capitalize(), dim_font, S,
                             fill=genre_fill, text_fill=genre_text)
    for qt in dp["quality_tags"][:3]:
        rx = _draw_info_pill(canvas, rx, pill_cy, qt, dim_font, S,
                             fill=quality_fill, text_fill=quality_text)

    _attach_poster_card(canvas, dp["poster_img"], dp["ppx"], dp["ppy"], dp["panel_w"], dp["panel_h"], S)
    return canvas


def _magic_template_classic(dp):
    S, W, H = dp["S"], dp["W"], dp["H"]
    canvas = dp["canvas"].copy()
    draw = ImageDraw.Draw(canvas)
    lm = 56 * S
    cw = dp["ppx"] - lm - 40 * S
    star_r = 11 * S
    badge_gap = 16 * S
    rating_font = _load_font(_FONT_BOLD, 30 * S)
    imdb_font = _load_font(_FONT_BOLD, 15 * S)
    ipad_x, ipad_y = 8 * S, 5 * S
    rating_label, badge_w = "", 0
    if dp["rating"]:
        rating_label = f"{dp['rating']:.1f}" if isinstance(dp["rating"], float) else str(dp["rating"])
        badge_w = _imdb_badge_width(draw, rating_label, star_r, rating_font, imdb_font, ipad_x, S)
    tf, tl = _fit_title_with_badge(
        draw, dp["title"].upper(), cw, badge_w if dp["rating"] else 0,
        max_lines=2, start_size=68 * S, min_size=38 * S,
    )
    tlh = tf.getbbox("Hg")[3] + 4 * S
    ov_font = _load_font(_FONT_MEDIUM, 21 * S)
    ovl = _truncate(draw, dp["desc"], ov_font, cw, 4)
    ovlh = ov_font.getbbox("Hg")[3] + 6 * S
    dim_font = _load_font(_FONT_MEDIUM, 19 * S)
    row_h = max(34 * S, dim_font.getbbox("Hg")[3] + 14 * S)
    brand_font = _load_font(_FONT_BOLD, 18 * S)
    tg_size = 22 * S
    credit_h = 0
    credit_font = None
    if dp.get("credits"):
        credit_font = _load_font(_FONT_MEDIUM, 18 * S)
        credit_h = credit_font.getbbox("Hg")[3] + 14 * S
    total = tlh * len(tl) + credit_h + 27 * S + ovlh * len(ovl) + 22 * S + row_h + 20 * S + tg_size
    cy = max(40 * S, (H - total) // 2)
    for idx, line in enumerate(tl):
        draw.text((lm, cy), line, font=tf, fill=(255, 255, 255, 255))
        if dp["rating"] and idx == 0:
            bbox = draw.textbbox((0, 0), line, font=tf)
            _draw_imdb_rating_badge(
                canvas, lm + bbox[2] - bbox[0] + badge_gap, cy + tlh // 2,
                rating_label, star_r, rating_font, imdb_font, ipad_x, ipad_y, S,
            )
        cy += tlh
    if dp.get("credits") and credit_font:
        cy += 8 * S
        draw.text((lm, cy), dp["credits"], font=credit_font, fill=(210, 215, 225, 230))
        cy += credit_font.getbbox("Hg")[3] + 6 * S
    cy += 27 * S
    for line in ovl:
        draw.text((lm, cy), line, font=ov_font, fill=(220, 225, 235, 240))
        cy += ovlh
    cy += 22 * S
    _draw_info_row(canvas, draw, lm, cy + row_h // 2, dp, S)
    cy += row_h + 20 * S
    tg = _telegram_icon(tg_size)
    canvas.alpha_composite(tg, dest=(lm, cy))
    draw.text(
        (lm + tg_size + 10 * S, cy + (tg_size - brand_font.getbbox("Hg")[3]) // 2),
        dp["brand_text"], font=brand_font, fill=(255, 255, 255, 230),
    )
    _attach_poster_card(canvas, dp["poster_img"], dp["ppx"], dp["ppy"], dp["panel_w"], dp["panel_h"], S)
    return canvas


def _magic_template_netflix(dp):
    return _build_standard_magic(
        dp, overlay_color=(6, 6, 6, 175), accent_color=(229, 9, 20),
        brand_fill=(229, 9, 20, 255), brand_text_fill=(255, 255, 255, 255),
        title_fill=(255, 255, 255, 255), meta_fill=(229, 9, 20, 255),
        desc_fill=(210, 210, 210, 240), genre_fill=(40, 40, 40, 220),
        genre_text=(229, 9, 20, 255), quality_fill=(229, 9, 20, 200),
        quality_text=(255, 255, 255, 255), brand_icon="▶",
        bar={"x": int(44 * dp["S"]), "w": int(6 * dp["S"]), "color": (229, 9, 20)},
    )


def _magic_template_disney(dp):
    return _build_standard_magic(
        dp, overlay_color=(5, 15, 60, 200), accent_color=(0, 105, 218),
        brand_fill=(0, 105, 218, 240), brand_text_fill=(255, 255, 255, 255),
        title_fill=(255, 255, 255, 255), meta_fill=(100, 200, 255, 255),
        desc_fill=(200, 220, 255, 230), genre_fill=(0, 80, 180, 200),
        genre_text=(255, 255, 255, 255), quality_fill=(240, 197, 24, 220),
        quality_text=(0, 0, 0, 255), brand_icon="✦",
        glow=True, glow_color=(100, 180, 255, 60),
        particles={"count": 120, "color": (255, 255, 255), "min_r": 1, "max_r": 3,
                   "seed": 42, "y_range": (0, dp["H"] // 2)},
    )


def _magic_template_hbo(dp):
    return _build_standard_magic(
        dp, overlay_color=(8, 5, 2, 190), accent_color=(212, 175, 55),
        brand_fill=(212, 175, 55, 230), brand_text_fill=(0, 0, 0, 255),
        title_fill=(255, 248, 220, 255), meta_fill=(212, 175, 55, 240),
        desc_fill=(220, 215, 200, 230), genre_fill=(50, 40, 20, 220),
        genre_text=(212, 175, 55, 255), quality_fill=(212, 175, 55, 220),
        quality_text=(0, 0, 0, 255), brand_icon="◈",
        border_top=((212, 175, 55, 200), 3),
    )


def _magic_template_prime(dp):
    return _build_standard_magic(
        dp, overlay_color=(8, 18, 38, 185), accent_color=(0, 168, 204),
        brand_fill=(0, 168, 204, 230), brand_text_fill=(255, 255, 255, 255),
        title_fill=(255, 255, 255, 255), meta_fill=(0, 210, 255, 255),
        desc_fill=(200, 220, 240, 230), genre_fill=(0, 80, 110, 200),
        genre_text=(0, 210, 255, 255), quality_fill=(0, 168, 204, 220),
        quality_text=(0, 0, 0, 255), brand_icon="▸",
        bar={"x": int(44 * dp["S"]), "w": int(8 * dp["S"]), "color": (0, 168, 204)},
    )


def _magic_template_apple(dp):
    """Frosted left panel — applied to a copied pack so it is not discarded."""
    S, W, H = dp["S"], dp["W"], dp["H"]
    canvas = dp["canvas"].copy()
    pw = int(W * 0.56)
    crop = canvas.crop((0, 0, pw, H)).filter(ImageFilter.GaussianBlur(radius=int(18 * S))).convert("RGBA")
    frosted = Image.alpha_composite(crop, Image.new("RGBA", (pw, H), (255, 255, 255, 38))).convert("RGB")
    canvas.paste(frosted, (0, 0))
    dp = dict(dp)
    dp["canvas"] = canvas
    return _build_standard_magic(
        dp, overlay_color=(0, 0, 0, 0), accent_color=(255, 255, 255),
        brand_fill=(0, 0, 0, 170), brand_text_fill=(255, 255, 255, 255),
        title_fill=(255, 255, 255, 255), meta_fill=(230, 230, 230, 240),
        desc_fill=(230, 230, 230, 220), genre_fill=(255, 255, 255, 50),
        genre_text=(255, 255, 255, 255), quality_fill=(255, 255, 255, 160),
        quality_text=(0, 0, 0, 255), brand_icon="",
    )


def _magic_template_cyberpunk(dp):
    return _build_standard_magic(
        dp, overlay_color=(4, 2, 10, 200), accent_color=(200, 0, 255),
        brand_fill=(180, 0, 255, 230), brand_text_fill=(255, 255, 255, 255),
        title_fill=(0, 255, 255, 255), meta_fill=(200, 0, 255, 255),
        desc_fill=(180, 220, 255, 220), genre_fill=(60, 0, 100, 220),
        genre_text=(200, 0, 255, 255), quality_fill=(0, 200, 255, 200),
        quality_text=(0, 0, 0, 255), brand_icon="◉",
        glow=True, glow_color=(0, 255, 255, 50),
        scanlines=(255, 0, 255, 8),
        bar={"x": int(38 * dp["S"]), "w": int(80 * dp["S"]), "color": (200, 0, 255), "alpha": (0, 180)},
    )


def _magic_template_bollywood(dp):
    S, W, H = dp["S"], dp["W"], dp["H"]
    canvas = dp["canvas"].copy()
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for xx in range(W):
        t = xx / max(W - 1, 1)
        od.line([(xx, 0), (xx, H)], fill=(int(255 * (1 - t) + 180 * t), int(100 * (1 - t)), int(120 * t), 130))
    canvas.alpha_composite(ov)
    dp = dict(dp)
    dp["canvas"] = canvas
    return _build_standard_magic(
        dp, overlay_color=(0, 0, 0, 0), accent_color=(255, 215, 0),
        brand_fill=(255, 215, 0, 230), brand_text_fill=(120, 0, 0, 255),
        title_fill=(255, 255, 255, 255), meta_fill=(255, 240, 180, 255),
        desc_fill=(255, 250, 240, 230), genre_fill=(180, 0, 80, 200),
        genre_text=(255, 240, 180, 255), quality_fill=(255, 215, 0, 220),
        quality_text=(0, 0, 0, 255), brand_icon="✦",
        border_top=((255, 215, 0, 220), 6), border_bottom=((255, 215, 0, 220), 6),
    )


def _magic_template_anime(dp):
    return _build_standard_magic(
        dp, overlay_color=(14, 6, 28, 190), accent_color=(220, 80, 150),
        brand_fill=(200, 50, 120, 230), brand_text_fill=(255, 220, 240, 255),
        title_fill=(255, 240, 250, 255), meta_fill=(255, 180, 210, 255),
        desc_fill=(230, 210, 240, 220), genre_fill=(120, 20, 80, 200),
        genre_text=(255, 180, 220, 255), quality_fill=(255, 150, 190, 220),
        quality_text=(0, 0, 0, 255), brand_icon="✿",
        glow=True, glow_color=(255, 150, 200, 60),
        particles={"count": 60, "color": (255, 150, 180), "seed": 99},
        bar={"x": int(38 * dp["S"]), "w": int(70 * dp["S"]), "color": (220, 80, 150), "alpha": (0, 200)},
    )


def _magic_template_mono(dp):
    S, W, H = dp["S"], dp["W"], dp["H"]
    bg_g = dp["bg"].convert("L").convert("RGB")
    bg_bw = ImageEnhance.Brightness(Image.blend(dp["bg"], bg_g, 0.75)).enhance(0.55)
    dp = dict(dp)
    dp["canvas"] = bg_bw.convert("RGBA")
    dp["canvas"].alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 160)))
    return _build_standard_magic(
        dp, overlay_color=(0, 0, 0, 0), accent_color=(255, 255, 255),
        brand_fill=(255, 255, 255, 40), brand_text_fill=(255, 255, 255, 200),
        title_fill=(255, 255, 255, 255), meta_fill=(200, 200, 200, 240),
        desc_fill=(210, 210, 210, 220), genre_fill=(255, 255, 255, 40),
        genre_text=(255, 255, 255, 255), quality_fill=(255, 255, 255, 180),
        quality_text=(0, 0, 0, 255), brand_icon="—",
    )


def _magic_template_hotstar(dp):
    return _build_standard_magic(
        dp, overlay_color=(10, 15, 35, 195), accent_color=(22, 128, 201),
        brand_fill=(22, 128, 201, 240), brand_text_fill=(255, 255, 255, 255),
        title_fill=(255, 255, 255, 255), meta_fill=(90, 200, 250, 255),
        desc_fill=(200, 215, 235, 230), genre_fill=(15, 80, 140, 200),
        genre_text=(90, 200, 250, 255), quality_fill=(255, 204, 0, 220),
        quality_text=(0, 0, 0, 255), brand_icon="★",
    )


def _magic_template_crunchyroll(dp):
    return _build_standard_magic(
        dp, overlay_color=(10, 5, 0, 190), accent_color=(245, 130, 30),
        brand_fill=(245, 130, 30, 240), brand_text_fill=(255, 255, 255, 255),
        title_fill=(255, 255, 255, 255), meta_fill=(245, 160, 60, 255),
        desc_fill=(240, 220, 200, 230), genre_fill=(80, 40, 0, 200),
        genre_text=(245, 160, 60, 255), quality_fill=(245, 130, 30, 220),
        quality_text=(0, 0, 0, 255), brand_icon="▶",
        bar={"x": int(44 * dp["S"]), "w": int(6 * dp["S"]), "color": (245, 130, 30)},
    )


def _magic_template_peacock(dp):
    return _build_standard_magic(
        dp, overlay_color=(2, 18, 12, 190), accent_color=(0, 190, 120),
        brand_fill=(0, 190, 120, 240), brand_text_fill=(255, 255, 255, 255),
        title_fill=(255, 255, 255, 255), meta_fill=(0, 230, 150, 255),
        desc_fill=(200, 235, 220, 230), genre_fill=(0, 90, 60, 200),
        genre_text=(0, 230, 150, 255), quality_fill=(0, 190, 120, 220),
        quality_text=(0, 0, 0, 255), brand_icon="◆",
    )


def _magic_template_paramount(dp):
    return _build_standard_magic(
        dp, overlay_color=(2, 8, 30, 190), accent_color=(0, 100, 210),
        brand_fill=(0, 100, 210, 240), brand_text_fill=(255, 255, 255, 255),
        title_fill=(255, 255, 255, 255), meta_fill=(100, 180, 255, 255),
        desc_fill=(190, 210, 240, 230), genre_fill=(0, 60, 140, 200),
        genre_text=(100, 180, 255, 255), quality_fill=(0, 100, 210, 220),
        quality_text=(255, 255, 255, 255), brand_icon="▲",
        particles={"count": 50, "color": (100, 180, 255), "min_r": 1, "max_r": 2, "seed": 33,
                   "y_range": (0, dp["H"] // 3)},
    )


def _magic_template_horror(dp):
    return _build_standard_magic(
        dp, overlay_color=(10, 0, 0, 210), accent_color=(160, 0, 0),
        brand_fill=(140, 0, 0, 240), brand_text_fill=(255, 200, 200, 255),
        title_fill=(200, 0, 0, 255), meta_fill=(180, 80, 80, 255),
        desc_fill=(180, 160, 160, 220), genre_fill=(80, 0, 0, 220),
        genre_text=(255, 100, 100, 255), quality_fill=(160, 0, 0, 220),
        quality_text=(255, 200, 200, 255), brand_icon="☠",
        glow=True, glow_color=(200, 0, 0, 60),
        scanlines=(120, 0, 0, 6),
    )


def _magic_template_kdrama(dp):
    return _build_standard_magic(
        dp, overlay_color=(18, 5, 15, 185), accent_color=(255, 105, 140),
        brand_fill=(255, 105, 140, 240), brand_text_fill=(255, 255, 255, 255),
        title_fill=(255, 255, 255, 255), meta_fill=(255, 150, 180, 255),
        desc_fill=(240, 210, 225, 230), genre_fill=(120, 30, 60, 200),
        genre_text=(255, 150, 180, 255), quality_fill=(255, 105, 140, 220),
        quality_text=(0, 0, 0, 255), brand_icon="♡",
        particles={"count": 40, "color": (255, 180, 200), "min_r": 2, "max_r": 5, "seed": 77},
    )


def _magic_template_vintage(dp):
    S, W, H = dp["S"], dp["W"], dp["H"]
    bg_g = dp["bg"].convert("L").convert("RGB")
    gray = bg_g.split()[0]
    sepia = Image.merge("RGB", (
        gray.point(lambda p: min(255, int(p * 1.2))),
        gray.point(lambda p: min(255, int(p * 0.95))),
        gray.point(lambda p: min(255, int(p * 0.7))),
    ))
    dp = dict(dp)
    dp["canvas"] = sepia.convert("RGBA")
    dp["canvas"].alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 120)))
    return _build_standard_magic(
        dp, overlay_color=(0, 0, 0, 0), accent_color=(200, 160, 80),
        brand_fill=(180, 140, 60, 220), brand_text_fill=(40, 20, 0, 255),
        title_fill=(255, 240, 210, 255), meta_fill=(200, 170, 100, 255),
        desc_fill=(220, 200, 170, 220), genre_fill=(80, 60, 20, 200),
        genre_text=(200, 170, 100, 255), quality_fill=(180, 140, 60, 220),
        quality_text=(0, 0, 0, 255), brand_icon="✧",
    )


def _magic_template_adult(dp):
    return _build_standard_magic(
        dp, overlay_color=(15, 2, 5, 215), accent_color=(180, 20, 60),
        brand_fill=(180, 20, 60, 245), brand_text_fill=(255, 200, 210, 255),
        title_fill=(255, 220, 230, 255), meta_fill=(220, 80, 110, 255),
        desc_fill=(200, 170, 180, 220), genre_fill=(100, 10, 30, 220),
        genre_text=(255, 120, 150, 255), quality_fill=(180, 20, 60, 220),
        quality_text=(255, 220, 230, 255), brand_icon="♠", badge_18=True,
        glow=True, glow_color=(220, 30, 80, 50),
        bar={"x": int(38 * dp["S"]), "w": int(6 * dp["S"]), "color": (180, 20, 60)},
    )


def _magic_template_adult_purple(dp):
    return _build_standard_magic(
        dp, overlay_color=(10, 2, 20, 220), accent_color=(140, 30, 180),
        brand_fill=(140, 30, 180, 245), brand_text_fill=(255, 210, 255, 255),
        title_fill=(240, 200, 255, 255), meta_fill=(180, 80, 220, 255),
        desc_fill=(200, 180, 220, 220), genre_fill=(70, 10, 100, 220),
        genre_text=(200, 120, 255, 255), quality_fill=(140, 30, 180, 220),
        quality_text=(255, 220, 255, 255), brand_icon="♦", badge_18=True,
        glow=True, glow_color=(180, 50, 230, 50),
        scanlines=(140, 0, 180, 6),
        bar={"x": int(38 * dp["S"]), "w": int(8 * dp["S"]), "color": (140, 30, 180), "alpha": (0, 200)},
    )


def _magic_template_adult_gold(dp):
    return _build_standard_magic(
        dp, overlay_color=(8, 5, 0, 220), accent_color=(200, 150, 30),
        brand_fill=(200, 150, 30, 245), brand_text_fill=(0, 0, 0, 255),
        title_fill=(255, 230, 150, 255), meta_fill=(200, 160, 50, 255),
        desc_fill=(210, 195, 160, 220), genre_fill=(80, 60, 0, 220),
        genre_text=(200, 160, 50, 255), quality_fill=(200, 150, 30, 220),
        quality_text=(0, 0, 0, 255), brand_icon="♛", badge_18=True,
        border_top=((200, 150, 30, 200), 4), border_bottom=((200, 150, 30, 200), 4),
    )


_MAGIC_TEMPLATES = {
    "1": _magic_template_classic, "classic": _magic_template_classic,
    "2": _magic_template_netflix, "netflix": _magic_template_netflix,
    "3": _magic_template_disney, "disney": _magic_template_disney,
    "4": _magic_template_hbo, "hbo": _magic_template_hbo,
    "5": _magic_template_prime, "prime": _magic_template_prime,
    "6": _magic_template_apple, "apple": _magic_template_apple,
    "7": _magic_template_cyberpunk, "cyberpunk": _magic_template_cyberpunk,
    "8": _magic_template_bollywood, "bollywood": _magic_template_bollywood,
    "9": _magic_template_anime, "anime": _magic_template_anime,
    "10": _magic_template_mono, "mono": _magic_template_mono,
    "11": _magic_template_hotstar, "hotstar": _magic_template_hotstar,
    "12": _magic_template_crunchyroll, "crunchyroll": _magic_template_crunchyroll,
    "13": _magic_template_peacock, "peacock": _magic_template_peacock,
    "14": _magic_template_paramount, "paramount": _magic_template_paramount,
    "15": _magic_template_horror, "horror": _magic_template_horror,
    "16": _magic_template_kdrama, "kdrama": _magic_template_kdrama,
    "17": _magic_template_vintage, "vintage": _magic_template_vintage,
    "18": _magic_template_adult, "adult": _magic_template_adult,
    "19": _magic_template_adult_purple, "adult_purple": _magic_template_adult_purple,
    "20": _magic_template_adult_gold, "adult_gold": _magic_template_adult_gold,
}


def _make_magic_thumbnail_sync(backdrop_path, poster_path, output_path, title,
                                overview="", brand="TELLY_HUB", bot_handle="",
                                media_type="movie", year="", rating=0.0, genres=None,
                                runtime="", age_rating="", rotten_tomatoes="",
                                seasons=None, season=None, episode=None,
                                custom_channel="", quality_tags=None, filename="",
                                template="1", director="", actors="", metascore=""):
    dp = _magic_data_pack(
        backdrop_path, poster_path, title, overview, brand, year,
        rating, genres, runtime, age_rating, rotten_tomatoes,
        seasons, season, episode, custom_channel, quality_tags, filename,
        director=director, actors=actors, metascore=metascore,
    )
    renderer = _MAGIC_TEMPLATES.get(str(template).lower(), _magic_template_classic)
    _finish_and_save(renderer(dp), output_path, quality=97)


async def make_magic_thumbnail(backdrop_path, poster_path, output_path, title,
                                overview="", brand="TELLY_HUB", bot_handle="",
                                media_type="movie", year="", rating=0.0, genres=None,
                                runtime="", age_rating="", rotten_tomatoes="",
                                seasons=None, season=None, episode=None,
                                custom_channel="", quality_tags=None, filename="",
                                template="1", director="", actors="", metascore=""):
    """Generate 2560×1440 Magic Thumbnail — 20 templates available."""
    try:
        await asyncio.to_thread(
            _make_magic_thumbnail_sync,
            backdrop_path=backdrop_path, poster_path=poster_path,
            output_path=output_path, title=title, overview=overview,
            brand=brand, bot_handle=bot_handle, media_type=media_type,
            year=year, rating=rating, genres=genres, runtime=runtime,
            age_rating=age_rating, rotten_tomatoes=rotten_tomatoes,
            seasons=seasons, season=season, episode=episode,
            custom_channel=custom_channel, quality_tags=quality_tags,
            filename=filename, template=template,
            director=director, actors=actors, metascore=metascore,
        )
    finally:
        _release_native_memory()


# ══════════════════════════════════════════════════════════════════════════════
# ── PREMIERE THUMBNAIL  (12 Styles)
# ══════════════════════════════════════════════════════════════════════════════

def _premiere_base(backdrop_path):
    S = 2
    W, H = 1280 * S, 720 * S
    bg_src = _open_convert(backdrop_path, "RGB")
    bg = _sharpen_image(_cover_crop(bg_src, W, H).filter(ImageFilter.GaussianBlur(radius=0.8 * S)))
    return S, W, H, bg


def _premiere_meta_pills(canvas, draw, lm, curr_y, S, rating, year, runtime, season, episode):
    dim_font = _load_font(_FONT_MEDIUM, int(20 * S))
    rx = lm
    if season is not None and episode is not None:
        rx = _draw_info_pill(canvas, rx, curr_y, f"S{season:02d} E{episode:02d}", dim_font, S,
                             fill=(229, 9, 20, 240))
    if rating:
        rx = _draw_info_pill(canvas, rx, curr_y, f"★ {rating:.1f}", dim_font, S,
                             fill=(245, 197, 24, 240), text_fill=(0, 0, 0, 255))
    if year:
        rx = _draw_info_pill(canvas, rx, curr_y, str(year), dim_font, S, fill=(40, 40, 40, 220))
    if runtime:
        rx = _draw_info_pill(canvas, rx, curr_y, runtime, dim_font, S, fill=(60, 60, 80, 220))
    return rx


def _premiere_desc(draw, lm, curr_y, S, max_w, overview, filename):
    ov_font = _load_font(_FONT_MEDIUM, int(20 * S))
    desc = overview.strip() if overview else (
        f"File: {filename}" if filename else "No description available."
    )
    for line in _truncate(draw, desc, ov_font, int(max_w), 3):
        draw.text((lm, curr_y), line, font=ov_font, fill=(220, 225, 235, 240))
        curr_y += int(28 * S)
    return curr_y


def _premiere_classic(S, W, H, canvas, title, overview, brand, year, rating,
                       genres, runtime, season, episode, custom_channel, filename):
    canvas.alpha_composite(_horizontal_scrim(W, H))
    draw = ImageDraw.Draw(canvas)
    lm = int(60 * S)
    tf = _load_font(_FONT_BOLD, int(64 * S))
    draw.text((lm, int(80 * S)), title.upper(), font=tf, fill=(255, 255, 255, 255))
    _premiere_meta_pills(canvas, draw, lm, int(175 * S), S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, int(235 * S), S, W * 0.58, overview, filename)
    _draw_laurel_branch(draw, W - int(100 * S), H // 2, int(220 * S), -1, 9, (235, 178, 62, 220), S)


def _premiere_netflix(S, W, H, canvas, title, overview, brand, year, rating,
                       genres, runtime, season, episode, custom_channel, filename):
    canvas.alpha_composite(Image.new("RGBA", (W, H), (8, 5, 2, 210)))
    canvas.alpha_composite(Image.new("RGBA", (W, int(8 * S)), (229, 9, 20, 255)), dest=(0, H - int(8 * S)))
    draw = ImageDraw.Draw(canvas)
    lm = int(80 * S)
    _draw_badge(canvas, lm, int(40 * S), f"▶  {brand}", _load_font(_FONT_BOLD, int(15 * S)),
                fill=(229, 9, 20, 255), text_fill=(255, 255, 255, 255), S=int(S))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.65), 0,
                                    max_lines=2, start_size=80 * S, min_size=44 * S)
    cy = int(130 * S)
    for line in tl:
        draw.text((lm, cy), line, font=tf, fill=(255, 255, 255, 255))
        cy += tf.getbbox("Hg")[3] + int(8 * S)
    cy += int(14 * S)
    _premiere_meta_pills(canvas, draw, lm, cy, S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, cy + int(48 * S), S, W * 0.65, overview, filename)


def _premiere_gold(S, W, H, canvas, title, overview, brand, year, rating,
                    genres, runtime, season, episode, custom_channel, filename):
    canvas.alpha_composite(Image.new("RGBA", (W, H), (10, 8, 2, 200)))
    canvas.alpha_composite(Image.new("RGBA", (W, int(4 * S)), (212, 175, 55, 255)))
    canvas.alpha_composite(Image.new("RGBA", (W, int(4 * S)), (212, 175, 55, 255)), dest=(0, H - int(4 * S)))
    draw = ImageDraw.Draw(canvas)
    lm = int(80 * S)
    _draw_badge(canvas, lm, int(18 * S), f"◈  {brand}", _load_font(_FONT_BOLD, int(14 * S)),
                fill=(212, 175, 55, 230), text_fill=(0, 0, 0, 255), S=int(S))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.62), 0,
                                    max_lines=2, start_size=80 * S, min_size=44 * S)
    cy = int(80 * S)
    for line in tl:
        draw.text((lm + 2, cy + 2), line, font=tf, fill=(0, 0, 0, 150))
        draw.text((lm, cy), line, font=tf, fill=(255, 248, 210, 255))
        cy += tf.getbbox("Hg")[3] + int(8 * S)
    cy += int(10 * S)
    draw.line([(lm, cy), (lm + int(W * 0.28), cy)], fill=(212, 175, 55, 180), width=int(2 * S))
    cy += int(16 * S)
    _premiere_meta_pills(canvas, draw, lm, cy, S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, cy + int(48 * S), S, W * 0.62, overview, filename)
    _draw_laurel_branch(draw, int(W * 0.78), H // 2, int(200 * S), -1, 9, (212, 175, 55, 230), S)
    _draw_laurel_branch(draw, int(W * 0.94), H // 2, int(200 * S), 1, 9, (212, 175, 55, 230), S)


def _premiere_neon(S, W, H, canvas, title, overview, brand, year, rating,
                    genres, runtime, season, episode, custom_channel, filename):
    canvas.alpha_composite(Image.new("RGBA", (W, H), (4, 2, 12, 210)))
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sld = ImageDraw.Draw(sl)
    for yy in range(0, H, int(4 * S)):
        sld.line([(0, yy), (W, yy)], fill=(0, 255, 200, 6))
    canvas.alpha_composite(sl)
    draw = ImageDraw.Draw(canvas)
    lm = int(80 * S)
    _draw_badge(canvas, lm, int(30 * S), f"◉  {brand}", _load_font(_FONT_BOLD, int(14 * S)),
                fill=(0, 230, 180, 230), text_fill=(0, 0, 0, 255), S=int(S))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.64), 0,
                                    max_lines=2, start_size=78 * S, min_size=42 * S)
    cy = int(100 * S)
    for line in tl:
        _draw_glow_text(canvas, draw, lm, cy, line, tf, (0, 255, 200, 255), (0, 230, 180, 55), int(7 * S), W, H)
        cy += tf.getbbox("Hg")[3] + int(8 * S)
    cy += int(14 * S)
    _premiere_meta_pills(canvas, draw, lm, cy, S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, cy + int(48 * S), S, W * 0.64, overview, filename)


def _premiere_minimal(S, W, H, canvas, title, overview, brand, year, rating,
                       genres, runtime, season, episode, custom_channel, filename):
    bg_g = canvas.convert("RGB").convert("L").convert("RGB")
    blended = Image.blend(canvas.convert("RGB"), bg_g, 0.85)
    blended = ImageEnhance.Brightness(blended).enhance(0.45)
    canvas.paste(blended.convert("RGB"))
    canvas.alpha_composite(Image.new("RGBA", (int(4 * S), H), (255, 255, 255, 200)), dest=(int(60 * S), 0))
    draw = ImageDraw.Draw(canvas)
    lm = int(78 * S)
    draw.text((lm, int(36 * S)), brand.upper(),
              font=_load_font(_FONT_BOLD, int(14 * S)), fill=(255, 255, 255, 180))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.64), 0,
                                    max_lines=2, start_size=76 * S, min_size=42 * S)
    cy = int(90 * S)
    for line in tl:
        draw.text((lm, cy), line, font=tf, fill=(255, 255, 255, 255))
        cy += tf.getbbox("Hg")[3] + int(6 * S)
    cy += int(8 * S)
    draw.line([(lm, cy), (lm + int(W * 0.22), cy)], fill=(255, 255, 255, 100), width=int(1 * S))
    cy += int(14 * S)
    mf = _load_font(_FONT_MEDIUM, int(18 * S))
    try:
        rating_bit = f"★ {float(rating):.1f}" if rating else ""
    except (TypeError, ValueError):
        rating_bit = f"★ {rating}" if rating else ""
    parts = [p for p in [str(year) if year else "", rating_bit, runtime or ""] if p]
    if parts:
        draw.text((lm, cy), "   ·   ".join(parts), font=mf, fill=(190, 190, 190, 240))
        cy += int(28 * S)
    _premiere_desc(draw, lm, cy, S, W * 0.64, overview, filename)


def _premiere_anime(S, W, H, canvas, title, overview, brand, year, rating,
                     genres, runtime, season, episode, custom_channel, filename):
    canvas.alpha_composite(Image.new("RGBA", (W, H), (14, 5, 28, 200)))
    _scatter_particles(canvas, W, H, 80, (255, 140, 180), int(2 * S), int(8 * S), seed=77)
    draw = ImageDraw.Draw(canvas)
    lm = int(80 * S)
    _draw_badge(canvas, lm, int(30 * S), f"✿  {brand}  ✿", _load_font(_FONT_BOLD, int(14 * S)),
                fill=(200, 50, 120, 230), text_fill=(255, 220, 240, 255), S=int(S))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.62), 0,
                                    max_lines=2, start_size=78 * S, min_size=42 * S)
    cy = int(100 * S)
    for line in tl:
        _draw_glow_text(canvas, draw, lm, cy, line, tf, (255, 230, 245, 255), (255, 150, 200, 55), int(5 * S), W, H)
        cy += tf.getbbox("Hg")[3] + int(8 * S)
    cy += int(12 * S)
    _premiere_meta_pills(canvas, draw, lm, cy, S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, cy + int(48 * S), S, W * 0.62, overview, filename)
    _draw_laurel_branch(draw, W - int(100 * S), H // 2, int(200 * S), -1, 9, (220, 100, 150, 200), S)


def _premiere_horror(S, W, H, canvas, title, overview, brand, year, rating,
                      genres, runtime, season, episode, custom_channel, filename):
    canvas.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 0, 220)))
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sld = ImageDraw.Draw(sl)
    for yy in range(0, H, int(3 * S)):
        sld.line([(0, yy), (W, yy)], fill=(120, 0, 0, 8))
    canvas.alpha_composite(sl)
    draw = ImageDraw.Draw(canvas)
    lm = int(80 * S)
    _draw_badge(canvas, lm, int(30 * S), f"☠  {brand}", _load_font(_FONT_BOLD, int(14 * S)),
                fill=(140, 0, 0, 240), text_fill=(255, 200, 200, 255), S=int(S))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.64), 0,
                                    max_lines=2, start_size=78 * S, min_size=42 * S)
    cy = int(100 * S)
    for line in tl:
        _draw_glow_text(canvas, draw, lm, cy, line, tf, (200, 0, 0, 255), (180, 0, 0, 60), int(7 * S), W, H)
        cy += tf.getbbox("Hg")[3] + int(8 * S)
    cy += int(14 * S)
    _premiere_meta_pills(canvas, draw, lm, cy, S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, cy + int(48 * S), S, W * 0.64, overview, filename)


def _premiere_kdrama(S, W, H, canvas, title, overview, brand, year, rating,
                      genres, runtime, season, episode, custom_channel, filename):
    canvas.alpha_composite(Image.new("RGBA", (W, H), (18, 5, 15, 195)))
    _scatter_particles(canvas, W, H, 50, (255, 180, 200), int(2 * S), int(5 * S), seed=55)
    draw = ImageDraw.Draw(canvas)
    lm = int(80 * S)
    _draw_badge(canvas, lm, int(30 * S), f"♡  {brand}", _load_font(_FONT_BOLD, int(14 * S)),
                fill=(255, 105, 140, 240), text_fill=(255, 255, 255, 255), S=int(S))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.64), 0,
                                    max_lines=2, start_size=78 * S, min_size=42 * S)
    cy = int(100 * S)
    for line in tl:
        draw.text((lm, cy), line, font=tf, fill=(255, 255, 255, 255))
        cy += tf.getbbox("Hg")[3] + int(8 * S)
    cy += int(12 * S)
    _premiere_meta_pills(canvas, draw, lm, cy, S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, cy + int(48 * S), S, W * 0.64, overview, filename)


def _premiere_adult(S, W, H, canvas, title, overview, brand, year, rating,
                     genres, runtime, season, episode, custom_channel, filename):
    canvas.alpha_composite(Image.new("RGBA", (W, H), (15, 2, 5, 220)))
    _vertical_gradient_bar(canvas, int(38 * S), int(6 * S), H, (180, 20, 60))
    draw = ImageDraw.Draw(canvas)
    lm = int(80 * S)
    bx = _draw_18_plus_badge(canvas, lm, int(28 * S), S)
    _draw_badge(canvas, bx, int(30 * S), f"♠  {brand}", _load_font(_FONT_BOLD, int(14 * S)),
                fill=(180, 20, 60, 245), text_fill=(255, 200, 210, 255), S=int(S))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.62), 0,
                                    max_lines=2, start_size=76 * S, min_size=42 * S)
    cy = int(100 * S)
    for line in tl:
        _draw_glow_text(canvas, draw, lm, cy, line, tf, (255, 220, 230, 255), (220, 30, 80, 50), int(6 * S), W, H)
        cy += tf.getbbox("Hg")[3] + int(8 * S)
    cy += int(14 * S)
    _premiere_meta_pills(canvas, draw, lm, cy, S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, cy + int(48 * S), S, W * 0.62, overview, filename)


def _premiere_adult_purple(S, W, H, canvas, title, overview, brand, year, rating,
                            genres, runtime, season, episode, custom_channel, filename):
    canvas.alpha_composite(Image.new("RGBA", (W, H), (10, 2, 20, 225)))
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sld = ImageDraw.Draw(sl)
    for yy in range(0, H, int(4 * S)):
        sld.line([(0, yy), (W, yy)], fill=(140, 0, 180, 6))
    canvas.alpha_composite(sl)
    _vertical_gradient_bar(canvas, int(38 * S), int(8 * S), H, (140, 30, 180), (0, 200))
    draw = ImageDraw.Draw(canvas)
    lm = int(80 * S)
    bx = _draw_18_plus_badge(canvas, lm, int(28 * S), S)
    _draw_badge(canvas, bx, int(30 * S), f"♦  {brand}", _load_font(_FONT_BOLD, int(14 * S)),
                fill=(140, 30, 180, 245), text_fill=(255, 210, 255, 255), S=int(S))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.62), 0,
                                    max_lines=2, start_size=76 * S, min_size=42 * S)
    cy = int(100 * S)
    for line in tl:
        _draw_glow_text(canvas, draw, lm, cy, line, tf, (240, 200, 255, 255), (180, 50, 230, 50), int(6 * S), W, H)
        cy += tf.getbbox("Hg")[3] + int(8 * S)
    cy += int(14 * S)
    _premiere_meta_pills(canvas, draw, lm, cy, S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, cy + int(48 * S), S, W * 0.62, overview, filename)


def _premiere_adult_gold(S, W, H, canvas, title, overview, brand, year, rating,
                          genres, runtime, season, episode, custom_channel, filename):
    canvas.alpha_composite(Image.new("RGBA", (W, H), (8, 5, 0, 225)))
    canvas.alpha_composite(Image.new("RGBA", (W, int(4 * S)), (200, 150, 30, 200)))
    canvas.alpha_composite(Image.new("RGBA", (W, int(4 * S)), (200, 150, 30, 200)), dest=(0, H - int(4 * S)))
    draw = ImageDraw.Draw(canvas)
    lm = int(80 * S)
    bx = _draw_18_plus_badge(canvas, lm, int(18 * S), S)
    _draw_badge(canvas, bx, int(20 * S), f"♛  {brand}", _load_font(_FONT_BOLD, int(14 * S)),
                fill=(200, 150, 30, 245), text_fill=(0, 0, 0, 255), S=int(S))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.62), 0,
                                    max_lines=2, start_size=76 * S, min_size=42 * S)
    cy = int(90 * S)
    for line in tl:
        draw.text((lm + 2, cy + 2), line, font=tf, fill=(0, 0, 0, 150))
        draw.text((lm, cy), line, font=tf, fill=(255, 230, 150, 255))
        cy += tf.getbbox("Hg")[3] + int(8 * S)
    cy += int(10 * S)
    draw.line([(lm, cy), (lm + int(W * 0.25), cy)], fill=(200, 150, 30, 180), width=int(2 * S))
    cy += int(16 * S)
    _premiere_meta_pills(canvas, draw, lm, cy, S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, cy + int(48 * S), S, W * 0.62, overview, filename)
    _draw_laurel_branch(draw, int(W * 0.80), H // 2, int(180 * S), -1, 8, (200, 150, 30, 220), S)
    _draw_laurel_branch(draw, int(W * 0.96), H // 2, int(180 * S), 1, 8, (200, 150, 30, 220), S)


def _premiere_vintage(S, W, H, canvas, title, overview, brand, year, rating,
                       genres, runtime, season, episode, custom_channel, filename):
    bg_g = canvas.convert("RGB").convert("L").convert("RGB")
    gray = bg_g.split()[0]
    sepia = Image.merge("RGB", (
        gray.point(lambda p: min(255, int(p * 1.15))),
        gray.point(lambda p: min(255, int(p * 0.90))),
        gray.point(lambda p: min(255, int(p * 0.65))),
    ))
    canvas.paste(sepia.convert("RGBA"))
    canvas.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 130)))
    draw = ImageDraw.Draw(canvas)
    lm = int(80 * S)
    _draw_badge(canvas, lm, int(30 * S), f"✧  {brand}", _load_font(_FONT_BOLD, int(14 * S)),
                fill=(180, 140, 60, 220), text_fill=(40, 20, 0, 255), S=int(S))
    tf, tl = _fit_title_with_badge(draw, title.upper(), int(W * 0.64), 0,
                                    max_lines=2, start_size=78 * S, min_size=42 * S)
    cy = int(100 * S)
    for line in tl:
        draw.text((lm, cy), line, font=tf, fill=(255, 240, 210, 255))
        cy += tf.getbbox("Hg")[3] + int(8 * S)
    cy += int(12 * S)
    _premiere_meta_pills(canvas, draw, lm, cy, S, rating, year, runtime, season, episode)
    _premiere_desc(draw, lm, cy + int(48 * S), S, W * 0.64, overview, filename)


_PREMIERE_STYLES = {
    "1": _premiere_classic, "classic": _premiere_classic,
    "2": _premiere_netflix, "netflix": _premiere_netflix,
    "3": _premiere_gold, "gold": _premiere_gold,
    "4": _premiere_neon, "neon": _premiere_neon,
    "5": _premiere_minimal, "minimal": _premiere_minimal,
    "6": _premiere_anime, "anime": _premiere_anime,
    "7": _premiere_horror, "horror": _premiere_horror,
    "8": _premiere_kdrama, "kdrama": _premiere_kdrama,
    "9": _premiere_adult, "adult": _premiere_adult,
    "10": _premiere_adult_purple, "adult_purple": _premiere_adult_purple,
    "11": _premiere_adult_gold, "adult_gold": _premiere_adult_gold,
    "12": _premiere_vintage, "vintage": _premiere_vintage,
}


def _make_premiere_thumbnail_sync(backdrop_path, output_path, title,
                                   overview="", brand="TELLY_HUB", year="", rating=0.0,
                                   genres=None, runtime="", season=None, episode=None,
                                   custom_channel="", filename="", style="classic"):
    S, W, H, bg = _premiere_base(backdrop_path)
    canvas = bg.convert("RGBA")
    renderer = _PREMIERE_STYLES.get(str(style).lower(), _premiere_classic)
    renderer(S, W, H, canvas, title, overview, brand, year, rating,
             genres, runtime, season, episode, custom_channel, filename)
    _finish_and_save(canvas, output_path, quality=97)


async def make_premiere_thumbnail(backdrop_path, output_path, title,
                                   overview="", brand="TELLY_HUB", year="", rating=0.0,
                                   genres=None, runtime="", season=None, episode=None,
                                   custom_channel="", filename="", style="classic"):
    """Generate Premiere Thumbnail — 12 styles available."""
    try:
        await asyncio.to_thread(
            _make_premiere_thumbnail_sync,
            backdrop_path=backdrop_path, output_path=output_path,
            title=title, overview=overview, brand=brand,
            year=year, rating=rating, genres=genres,
            runtime=runtime, season=season, episode=episode,
            custom_channel=custom_channel, filename=filename, style=style,
        )
    finally:
        _release_native_memory()
