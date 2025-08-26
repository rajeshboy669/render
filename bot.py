import os
import re
import requests
from urllib.parse import urlparse
from tempfile import NamedTemporaryFile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7797521990:AAFjqOCQTrdqE4vUyJSxNOI9PjdpsHGF2W4")
TERABOX_COOKIES = os.getenv("COOKIES")  # put full cookie string here

headers = {
    "User-Agent": "Mozilla/5.0",
    "Cookie": TERABOX_COOKIES
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me a Terabox share link (`/s/...`). I’ll fetch the file and send it 🚀"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    status_msg = await update.message.reply_text("⏳ Getting direct link...")

    try:
        direct_url, filename = get_direct_link(link)
        await status_msg.edit_text(f"⬇️ Downloading {filename}...")

        temp_file = NamedTemporaryFile(delete=False, dir="/tmp")
        r = requests.get(direct_url, headers=headers, stream=True)

        downloaded = 0
        total_size = int(r.headers.get("Content-Length", 0))

        for chunk in r.iter_content(1024 * 1024):
            temp_file.write(chunk)
            downloaded += len(chunk)

        temp_file.flush()
        await status_msg.edit_text("📤 Uploading to Telegram...")

        with open(temp_file.name, "rb") as f:
            await update.message.reply_document(f, filename=filename)

        await status_msg.edit_text("✅ Done!")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")

def get_direct_link(share_url):
    r = requests.get(share_url, headers=headers)
    if r.status_code != 200:
        raise Exception("Failed to open share link")

    # find direct link in HTML/JS
    match = re.search(r'"dlink":"(https:[^"]+)"', r.text)
    if not match:
        raise Exception("Direct link not found. Cookie might be expired.")

    dlink = match.group(1).replace("\\u0026", "&")

    # find filename if possible
    fname = "file.bin"
    fname_match = re.search(r'"server_filename":"([^"]+)"', r.text)
    if fname_match:
        fname = fname_match.group(1)

    return dlink, fname

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling()

if __name__ == "__main__":
    main()
