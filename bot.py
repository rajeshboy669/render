import os
import logging
import time
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

# Logging
logging.basicConfig(level=logging.INFO)

# Flask app for Render health check
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Telegram Terabox Bot running!"

# --- Config ---
TOKEN = os.getenv("TOKEN", "7797521990:AAFjqOCQTrdqE4vUyJSxNOI9PjdpsHGF2W4")
EMAIL = os.getenv("TERABOX_EMAIL", "realaaroha@gmail.com")
PASSWORD = os.getenv("TERABOX_PASSWORD", "@aaroha123")

# ---------------- TELEGRAM HANDLERS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! Send me a Terabox link and I’ll fetch the file for you."
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("🔑 Logging into Terabox... Please wait.")

try:
    # Setup Selenium headless Chrome
    options = Options()
    options.binary_location = os.getenv("CHROME_BIN", "/usr/bin/chromium")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(os.getenv("CHROMEDRIVER", "/usr/bin/chromedriver"))
    driver = webdriver.Chrome(service=service, options=options)

    # Open Terabox
    driver.get("https://www.terabox.com")
    time.sleep(3)

        # Login process
    try:
            login_btn = driver.find_element(By.XPATH, "//a[contains(@class,'login-button')]")
            login_btn.click()
            time.sleep(2)
        except Exception:
            pass  # already redirected

        # Enter credentials
        email_input = driver.find_element(By.NAME, "userName")
        pw_input = driver.find_element(By.NAME, "password")
        email_input.send_keys(TERABOX_EMAIL)
        pw_input.send_keys(TERABOX_PASSWORD)
        driver.find_element(By.ID, "TANGRAM__PSP_4__submit").click()
        time.sleep(5)

        # Open the shared link
        driver.get(url)
        time.sleep(6)

        # Extract download button link
    try:
            dl_button = driver.find_element(By.XPATH, "//a[contains(@class,'g-button')]")
            dl_link = dl_button.get_attribute("href")
        except Exception:
            dl_link = None

        driver.quit()

        if not dl_link:
            await update.message.reply_text("❌ Could not fetch direct file link.")
            return

        await update.message.reply_text("📥 Downloading file...")

        # Download the file into temp storage
        local_path = "/tmp/file_from_terabox"
        with requests.get(dl_link, stream=True) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        # Send file to Telegram
        await update.message.reply_document(
            document=open(local_path, "rb"),
            filename="terabox_file"
        )

        # Cleanup
        os.remove(local_path)

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

# ---------------- MAIN APP ---------------- #

def main():
    app_telegram = ApplicationBuilder().token(TOKEN).build()

    app_telegram.add_handler(CommandHandler("start", start))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    app_telegram.run_polling()

if __name__ == "__main__":
    main()
