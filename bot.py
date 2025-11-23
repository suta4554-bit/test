import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import tempfile

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = "7714074717:AAEUdT9tXgRH1v2V1ffnYEPGUGCcehkR4oM"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Welcome! Send me a URL and I'll download the file and send it back to you.\n\n"
        "Example: https://example.com/file.pdf"
    )

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Download file from URL and send it back to user."""
    url = update.message.text.strip()
    
    # Check if the message contains a URL
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("Please send a valid URL starting with http:// or https://")
        return
    
    await update.message.reply_text("Downloading file... Please wait.")
    
    try:
        # Send GET request to download the file
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()
        
        # Get filename from URL or Content-Disposition header
        filename = None
        if 'Content-Disposition' in response.headers:
            content_disposition = response.headers['Content-Disposition']
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"')
        
        if not filename:
            filename = url.split('/')[-1] or 'downloaded_file'
        
        # Create temporary file to save the downloaded content
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}") as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            temp_path = tmp_file.name
        
        # Get file size
        file_size = os.path.getsize(temp_path)
        file_size_mb = file_size / (1024 * 1024)
        
        # Telegram bot API has a 50MB file size limit
        if file_size_mb > 50:
            await update.message.reply_text(
                f"File is too large ({file_size_mb:.2f} MB). "
                "Telegram bot API supports files up to 50 MB."
            )
            os.unlink(temp_path)
            return
        
        # Send the file to user
        await update.message.reply_text(f"Uploading {filename} ({file_size_mb:.2f} MB)...")
        
        with open(temp_path, 'rb') as file:
            await update.message.reply_document(
                document=file,
                filename=filename,
                caption=f"Downloaded from: {url}"
            )
        
        # Clean up temporary file
        os.unlink(temp_path)
        
    except requests.exceptions.Timeout:
        await update.message.reply_text("Download timeout. The server took too long to respond.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading file: {e}")
        await update.message.reply_text(f"Error downloading file: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await update.message.reply_text(f"An error occurred: {str(e)}")

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))

    # Run the bot
    logger.info("Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
