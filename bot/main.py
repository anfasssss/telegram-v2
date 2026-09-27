import os
import re
import asyncio
import http.server
import socketserver
import threading

from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


from services.downloader import download_instagram
from services.metadata import extract_metadata
from services.comments import extract_top_comment
from services.watermark.engine import add_watermark
from services.download_queue import DownloadQueue
from services.database import (
    create_download,
    update_download_status
)
from services.database import (
    initialize_database,
    create_download,
    update_download_status,
    get_download_stats,
    get_user_downloads,
    check_database,
)
from utils.media import get_media_type
from utils.system import (
    check_ffmpeg,
    check_ytdlp,
    check_instaloader,
    check_playwright,
)
from telegram.error import BadRequest



load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")


def is_instagram_url(text: str) -> bool:
    pattern = r"https?://(www\.)?instagram\.com/[^\s]+"
    return bool(re.search(pattern, text, re.IGNORECASE))


def extract_instagram_urls(text: str) -> list[str]:
    """
    Extract all Instagram URLs from a message.
    """

    pattern = r"https?://(?:www\.)?instagram\.com/[^\s]+"

    return re.findall(
        pattern,
        text,
        re.IGNORECASE
    )


async def update_status(status_message, text):
    try:
        await status_message.edit_text(text)

    except BadRequest as e:
        if "Message is not modified" in str(e):
            return

        print(
            f"⚠️ Status update warning: "
            f"{type(e).__name__}: {e}"
        )

    except Exception as e:
        print(
            f"⚠️ Status update warning: "
            f"{type(e).__name__}: {e}"
        )

                    
download_queue = DownloadQueue(max_concurrent=1)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Send me an Instagram Reel, video, photo, "
        "or carousel URL and I'll download the media for you.\n\n"
        "🎥 Videos include the original creator's "
        "username as a watermark.\n\n"
        "📜 /history — View your recent downloads\n"
        "❓ /help — Learn how to use the bot"
    )
    
async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Show download statistics to the admin only.
    """

    if str(update.effective_user.id) != ADMIN_USER_ID:
        await update.message.reply_text(
            "❌ You are not authorized to use this command."
        )
        return

    statistics = get_download_stats()

    message = (
        "📊 Bot Statistics\n\n"
        f"📥 Total downloads: {statistics['total']}\n"
        f"✅ Completed: {statistics['completed']}\n"
        f"❌ Failed: {statistics['failed']}\n\n"
        f"🎥 Videos: {statistics['videos']}\n"
        f"🖼️ Photos: {statistics['photos']}"
    )

    await update.message.reply_text(message)
    

async def history(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Show the user's recent download history.
    """

    user_id = update.effective_user.id

    downloads = get_user_downloads(
        user_id,
        limit=10
    )

    if not downloads:
        await update.message.reply_text(
            "📜 You don't have any download history yet."
        )
        return

    message = "📜 Your Recent Downloads\n\n"

    for index, download in enumerate(downloads, start=1):

        creator = (
            download["creator_username"]
            or "Unknown creator"
        )

        media_icon = (
            "🎥"
            if download["media_type"] == "video"
            else "🖼️"
        )

        status_icon = (
            "✅"
            if download["status"] == "completed"
            else "❌"
            if download["status"] == "failed"
            else "⏳"
        )

        message += (
            f"{index}. {media_icon} @{creator}\n"
            f"   {status_icon} {download['status'].title()}\n"
            f"   📅 {download['created_at']}\n\n"
        )

    await update.message.reply_text(message)
    
    
async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Show instructions for using the bot.
    """

    message = (
        "📖 How to use the bot\n\n"
        "1️⃣ Send an Instagram Reel, video, photo, "
        "or carousel URL.\n\n"
        "2️⃣ The bot will download the media and "
        "send it back to you.\n\n"
        "3️⃣ Videos will include the original "
        "creator's username as a watermark.\n\n"
        "📜 /history — View your recent downloads\n"
        "❓ /help — Show these instructions\n\n"
        "💡 You can send multiple Instagram URLs "
        "in one message."
    )

    await update.message.reply_text(message)
    
    
async def diagnostics(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Show basic system diagnostics to the admin only.
    """

    if str(update.effective_user.id) != ADMIN_USER_ID:
        await update.message.reply_text(
            "❌ You are not authorized to use this command."
        )
        return

    database_status = check_database()
    ffmpeg_status = check_ffmpeg()
    ytdlp_status = check_ytdlp()
    instaloader_status = check_instaloader()
    playwright_status = await asyncio.to_thread(
        check_playwright 
    )

    database_icon = (
        "✅" if database_status else "❌"
    )
    
    ffmpeg_icon = (
        "✅" if ffmpeg_status else "❌"
    )
    
    ytdlp_icon = (
        "✅" if ytdlp_status else "❌"
    )
    
    instaloader_icon = (
        "✅" if instaloader_status else "❌"
    )
    
    playwright_icon = (
        "✅" if playwright_status else "❌"
    )

    message = (
        "🛠️ System Diagnostics\n\n"
        f"🗄️ SQLite Database: {database_icon}"
        f"🎬 FFmpeg: {ffmpeg_icon}"
        f"📥 yt-dlp: {ytdlp_icon}"
        f"📊 Instaloader: {instaloader_icon}"
        f"🌐 Playwright: {playwright_icon}"
    )

    await update.message.reply_text(message)
    

async def send_long_message(update, text):
    """
    Send a long text message in chunks that fit
    within Telegram's message length limit.
    """
    max_length = 4000

    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]

        await update.message.reply_text(
            chunk,
            connect_timeout=60,
            read_timeout=300,
            write_timeout=300,
        )

async def process_instagram(
    update,
    text,
    status_message,
    download_id
):
    await update_status(
        status_message,
        "⬇️ Downloading Instagram media..."
    )

    file_path = None
    processed_file_path = None

    try:
        update_download_status(
            download_id,
            "processing"
        )

        # -------------------------------------------------
        # 1. Download Instagram media
        # -------------------------------------------------

        print("[1] Starting download...")

        downloaded = await asyncio.to_thread(
            download_instagram,
            text
        )

        print(
            f"[1] Download complete: {downloaded}"
        )

        file_path = downloaded

        # -------------------------------------------------
        # Detect single media / carousel
        # -------------------------------------------------

        if isinstance(downloaded, list):
            file_paths = downloaded
            is_carousel = True

        else:
            file_paths = [downloaded]
            is_carousel = False

        print(
            f"📦 Media count: {len(file_paths)}"
        )

        # -------------------------------------------------
        # Detect media type
        # -------------------------------------------------

        if is_carousel:
            media_type = "photo"

        else:
            media_type = await asyncio.to_thread(
                get_media_type,
                file_paths[0]
            )

        print(
            f"📁 Detected media type: {media_type}"
        )

        # -------------------------------------------------
        # 2. Extract Instagram metadata
        # -------------------------------------------------

        await update_status(
            status_message,
            "📝 Extracting Instagram metadata..."
        )

        print(
            "[2] Starting metadata extraction..."
        )

        metadata = await asyncio.to_thread(
            extract_metadata,
            text
        )

        print(
            "[2] Metadata extraction complete."
        )

        # -------------------------------------------------
        # 3. Prepare files for sending
        # -------------------------------------------------

        if is_carousel:

            processed_file_path = file_paths

            print(
                "[3] Watermark skipped — "
                "carousel."
            )

        else:

            processed_file_path = file_paths[0]

            # ---------------------------------------------
            # Watermark video
            # ---------------------------------------------

            if media_type == "video":

                await update_status(
                    status_message,
                    "🏷️ Adding creator watermark..."
                )

                print(
                    "[3] Adding video watermark..."
                )

                processed_file_path = (
                    await asyncio.to_thread(
                        add_watermark,
                        file_paths[0],
                        metadata["username"]
                    )
                )

                print(
                    f"[3] Watermark complete: "
                    f"{processed_file_path}"
                )

            else:

                print(
                    "[3] Watermark skipped — "
                    "media is not a video."
                )

        # -------------------------------------------------
        # 4. Build merged caption
        # -------------------------------------------------

        caption_parts = []

        # Creator username
        username = metadata.get(
            "username"
        )

        if username:
            caption_parts.append(
                f"👤 @{username}"
            )

        # Original Instagram caption
        caption_text = (
            metadata.get("caption") or ""
        ).strip()

        if caption_text:
            caption_parts.append(
                caption_text
            )

        # Hashtags
        hashtags = metadata.get(
            "hashtags",
            []
        )

        if hashtags:

            formatted_hashtags = " ".join(
                f"#{tag}"
                for tag in hashtags
            )

            caption_parts.append(
                formatted_hashtags
            )

        # Upload date
        upload_date = metadata.get(
            "date"
        )

        if upload_date:

            try:

                formatted_date = (
                    datetime
                    .fromisoformat(
                        upload_date
                    )
                    .strftime(
                        "%d %B %Y"
                    )
                )

            except (
                ValueError,
                TypeError
            ):

                formatted_date = (
                    upload_date
                )

            caption_parts.append(
                f"📅 {formatted_date}"
            )

        # Original Instagram URL
        original_url = metadata.get(
            "url"
        )

        if original_url:
            caption_parts.append(
                original_url
            )

        # Join everything
        media_caption = "\n\n".join(
            caption_parts
        )

        # -------------------------------------------------
        # Telegram caption limit
        # -------------------------------------------------

        MAX_CAPTION_LENGTH = 1024

        if len(media_caption) > MAX_CAPTION_LENGTH:

            print(
                "⚠️ Caption exceeds Telegram "
                "1024 character limit."
            )

            # Preserve the important information:
            # username, date and URL.

            short_parts = []

            if username:
                short_parts.append(
                    f"👤 @{username}"
                )

            # Calculate space remaining
            reserved_parts = []

            if upload_date:
                reserved_parts.append(
                    f"📅 {formatted_date}"
                )

            if original_url:
                reserved_parts.append(
                    original_url
                )

            reserved_text = "\n\n".join(
                reserved_parts
            )

            remaining_length = (
                MAX_CAPTION_LENGTH
                - len(reserved_text)
                - 4
            )

            if caption_text and remaining_length > 0:

                shortened_caption = (
                    caption_text[
                        :remaining_length
                    ].rstrip()
                )

                if len(shortened_caption) < len(
                    caption_text
                ):
                    shortened_caption += "..."

                short_parts.append(
                    shortened_caption
                )

            # Add hashtags if space remains
            if hashtags:

                hashtag_text = " ".join(
                    f"#{tag}"
                    for tag in hashtags
                )

                current_length = len(
                    "\n\n".join(short_parts)
                )

                available = (
                    MAX_CAPTION_LENGTH
                    - current_length
                    - len(reserved_text)
                    - 4
                )

                if available > len(hashtag_text):

                    short_parts.append(
                        hashtag_text
                    )

            # Date
            if upload_date:
                short_parts.append(
                    f"📅 {formatted_date}"
                )

            # URL
            if original_url:
                short_parts.append(
                    original_url
                )

            media_caption = (
                "\n\n".join(short_parts)
            )

            # Final safety cut
            media_caption = (
                media_caption[
                    :MAX_CAPTION_LENGTH
                ]
            )

        print(
            f"📝 Final caption length: "
            f"{len(media_caption)}"
        )

        # -------------------------------------------------
        # 5. Send media
        # -------------------------------------------------

        await update_status(
            status_message,
            "📤 Sending media..."
        )

        # -------------------------------------------------
        # Carousel
        # -------------------------------------------------

        if is_carousel:

            print(
                f"📸 Sending carousel with "
                f"{len(processed_file_path)} images..."
            )

            for index, path in enumerate(
                processed_file_path
            ):

                with open(
                    path,
                    "rb"
                ) as media:

                    if index == 0:

                        await update.message.reply_photo(
                            photo=media,
                            caption=media_caption,
                            connect_timeout=60,
                            read_timeout=300,
                            write_timeout=300,
                            pool_timeout=60,
                        )

                    else:

                        await update.message.reply_photo(
                            photo=media,
                            connect_timeout=60,
                            read_timeout=300,
                            write_timeout=300,
                            pool_timeout=60,
                        )

            update_download_status(
                download_id,
                "completed",
                media_type="photo",
                creator_username=metadata.get(
                    "username"
                ),
            )

        # -------------------------------------------------
        # Single media
        # -------------------------------------------------

        else:

            with open(
                processed_file_path,
                "rb"
            ) as media:

                # -----------------------------------------
                # Video
                # -----------------------------------------

                if media_type == "video":

                    print(
                        "📤 Starting Telegram "
                        "video upload..."
                    )

                    try:

                        await update.message.reply_video(
                            video=media,
                            caption=media_caption,
                            supports_streaming=True,
                            connect_timeout=60,
                            read_timeout=300,
                            write_timeout=300,
                            pool_timeout=60,
                        )

                        print(
                            "✅ Telegram video "
                            "upload finished."
                        )

                    except Exception as e:

                        print(
                            "❌ Telegram video "
                            "upload failed: "
                            f"{type(e).__name__}: {e}"
                        )

                        raise

                # -----------------------------------------
                # Photo
                # -----------------------------------------

                elif media_type == "photo":

                    print(
                        "📤 Starting Telegram "
                        "photo upload..."
                    )

                    await update.message.reply_photo(
                        photo=media,
                        caption=media_caption,
                        connect_timeout=60,
                        read_timeout=300,
                        write_timeout=300,
                        pool_timeout=60,
                    )

                    print(
                        "✅ Telegram photo "
                        "upload finished."
                    )

                # -----------------------------------------
                # Other media
                # -----------------------------------------

                else:

                    print(
                        "📤 Sending media as document..."
                    )

                    await update.message.reply_document(
                        document=media,
                        caption=media_caption,
                        connect_timeout=60,
                        read_timeout=300,
                        write_timeout=300,
                        pool_timeout=60,
                    )

                    print(
                        "✅ Telegram document "
                        "upload finished."
                    )

            update_download_status(
                download_id,
                "completed",
                media_type=media_type,
                creator_username=metadata.get(
                    "username"
                ),
            )

        print(
            "[4] Telegram upload complete."
        )

        # -------------------------------------------------
        # 6. Delete status message
        # -------------------------------------------------

        try:

            await status_message.delete()

        except Exception as e:

            print(
                "Status message cleanup warning: "
                f"{e}"
            )

    # -----------------------------------------------------
    # Error handling
    # -----------------------------------------------------

    except Exception as e:

        update_download_status(
            download_id,
            "failed",
            error_message=str(e)
        )

        print(
            f"❌ Processing error: "
            f"{type(e).__name__}: {e}"
        )

        try:

            await status_message.edit_text(
                "❌ Could not download this "
                "Instagram post.\n\n"
                "The post may be unavailable, "
                "deleted, private, or the URL "
                "may be invalid."
            )

        except Exception as status_error:

            print(
                "Status update warning: "
                f"{type(status_error).__name__}: "
                f"{status_error}"
            )

    # -----------------------------------------------------
    # Cleanup
    # -----------------------------------------------------

    finally:

        files_to_delete = []

        # Original downloaded files
        if isinstance(
            file_path,
            list
        ):

            files_to_delete.extend(
                file_path
            )

        elif file_path:

            files_to_delete.append(
                file_path
            )

        # Processed files
        if isinstance(
            processed_file_path,
            list
        ):

            files_to_delete.extend(
                processed_file_path
            )

        elif processed_file_path:

            files_to_delete.append(
                processed_file_path
            )

        # Remove duplicates
        files_to_delete = list(
            dict.fromkeys(
                files_to_delete
            )
        )

        print(
            "🧹 Cleanup started. "
            f"Files to delete: "
            f"{files_to_delete}"
        )

        # Delete processed files first
        for path in reversed(
            files_to_delete
        ):

            if not path:
                continue

            path = os.fspath(path)

            absolute_path = os.path.abspath(
                path
            )

            print(
                "🔍 Checking cleanup file: "
                f"{absolute_path}"
            )

            if os.path.isfile(
                absolute_path
            ):

                try:

                    os.remove(
                        absolute_path
                    )

                    print(
                        "🗑️ Deleted temporary file: "
                        f"{absolute_path}"
                    )

                except PermissionError as e:

                    print(
                        "❌ File is still in use: "
                        f"{absolute_path}"
                    )

                    print(
                        f"   {e}"
                    )

                except Exception as e:

                    print(
                        "❌ Cleanup error for "
                        f"{absolute_path}: "
                        f"{type(e).__name__}: {e}"
                    )

            else:

                print(
                    "ℹ️ File not found during "
                    f"cleanup: {absolute_path}"
                )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    text = update.message.text.strip()

    urls = extract_instagram_urls(text)

    if not urls:
        await update.message.reply_text(
            "❌ Please send a valid Instagram URL."
        )
        return

    print(
        f"🔗 Found {len(urls)} Instagram URL(s)."
    )

    for url in urls:

        status_message = await update.message.reply_text(
            "⏳ Your request is being added to the queue..."
        )
        
        download_id = create_download(
            user_id=update.effective_user.id,
            username=update.effective_user.username,
            instagram_url=url,
        )

        async def job(
            url=url,
            status_message=status_message,
            download_id=download_id
        ):
            await process_instagram(
                update,
                url,
                status_message,
                download_id
            )

        position = await download_queue.add(job)

        if position == 0:
            await update_status(
                status_message,
                "⏳ Your request is starting..."
            )
        else:
            await update_status(
                status_message,
                f"⏳ Your request is queued.\n"
                f"📋 Position: {position}"
            )

async def post_init(application):
    await download_queue.start()
    print("📋 Download queue started.")
    
async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    print(
        f"⚠️ Telegram network/error: "
        f"{type(context.error).__name__}: "
        f"{context.error}"
    )


class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        pass


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def start_health_server():
    port_str = os.environ.get("PORT", "10000")
    try:
        port = int(port_str)
        server = ReusableTCPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"🌐 Health check server listening on port {port}")
    except Exception as e:
        print(f"⚠️ Could not start health check server: {e}")


def main():
    start_health_server()
    initialize_database()
    
    if not TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is not set in .env"
        )

    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(60)
        .read_timeout(300)
        .write_timeout(300)
        .pool_timeout(60)
        .post_init(post_init)
        .post_shutdown(lambda application: download_queue.stop())
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )
    
    app.add_handler(
        CommandHandler("stats", stats)
    )
    
    app.add_handler(
        CommandHandler("history", history)
    )
    
    app.add_handler(
        CommandHandler("help", help_command)
    )
    
    app.add_handler(
        CommandHandler("diagnostics", diagnostics)
    )
    

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )
    
    app.add_error_handler(error_handler)

    print("🤖 Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()