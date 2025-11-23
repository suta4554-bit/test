import os
import time
import logging
import aiohttp
import re
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
    bot_token=BOT_TOKEN,
    in_memory=True
)

async def extract_direct_link(url, session):
    """Try to extract direct download link from file hosting pages"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        async with session.get(url, headers=headers, timeout=30) as response:
            if response.status != 200:
                return None
            
            html = await response.text()
            
            # Pattern 1: Look for direct download URLs in common formats
            patterns = [
                r'href=["\']([^"\']+\.(?:mp4|mkv|avi|mov|pdf|zip|rar|7z|exe|apk)[^"\']*)["\']',
                r'src=["\']([^"\']+\.(?:mp4|mkv|avi|mov)[^"\']*)["\']',
                r'<a[^>]+download[^>]+href=["\']([^"\']+)["\']',
                r'window\.location\.href\s*=\s*["\']([^"\']+)["\']',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    # Filter out obviously wrong matches
                    for match in matches:
                        if not any(x in match.lower() for x in ['javascript:', 'void(0)', '#', 'logo', 'icon', 'banner']):
                            logger.info(f"Found potential direct link: {match}")
                            # Make absolute URL if relative
                            if match.startswith('http'):
                                return match
                            elif match.startswith('/'):
                                from urllib.parse import urlparse
                                parsed = urlparse(url)
                                return f"{parsed.scheme}://{parsed.netloc}{match}"
            
            return None
    except Exception as e:
        logger.error(f"Link extraction error: {e}")
        return None

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        f"Welcome! Send me a download link and I'll upload it to @{CHANNEL_USERNAME}.\n\n"
        "Supported: Direct links, MediaFire, GoFile, and similar sites."
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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': url
        }
        
        async with aiohttp.ClientSession() as session:
            # First, try to check if it's a direct link
            async with session.head(url, headers=headers, timeout=30, allow_redirects=True) as head_response:
                content_type = head_response.headers.get('Content-Type', '').lower()
                
                # If it's HTML, try to extract the real download link
                if 'text/html' in content_type:
                    await status_msg.edit_text("Extracting download link...")
                    direct_link = await extract_direct_link(url, session)
                    
                    if direct_link:
                        logger.info(f"Extracted direct link: {direct_link}")
                        url = direct_link
                        await status_msg.edit_text("Found direct link! Starting download...")
                    else:
                        await status_msg.edit_text(
                            "❌ Could not extract direct download link.\n\n"
                            "Please provide a **direct download URL** or right-click the download button and copy the link."
                        )
                        return
            
            # Now download the file
            async with session.get(url, headers=headers, timeout=600, allow_redirects=True) as response:
                
                if response.status != 200:
                    await status_msg.edit_text(f"❌ Error: Server returned status {response.status}")
                    return
                
                # Double-check content type
                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type:
                    await status_msg.edit_text(
                        "❌ Still getting HTML instead of a file.\n\n"
                        "The link extractor couldn't find the direct download URL. "
                        "Please manually copy the direct download link."
                    )
                    return
                
                # Extract filename
                filename = "downloaded_file"
                if "Content-Disposition" in response.headers:
                    cd = response.headers["Content-Disposition"]
                    if "filename=" in cd:
                        filename = cd.split("filename=")[1].strip('"').strip("'")
                
                if filename == "downloaded_file" and url.split("/")[-1]:
                    filename = url.split("/")[-1].split("?")[0]
                
                # Add extension based on content type if missing
                if "." not in filename:
                    ext_map = {
                        'video/mp4': '.mp4',
                        'video/x-matroska': '.mkv',
                        'application/pdf': '.pdf',
                        'application/zip': '.zip',
                        'image/jpeg': '.jpg',
                        'image/png': '.png',
                        'video/x-msvideo': '.avi'
                    }
                    for ct, ext in ext_map.items():
                        if ct in content_type:
                            filename += ext
                            break

                await status_msg.edit_text(f"Downloading **{filename}**...")
                
                file_path = os.path.join("/tmp", filename)
                
                with open(file_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024): 
                        f.write(chunk)

        # Upload to Channel
        await status_msg.edit_text(f"Upload to @{CHANNEL_USERNAME}...")

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

        link = sent_msg.link if sent_msg.link else f"t.me/{CHANNEL_USERNAME}"
        await status_msg.edit_text(f"✅ Uploaded!\nLink: {link}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")
    
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

if __name__ == "__main__":
    logger.info(f"Bot started. Target: @{CHANNEL_USERNAME}")
    app.run()
