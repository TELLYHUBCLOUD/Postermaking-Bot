"""
Per-user Settings (callback-driven)
===================================
A single ``/settings`` command shows every user config as inline buttons.
No separate commands needed — you tap a button, choose/set a value, and use
**Back** / **Set Default** buttons to navigate.

Settings stored per-user in MongoDB (``user_settings`` collection):

    Key                  Type    Meaning
    -------------------- ------- -----------------------------------------------
    thumbnail_brand      text    @handle badge shown on thumbnails
    thumbnail_channel    text    custom channel text/URL (overrides brand badge)
    quality_tags         text    comma-separated quality tags (e.g. 1080p, HD)
    default_template     choice  auto-use a Magic template (else show picker)
    default_style        choice  auto-use a Premiere style  (else show picker)

Every setting = one document ``(user_id, key) -> value`` in MongoDB.
"""
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from utils.db import db
from plugins.thumbnail_choices import MAGIC_CHOICES, PREMIERE_CHOICES

# ── Setting keys ─────────────────────────────────────────────────────────────
KEY_BRAND = "thumbnail_brand"
KEY_CHANNEL = "thumbnail_channel"
KEY_QUALITY = "quality_tags"
KEY_TEMPLATE = "default_template"
KEY_STYLE = "default_style"

# Free-text presets offered for quality tags.
QUALITY_PRESETS = ["1080p", "1080p, 720p", "4K, HDR", "HD"]

# In-memory pending custom-text input (user_id -> key)
_pending_input: dict = {}


# ── Helpers ──────────────────────────────────────────────────────────────────
def _default_of(key: str):
    return {
        KEY_BRAND: Config.THUMBNAIL_BRAND,
        KEY_CHANNEL: Config.THUMBNAIL_CHANNEL,
        KEY_QUALITY: ", ".join(Config.THUMBNAIL_QUALITY_TAGS),
        KEY_TEMPLATE: Config.THUMBNAIL_DEFAULT_TEMPLATE,
        KEY_STYLE: Config.THUMBNAIL_DEFAULT_STYLE,
    }[key]


def _is_choice(key: str) -> bool:
    return key in (KEY_TEMPLATE, KEY_STYLE)


def _label_of(key: str) -> str:
    return {
        KEY_BRAND: "🖼 Thumbnail Brand",
        KEY_CHANNEL: "📢 Channel Badge",
        KEY_QUALITY: "🏷 Quality Tags",
        KEY_TEMPLATE: "🎨 Default Magic Template",
        KEY_STYLE: "✨ Default Premiere Style",
    }[key]


async def _current_value(user_id: int, key: str):
    """Return the user's current value for a setting (falls back to default)."""
    val = await db.get_user_setting(user_id, key, _default_of(key))
    if val in (None, ""):
        val = _default_of(key)
    return val


# ── /settings command ────────────────────────────────────────────────────────
@Client.on_message(filters.command("settings"))
async def settings_cmd(client, message):
    await db.add_user(message.from_user.id)
    await _show_main_menu(message, message)


async def _show_main_menu(msg_or_cq, target):
    """Main settings menu listing every setting with its current value."""
    user_id = (msg_or_cq.from_user.id if hasattr(msg_or_cq, "from_user")
               else msg_or_cq.message.from_user.id)
    rows = [
        (KEY_BRAND, await _current_value(user_id, KEY_BRAND)),
        (KEY_CHANNEL, await _current_value(user_id, KEY_CHANNEL)),
        (KEY_QUALITY, await _current_value(user_id, KEY_QUALITY)),
        (KEY_TEMPLATE, await _current_value(user_id, KEY_TEMPLATE)),
        (KEY_STYLE, await _current_value(user_id, KEY_STYLE)),
    ]

    text = ["⚙️ **Your Settings** ⚙️\n", "Tap a button to change that option.\n"]
    buttons = []
    for key, val in rows:
        show = str(val) if val else "Not set"
        buttons.append([InlineKeyboardButton(
            f"{_label_of(key)}: `{show}`",
            callback_data=f"settings_edit_{key}",
        )])

    buttons.append([
        InlineKeyboardButton("💎 Premium", callback_data="plans_menu"),
        InlineKeyboardButton("❌ Close", callback_data="close_menu"),
    ])
    markup = InlineKeyboardMarkup(buttons)

    if hasattr(msg_or_cq, "edit_text"):
        await msg_or_cq.edit_text("\n".join(text), reply_markup=markup)
    else:
        await msg_or_cq.reply_text("\n".join(text), reply_markup=markup, quote=True)


# ── Open a setting's edit menu ───────────────────────────────────────────────
async def _open_edit(client, message, key):
    """Render the edit menu for ``key`` (used by the callback and refreshes)."""
    user_id = message.from_user.id
    current = await _current_value(user_id, key)
    label = _label_of(key)
    is_choice = _is_choice(key)

    buttons = []
    if is_choice:
        # Choice setting: show every option as a button.
        choices = MAGIC_CHOICES if key == KEY_TEMPLATE else PREMIERE_CHOICES
        rows = [choices[i:i + 2] for i in range(0, len(choices), 2)]
        for row in rows:
            r = []
            for ckey, clabel in row:
                mark = "✅ " if str(ckey) == str(current) else ""
                r.append(InlineKeyboardButton(
                    f"{mark}{clabel}", callback_data=f"settings_set_{key}_{ckey}"
                ))
            buttons.append(r)
    else:
        # Text setting.
        if key == KEY_QUALITY:
            row = []
            for i, p in enumerate(QUALITY_PRESETS):
                row.append(InlineKeyboardButton(
                    p, callback_data=f"settings_preset_{key}_{i}"
                ))
            # split presets 2 per row
            for i in range(0, len(row), 2):
                buttons.append(row[i:i + 2])
        # "set custom" for any text setting
        buttons.append([InlineKeyboardButton(
            "✍️ Set Custom Value", callback_data=f"settings_custom_{key}"
        )])

    # Default + Back
    buttons.append([
        InlineKeyboardButton("↩️ Set Default", callback_data=f"settings_default_{key}"),
        InlineKeyboardButton("◀ Back", callback_data="settings_menu"),
    ])

    text = (
        f"**{label}**\n\n"
        f"Current: `{current if current else 'Not set'}`\n"
        + ("Tap one of the options below to choose it." if is_choice
           else "Tap a preset, or **Set Custom Value** to type your own.")
    )
    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^settings_edit_(.+)$"))
async def settings_edit(client, callback_query):
    import re as _re
    key = _re.match(r"^settings_edit_(.+)$", callback_query.data).group(1)
    await _open_edit(client, callback_query.message, key)
    await callback_query.answer()


# ── Choice option selected ───────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^settings_set_(default_template|default_style)_(.+)$"))
async def settings_set_choice(client, callback_query):
    import re as _re
    m = _re.match(r"^settings_set_(default_template|default_style)_(.+)$", callback_query.data)
    key, value = m.group(1), m.group(2)
    user_id = callback_query.from_user.id
    await db.set_user_setting(user_id, key, value)
    await callback_query.answer(f"Saved: {value}", show_alert=False)
    # Refresh the edit menu
    await _open_edit(client, callback_query.message, key)


# ── Preset applied (text settings) ───────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^settings_preset_(quality_tags)_(\d+)$"))
async def settings_preset(client, callback_query):
    import re as _re
    m = _re.match(r"^settings_preset_(quality_tags)_(\d+)$", callback_query.data)
    key, idx = m.group(1), int(m.group(2))
    value = QUALITY_PRESETS[idx]
    await db.set_user_setting(callback_query.from_user.id, key, value)
    await callback_query.answer(f"Saved: {value}", show_alert=False)
    await _open_edit(client, callback_query.message, key)


# ── Request a custom value → next text message becomes the value ─────────────
@Client.on_callback_query(filters.regex(r"^settings_custom_(.+)$"))
async def settings_custom(client, callback_query):
    import re as _re
    key = _re.match(r"^settings_custom_(.+)$", callback_query.data).group(1)
    user_id = callback_query.from_user.id
    _pending_input[user_id] = key
    label = _label_of(key)
    await callback_query.message.edit_text(
        f"✍️ **{label}**\n\n"
        f"Send me your value now as a normal message.\n"
        f"*(e.g. for Brand: `MyChannel`, for Quality Tags: `1080p, HD`)*\n\n"
        f"Click **Cancel** to abort.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"settings_edit_{key}"),
        ]]),
    )
    await callback_query.answer()


# ── Catch the custom text message ────────────────────────────────────────────
@Client.on_message(filters.text & filters.private & ~filters.command([]))
async def capture_custom_text(client, message):
    user_id = message.from_user.id
    key = _pending_input.pop(user_id, None)
    if not key:
        return
    value = message.text.strip()
    if not value:
        await message.reply_text("⚠️ Empty value. Please send a non-empty value.")
        _pending_input[user_id] = key
        return
    # Light sanitise: strip leading @ for brand
    if key == KEY_BRAND:
        value = value.lstrip("@").strip()
    await db.set_user_setting(user_id, key, value)
    await message.reply_text(
        f"✅ **{_label_of(key)} updated!**\n`{value}`\n\n"
        f"Open `/settings` to review or change more.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⚙️ Back to Settings", callback_data="settings_menu"),
        ]]),
    )


# ── Reset a setting to default ───────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^settings_default_(.+)$"))
async def settings_default(client, callback_query):
    import re as _re
    key = _re.match(r"^settings_default_(.+)$", callback_query.data).group(1)
    user_id = callback_query.from_user.id
    await db.reset_user_setting(user_id, key)
    default = _default_of(key)
    await callback_query.answer(f"Reset to default: {default}", show_alert=True)
    await _open_edit(client, callback_query.message, key)


# ── Back to main menu ────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^settings_menu$"))
async def settings_menu_back(client, callback_query):
    await _show_main_menu(callback_query.message, callback_query)
    await callback_query.answer()


# ── Public helpers for other modules ─────────────────────────────────────────
async def user_setting_quality_tags(user_id: int) -> list:
    raw = await _current_value(user_id, KEY_QUALITY)
    return [x.strip() for x in str(raw or "").split(",") if x.strip()]


async def user_setting_default_template(user_id: int):
    return await _current_value(user_id, KEY_TEMPLATE)


async def user_setting_default_style(user_id: int):
    return await _current_value(user_id, KEY_STYLE)
