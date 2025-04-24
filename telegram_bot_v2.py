import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from news_manager import NewsManager
from llm_manager import LLMManager
import os
from datetime import datetime, timedelta
import asyncio
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv

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
        "👋 Welcome to the News Bot, {username}! 📰\n\n"
        "I can help you stay updated with the latest news from your favorite sources.\n\n"
        "Here's what I can do for you:\n"
        "• Add and manage RSS feeds\n"
        "• Get news in your preferred language\n"
        "• Set up automatic news delivery\n"
        "• Customize your news experience\n\n"
        "Click the Help button below to learn more about my features!"
    ).format(username=username)
    
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

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main() 