import os
import time
import logging
import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from keep_alive import keep_alive  # Import the Flask server

# --- Configuration ---
BOT_TOKEN = "8479713796:AAE2_60AwV5mXL51LoApo45WQGbwQ2XZYEw"
API_ID = 21845364
API_HASH = "ae2387f39ee2ae207f378feaa19579b6"
CHANNEL_ID = -1003353251476

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize the Pyrogram Client
app = Client(
    "my_bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Welcome! Send me a direct download link (HTTP/HTTPS), and I will "
        "download the file and send it back to you.\n\n"
        "I can handle files up to 2GB."
    )

@app.on_message(filters.text & ~filters.command(["start"]))
async def download_and_send(client: Client, message: Message):
    url = message.text.strip()
    
    if not url.startswith(("http://", "https://")):
        await message.reply_text("Please send a valid HTTP/HTTPS URL.")
        return

    status_msg = await message.reply_text("Checking URL...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as response:
                if response.status != 200:
                    await status_msg.edit_text(f"Error: Server returned status {response.status}")
                    return
                
                filename = "downloaded_file"
                if "Content-Disposition" in response.headers:
                    cd = response.headers["Content-Disposition"]
                    if "filename=" in cd:
                        filename = cd.split("filename=")[1].strip('"').strip("'")
                else:
                    if url.split("/")[-1]:
                        filename = url.split("/")[-1]

                file_size = int(response.headers.get("Content-Length", 0))
                
                if file_size > 2000 * 1024 * 1024:
                    await status_msg.edit_text("Error: File is larger than 2GB limit.")
                    return

                await status_msg.edit_text(f"Downloading **{filename}**...\nThis may take a while for large files.")
                
                file_path = os.path.join(os.getcwd(), filename)
                
                downloaded = 0
                last_update_time = 0
                
                with open(file_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024): 
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        current_time = time.time()
                        if current_time - last_update_time > 5:
                            size_mb = downloaded / (1024 * 1024)
                            await status_msg.edit_text(f"Downloading: {size_mb:.2f} MB")
                            last_update_time = current_time
                
                await status_msg.edit_text("Download complete. Uploading to Telegram...")

                async def progress(current, total):
                    current_time = time.time()
                    if hasattr(progress, 'last_update') and current_time - progress.last_update < 5:
                        return
                    progress.last_update = current_time
                    percent = (current / total) * 100
                    try:
                        await status_msg.edit_text(f"Uploading: {percent:.1f}%")
                    except:
                        pass
                progress.last_update = 0

                await client.send_document(
                    chat_id=message.chat.id,
                    document=file_path,
                    caption=f"File: {filename}\nSource: {url}",
                    progress=progress
                )
                
                await status_msg.delete()
                
                if os.path.exists(file_path):
                    os.remove(file_path)

    except aiohttp.ClientError as e:
        await status_msg.edit_text(f"Network error during download: {e}")
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"An error occurred: {str(e)}")
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

if __name__ == "__main__":
    print("Starting web server...")
    keep_alive()  # Starts the Flask server in a separate thread
    print("Bot started...")
    app.run()
