import os
import logging
import time
import requests
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters, CallbackContext
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# --- Config ---
TOKEN = os.getenv("TELEGRAM_TOKEN", "7797521990:AAFjqOCQTrdqE4vUyJSxNOI9PjdpsHGF2W4")
EMAIL = os.getenv("TERABOX_EMAIL", "realaaroha@gmail.com")
PASSWORD = os.getenv("TERABOX_PASSWORD", "@aaroha123")
APP_URL = os.getenv("APP_URL", "")  # Render app URL, e.g. https://mybot.onrender.com

bot = Bot(token=TOKEN)
app = Flask(__name__)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Function: Login to Terabox and return cookies ---
def login_and_get_cookies():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get("https://www.terabox.com")

        time.sleep(5)

        # login form
        email_input = driver.find_element(By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")

        email_input.send_keys(EMAIL)
        password_input.send_keys(PASSWORD)

        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        time.sleep(7)

        cookies = driver.get_cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}

        return cookie_dict
    finally:
        driver.quit()

# --- Function: Get direct download link ---
def get_direct_link(file_url, cookies):
    headers = {
        "User-Agent": "Mozilla/5.0",
    }

    # Use cookies
    session = requests.Session()
    for k, v in cookies.items():
        session.cookies.set(k, v)

    # Fetch the page
    resp = session.get(file_url, headers=headers)
    if "window.location.href" in resp.text:
        # Some Terabox pages auto-redirect with JS
        import re
        m = re.search(r'window\.location\.href\s*=\s*"(.*?)"', resp.text)
        if m:
            return m.group(1)

    # Otherwise, look for download API endpoint
    if "download" in resp.url:
        return resp.url

    return None

# --- Handlers ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text("👋 Hi! Send me a Terabox link and I’ll fetch the file.")

def handle_message(update: Update, context: CallbackContext):
    link = update.message.text.strip()
    update.message.reply_text("⏳ Logging into Terabox and fetching your file...")

    try:
        cookies = login_and_get_cookies()
        direct_link = get_direct_link(link, cookies)

        if not direct_link:
            update.message.reply_text("❌ Could not resolve direct link. Maybe login is required.")
            return

        update.message.reply_text(f"✅ Direct link: {direct_link}")

        # Download small/medium files and send to Telegram
        resp = requests.get(direct_link, stream=True)
        filename = link.split("/")[-1] or "file.bin"

        if int(resp.headers.get("Content-Length", 0)) < 50 * 1024 * 1024:  # <50MB
            update.message.reply_document(document=resp.content, filename=filename)
        else:
            update.message.reply_text("⚠️ File too large to send via Telegram. Use the direct link above.")

    except Exception as e:
        logger.error("Error: %s", str(e))
        update.message.reply_text(f"❌ Error: {str(e)}")

# --- Dispatcher ---
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Flask routes ---
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route("/")
def index():
    return "Terabox Bot is running ✅", 200

# --- Start with webhook ---
if __name__ == "__main__":
    bot.delete_webhook()
    bot.set_webhook(f"{APP_URL}/webhook/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
