import os
from pyrogram import Client, filters
from anilist import get_anime_data
from templates.modern import create_poster
from config import Config

"""
Simple CLI/Standalone entry point for the Anime Poster Bot.
"""

app = Client(
    "anime_poster_bot", 
    api_id=Config.API_ID, 
    api_hash=Config.API_HASH, 
    bot_token=Config.BOT_TOKEN
)

@app.on_message(filters.command("poster"))
async def generate_poster(client, message):
    if len(message.command) < 2:
        await message.reply_text("Please provide an anime name! Usage: /poster <anime_name>")
        return
    
    query = message.text.split(None, 1)[1]
    status_msg = await message.reply_text(f"Searching for **{query}**...")
    
    try:
        data = get_anime_data(query)
        if not data:
            await status_msg.edit_text("Anime not found on AniList.")
            return

        await status_msg.edit_text("Designing poster... 🎨")
        
        poster_io = create_poster(data)
        if not poster_io:
             await status_msg.edit_text("Failed to generate image.")
             return
             
        poster_io.name = "poster.png"
        
        caption = f"**{data['title']['english'] or data['title']['romaji']}**\n"
        caption += f"Score: {data.get('averageScore')}/100"

        await message.reply_photo(poster_io, caption=caption)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"Error: {str(e)}")

if __name__ == "__main__":
    print("Bot Started...")
    app.run()
