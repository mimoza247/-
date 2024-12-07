import os
import time
import whois
import socket
import requests
from PIL import Image
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# List of allowed Telegram user IDs (replace with actual IDs)
ALLOWED_USERS = [123456789, 987654321]  # Replace with your Telegram ID

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Configure Chrome options for Selenium
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--start-maximized')

async def check_auth(update: Update) -> bool:
    """Check if user is authorized to use the bot"""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    if not await check_auth(update):
        return
    
    await update.message.reply_text(
        "Welcome to the Website Checker Bot!\n"
        "Send me a website URL to check its availability and get detailed information."
    )

async def get_website_info(url: str) -> dict:
    """Get website information including response time and other details"""
    try:
        # Check connection time
        start_time = time.time()
        response = requests.get(url, timeout=10)
        response_time = round((time.time() - start_time) * 1000)  # in milliseconds

        # Get domain info
        domain = url.split("//")[-1].split("/")[0]
        ip = socket.gethostbyname(domain)
        
        try:
            domain_info = whois.whois(domain)
        except:
            domain_info = None

        return {
            "status": response.status_code,
            "response_time": response_time,
            "ip": ip,
            "domain": domain,
            "registrar": domain_info.registrar if domain_info else "N/A",
            "creation_date": domain_info.creation_date[0] if domain_info and isinstance(domain_info.creation_date, list) else domain_info.creation_date if domain_info else "N/A",
            "expiration_date": domain_info.expiration_date[0] if domain_info and isinstance(domain_info.expiration_date, list) else domain_info.expiration_date if domain_info else "N/A"
        }
    except Exception as e:
        return {"error": str(e)}

async def take_screenshot(url: str) -> str:
    """Take a screenshot of the website"""
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        time.sleep(2)  # Wait for page to load
        screenshot_path = "screenshot.png"
        driver.save_screenshot(screenshot_path)
        driver.quit()

        # Resize image if too large
        with Image.open(screenshot_path) as img:
            if img.size[0] > 1280:
                ratio = 1280 / img.size[0]
                new_size = (1280, int(img.size[1] * ratio))
                img = img.resize(new_size, Image.LANCZOS)
                img.save(screenshot_path)

        return screenshot_path
    except Exception as e:
        return None

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle URL messages"""
    if not await check_auth(update):
        return

    url = update.message.text
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # Send "processing" message
    processing_msg = await update.message.reply_text("Processing your request...")

    try:
        # Get website info
        info = await get_website_info(url)
        
        # Take screenshot
        screenshot = await take_screenshot(url)

        # Prepare initial response
        response_text = f"🌐 Website: {url}\n"
        response_text += f"⏱ Response Time: {info.get('response_time', 'N/A')}ms\n"
        response_text += f"📊 Status: {info.get('status', 'N/A')}\n"

        # Create "More Info" button
        keyboard = [[InlineKeyboardButton("More Info ℹ️", callback_data=f"more_{url}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Delete processing message
        await processing_msg.delete()

        # Send screenshot if available
        if screenshot:
            with open(screenshot, 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=response_text,
                    reply_markup=reply_markup
                )
            os.remove(screenshot)
        else:
            await update.message.reply_text(
                response_text + "\n❌ Could not generate screenshot",
                reply_markup=reply_markup
            )

    except Exception as e:
        await processing_msg.edit_text(f"Error checking website: {str(e)}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    if not await check_auth(update):
        return

    query = update.callback_query
    await query.answer()

    if query.data.startswith("more_"):
        url = query.data[5:]
        info = await get_website_info(url)

        detailed_info = f"🌐 Detailed Information for {url}\n\n"
        detailed_info += f"🔍 IP Address: {info.get('ip', 'N/A')}\n"
        detailed_info += f"🏢 Registrar: {info.get('registrar', 'N/A')}\n"
        detailed_info += f"📅 Created: {info.get('creation_date', 'N/A')}\n"
        detailed_info += f"⌛ Expires: {info.get('expiration_date', 'N/A')}\n"

        await query.edit_message_caption(
            caption=detailed_info,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Back 🔙", callback_data=f"back_{url}")
            ]])
        )

    elif query.data.startswith("back_"):
        url = query.data[5:]
        info = await get_website_info(url)

        basic_info = f"🌐 Website: {url}\n"
        basic_info += f"⏱ Response Time: {info.get('response_time', 'N/A')}ms\n"
        basic_info += f"📊 Status: {info.get('status', 'N/A')}\n"

        await query.edit_message_caption(
            caption=basic_info,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("More Info ℹ️", callback_data=f"more_{url}")
            ]])
        )

def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))

    application.run_polling()

if __name__ == '__main__':
    main()