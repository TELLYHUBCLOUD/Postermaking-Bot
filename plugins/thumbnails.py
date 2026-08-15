"""
Magic & Premiere Thumbnail Commands
===================================
Advanced callback-driven thumbnail generator.

Flow:
    1.  /magic <name>  or  /premiere <name>
    2.  Bot searches TMDB and shows a list of matching titles.
        -> user taps the CORRECT one via an inline button
    3.  Bot shows the template / style picker.
        -> user taps a template (Magic: 20 | Premiere: 12)
    4.  Bot downloads backdrop+poster, renders, and sends the image.

If the user has set a **default template/style** in `/settings`, step 3 is
skipped and their preferred style is used automatically.

Per-user values (brand, channel badge, quality tags) come from MongoDB and
override the bot defaults.
"""
import logging
import os
import tempfile

import requests

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from utils.db import db
from api.tmdb_client import search_media_candidates, get_tmdb_media_by_id
from thumbnail_generator import make_magic_thumbnail, make_premiere_thumbnail
from plugins.thumbnail_choices import MAGIC_CHOICES, PREMIERE_CHOICES

# Per-user settings (see plugins/user_settings.py)
from plugins.user_settings import (
    KEY_BRAND as _S_KEY_BRAND,
    KEY_CHANNEL as _S_KEY_CHANNEL,
    user_setting_quality_tags,
    user_setting_default_template,
    user_setting_default_style,
)

logger = logging.getLogger(__name__)

DEFAULT_BRAND = Config.THUMBNAIL_BRAND


# ── Per-user helpers ─────────────────────────────────────────────────────────
async def _get_user_brand(user_id: int) -> str:
    brand = await db.get_user_setting(user_id, _S_KEY_BRAND, DEFAULT_BRAND)
    brand = (brand or DEFAULT_BRAND).lstrip("@")
    return f"@{brand}" if not brand.startswith("@") else brand


async def _get_user_channel(user_id: int) -> str:
    return await db.get_user_setting(user_id, _S_KEY_CHANNEL, "") or ""


async def _group_authorized(message) -> bool:
    if message.chat.type not in ("group", "supergroup"):
        return True
    user_ok = await db.is_authorized(message.from_user.id)
    chat_ok = await db.is_authorized(message.chat.id)
    return user_ok or chat_ok


def _download_image(url: str, prefix: str):
    if not url:
        return None
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
        fd, path = tempfile.mkstemp(suffix=".jpg", prefix=f"thumb_{prefix}_")
        with os.fdopen(fd, "wb") as f:
            f.write(r.content)
        return path
    except Exception as e:
        logger.warning(f"Download failed ({prefix}): {e}")
        return None


def _cleanup(*paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


def _pick_backdrop(data):
    imgs = data.get("images", {}) or {}
    bd = imgs.get("backdrops", {}) or {}
    if bd.get("en"):
        return bd["en"][0]
    if bd.get("all"):
        return bd["all"][0]
    return data.get("poster_url")


def _pick_poster(data):
    imgs = data.get("images", {}) or {}
    ps = imgs.get("posters", {}) or {}
    if ps.get("en"):
        return ps["en"][0]
    if ps.get("all"):
        return ps["all"][0]
    return data.get("poster_url")


def _genres_list(data):
    g = (data.get("genres") or "").split(",")
    return [x.strip() for x in g if x.strip()]


# ── Step 1: command entry ───────────────────────────────────────────────────
async def _start_thumbnail(client, message, mode):
    if not await _group_authorized(message):
        await message.reply_text(
            "⛔ **Not Authorized**\nThis bot is only allowed in authorized groups.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👑 Contact Owner", url=Config.OWNER_CONTACT_URL)
            ]]),
            quote=True,
        )
        return

    if len(message.command) < 2:
        kind = "Magic" if mode == "magic" else "Premiere"
        await message.reply_text(
            f"🎬 **Usage:** `/{mode} <movie or TV name>`\n"
            f"Example: `/{mode} Inception`\n\n"
            f"Generate a **{kind}** thumbnail — "
            f"{len(MAGIC_CHOICES if mode=='magic' else PREMIERE_CHOICES)} styles to pick from.",
            quote=True,
        )
        return

    query = message.text.split(None, 1)[1].strip()
    status = await message.reply_text(f"🔎 Searching TMDB for `{query}`…", quote=True)

    try:
        candidates = search_media_candidates(query, limit=6)
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        await status.edit_text("❌ **Error while searching.** Please try again later.")
        return

    if not candidates:
        await status.edit_text(f"❌ **Not Found.**\nNo movie/TV found for `{query}`.")
        return

    buttons = []
    for c in candidates:
        label = f"🎬 {c['title']}" + (f" ({c['year']})" if c.get("year") else "")
        media_tag = "movie" if c["media_type"] == "movie" else "tv"
        buttons.append([InlineKeyboardButton(
            label, callback_data=f"{mode}_sel_{media_tag}_{c['media_id']}"
        )])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="thumb_cancel")])

    await status.edit_text(
        f"❓ **Found {len(candidates)} matches for** `{query}`.\n"
        f"**Select the correct one** to continue:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_message(filters.command(["magic", "premiere"]))
async def thumb_cmd(client, message):
    mode = message.command[0]
    await _start_thumbnail(client, message, mode)


# ── Step 2: title chosen ────────────────────────────────────────────────────
def _choice_keyboard(mode, media_tag, media_id):
    choices = MAGIC_CHOICES if mode == "magic" else PREMIERE_CHOICES
    cb = "tpl" if mode == "magic" else "stl"
    rows = [choices[i:i + 2] for i in range(0, len(choices), 2)]
    buttons = []
    for row in rows:
        r = []
        for key, label in row:
            r.append(InlineKeyboardButton(
                label, callback_data=f"{mode}_{cb}_{media_tag}_{media_id}_{key}"
            ))
        buttons.append(r)
    buttons.append([
        InlineKeyboardButton("◀ Back to Titles", callback_data="thumb_back"),
        InlineKeyboardButton("❌ Cancel", callback_data="thumb_cancel"),
    ])
    return InlineKeyboardMarkup(buttons)


@Client.on_callback_query(filters.regex(r"^(magic|premiere)_sel_(movie|tv)_(\d+)$"))
async def title_selected(client, callback_query):
    import re as _re
    m = _re.match(r"^(magic|premiere)_sel_(movie|tv)_(\d+)$", callback_query.data)
    mode, media_tag, media_id = m.group(1), m.group(2), m.group(3)
    user_id = callback_query.from_user.id

    # Auto-use the user's default style/template if they set one.
    if mode == "magic":
        default = await user_setting_default_template(user_id)
        if default:
            await callback_query.message.edit_text("⚡ **Using your default template…**")
            await _render_and_send(client, callback_query.message, mode, media_tag, media_id, default)
            await callback_query.answer()
            return
    else:
        default = await user_setting_default_style(user_id)
        if default:
            await callback_query.message.edit_text("⚡ **Using your default style…**")
            await _render_and_send(client, callback_query.message, mode, media_tag, media_id, default)
            await callback_query.answer()
            return

    kind = "Magic" if mode == "magic" else "Premiere"
    await callback_query.message.edit_text(
        f"✨ **Choose a {kind} template:**\n"
        f"`{media_id}` · {media_tag}",
        reply_markup=_choice_keyboard(mode, media_tag, media_id),
    )
    await callback_query.answer()


@Client.on_callback_query(filters.regex(r"^thumb_back$"))
async def back_to_search(client, callback_query):
    await callback_query.message.edit_text(
        "↩️ Use the command again with the title:\n`/magic <name>` or `/premiere <name>`"
    )
    await callback_query.answer()


@Client.on_callback_query(filters.regex(r"^thumb_cancel$"))
async def thumb_cancel(client, callback_query):
    await callback_query.message.edit_text("🚫 **Cancelled.**")
    await callback_query.answer()


# ── Step 3: template chosen → generate & send ──────────────────────────────
async def _render_and_send(client, message, mode, media_tag, media_id, style):
    """Shared generation routine (used by picker & auto-default flows)."""
    user_id = message.from_user.id

    # premium & daily limit
    is_premium = await db.is_premium_user(user_id)
    rank = (await db.get_premium_user_rank(user_id)) if is_premium else "default"
    limit = Config.TASK_LIMITS.get(rank, Config.TASK_LIMITS["default"])
    allowed = await db.check_and_update_usage(user_id, limit)
    if not allowed:
        await message.edit_text(
            f"🚫 **Daily Limit Reached!**\nYou've used all **{limit}** generations today.\n"
            f"Upgrade to Premium for more.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💎 Upgrade", url=Config.OWNER_CONTACT_URL)
            ]]),
        )
        return

    await message.edit_text("⏳ **Fetching data…**")

    # per-user brand / channel / quality tags
    brand = await _get_user_brand(user_id)
    custom_channel = await _get_user_channel(user_id)
    quality_tags = await user_setting_quality_tags(user_id)

    backdrop = poster = out_path = None
    try:
        data = get_tmdb_media_by_id(media_tag, int(media_id))
        if not data:
            await message.edit_text("❌ **Could not load this title.**")
            return

        await message.edit_text("📥 **Downloading images…**")
        backdrop = _download_image(_pick_backdrop(data), "bd")
        poster = _download_image(_pick_poster(data), "po")
        if not backdrop:
            backdrop = poster
        if not backdrop:
            await message.edit_text("❌ **No images available for this title.**")
            return

        fd, out_path = tempfile.mkstemp(suffix=".jpg", prefix="thumb_out_")
        os.close(fd)

        await message.edit_text("🎨 **Rendering…**")
        title = data.get("title") or data.get("localized_title") or "Unknown"
        rating = data.get("rating") or 0
        runtime = data.get("runtime") or ""
        year = data.get("year") or ""
        age_rating = data.get("certificates") or ""
        seasons = data.get("seasons")
        genres = _genres_list(data)

        if mode == "magic":
            await make_magic_thumbnail(
                backdrop_path=backdrop, poster_path=poster or backdrop,
                output_path=out_path, title=title, overview=data.get("plot") or "",
                brand=brand, year=year, rating=rating, genres=genres,
                runtime=runtime, age_rating=age_rating,
                seasons=seasons, season=None, episode=None,
                custom_channel=custom_channel,
                quality_tags=quality_tags, filename=data.get("query") or title,
                template=style, director=data.get("director") or "",
                actors=data.get("cast") or "",
            )
        else:
            await make_premiere_thumbnail(
                backdrop_path=backdrop, output_path=out_path,
                title=title, overview=data.get("plot") or "",
                brand=brand, year=year, rating=rating, genres=genres,
                runtime=runtime, season=None, episode=None,
                custom_channel=custom_channel,
                filename=data.get("query") or title, style=style,
            )

        kind = "Magic" if mode == "magic" else "Premiere"
        caption = (
            f"✨ **{kind} Thumbnail — {title}** ({year})\n"
            f"⭐ {rating:.1f}  |  {runtime}\n"
            f"🎨 Style: `{style}`\n\n"
            f"*Powered by {Config.BRANDING['powered_by']}*"
        )
        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎨 More Templates", callback_data="thumb_back"),
            InlineKeyboardButton("📢 Channel", url=Config.UPDATE_CHANNEL_URL),
        ]])
        await client.send_photo(
            chat_id=message.chat.id,
            photo=out_path,
            caption=caption,
            reply_markup=buttons,
        )
        await message.delete()
    except Exception as e:
        logger.error(f"Thumbnail generation error: {e}", exc_info=True)
        try:
            await message.edit_text("⚠️ **Error generating thumbnail.** Please try again later.")
        except Exception:
            pass
    finally:
        _cleanup(backdrop, poster, out_path)


@Client.on_callback_query(filters.regex(r"^(magic|premiere)_(tpl|stl)_(movie|tv)_(\d+)_(.+)$"))
async def template_chosen(client, callback_query):
    import re as _re
    m = _re.match(r"^(magic|premiere)_(tpl|stl)_(movie|tv)_(\d+)_(.+)$", callback_query.data)
    mode, media_tag, media_id, style = m.group(1), m.group(3), m.group(4), m.group(5)
    await _render_and_send(client, callback_query.message, mode, media_tag, media_id, style)
    await callback_query.answer()
