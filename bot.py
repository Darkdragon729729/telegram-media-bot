import asyncio
import logging
from datetime import datetime, timedelta
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# 1. SETUP LOGGING
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# ⚠️ REPLACE THIS WITH YOUR ACTUAL BOT TOKEN FROM BOTFATHER
BOT_TOKEN = "6157539252:AAFRruT4s8SNJzzGS_5gDHt5CPtlB273ep4"

# 2. DATABASE SETUP
def init_db():
    conn = sqlite3.connect('mediabot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            file_id TEXT,
            file_type TEXT,
            timestamp DATETIME
        )
    ''')
    conn.commit()
    conn.close()

def clean_old_media():
    conn = sqlite3.connect('mediabot.db')
    cursor = conn.cursor()
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("DELETE FROM media WHERE timestamp < ?", (seven_days_ago,))
    conn.commit()
    conn.close()

# 3. BOT COMMAND HANDLERS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when anyone starts the bot - Shows detailed guide"""
    welcome_text = (
        "👋 *Welcome to the Community Media Hub Bot!*\n"
        "Anyone can upload and anyone can view media here anonymously!\n\n"
        "📖 *HOW TO USE THIS BOT:*\n\n"
        "📤 *How to Upload:* \n"
        "• Simply select a photo, video, or reel from your phone gallery.\n"
        "• Send it directly to this chat window like you are sending a message to a friend.\n"
        "• The bot will instantly save it to the public feed.\n\n"
        "👀 *How to View:* \n"
        "• Type /photos - To look at all the images uploaded by users.\n"
        "• Type /videos - To watch all videos and reels uploaded by users.\n"
        "• Use the ⬅️ and ➡️ buttons under the post to navigate through items.\n\n"
        "📊 *Check Data:* \n"
        "• Type /stats - See how many active files are live right now.\n\n"
        "⚠️ *Rule:* To keep the database clean, all files are auto-deleted after exactly 7 days!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming user uploads"""
    clean_old_media()
    
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    user_id = user.id
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = "photo"
    elif update.message.video:
        file_id = update.message.video.file_id
        file_type = "video"
    else:
        return

    conn = sqlite3.connect('mediabot.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO media (user_id, username, file_id, file_type, timestamp) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, file_id, file_type, current_time)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ *Upload Successful!*\nYour {file_type} is now live. People can view it using "
        f"{'/photos' if file_type == 'photo' else '/videos'}.", 
        parse_mode="Markdown"
    )

async def view_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and handles only Photos"""
    clean_old_media()
    
    conn = sqlite3.connect('mediabot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_type, username FROM media WHERE file_type='photo' ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📂 No photos have been uploaded in the past 7 days.")
        return

    context.user_data['feed'] = rows
    context.user_data['index'] = 0
    context.user_data['feed_type'] = 'photo'

    await send_feed_item(update, context)

async def view_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and handles only Videos and Reels"""
    clean_old_media()
    
    conn = sqlite3.connect('mediabot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_type, username FROM media WHERE file_type='video' ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📂 No videos or reels have been uploaded in the past 7 days.")
        return

    context.user_data['feed'] = rows
    context.user_data['index'] = 0
    context.user_data['feed_type'] = 'video'

    await send_feed_item(update, context)

async def send_feed_item(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    """Helper to route and paginate structured lists"""
    feed_data = context.user_data.get('feed', [])
    index = context.user_data.get('index', 0)
    feed_type = context.user_data.get('feed_type', 'media')

    if not feed_data or index < 0 or index >= len(feed_data):
        if query:
            await query.answer("No more items available.")
        return

    file_id, file_type, username = feed_data[index]
    caption = f"👤 Uploaded by: {username}\n📄 {feed_type.capitalize()} {index + 1} of {len(feed_data)}"

    keyboard = []
    buttons = []
    if index > 0:
        buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="prev"))
    if index < len(feed_data) - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data="next"))
    if buttons:
        keyboard.append(buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        try:
            await query.message.delete()
        except Exception:
            pass
        
        if file_type == "photo":
            await query.message.reply_photo(photo=file_id, caption=caption, reply_markup=reply_markup)
        elif file_type == "video":
            await query.message.reply_video(video=file_id, caption=caption, reply_markup=reply_markup)
    else:
        if file_type == "photo":
            await update.message.reply_photo(photo=file_id, caption=caption, reply_markup=reply_markup)
        elif file_type == "video":
            await update.message.reply_video(video=file_id, caption=caption, reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pagination state controls"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    index = context.user_data.get('index', 0)

    if action == "next":
        context.user_data['index'] = index + 1
    elif action == "prev":
        context.user_data['index'] = index - 1

    await send_feed_item(update, context, query=query)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calculates live active operational stats"""
    clean_old_media()
    
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('mediabot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM media WHERE timestamp LIKE ?", (f"{today_str}%",))
    today_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM media WHERE timestamp LIKE ?", (f"{yesterday_str}%",))
    yesterday_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM media")
    week_count = cursor.fetchone()[0]
    
    conn.close()

    stats_text = (
        "📊 *Upload Statistics:*\n\n"
        f"📅 *Today:* {today_count} posts\n"
        f"⏳ *Yesterday:* {yesterday_count} posts\n"
        f"🗓️ *Past 7 Days Total:* {week_count} posts"
    )
    await update.message.reply_text(stats_text, parse_mode="Markdown")

# 4. BOT LAUNCH ENGINE
def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands mapping
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("photos", view_photos))
    application.add_handler(CommandHandler("videos", view_videos))
    application.add_handler(CommandHandler("stats", stats))
    
    # Input filters
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))
    application.add_handler(CallbackQueryHandler(button_click))

    print("🤖 Bot is successfully running with split sections... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
    