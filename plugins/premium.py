from datetime import datetime, timedelta
from pyrogram import Client, filters
from config import Config
from core.database import db
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

PLANS_TXT = """
📛 **Available Plans**

🥉 **Bronze Plan**
- Limit: {bronze_limit} Posters/Day
- Price: Contact Owner

🥈 **Silver Plan**
- Limit: {silver_limit} Posters/Day
- Price: Contact Owner

🥇 **Gold Plan**
- Limit: {gold_limit} Posters/Day
- Price: Contact Owner

🆓 **Free Plan**
- Limit: {default_limit} Posters/Day
"""

def parse_add_premium_args(message):
    """Parses user_id, rank, and expiry duration string from message arguments or reply."""
    user_id = None
    rank = "bronze"
    expiry_str = None

    cmd_args = message.command[1:]  # Arguments after /add_premium

    if cmd_args and (cmd_args[0].isdigit() or (cmd_args[0].startswith("-") and cmd_args[0][1:].isdigit())):
        user_id = int(cmd_args[0])
        if len(cmd_args) > 1:
            rank = cmd_args[1].lower()
        if len(cmd_args) > 2:
            expiry_str = cmd_args[2]
    elif message.reply_to_message:
        if message.reply_to_message.from_user:
            user_id = message.reply_to_message.from_user.id
        elif message.reply_to_message.sender_chat:
            user_id = message.reply_to_message.sender_chat.id
        if len(cmd_args) > 0:
            rank = cmd_args[0].lower()
        if len(cmd_args) > 1:
            expiry_str = cmd_args[1]

    return user_id, rank, expiry_str


def parse_expiry_time(duration_str):
    if not duration_str:
        return None
    try:
        duration_str = duration_str.lower()
        if duration_str.endswith("min"):
            return datetime.now() + timedelta(minutes=int(duration_str[:-3]))
        elif duration_str.endswith("h"):
            return datetime.now() + timedelta(hours=int(duration_str[:-1]))
        elif duration_str.endswith("d"):
            return datetime.now() + timedelta(days=int(duration_str[:-1]))
        elif duration_str.endswith("w"):
            return datetime.now() + timedelta(weeks=int(duration_str[:-1]))
        elif duration_str.endswith("m"):
            return datetime.now() + timedelta(days=30 * int(duration_str[:-1]))
        return None
    except (ValueError, TypeError):
        return None


def get_user_id(message):
    cmd_args = message.command[1:]
    if cmd_args and (cmd_args[0].isdigit() or (cmd_args[0].startswith("-") and cmd_args[0][1:].isdigit())):
        return int(cmd_args[0])
    if message.reply_to_message:
        if message.reply_to_message.from_user:
            return message.reply_to_message.from_user.id
        elif message.reply_to_message.sender_chat:
            return message.reply_to_message.sender_chat.id
    return None


def format_timedelta(td):
    """Formats a timedelta object into a human-readable string."""
    if td is None:
        return "Permanent"
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days} day(s)")
    if hours > 0:
        parts.append(f"{hours} hour(s)")
    if minutes > 0:
        parts.append(f"{minutes} minute(s)")
        
    return ", ".join(parts) if parts else "Less than a minute"

@Client.on_message(filters.command("add_premium") & filters.user(Config.BOT_OWNER))
async def add_premium(client, message):
    user_id, rank, expiry_str = parse_add_premium_args(message)
    if not user_id:
        return await message.reply_text("Please reply to a user or provide a user ID.\nUsage: `/add_premium <user_id> <rank> <time>`\nOr reply: `/add_premium <rank> <time>`\nRank: gold/silver/bronze\nTime: 1d/1w/1m")

    if rank not in ["gold", "silver", "bronze"]:
        return await message.reply_text("Invalid rank. Please use 'gold', 'silver', or 'bronze'.")

    expiry_time = parse_expiry_time(expiry_str)
    await db.add_premium_user(user_id, rank, expiry_time)
    
    expiry_text = f"until {expiry_time.strftime('%Y-%m-%d %H:%M:%S')}" if expiry_time else "permanently"
    
    await message.reply_text(f"User `{user_id}` has been given **{rank}** premium status {expiry_text}.")

    try:
        task_limit = Config.TASK_LIMITS.get(rank, Config.TASK_LIMITS["default"])
        user_notification = (
            f"🎉 **Congratulations!** 🎉\n\n"
            f"You have been upgraded to the **{rank.title()}** premium plan!\n\n"
            f"**Your benefits:**\n"
            f"- You can now create up to **{task_limit}** Posters.\n\n"
            f"This plan is valid **{expiry_text}**."
        )
        await client.send_message(user_id, user_notification)
    except Exception as e:
        await message.reply_text(f"Could not send a notification to the user `{user_id}`. Reason: `{e}`")


@Client.on_message(filters.command("remove_premium") & filters.user(Config.BOT_OWNER))
async def remove_premium(client, message):
    user_id = get_user_id(message)
    if not user_id:
        return await message.reply_text("Please reply to a user or provide a user ID.")

    if await db.get_premium_user(user_id):
        await db.remove_premium_user(user_id)
        await message.reply_text(f"Premium status for user `{user_id}` has been removed.")
        try:
            await client.send_message(user_id, "Your premium plan has been manually removed by the administrator.")
        except Exception as e:
            await message.reply_text(f"Could not send a notification to the user `{user_id}`. Reason: `{e}`")
    else:
        await message.reply_text("This user does not have premium status.")

@Client.on_callback_query(filters.regex("plans_menu"))
async def plans_callback(client, callback_query):
    plans_text = PLANS_TXT.format(
        bronze_limit=Config.TASK_LIMITS.get("bronze", "N/A"),
        silver_limit=Config.TASK_LIMITS.get("silver", "N/A"),
        gold_limit=Config.TASK_LIMITS.get("gold", "N/A"),
        default_limit=Config.TASK_LIMITS.get("default", "N/A"),
    )
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton('👑 Contact Owner to Upgrade', url=f'tg://user?id={Config.BOT_OWNER}')
    ]])
    try:
        await callback_query.message.edit_text(
            plans_text, reply_markup=buttons, disable_web_page_preview=True
        )
    except Exception:
        await callback_query.answer()
    await callback_query.answer()


@Client.on_message(filters.command("my_plan"))
async def my_plan(client, message):
    user_id = message.from_user.id
    user_plan = await db.get_premium_user(user_id)
    
    if not user_plan:
        default_limit = Config.TASK_LIMITS["default"]
        return await message.reply_text(f"You are currently on the **Free** plan.\n- Limit: **{default_limit}** posters.")

    rank = user_plan.get('rank', 'default')
    expiry_time = user_plan.get('expiry_time')
    
    if expiry_time and expiry_time < datetime.now():
        await db.remove_premium_user(user_id)
        await message.reply_text(
            "😢 **Your premium plan has expired.** 😢\n\n"
            "You have been reverted to the Free plan. To upgrade again, please contact the bot owner."
        )
        return

    task_limit = Config.TASK_LIMITS.get(rank, Config.TASK_LIMITS["default"])
    
    if expiry_time:
        remaining_time = expiry_time - datetime.now()
        expiry_str = f"**Expires in:** `{format_timedelta(remaining_time)}`"
    else:
        expiry_str = "Your plan is **Permanent** and does not expire."

    plan_details = (
        f"📋 **Your Plan Details** 📋\n\n"
        f"**Plan:** `{rank.title()}`\n"
        f"**Limit:** `{task_limit}` posters\n\n"
        f"{expiry_str}"
    )
    await message.reply_text(plan_details)

@Client.on_message(filters.command("plans"))
async def show_plans(client, message):
    """Shows available premium plans."""
    plans_text = PLANS_TXT.format(
        bronze_limit=Config.TASK_LIMITS.get("bronze", "N/A"),
        silver_limit=Config.TASK_LIMITS.get("silver", "N/A"),
        gold_limit=Config.TASK_LIMITS.get("gold", "N/A"),
        default_limit=Config.TASK_LIMITS.get("default", "N/A")
    )
    
    buttons = [[
        InlineKeyboardButton('Contact Owner to Upgrade 👑', url=f'tg://user?id={Config.BOT_OWNER}')
    ]]
    
    await message.reply_text(
        plans_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )
