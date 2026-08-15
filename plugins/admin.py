"""
Group / User Authorization
==========================
Owner-only commands to control where the bot is allowed to run.

- `/authorize <id>`    -> allow a user or group chat to use the bot
- `/unauthorize <id>`  -> revoke access from a user or group chat
- `/authorized`        -> list every authorized user/group

You can also reply to a user's message with `/authorize` to authorize that user.
"""
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.db import db
from config import Config


def _resolve_target(message):
    """Resolve the target id from a reply, an argument, or the current chat."""
    if message.reply_to_message:
        if message.reply_to_message.from_user:
            return message.reply_to_message.from_user.id
        elif message.reply_to_message.sender_chat:
            return message.reply_to_message.sender_chat.id
    if len(message.command) >= 2:
        try:
            return int(message.command[1])
        except (IndexError, ValueError):
            return None
    # Fallback: authorize the current chat (useful for groups)
    return message.chat.id if message.chat.type in ("group", "supergroup") else None


@Client.on_message(filters.command("authorize") & filters.user(Config.BOT_OWNER))
async def authorize_cmd(client, message):
    target = _resolve_target(message)
    if target is None:
        return await message.reply_text(
            "⚠️ **Usage:**\n`/authorize <id>`\n"
            "Or reply to a user's message with `/authorize`."
        )

    authorized_by = message.from_user.id if message.from_user else Config.BOT_OWNER
    is_new = await db.authorize_user(target, authorized_by)

    is_group = target < 0 or (target == message.chat.id and message.chat.type in ("group", "supergroup"))

    if is_group:
        text = (
            f"✅ **Group Authorized**\n"
            f"Chat ID: `{target}`\n"
            f"Members can now use the poster commands here."
        )
    else:
        text = (
            f"✅ **User Authorized**\n"
            f"User ID: `{target}`\n"
            + ("This is a new entry." if is_new else "Already authorized (updated).")
        )

    await message.reply_text(text)


@Client.on_message(filters.command("unauthorize") & filters.user(Config.BOT_OWNER))
async def unauthorize_cmd(client, message):
    target = _resolve_target(message)
    if target is None:
        return await message.reply_text("⚠️ **Usage:** `/unauthorize <id>`")

    removed = await db.unauthorize_user(target)
    await message.reply_text(
        f"{'⛔ **Access Revoked**' if removed else 'ℹ️ **Not Found**'}\n"
        f"Target ID: `{target}`"
    )


@Client.on_message(filters.command("authorized") & filters.user(Config.BOT_OWNER))
async def authorized_list_cmd(client, message):
    ids = await db.get_all_authorized()
    count = len(ids)
    if not ids:
        return await message.reply_text("📭 No users/groups are authorized yet.")

    # Page through the list
    chunk = ids[:50]
    lines = [f"**Authorized targets ({count}):**\n"]
    lines += [f"• `{i}`" for i in chunk]
    if count > 50:
        lines.append(f"\n*…and {count - 50} more.*")

    await message.reply_text("\n".join(lines))
