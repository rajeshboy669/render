import os
import requests
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from tempfile import NamedTemporaryFile

BOT_TOKEN = os.getenv("BOT_TOKEN")

def start(update, context):
    update.message.reply_text("Send me a Terabox direct link (test version). I’ll fetch and send it fast 🚀")

def handle_link(update, context):
    link = update.message.text.strip()
    update.message.reply_text("⏳ Fetching and uploading, please wait...")

    try:
        filename, temp_file = stream_file(link)

        # Check file size
        size = os.path.getsize(temp_file.name)
        if size <= 2 * 1024 * 1024 * 1024:
            with open(temp_file.name, "rb") as f:
                update.message.reply_document(f, filename=filename)
        else:
            update.message.reply_text("⚠️ File is larger than 2GB. Cannot send via Telegram.")

    except Exception as e:
        update.message.reply_text(f"❌ Error: {e}")

    finally:
        temp_file.close()
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)

def stream_file(url):
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise Exception("Failed to fetch file")

    cd = r.headers.get("Content-Disposition", "")
    filename = cd.split("filename=")[-1].strip('"') if "filename=" in cd else "video.mp4"

    temp_file = NamedTemporaryFile(delete=False, dir="/tmp")
    for chunk in r.iter_content(1024 * 1024):
        temp_file.write(chunk)
    temp_file.flush()

    return filename, temp_file

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_link))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
