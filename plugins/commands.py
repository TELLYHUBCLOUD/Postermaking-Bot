import logging

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.helper import generate_poster_image
from utils.upload import upload_to_imgbb
from utils.db import db
from config import Config
from api.tmdb_client import TMDBAuthError

# Command mappings:  command -> (template name, media type)
# TMDB is a movie / TV poster and ignores the anime/manga media type.
COMMAND_MAP = {
    "ani": ("ani", "ANIME"),
    "anim": ("anim", "MANGA"),
    "crun": ("crun", "ANIME"),
    "light": ("light", "ANIME"),
    "lightm": ("lightm", "MANGA"),
    "net": ("net", "ANIME"),
    "netm": ("netm", "MANGA"),
    "dark": ("dark", "ANIME"),
    "darkm": ("darkm", "MANGA"),
    "netcr": ("netcr", "ANIME"),
    "mod": ("mod", "ANIME"),
    "modm": ("modm", "MANGA"),
    # TMDB movies / TV shows
    "tmdb": ("tmdb", "MOVIE"),
    "movie": ("tmdb", "MOVIE"),
    "tv": ("tmdb", "TV"),
}

# Nicely "colored" (emoji-styled) buttons shown under every generated poster.
def result_buttons(query: str = ""):
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💎 Upgrade to Premium", callback_data="plans_menu"),
        ],
        [
            InlineKeyboardButton("🎨 More Styles", callback_data="help_menu"),
            InlineKeyboardButton("📢 Update Channel", url=Config.UPDATE_CHANNEL_URL),
        ],
        [
            InlineKeyboardButton("🔗 Share Link", callback_data=f"share_{query[:50]}"),
        ],
    ])
    return buttons


async def _is_authorized_in_group(message) -> bool:
    """Only used in groups: the bot works if the chat OR the sender is authorized."""
    if message.chat.type not in ("group", "supergroup"):
        return True
    if message.chat.type in ("channel",):
        return False
    user_ok = await db.is_authorized(message.from_user.id)
    chat_ok = await db.is_authorized(message.chat.id)
    return user_ok or chat_ok


async def generic_gen(client, message, template, media_type):
    # ── Group access control ─────────────────────────────────────────────
    if not await _is_authorized_in_group(message):
        owner_btn = InlineKeyboardMarkup([[
            InlineKeyboardButton("👑 Contact Owner", url=Config.OWNER_CONTACT_URL)
        ]])
        await message.reply_text(
            "⛔ **Not Authorized**\n\n"
            "This bot is only allowed in authorized groups.\n"
            "Please ask the group admin / bot owner to run `/authorize` for this chat.",
            reply_markup=owner_btn,
            quote=True,
        )
        return

    if len(message.command) < 2:
        await message.reply_text(
            f"⚠️ **Usage:** `/{message.command[0]} <name>`\n"
            f"Example: `/{message.command[0]} Naruto`\n"
            f"Movie Example: `/tmdb Inception 2010`",
            quote=True,
        )
        return

    # ── Premium status & daily limit ─────────────────────────────────────
    user_id = message.from_user.id
    is_premium = await db.is_premium_user(user_id)

    if is_premium:
        rank = await db.get_premium_user_rank(user_id)
        limit = Config.TASK_LIMITS.get(rank, Config.TASK_LIMITS["gold"])
    else:
        rank = "default"
        limit = Config.TASK_LIMITS["default"]

    allowed = await db.check_and_update_usage(user_id, limit)
    if not allowed:
        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton("💎 Upgrade to Premium", url=Config.OWNER_CONTACT_URL)
        ]])
        await message.reply_text(
            f"🚫 **Daily Limit Reached!**\n\n"
            f"You have used all **{limit}** free generations for today.\n"
            f"Upgrade to Premium for more!",
            reply_markup=buttons,
            quote=True,
        )
        return

    query = message.text.split(None, 1)[1]
    status = await message.reply_text(
        f"🎨 **Designing {template} poster for:** `{query}`...", quote=True
    )

    try:
        poster_io = await generate_poster_image(template, query, media_type, is_premium=is_premium)

        if not poster_io:
            await status.edit_text(f"❌ **Not Found.**\nCould not find content for `{query}`.")
            return

        await status.edit_text("📤 **Uploading...**")
        poster_io.name = f"{template}_{query[:40]}.jpg"

        # Optional ImgBB link
        img_url = upload_to_imgbb(poster_io)

        caption = f"🎨 **Poster generated for** `{query}`"
        caption += f"\n\n*Powered by {Config.BRANDING['powered_by']}*"

        if img_url:
            caption += f"\n\n🔗 **Link:** {img_url}"

        await message.reply_photo(
            photo=poster_io,
            caption=caption,
            reply_markup=result_buttons(query),
        )
        await status.delete()

    except TMDBAuthError:
        await status.edit_text(
            "🔑 **TMDB API error.**\n"
            "The bot's TMDB token is invalid/expired. Please ask the admin "
            "to set a valid `TMDB_BEARER_TOKEN`."
        )
    except Exception as e:
        logging.error(f"Error in command /{message.command[0]}: {e}", exc_info=True)
        await status.edit_text("⚠️ **Error.**\nAn unexpected error occurred. Please try again later.")


# Register Command Handlers
@Client.on_message(filters.command(list(COMMAND_MAP.keys())))
async def router(client, message):
    cmd = message.command[0]
    if cmd in COMMAND_MAP:
        template, media_type = COMMAND_MAP[cmd]
        await generic_gen(client, message, template, media_type)


@Client.on_callback_query(filters.regex(r"share_(.*)"))
async def share_callback(client, callback_query):
    query = callback_query.matches[0].group(1) or ""
    share_text = f"Check out `{query}` — generated with {Config.BRANDING['powered_by']} 🎨"
    try:
        await callback_query.message.edit_text(share_text)
    except Exception:
        pass
    await callback_query.answer(f"Sharing: {query}", show_alert=False)
