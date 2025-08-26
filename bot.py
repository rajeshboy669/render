import os
import requests
from tempfile import NamedTemporaryFile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7797521990:AAFjqOCQTrdqE4vUyJSxNOI9PjdpsHGF2W4")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me a *direct download link* (not share link).\n"
        "I’ll fetch the file and send it back 🚀",
        parse_mode="Markdown"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    status_msg = await update.message.reply_text("⏳ Starting download...")

    try:
        filename, temp_file = await download_with_progress(link, status_msg, context)

        size = os.path.getsize(temp_file.name)
        if size <= 2 * 1024 * 1024 * 1024:  # 2GB limit
            await status_msg.edit_text("📤 Uploading to Telegram...")
            with open(temp_file.name, "rb") as f:
                await update.message.reply_document(f, filename=filename)
            await status_msg.edit_text("✅ Done!")
        else:
            await status_msg.edit_text("⚠️ File is larger than 2GB. Cannot send via Telegram.")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")

    finally:
        temp_file.close()
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)

async def download_with_progress(url, status_msg, context):
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise Exception("Failed to fetch file")

    total_size = int(r.headers.get("Content-Length", 0))
    cd = r.headers.get("Content-Disposition", "")
    filename = cd.split("filename=")[-1].strip('"') if "filename=" in cd else "file.bin"

    temp_file = NamedTemporaryFile(delete=False, dir="/tmp")

    downloaded = 0
    last_percent = 0
    for chunk in r.iter_content(1024 * 1024):  # 1 MB
        temp_file.write(chunk)
        downloaded += len(chunk)

        if total_size > 0:
            percent = int(downloaded * 100 / total_size)
            if percent - last_percent >= 5:  # update every 5%
                last_percent = percent
                try:
                    await status_msg.edit_text(f"⬇️ Downloading... {percent}%")
                except Exception:
                    pass  # ignore if can't edit

    temp_file.flush()
    return filename, temp_file

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    app.run_polling()

if __name__ == "__main__":
    main()
