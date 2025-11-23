import os
import time
import logging
import aiohttp
from pyrogram import Client, filters, errors
from pyrogram.types import Message

# --- Configuration ---
BOT_TOKEN = "7714074717:AAEUdT9tXgRH1v2V1ffnYEPGUGCcehkR4oM"
API_ID = 21845364
API_HASH = "ae2387f39ee2ae207f378feaa19579b6"

# Use the username (without t.me/) for public channels
CHANNEL_USERNAME = "ahajajjaowij" 

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Client(
    "my_bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        f"Welcome! Send me a link, and I will upload the file to @{CHANNEL_USERNAME}."
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
                
                filename = "downloaded_file"
                if "Content-Disposition" in response.headers:
                    cd = response.headers["Content-Disposition"]
                    if "filename=" in cd:
                        filename = cd.split("filename=")[1].strip('"').strip("'")
                else:
                    if url.split("/")[-1]:
                        filename = url.split("/")[-1]

                await status_msg.edit_text(f"Downloading **{filename}**...")
                
                file_path = os.path.join(os.getcwd(), filename)
                
                with open(file_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024): 
                        f.write(chunk)

        # 2. Upload to Channel
        await status_msg.edit_text(f"Download done. Uploading to @{CHANNEL_USERNAME}...")

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

        sent_msg = await client.send_document(
            chat_id=CHANNEL_USERNAME, 
            document=file_path,
            caption=f"Filename: {filename}\nSource: {url}\nUser: {message.from_user.mention}",
            progress=progress
        )

        # 3. Confirmation
        link = sent_msg.link if sent_msg.link else f"t.me/{CHANNEL_USERNAME}"
        await status_msg.edit_text(f"? File successfully uploaded!\nLink: {link}")

    except errors.UsernameNotOccupied:
        await status_msg.edit_text(f"? **Error**: The username @{CHANNEL_USERNAME} does not exist.")
    except errors.UsernameInvalid:
         await status_msg.edit_text(f"? **Error**: The username @{CHANNEL_USERNAME} is invalid.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"An error occurred: {str(e)}")
    
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

if __name__ == "__main__":
    print(f"Bot started. Target channel: @{CHANNEL_USERNAME}")
    app.run()
