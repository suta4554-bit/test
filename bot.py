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
        f"Welcome! Send me a **direct download link** (must return a file), and I will upload it to @{CHANNEL_USERNAME}.\n\n"
        "Note: Regular website links that require JavaScript or show download buttons will NOT work."
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
        # 1. Download with better headers and redirect handling
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': url
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=600, allow_redirects=True) as response:
                
                # Log the response for debugging
                logger.info(f"Status: {response.status}, URL: {response.url}, Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
                
                if response.status != 200:
                    await status_msg.edit_text(
                        f"❌ Error: Server returned status {response.status}\n\n"
                        f"This URL might not be a direct download link. "
                        f"Make sure the link directly returns a file, not a webpage."
                    )
                    return
                
                # Check if content is actually a file (not HTML)
                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type:
                    await status_msg.edit_text(
                        "❌ Error: This URL returns a webpage (HTML), not a file.\n\n"
                        "Please send a **direct download link** that starts the download immediately."
                    )
                    return
                
                # Extract filename
                filename = "downloaded_file"
                if "Content-Disposition" in response.headers:
                    cd = response.headers["Content-Disposition"]
                    if "filename=" in cd:
                        filename = cd.split("filename=")[1].strip('"').strip("'")
                
                # Fallback to URL if no filename in headers
                if filename == "downloaded_file" and url.split("/")[-1]:
                    filename = url.split("/")[-1].split("?")[0]  # Remove query params
                
                # If still no extension, try to guess from Content-Type
                if "." not in filename and content_type:
                    ext_map = {
                        'video/mp4': '.mp4',
                        'video/x-matroska': '.mkv',
                        'application/pdf': '.pdf',
                        'application/zip': '.zip',
                        'image/jpeg': '.jpg',
                        'image/png': '.png'
                    }
                    for ct, ext in ext_map.items():
                        if ct in content_type:
                            filename += ext
                            break

                await status_msg.edit_text(f"Downloading **{filename}**...")
                
                file_path = os.path.join(os.getcwd(), filename)
                
                downloaded_size = 0
                with open(file_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024): 
                        f.write(chunk)
                        downloaded_size += len(chunk)

                # Check if file is suspiciously small (might be error page)
                if downloaded_size < 1024:  # Less than 1KB
                    with open(file_path, 'r', errors='ignore') as f:
                        content = f.read(500)
                        if '<html' in content.lower() or '<body' in content.lower():
                            await status_msg.edit_text(
                                "❌ Error: The downloaded file appears to be an HTML error page.\n\n"
                                "The link you provided is not a direct download link."
                            )
                            os.remove(file_path)
                            return

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

        caption_text = f"Filename: {filename}\nSource: {url}\nUser: {message.from_user.mention}"

        sent_msg = await client.send_document(
            chat_id=CHANNEL_USERNAME, 
            document=file_path,
            caption=caption_text,
            progress=progress
        )

        # 3. Confirmation
        link = sent_msg.link if sent_msg.link else f"t.me/{CHANNEL_USERNAME}"
        await status_msg.edit_text(f"✅ File successfully uploaded!\nLink: {link}")

    except aiohttp.ClientError as e:
        await status_msg.edit_text(f"❌ Network error: {str(e)}")
    except errors.UsernameNotOccupied:
        await status_msg.edit_text(f"❌ **Error**: The username @{CHANNEL_USERNAME} does not exist.")
    except errors.UsernameInvalid:
        await status_msg.edit_text(f"❌ **Error**: The username @{CHANNEL_USERNAME} is invalid.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"An error occurred: {str(e)}")
    
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

if __name__ == "__main__":
    print(f"Bot started. Target channel: @{CHANNEL_USERNAME}")
    app.run()
