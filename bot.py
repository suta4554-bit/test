import os
import time
import logging
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from flask import Flask
from threading import Thread

# --- Configuration ---
BOT_TOKEN = "7714074717:AAEUdT9tXgRH1v2V1ffnYEPGUGCcehkR4oM"
API_ID = 21845364
API_HASH = "ae2387f39ee2ae207f378feaa19579b6"
CHANNEL_ID = -1003353251476

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app for health check
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return """
    <html>
        <head><title>Telegram File Uploader Bot</title></head>
        <body style="font-family: Arial; padding: 20px; background: #f0f0f0;">
            <h1>🤖 Bot Status: Running</h1>
            <p>Bot is active and monitoring messages.</p>
            <p>Channel ID: <code>-1003353251476</code></p>
            <p>Uptime: Online ✅</p>
        </body>
    </html>
    """

@flask_app.route('/health')
def health():
    return {"status": "healthy", "bot": "running"}, 200

@flask_app.route('/ping')
def ping():
    return "pong", 200

def run_flask():
    """Run Flask in a separate thread"""
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Pyrogram client
app = Client(
    "my_bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Welcome! Send me a link, and I will upload the file to the storage channel."
    )

@app.on_message(filters.text & ~filters.command(["start"]))
async def download_to_channel(client: Client, message: Message):
    url = message.text.strip()
    
    if not url.startswith(("http://", "https://")):
        await message.reply_text("Please send a valid HTTP/HTTPS URL.")
        return

    status_msg = await message.reply_text("Processing link...")
    
    file_path = None
    try:
        # 1. Download
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=600) as response:
                if response.status != 200:
                    await status_msg.edit_text(f"Error: Server returned status {response.status}")
                    return
                
                # Extract filename
                filename = "downloaded_file"
                if "Content-Disposition" in response.headers:
                    cd = response.headers["Content-Disposition"]
                    if "filename=" in cd:
                        filename = cd.split("filename=")[1].strip('"').strip("'")
                else:
                    if url.split("/")[-1]:
                        filename = url.split("/")[-1]

                await status_msg.edit_text(f"Downloading **{filename}**...")
                
                file_path = os.path.join("/tmp", filename)
                
                # Write to disk
                with open(file_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)

        # 2. Upload to Channel
        await status_msg.edit_text(f"Download done. Uploading to channel...")

        # Progress tracker
        async def progress(current, total):
            now = time.time()
            if hasattr(progress, 'last_time') and now - progress.last_time < 5:
                return
            progress.last_time = now
            
            percent = (current / total) * 100
            try:
                await status_msg.edit_text(f"Uploading: {percent:.1f}%")
            except:
                pass
        progress.last_time = 0

        caption_text = f"Filename: {filename}\nSource: {url}\nUser: {message.from_user.mention}"

        sent_msg = await client.send_document(
            chat_id=CHANNEL_ID,
            document=file_path,
            caption=caption_text,
            progress=progress
        )

        # 3. Confirmation
        link = sent_msg.link if sent_msg.link else "in the channel"
        await status_msg.edit_text(f"✅ File successfully uploaded!\nLink: {link}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"An error occurred: {str(e)}")
    
    finally:
        # Cleanup
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

if __name__ == "__main__":
    # Start Flask server in background thread
    logger.info("Starting Flask server...")
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Start Pyrogram bot
    logger.info("Starting Telegram bot...")
    app.run()
