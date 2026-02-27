from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.db import db
from config import Config

@Client.on_message(filters.command("start"))
async def start_handler(client, message):
    # Add user to DB
    await db.add_user(message.from_user.id)
    
    txt = (
        f"Hi **{message.from_user.first_name}**! 👋\n\n"
        "I am an advanced **Anime/Manga Poster Bot**.\n"
        "I can generate beautiful posters in various styles!\n\n"
        "Click the button below to see the available commands."
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Update Channel", url="https://t.me/Blaze_Updatez")],
        [InlineKeyboardButton("ℹ️ Help / Commands", callback_data="help_menu")]
    ])
    
    # Using AniList preview as the start image
    START_IMG = "https://i.pinimg.com/736x/26/8f/68/268f680f5a32c8d37cad7b28455a1123.jpg"
    
    await message.reply_photo(
        photo=START_IMG,
        caption=txt,
        reply_markup=buttons
    )

@Client.on_message(filters.command("help"))
async def help_command_handler(client, message):
    # Reuse get_help_page to ensure consistency
    media, markup = get_help_page(0)
    
    # InputMediaPhoto wrapper acts differently than send_photo arguments
    # media.media contains the file_id/url
    # media.caption contains the text
    
    await message.reply_photo(
        photo=media.media,
        caption=media.caption,
        reply_markup=markup
    )

TEMPLATES = [
    {
        "name": "AniList Style",
        "desc": "A clean information-rich style mimicking the AniList.co interface.",
        "cmd_anime": "/ani Naruto",
        "cmd_manga": "/anim Berserk",
        "image": "https://i.ibb.co/Tx6BVk8Z/x.jpg?=482"
    },
    {
        "name": "Netflix Style",
        "desc": "A cinematic style mimicking the Netflix UI. Features a vignette effect, N-logo, and 'Watch Now' buttons.",
        "cmd_anime": "/net Erased",
        "cmd_manga": "/netm Berserk",
        "image": "https://i.ibb.co/0VDzW0tC/x.jpg?=912"
    },
    {
        "name": "Crunchyroll Style",
        "desc": "Vibrant orange and white design based on the Crunchyroll TV app. Features a large backdrop and season/episode info.",
        "cmd_anime": "/crun One Piece",
        "cmd_manga": "N/A",
        "image": "https://i.ibb.co/YFF1bn3r/x.jpg?=375"
    },
    {
        "name": "Light Simple Style",
        "desc": "A clean, bright aesthetic. Great for manga with a white/paper-like feel.",
        "cmd_anime": "/light One Piece",
        "cmd_manga": "/lightm One Piece",
        "image": "https://i.ibb.co/4nKS5N6C/x.jpg?=821"
    },
    {
        "name": "Dark Simple Style",
        "desc": "A sleek, dark mode design. High contrast and easy on the eyes.",
        "cmd_anime": "/dark Solo Leveling",
        "cmd_manga": "/darkm Solo Leveling",
        "image": "https://i.ibb.co/nsFSWtkZ/x.jpg?=593"
    },
    {
        "name": "Modern Style",
        "desc": "A customized modern layout with glassmorphism effects and clean typography.",
        "cmd_anime": "/mod Jujutsu Kaisen",
        "cmd_manga": "/modm Vagabond",
        "image": "https://i.ibb.co/nN99g2BB/x.jpg?=246"
    },
    {
        "name": "Netflix x Crunchyroll",
        "desc": "A hybrid style combining Netflix layout with Crunchyroll colors and branding.",
        "cmd_anime": "/netcr Demon Slayer",
        "cmd_manga": "N/A",
        "image": "https://i.ibb.co/d4QCdDJR/x.jpg?=734"
    }
]

from pyrogram.types import InputMediaPhoto

# ... (Keep TEMPLATES list as is for now, will update IDs later) ...

from pyrogram.types import InputMediaPhoto

def get_help_page(page_idx):
    total = len(TEMPLATES)
    # Ensure cyclic navigation or clamping? Grid usually means direct access.
    # But let's safe guard.
    page_idx = page_idx % total
    current = TEMPLATES[page_idx]
    
    txt = (
        f"**{current['name']}** — {page_idx + 1}/{total}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{current['desc']}\n\n"
        f"**Usage:**\n"
        f"• Anime: `{current['cmd_anime']}`\n"
        f"• Manga: `{current['cmd_manga']}`"
    )
    
    # Grid Layout Generation
    buttons = []
    
    # Row 1: 1-4
    row1 = []
    for i in range(4):
        if i < total:
            btn_text = f"• {i+1} •" if i == page_idx else f"{i+1}"
            row1.append(InlineKeyboardButton(btn_text, callback_data=f"help_idx_{i}"))
    buttons.append(row1)
    
    # Row 2: 5-8 (We currently have 7)
    row2 = []
    for i in range(4, 8):
        if i < total:
            btn_text = f"• {i+1} •" if i == page_idx else f"{i+1}"
            row2.append(InlineKeyboardButton(btn_text, callback_data=f"help_idx_{i}"))
    if row2:
        buttons.append(row2)
        
    # Navigation / Functional Buttons
    nav_row = [
        InlineKeyboardButton("🏠 Home", callback_data="start_menu"),
        InlineKeyboardButton("🗑 Close", callback_data="close_menu")
    ]
    buttons.append(nav_row)
    
    media = InputMediaPhoto(media=current['image'], caption=txt)
    return media, InlineKeyboardMarkup(buttons)

@Client.on_callback_query(filters.regex("help_menu"))
async def help_init(client, callback_query):
    # Start at page 0
    media, markup = get_help_page(0)
    try:
        await callback_query.message.edit_media(media, reply_markup=markup)
    except Exception as e:
        # Fallback if media is same or error
        await callback_query.answer(f"Loaded.", show_alert=False)

@Client.on_callback_query(filters.regex(r"help_idx_(\d+)"))
async def help_navigate(client, callback_query):
    page_idx = int(callback_query.matches[0].group(1))
    media, markup = get_help_page(page_idx)
    try:
        await callback_query.message.edit_media(media, reply_markup=markup)
    except Exception as e:
        # Ignore if "message is not modified"
        await callback_query.answer()

@Client.on_callback_query(filters.regex("start_menu"))
async def back_to_start(client, callback_query):
    # Define Start details
    START_IMG = "https://i.pinimg.com/736x/26/8f/68/268f680f5a32c8d37cad7b28455a1123.jpg"
    
    txt = (
        f"Hi **{callback_query.from_user.first_name}**! 👋\n\n"
        "I am an advanced **Anime/Manga Poster Bot**.\n"
        "I can generate beautiful posters in various styles!\n\n"
        "Click the button below to see the available commands."
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Update Channel", url="https://t.me/Blaze_Updatez")],
        [InlineKeyboardButton("ℹ️ Help / Commands", callback_data="help_menu")]
    ])
    
    # Edit the existing message's media (Image + Caption)
    try:
        await callback_query.message.edit_media(
            media=InputMediaPhoto(
                media=START_IMG,
                caption=txt
            ),
            reply_markup=buttons
        )
    except Exception as e:
        # Prevents error if user double clicks or content is identical
        await callback_query.answer()

@Client.on_callback_query(filters.regex("close_menu"))
async def close_menu(client, callback_query):
    await callback_query.message.delete()

