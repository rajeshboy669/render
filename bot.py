import os
import re
import asyncio
import aiohttp
import logging
from pymongo import MongoClient
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Hardcoded Config (⚠️ less secure, but works) ---
TELEGRAM_TOKEN = "7797521990:AAFjqOCQTrdqE4vUyJSxNOI9PjdpsHGF2W4"
MONGO_URI = "mongodb+srv://aaroha:aaroha@cluster0.sohx6w6.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
ADLINKFLY_DOMAIN = "https://linxshort.me"  # your domain
ADLINKFLY_API_URL = f"{ADLINKFLY_DOMAIN}/api"

# MongoDB setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["adlinkfly_bot"]
users_collection = db["users"]

# URL regex
URL_REGEX = re.compile(r'https?://[^\s]+')


# -----------------------------
# Database Helpers
# -----------------------------
def get_user_api_key(user_id: int) -> str:
    user = users_collection.find_one({"user_id": user_id})
    return user["api_key"] if user and "api_key" in user else None


def set_user_api_key(user_id: int, api_key: str):
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"api_key": api_key}},
        upsert=True
    )


def delete_user_api_key(user_id: int):
    users_collection.delete_one({"user_id": user_id})


# -----------------------------
# Link Shortening
# -----------------------------
async def shorten_link(link: str, api_key: str) -> str:
    """Shorten a single link with AdLinkFly."""
    if "t.me/" in link or "https://t.me/" in link:
        return link  # Skip Telegram links
    try:
        params = {"api": api_key, "url": link}
        async with aiohttp.ClientSession() as session:
            async with session.get(ADLINKFLY_API_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("shortenedUrl", link)
        return link
    except Exception as e:
        logger.error(f"Error shortening link: {e}")
        return link


async def process_text(text: str, api_key: str) -> str:
    """Find all links in text and shorten them concurrently."""
    async def replace_link(match):
        link = match.group(0)
        return await shorten_link(link, api_key)

    tasks = [replace_link(match) for match in URL_REGEX.finditer(text)]
    shortened_links = await asyncio.gather(*tasks)

    for match, shortened in zip(URL_REGEX.finditer(text), shortened_links):
        text = text.replace(match.group(0), shortened)
    return text


# -----------------------------
# Bot Commands
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "/setapi <your_api_key> → Save your AdLinkFly API key\n"
        "/logout → Remove your saved API key\n\n"
        "Then send me any message (text/photo/video/doc/forwarded), "
        "I’ll shorten all links (except Telegram links) 🚀"
    )


async def setapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /setapi <your_api_key>")
        return

    api_key = context.args[0]
    user_id = update.message.from_user.id

    set_user_api_key(user_id, api_key)
    await update.message.reply_text("✅ Your API key has been saved!")


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    delete_user_api_key(user_id)
    await update.message.reply_text("✅ Your API key has been removed. Use /setapi to add a new one.")


# -----------------------------
# Message Handler
# -----------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id

    api_key = get_user_api_key(user_id)
    if not api_key:
        await message.reply_text("⚠️ You haven’t set your API key yet!\nUse /setapi <your_api_key>")
        return

    # Case 1: Text
    if message.text:
        new_text = await process_text(message.text, api_key)
        await message.reply_text(new_text)

    # Case 2: Photo with caption
    elif message.photo:
        caption = await process_text(message.caption or "", api_key)
        file_id = message.photo[-1].file_id
        await message.reply_photo(photo=file_id, caption=caption)

    # Case 3: Document with caption
    elif message.document:
        caption = await process_text(message.caption or "", api_key)
        file_id = message.document.file_id
        await message.reply_document(document=file_id, caption=caption)

    # Case 4: Video with caption
    elif message.video:
        caption = await process_text(message.caption or "", api_key)
        file_id = message.video.file_id
        await message.reply_video(video=file_id, caption=caption)

    else:
        await message.reply_text("⚠️ Unsupported message type.")


# -----------------------------
# Run Bot
# -----------------------------
# -----------------------------
# Run Bot
# -----------------------------
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setapi", setapi))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    app.run_polling()


if __name__ == "__main__":
    logger.info("🚀 Bot is starting...")
    main()

