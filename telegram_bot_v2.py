import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)
from news_manager import NewsManager
from llm_manager import LLMManager
import os
from datetime import datetime, timedelta
import asyncio
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import langdetect

# Load environment variables
load_dotenv()

# Initialize managers
news_manager = NewsManager()
llm_manager = LLMManager()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

# Constants for ConversationHandler states
CHOOSING_LANGUAGE, ENTERING_FEED_URL, CONFIRMING_REMOVAL, SETTING_SCHEDULE = range(4)

# Dictionary of supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ar": "Arabic"
}

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "User"
    
    # Add user to database
    news_manager.add_user(user_id, username)
    
    # Create keyboard with help button
    keyboard = [
        [InlineKeyboardButton("📚 Help", callback_data="show_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        f"👋 Welcome to the News Bot, {username}! 📰\n\n"
        "I can help you stay updated with the latest news from your favorite sources.\n\n"
        "Here's what I can do for you:\n"
        "• Add and manage RSS feeds\n"
        "• Get news in your preferred language\n"
        "• Set up automatic news delivery\n"
        "• Customize your news experience\n\n"
        "Click the Help button below to learn more about my features!"
    )
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_message = (
        "📚 *News Bot Help*\n\n"
        "*Available Commands:*\n"
        "/start - Start the bot and register\n"
        "/help - Show this help message\n"
        "/status - Show current settings\n"
        "/addfeed <url> - Add a new RSS feed\n"
        "/listfeeds - Show subscribed feeds\n"
        "/removefeed <url> - Remove a feed\n"
        "/settings - Configure news delivery settings\n"
        "/schedule - Set news delivery schedule\n"
        "/language - Change preferred language\n"
        "/getnews - Get latest news\n\n"
        "*Features:*\n"
        "• Automatic news delivery\n"
        "• News translation\n"
        "• News summarization\n"
        "• Multiple language support\n"
        "• Custom delivery schedules"
    )
    
    await update.message.reply_text(help_message, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's current settings and subscription status."""
    user_id = str(update.effective_user.id)
    
    # Get user's feeds
    feeds = news_manager.get_feeds(user_id)
    
    # Get user's schedule
    schedule = news_manager.get_user_schedule(user_id)
    
    # Get user's language preference (implement this in news_manager)
    # For now, we'll simulate this
    language = get_user_language(user_id)
    
    status_message = "📊 *Your Current Settings*\n\n"
    
    # Add language information
    status_message += f"🌐 *Language:* {SUPPORTED_LANGUAGES.get(language, 'Not set')}\n\n"
    
    # Add schedule information
    if schedule:
        status_message += "⏰ *Delivery Schedule:*\n"
        status_message += f"  • Status: {'Enabled' if schedule['enabled'] else 'Disabled'}\n"
        status_message += f"  • Interval: Every {schedule['interval_minutes']} minutes\n"
        if schedule['last_delivery']:
            status_message += f"  • Last delivery: {schedule['last_delivery']}\n"
        status_message += "\n"
    else:
        status_message += "⏰ *Delivery Schedule:* Not configured\n\n"
    
    # Add feeds information
    status_message += f"📰 *Subscribed Feeds:* {len(feeds)}\n"
    if feeds:
        for i, feed in enumerate(feeds, 1):
            status_message += f"  {i}. {feed['feed_name']} ({feed['feed_url'][:30]}...)\n"
    else:
        status_message += "  No feeds subscribed yet. Use /addfeed to add feeds.\n"
    
    await update.message.reply_text(status_message, parse_mode='Markdown')

async def add_feed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new RSS feed."""
    if not context.args:
        await update.message.reply_text(
            "Please provide the RSS feed URL.\n"
            "Example: /addfeed https://news.example.com/rss"
        )
        return
    
    user_id = str(update.effective_user.id)
    feed_url = context.args[0]
    
    # Extract feed name from URL (you might want to improve this)
    feed_name = extract_feed_name(feed_url)
    
    # Add feed to database
    feed_id = news_manager.add_feed(feed_url, feed_name)
    
    if feed_id > 0:
        # Subscribe user to feed
        news_manager.subscribe_user_to_feed(user_id, feed_id)
        await update.message.reply_text(
            f"✅ Successfully added feed: {feed_name}\n"
            "You will now receive updates from this source."
        )
    elif feed_id == -1:  # Feed already exists
        # Get the feed_id for the existing feed
        news_manager.cursor.execute("SELECT feed_id FROM rss_feeds WHERE feed_url = ?", (feed_url,))
        result = news_manager.cursor.fetchone()
        if result:
            existing_feed_id = result[0]
            # Check if user is already subscribed
            news_manager.cursor.execute(
                "SELECT * FROM user_feeds WHERE user_id = ? AND feed_id = ?", 
                (user_id, existing_feed_id)
            )
            if news_manager.cursor.fetchone():
                await update.message.reply_text(
                    f"You are already subscribed to this feed: {feed_name}"
                )
            else:
                # Subscribe user to existing feed
                news_manager.subscribe_user_to_feed(user_id, existing_feed_id)
                await update.message.reply_text(
                    f"✅ Successfully subscribed to existing feed: {feed_name}"
                )
    else:
        await update.message.reply_text(
            f"❌ Failed to add feed. Please check the URL and try again."
        )

async def list_feeds_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all feeds a user is subscribed to."""
    user_id = str(update.effective_user.id)
    feeds = news_manager.get_user_feeds(user_id)
    
    if not feeds:
        await update.message.reply_text(
            "You haven't subscribed to any feeds yet.\n"
            "Use /addfeed <url> to add a new feed."
        )
        return
    
    message = "📋 *Your Subscribed Feeds:*\n\n"
    for i, feed in enumerate(feeds, 1):
        last_updated = feed['last_updated'] if feed['last_updated'] else "Never"
        message += f"{i}. *{feed['feed_name']}*\n"
        message += f"   URL: {feed['feed_url']}\n"
        message += f"   Last updated: {last_updated}\n\n"
    
    message += "To remove a feed, use /removefeed <feed_id>"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def remove_feed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a subscribed feed."""
    if not context.args:
        await update.message.reply_text(
            "Please provide the feed ID to remove.\n"
            "Use /listfeeds to see all your subscribed feeds with their IDs."
        )
        return
    
    user_id = str(update.effective_user.id)
    try:
        feed_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Feed ID must be a number.")
        return
    
    # Check if user is subscribed to this feed
    news_manager.cursor.execute(
        "SELECT * FROM user_feeds WHERE user_id = ? AND feed_id = ?", 
        (user_id, feed_id)
    )
    if not news_manager.cursor.fetchone():
        await update.message.reply_text(
            "You are not subscribed to this feed or the feed ID is invalid."
        )
        return
    
    # Unsubscribe user from feed
    if news_manager.unsubscribe_user_from_feed(user_id, feed_id):
        await update.message.reply_text(
            "✅ Successfully unsubscribed from the feed."
        )
    else:
        await update.message.reply_text(
            "❌ Failed to unsubscribe from the feed. Please try again."
        )

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's preferred language for news."""
    keyboard = []
    row = []
    
    # Create a button grid
    for i, (code, name) in enumerate(SUPPORTED_LANGUAGES.items(), 1):
        row.append(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
        if i % 2 == 0:  # 2 buttons per row
            keyboard.append(row)
            row = []
    
    if row:  # Add any remaining buttons
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌐 Select your preferred language for news:",
        reply_markup=reply_markup
    )
    
    return CHOOSING_LANGUAGE

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set news delivery schedule."""
    user_id = str(update.effective_user.id)
    schedule = news_manager.get_user_schedule(user_id)
    
    # Create keyboard for schedule options
    keyboard = [
        [
            InlineKeyboardButton("Enable", callback_data="schedule_enable"),
            InlineKeyboardButton("Disable", callback_data="schedule_disable")
        ],
        [
            InlineKeyboardButton("Every 30 min", callback_data="schedule_30"),
            InlineKeyboardButton("Hourly", callback_data="schedule_60")
        ],
        [
            InlineKeyboardButton("Every 3 hours", callback_data="schedule_180"),
            InlineKeyboardButton("Daily", callback_data="schedule_1440")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status = "Enabled" if schedule and schedule['enabled'] else "Disabled"
    interval = schedule['interval_minutes'] if schedule else 60
    
    message = (
        "⏰ *News Delivery Schedule*\n\n"
        f"Current status: *{status}*\n"
        f"Current interval: Every *{interval} minutes*\n\n"
        "Select an option to update your schedule:"
    )
    
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    return SETTING_SCHEDULE

async def get_news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get latest news from subscribed feeds."""
    user_id = str(update.effective_user.id)
    
    # First, check for new content in all feeds
    news_manager.check_feeds()
    
    # Get undelivered news for user
    news_items = news_manager.get_undelivered_news(user_id)
    
    if not news_items:
        await update.message.reply_text(
            "📭 No new articles found. Check back later!"
        )
        return
    
    # Limit to 5 news items to avoid flooding
    news_items = news_items[:5]
    
    # Get user's language preference
    user_language = get_user_language(user_id)
    
    await update.message.reply_text("🔍 Fetching your latest news...")
    
    # Process and send each news item
    for item in news_items:
        # Detect source language
        source_language = detect_language(item['description'])
        
        # Prepare news message
        news_message = f"📰 *{item['title']}*\n\n"
        
        # Check if translation is needed
        if source_language != user_language:
            try:
                # Translate using LLM
                translated_description = await llm_manager.translate_text(
                    item['description'], 
                    source_language, 
                    user_language
                )
                news_message += f"{translated_description}\n\n"
                news_message += f"🌐 *Translated from {SUPPORTED_LANGUAGES.get(source_language, source_language)}*\n\n"
            except Exception as e:
                logger.error(f"Translation error: {e}")
                news_message += f"{item['description']}\n\n"
                news_message += "⚠️ *Translation failed*\n\n"
        else:
            news_message += f"{item['description']}\n\n"
        
        news_message += f"Source: {item['feed_name']}\n"
        news_message += f"Link: {item['link']}"
        
        try:
            await update.message.reply_text(news_message, parse_mode='Markdown')
        except Exception as e:
            # If markdown parsing fails, send without markdown
            logger.error(f"Error sending message with markdown: {e}")
            await update.message.reply_text(news_message)
        
        # Mark as delivered
        news_manager.mark_news_delivered(user_id, item['news_id'])
    
    # Update last delivery time
    news_manager.update_last_delivery(user_id)
    
    await update.message.reply_text(
        f"✅ Delivered {len(news_items)} news items. Use /getnews again later for more updates."
    )

# Callback query handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    data = query.data
    
    if data == "show_help":
        help_message = (
            "📚 *News Bot Help*\n\n"
            "*Available Commands:*\n"
            "/start - Start the bot and register\n"
            "/help - Show this help message\n"
            "/status - Show current settings\n"
            "/addfeed <url> - Add a new RSS feed\n"
            "/listfeeds - Show subscribed feeds\n"
            "/removefeed <url> - Remove a feed\n"
            "/settings - Configure news delivery settings\n"
            "/schedule - Set news delivery schedule\n"
            "/language - Change preferred language\n"
            "/getnews - Get latest news\n\n"
            "*Features:*\n"
            "• Automatic news delivery\n"
            "• News translation\n"
            "• News summarization\n"
            "• Multiple language support\n"
            "• Custom delivery schedules\n\n"
            "Need more help? Just type /help anytime!"
        )
        await query.edit_message_text(
            help_message,
            parse_mode='Markdown'
        )
        return
    
    elif data.startswith("lang_"):
        # Handle language selection
        language_code = data.split("_")[1]
        set_user_language(user_id, language_code)
        
        await query.edit_message_text(
            f"✅ Language set to {SUPPORTED_LANGUAGES[language_code]}.\n"
            "Your news will now be translated to this language when needed."
        )
        return CHOOSING_LANGUAGE
    
    elif data.startswith("schedule_"):
        # Handle schedule selection
        action = data.split("_")[1]
        
        if action == "enable":
            news_manager.enable_auto_delivery(user_id)
            await query.edit_message_text(
                "✅ Automatic news delivery enabled.\n"
                "You will receive news at your scheduled interval."
            )
        
        elif action == "disable":
            news_manager.disable_auto_delivery(user_id)
            await query.edit_message_text(
                "⏸ Automatic news delivery disabled.\n"
                "You can still get news manually with /getnews."
            )
        
        elif action.isdigit():
            interval = int(action)
            news_manager.set_schedule(user_id, interval)
            
            if interval == 1440:
                interval_text = "day"
            elif interval == 60:
                interval_text = "hour"
            elif interval == 30:
                interval_text = "30 minutes"
            else:
                interval_text = f"{interval} minutes"
            
            await query.edit_message_text(
                f"⏰ Schedule updated. You will receive news every {interval_text}.\n"
                f"Make sure automatic delivery is enabled with /schedule."
            )
        
        return SETTING_SCHEDULE

# Helper functions
def extract_feed_name(url: str) -> str:
    """Extract a readable feed name from URL."""
    # Remove protocol
    name = re.sub(r'^https?://', '', url)
    # Remove www. if present
    name = re.sub(r'^www\.', '', name)
    # Remove path after domain
    name = re.sub(r'/.*$', '', name)
    # Capitalize first letters
    parts = name.split('.')
    if len(parts) > 1:
        name = parts[0].capitalize()
    
    return name

def detect_language(text: str) -> str:
    """Detect the language of a text."""
    try:
        # Strip HTML tags if present
        if '<' in text and '>' in text:
            soup = BeautifulSoup(text, 'html.parser')
            text = soup.get_text()
        
        # Detect language using langdetect
        detected = langdetect.detect(text)
        return detected if detected in SUPPORTED_LANGUAGES else 'en'
    except Exception as e:
        logger.error(f"Language detection error: {e}")
        return 'en'  # Default to English on error

def get_user_language(user_id: str) -> str:
    """Get user's preferred language from database."""
    try:
        # This is a stub - implement actual database storage in news_manager
        # For now, we'll return English as default
        return 'en'
    except Exception as e:
        logger.error(f"Error getting user language: {e}")
        return 'en'

def set_user_language(user_id: str, language_code: str) -> bool:
    """Set user's preferred language in database."""
    try:
        # This is a stub - implement actual database storage in news_manager
        # For now, we'll just log it
        logger.info(f"Setting language for user {user_id} to {language_code}")
        return True
    except Exception as e:
        logger.error(f"Error setting user language: {e}")
        return False

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("addfeed", add_feed_command))
    application.add_handler(CommandHandler("listfeeds", list_feeds_command))
    application.add_handler(CommandHandler("removefeed", remove_feed_command))
    application.add_handler(CommandHandler("getnews", get_news_command))
    
    # Add conversation handlers for interactive commands
    language_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("language", language_command)],
        states={
            CHOOSING_LANGUAGE: [CallbackQueryHandler(button_callback, pattern=r"^lang_")]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    application.add_handler(language_conv_handler)
    
    schedule_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("schedule", schedule_command)],
        states={
            SETTING_SCHEDULE: [CallbackQueryHandler(button_callback, pattern=r"^schedule_")]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    application.add_handler(schedule_conv_handler)
    
    # Add general callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()