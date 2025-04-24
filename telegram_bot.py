import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from database import Database
import feedparser
import asyncio
from datetime import datetime, timedelta
import sqlite3

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
db = Database()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    # Add user to database if not exists
    try:
        user_id = str(user.id)
        db.add_user(user_id, user.username or user_id)
        logger.info(f"Added new user: {user_id}")
        
        # Initialize schedule
        try:
            db.cursor.execute(
                "INSERT INTO user_schedule (user_id, enabled, interval_minutes) VALUES (?, FALSE, 60)",
                (user_id,)
            )
            db.conn.commit()
            logger.info(f"Initialized schedule for user {user_id}")
        except sqlite3.IntegrityError:
            logger.info(f"Schedule already exists for user {user_id}")
            
    except Exception as e:
        logger.error(f"Error in start command: {e}")
    
    await update.message.reply_text(
        f'Hi {user.first_name}! I am your RSS news bot. Use /help to see available commands.'
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove user and their subscriptions from the database."""
    user_id = update.effective_user.id
    
    try:
        # Remove user's subscriptions
        db.cursor.execute("DELETE FROM user_feeds WHERE user_id = ?", (user_id,))
        
        # Remove user's delivery records
        db.cursor.execute("DELETE FROM news_delivery WHERE user_id = ?", (user_id,))
        
        # Remove user
        db.cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        
        db.conn.commit()
        
        await update.message.reply_text(
            "You have been unsubscribed from all feeds and your data has been removed. "
            "Use /start if you want to use the bot again."
        )
    except Exception as e:
        logger.error(f"Error removing user: {e}")
        await update.message.reply_text("Failed to remove your data. Please try again later.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
Available commands:
/addfeed <url> - Add a new RSS feed
/listfeeds - List your subscribed feeds
/removefeed <feed_id> - Remove a feed from your subscriptions
/news - Get latest news from your feeds
/stop - Remove your account and all subscriptions
/schedule <minutes> - Set automatic news delivery interval (e.g., /schedule 60 for hourly)
/enable_auto - Enable automatic news delivery
/disable_auto - Disable automatic news delivery
/status - Show your current settings
    """
    await update.message.reply_text(help_text)

async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new RSS feed."""
    if not context.args:
        await update.message.reply_text('Please provide an RSS feed URL. Usage: /addfeed <url>')
        return

    feed_url = context.args[0]
    try:
        # Validate feed
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            await update.message.reply_text('Invalid RSS feed or no entries found.')
            return

        # Add feed to database
        feed_name = feed.feed.title if hasattr(feed.feed, 'title') else feed_url
        feed_id = db.add_rss_feed(feed_url, feed_name)
        
        # Subscribe user to feed
        user_id = update.effective_user.id
        db.subscribe_user_to_feed(user_id, feed_id)
        
        await update.message.reply_text(f'Successfully added feed: {feed_name}')
    except Exception as e:
        logger.error(f"Error adding feed: {e}")
        await update.message.reply_text('Failed to add feed. Please check the URL and try again.')

async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all subscribed feeds."""
    user_id = update.effective_user.id
    feeds = db.get_user_feeds(user_id)
    
    if not feeds:
        await update.message.reply_text('You have no subscribed feeds. Use /addfeed to add one.')
        return

    message = "Your subscribed feeds:\n\n"
    for feed in feeds:
        message += f"ID: {feed['feed_id']}\n"
        message += f"Name: {feed['feed_name']}\n"
        message += f"URL: {feed['feed_url']}\n"
        message += f"Last updated: {feed['last_updated']}\n\n"
    
    await update.message.reply_text(message)

async def remove_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a feed from subscriptions."""
    if not context.args:
        await update.message.reply_text('Please provide a feed ID. Usage: /removefeed <feed_id>')
        return

    try:
        feed_id = int(context.args[0])
        user_id = update.effective_user.id
        
        # Remove subscription
        db.cursor.execute(
            "DELETE FROM user_feeds WHERE user_id = ? AND feed_id = ?",
            (user_id, feed_id)
        )
        db.conn.commit()
        
        await update.message.reply_text(f'Successfully removed feed ID: {feed_id}')
    except ValueError:
        await update.message.reply_text('Invalid feed ID. Please provide a number.')
    except Exception as e:
        logger.error(f"Error removing feed: {e}")
        await update.message.reply_text('Failed to remove feed. Please try again.')

async def check_feeds(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodically check feeds for new content."""
    logger.info("Starting feed checking task")
    while True:
        try:
            # Get all feeds
            db.cursor.execute("SELECT feed_id, feed_url FROM rss_feeds")
            feeds = db.cursor.fetchall()
            logger.info(f"Found {len(feeds)} feeds to check")
            
            for feed_id, feed_url in feeds:
                try:
                    logger.info(f"Checking feed {feed_id}: {feed_url}")
                    # Parse feed
                    feed = feedparser.parse(feed_url)
                    
                    if not feed.entries:
                        logger.warning(f"No entries found in feed {feed_id}")
                        continue
                    
                    # Get latest news items
                    for entry in feed.entries:
                        try:
                            # Check if news item already exists
                            db.cursor.execute(
                                "SELECT news_id FROM news_items WHERE link = ?",
                                (entry.link,)
                            )
                            if not db.cursor.fetchone():
                                # Add new news item
                                news_id = db.add_news_item(
                                    feed_id,
                                    entry.title,
                                    entry.link,
                                    entry.description if hasattr(entry, 'description') else '',
                                    datetime.now()
                                )
                                logger.info(f"Added new news item {news_id} from feed {feed_id}")
                        except Exception as e:
                            logger.error(f"Error processing news item: {e}")
                    
                    # Update feed timestamp
                    db.update_feed_last_updated(feed_id)
                    logger.info(f"Updated timestamp for feed {feed_id}")
                    
                except Exception as e:
                    logger.error(f"Error checking feed {feed_id}: {e}")
            
            logger.info("Finished checking all feeds")
            # Wait for 5 minutes before next check
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Error in feed checking loop: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying

async def get_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get latest news from subscribed feeds."""
    user_id = update.effective_user.id
    logger.info(f"Getting news for user {user_id}")
    
    news_items = db.get_undelivered_news(user_id)
    logger.info(f"Found {len(news_items)} undelivered news items for user {user_id}")
    
    if not news_items:
        await update.message.reply_text('No new news items found.')
        return

    for news in news_items:
        try:
            message = f"*{news['title']}*\n"
            message += f"From: {news['feed_name']}\n"
            message += f"Link: {news['link']}\n"
            message += f"\n{news['description']}"
            
            # Send message with markdown formatting
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            # Mark news as delivered
            db.mark_news_delivered(user_id, news['news_id'])
            logger.info(f"Marked news {news['news_id']} as delivered to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending news {news['news_id']} to user {user_id}: {e}")

async def set_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set the automatic news delivery interval."""
    if not context.args:
        await update.message.reply_text('Please provide the interval in minutes. Usage: /schedule <minutes>')
        return

    try:
        interval = int(context.args[0])
        if interval < 5:
            await update.message.reply_text('Interval must be at least 5 minutes.')
            return

        user_id = update.effective_user.id
        
        # First check if schedule exists
        db.cursor.execute(
            "SELECT COUNT(*) FROM user_schedule WHERE user_id = ?",
            (user_id,)
        )
        exists = db.cursor.fetchone()[0]
        
        if not exists:
            # Create schedule if it doesn't exist
            db.cursor.execute(
                "INSERT INTO user_schedule (user_id, enabled, interval_minutes) VALUES (?, FALSE, ?)",
                (user_id, interval)
            )
            logger.info(f"Created new schedule for user {user_id} with interval {interval}")
        else:
            # Update existing schedule
            db.cursor.execute(
                "UPDATE user_schedule SET interval_minutes = ? WHERE user_id = ?",
                (interval, user_id)
            )
            logger.info(f"Updated schedule for user {user_id} to interval {interval}")
            
        db.conn.commit()
        await update.message.reply_text(f'Automatic news delivery interval set to {interval} minutes.')
        
    except ValueError:
        await update.message.reply_text('Please provide a valid number of minutes.')
    except Exception as e:
        logger.error(f"Error setting schedule for user {user_id}: {e}")
        await update.message.reply_text('Failed to set schedule. Please try again.')

async def enable_auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable automatic news delivery."""
    user_id = update.effective_user.id
    try:
        db.cursor.execute(
            "UPDATE user_schedule SET enabled = TRUE WHERE user_id = ?",
            (user_id,)
        )
        db.conn.commit()
        await update.message.reply_text('Automatic news delivery enabled.')
    except Exception as e:
        logger.error(f"Error enabling auto delivery: {e}")
        await update.message.reply_text('Failed to enable automatic delivery. Please try again.')

async def disable_auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable automatic news delivery."""
    user_id = update.effective_user.id
    try:
        db.cursor.execute(
            "UPDATE user_schedule SET enabled = FALSE WHERE user_id = ?",
            (user_id,)
        )
        db.conn.commit()
        await update.message.reply_text('Automatic news delivery disabled.')
    except Exception as e:
        logger.error(f"Error disabling auto delivery: {e}")
        await update.message.reply_text('Failed to disable automatic delivery. Please try again.')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's current settings."""
    user_id = update.effective_user.id
    try:
        # First check if user exists in schedule table
        db.cursor.execute(
            "SELECT COUNT(*) FROM user_schedule WHERE user_id = ?",
            (user_id,)
        )
        exists = db.cursor.fetchone()[0]
        
        if not exists:
            # Initialize schedule if it doesn't exist
            db.cursor.execute(
                "INSERT INTO user_schedule (user_id, enabled, interval_minutes) VALUES (?, FALSE, 60)",
                (user_id,)
            )
            db.conn.commit()
            logger.info(f"Created missing schedule for user {user_id}")
        
        # Now get the schedule
        db.cursor.execute(
            "SELECT enabled, interval_minutes, last_delivery FROM user_schedule WHERE user_id = ?",
            (user_id,)
        )
        schedule = db.cursor.fetchone()
        
        if schedule:
            enabled, interval, last_delivery = schedule
            status_text = f"Automatic delivery: {'Enabled' if enabled else 'Disabled'}\n"
            status_text += f"Delivery interval: {interval} minutes\n"
            status_text += f"Last delivery: {last_delivery if last_delivery else 'Never'}"
            
            await update.message.reply_text(status_text)
        else:
            logger.error(f"No schedule found for user {user_id} after initialization")
            await update.message.reply_text('Error: Could not retrieve schedule settings. Please try /start again.')
            
    except Exception as e:
        logger.error(f"Error getting status for user {user_id}: {e}")
        await update.message.reply_text('Failed to get status. Please try again.')

async def deliver_news_to_user(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Deliver news to a specific user."""
    try:
        # Get user's schedule
        db.cursor.execute(
            "SELECT enabled, interval_minutes, last_delivery FROM user_schedule WHERE user_id = ?",
            (user_id,)
        )
        schedule = db.cursor.fetchone()
        
        if not schedule or not schedule[0]:  # Not enabled
            return
            
        enabled, interval, last_delivery = schedule
        
        # Check if it's time to deliver
        if last_delivery:
            last_delivery = datetime.fromisoformat(last_delivery)
            next_delivery = last_delivery + timedelta(minutes=interval)
            if datetime.now() < next_delivery:
                return
        
        # Get undelivered news
        news_items = db.get_undelivered_news(user_id)
        if not news_items:
            return
            
        # Send news
        for news in news_items:
            try:
                message = f"*{news['title']}*\n"
                message += f"From: {news['feed_name']}\n"
                message += f"Link: {news['link']}\n"
                message += f"\n{news['description']}"
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                
                # Mark news as delivered
                db.mark_news_delivered(user_id, news['news_id'])
                
            except Exception as e:
                logger.error(f"Error sending news to user {user_id}: {e}")
        
        # Update last delivery time
        db.cursor.execute(
            "UPDATE user_schedule SET last_delivery = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        db.conn.commit()
        
    except Exception as e:
        logger.error(f"Error in deliver_news_to_user for user {user_id}: {e}")

async def check_scheduled_deliveries(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check and deliver news to users based on their schedules."""
    try:
        # Get all users with enabled schedules
        db.cursor.execute(
            "SELECT user_id FROM user_schedule WHERE enabled = TRUE"
        )
        users = db.cursor.fetchall()
        
        for (user_id,) in users:
            await deliver_news_to_user(context, user_id)
            
    except Exception as e:
        logger.error(f"Error in check_scheduled_deliveries: {e}")

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token("8177878498:AAGijQDFea0Q-e1olNuRG0-qceYXBdfq_uo").build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addfeed", add_feed))
    application.add_handler(CommandHandler("listfeeds", list_feeds))
    application.add_handler(CommandHandler("removefeed", remove_feed))
    application.add_handler(CommandHandler("news", get_news))
    application.add_handler(CommandHandler("schedule", set_schedule))
    application.add_handler(CommandHandler("enable_auto", enable_auto))
    application.add_handler(CommandHandler("disable_auto", disable_auto))
    application.add_handler(CommandHandler("status", status))

    # Start feed checking in background
    logger.info("Starting feed checking task")
    application.job_queue.run_repeating(check_feeds, interval=300, first=10)
    
    # Start scheduled delivery checking
    logger.info("Starting scheduled delivery task")
    application.job_queue.run_repeating(check_scheduled_deliveries, interval=60, first=10)

    # Start the Bot
    logger.info("Starting bot")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 