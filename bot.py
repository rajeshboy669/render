import os
import re
import json
import time
import requests
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from playwright.sync_api import sync_playwright

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7797521990:AAFjqOCQTrdqE4vUyJSxNOI9PjdpsHGF2W4")
TB_EMAIL = os.getenv("TB_EMAIL", "realaaroha@gmail.com")
TB_PASSWORD = os.getenv("TB_PASSWORD", "@aaroha123")

COOKIE_FILE = Path("/tmp/terabox_cookies.json")  # persisted across restarts on same instance
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36"

# ---------- Playwright login & cookie helpers ----------

def save_cookies(context):
    cookies = context.cookies()
    COOKIE_FILE.write_text(json.dumps(cookies))

def load_cookies(context):
    if COOKIE_FILE.exists():
        cookies = json.loads(COOKIE_FILE.read_text())
        context.add_cookies(cookies)
        return True
    return False

def cookies_to_header(context):
    # Build a Cookie header string from context cookies
    pairs = []
    for c in context.cookies():
        # Only include terabox domains
        if "terabox.com" in c.get("domain", ""):
            pairs.append(f'{c["name"]}={c["value"]}')
    return "; ".join(pairs)

def ensure_logged_in_and_get_cookie_header():
    """Open a headless Chromium, reuse cookies if available, otherwise log in, then return Cookie header string."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA)
        # Try existing cookies first
        had = load_cookies(context)

        page = context.new_page()
        page.goto("https://www.terabox.com/", wait_until="domcontentloaded", timeout=60000)

        # If not already logged in, attempt login flow
        def logged_in():
            # Heuristic: presence of user menu / absence of Sign in button
            return "logout" in page.content().lower() or "my files" in page.content().lower()

        if not had or not logged_in():
            # Click login if found
            try:
                # Common login entry points
                selectors = [
                    'text=Log in', 'text=Sign in', 'a[href*="login"]', 'button:has-text("Log in")'
                ]
                for sel in selectors:
                    if page.locator(sel).first.is_visible():
                        page.locator(sel).first.click()
                        break
            except:
                pass

            # Some tenants redirect to /login or show modal
            page.wait_for_load_state("domcontentloaded", timeout=60000)

            # try email/password fields
            # Note: selectors can change; we try a few common names/ids
            candidates_email = ['input[name="email"]', 'input#TANGRAM__PSP_4__email', 'input[type="email"]']
            candidates_pass  = ['input[name="password"]', 'input[type="password"]']

            filled = False
            for es in candidates_email:
                if page.locator(es).first.count() > 0:
                    page.locator(es).first.fill(TB_EMAIL)
                    filled = True
                    break
            if not filled:
                raise RuntimeError("Could not find email field. UI changed or captcha shown.")

            filled = False
            for ps in candidates_pass:
                if page.locator(ps).first.count() > 0:
                    page.locator(ps).first.fill(TB_PASSWORD)
                    filled = True
                    break
            if not filled:
                raise RuntimeError("Could not find password field. UI changed or captcha shown.")

            # submit
            # Try pressing Enter or clicking a submit/login button
            try:
                page.keyboard.press("Enter")
            except:
                pass
            try:
                page.locator('button[type="submit"]').first.click()
            except:
                pass

            # Wait for navigation / account area
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            # small grace time for JS
            time.sleep(3)

            # Check for captcha or failure
            html = page.content().lower()
            if "captcha" in html:
                browser.close()
                raise RuntimeError("Login blocked by CAPTCHA. Manual cookie method required.")

            if not logged_in():
                browser.close()
                raise RuntimeError("Login failed. Check credentials.")

            # Persist cookies for future runs
            save_cookies(context)

        cookie_header = cookies_to_header(context)
        browser.close()
        if not cookie_header:
            raise RuntimeError("Could not build cookie header after login.")
        return cookie_header

# ---------- Share link → direct link resolution ----------

def resolve_direct_link(share_url, cookie_header):
    """
    Load the share page (authenticated) and extract a `d.terabox.com` direct link
    and filename from the embedded JSON. Returns (dlink, filename).
    """
    headers = {"User-Agent": UA, "Cookie": cookie_header}
    resp = requests.get(share_url, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to open share link (HTTP {resp.status_code})")

    text = resp.text

    # Extract filename
    fname = "file.bin"
    m_name = re.search(r'"server_filename"\s*:\s*"([^"]+)"', text)
    if m_name:
        fname = m_name.group(1)

    # Extract direct link (escaped)
    m_dlink = re.search(r'"dlink"\s*:\s*"(https:[^"]+)"', text)
    if not m_dlink:
        # Sometimes link is under "downloadlink" or similar keys
        m_dlink = re.search(r'"downloadlink"\s*:\s*"(https:[^"]+)"', text)
    if not m_dlink:
        raise RuntimeError("Direct link not found on the page (maybe cookies invalid or file requires extra auth).")

    dlink = m_dlink.group(1)
    # Unescape \u0026 → &
    dlink = dlink.replace("\\u0026", "&").replace("\\/", "/")
    return dlink, fname

# ---------- Download with progress ----------

async def download_with_progress(url, status_msg, cookie_header, suggested_name):
    headers = {"User-Agent": UA, "Cookie": cookie_header}
    r = requests.get(url, headers=headers, stream=True, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Direct download failed (HTTP {r.status_code})")

    total = int(r.headers.get("Content-Length", 0))
    # filename from header or fallback to suggested
    cd = r.headers.get("Content-Disposition", "")
    if "filename=" in cd:
        filename = cd.split("filename=")[-1].strip('"')
    else:
        filename = suggested_name or "file.bin"
        # try URL tail
        tail = os.path.basename(urlparse(url).path)
        if tail and "." in tail:
            filename = tail

    tmp = NamedTemporaryFile(delete=False, dir="/tmp")
    downloaded = 0
    last_pct = -1
    for chunk in r.iter_content(1024 * 1024):
        if not chunk:
            continue
        tmp.write(chunk)
        downloaded += len(chunk)
        if total > 0:
            pct = int(downloaded * 100 / total)
            if pct // 5 > last_pct // 5:  # update every ~5%
                last_pct = pct
                try:
                    await status_msg.edit_text(f"⬇️ Downloading… {pct}%")
                except:
                    pass
    tmp.flush()
    return filename, tmp

# ---------- Telegram handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a Terabox *share link* like `https://www.terabox.com/s/...`.\n"
        "I will log in, resolve the direct link, download fast, and send it back (≤ 2GB).",
        parse_mode="Markdown"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = (update.message.text or "").strip()
    status = await update.message.reply_text("🔐 Logging in to Terabox…")
    try:
        if not TB_EMAIL or not TB_PASSWORD:
            raise RuntimeError("TB_EMAIL / TB_PASSWORD env vars are not set.")

        cookie_header = ensure_logged_in_and_get_cookie_header()
        await status.edit_text("🔎 Resolving direct link…")

        dlink, fname = resolve_direct_link(link, cookie_header)
        await status.edit_text(f"⬇️ Starting download: {fname}")

        fname, tempf = await download_with_progress(dlink, status, cookie_header, fname)

        size = os.path.getsize(tempf.name)
        if size > 2 * 1024 * 1024 * 1024:
            await status.edit_text("⚠️ File is larger than 2 GB. Telegram bots cannot send it.")
        else:
            await status.edit_text("📤 Uploading to Telegram…")
            with open(tempf.name, "rb") as f:
                await update.message.reply_document(f, filename=fname)
            await status.edit_text("✅ Done!")

    except Exception as e:
        await status.edit_text(f"❌ Error: {e}")

    finally:
        try:
            temp_path = locals().get("tempf").name if "tempf" in locals() and tempf else None
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling()

if __name__ == "__main__":
    main()
