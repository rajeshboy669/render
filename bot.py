import os
import logging
import time
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

# --- Function: Login to Terabox ---
def login_and_get_cookies():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get("https://www.terabox.com")

        time.sleep(5)  # allow page to load

        # Find and fill inputs (selectors may need adjustments)
        email_input = driver.find_element(By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")

        email_input.send_keys(EMAIL)
        password_input.send_keys(PASSWORD)

        # Click login
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        time.sleep(7)  # wait for login

        cookies = driver.get_cookies()
        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

        return cookie_string
    finally:
        driver.quit()

# --- Handlers ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text("👋 Hi! Send me a Terabox link and I’ll try to fetch it.")

def handle_message(update: Update, context: CallbackContext):
    link = update.message.text
    update.message.reply_text("⏳ Logging into Terabox...")

    try:
        cookie_string = login_and_get_cookies()
        # TODO: Use cookies + link to fetch the real file
        update.message.reply_text(f"✅ Logged in! Got cookies.\n\nExample: {cookie_string[:100]}...")
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
