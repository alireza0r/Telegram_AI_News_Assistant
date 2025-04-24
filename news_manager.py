import sqlite3
import feedparser
import logging
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class NewsManager:
    def __init__(self):
        """Initialize the News Manager."""
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing News Manager")
        
        # Initialize database
        self.db_path = 'news_bot.db'
        self._init_db()
        
    def _init_db(self):
        """Initialize the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'en',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create feeds table
        c.execute('''
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                feed_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Create settings table
        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                user_id TEXT PRIMARY KEY,
                language TEXT DEFAULT 'en',
                schedule TEXT DEFAULT '24h',
                summarize BOOLEAN DEFAULT 1,
                translate BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def add_user(self, user_id: str, username: str):
        """Add a new user to the database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            c.execute(
                "INSERT OR IGNORE INTO settings (user_id) VALUES (?)",
                (user_id,)
            )
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error adding user: {str(e)}")
            raise
        finally:
            conn.close()
            
    def add_feed(self, user_id: str, feed_url: str):
        """Add a new RSS feed for a user."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Verify feed URL
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                raise ValueError("Invalid or empty RSS feed")
                
            c.execute(
                "INSERT INTO feeds (user_id, feed_url) VALUES (?, ?)",
                (user_id, feed_url)
            )
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error adding feed: {str(e)}")
            raise
        finally:
            conn.close()
            
    def remove_feed(self, user_id: str, feed_url: str):
        """Remove a feed from a user's subscriptions."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute(
                "DELETE FROM feeds WHERE user_id = ? AND feed_url = ?",
                (user_id, feed_url)
            )
            if c.rowcount == 0:
                raise ValueError("Feed not found in your subscriptions")
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error removing feed: {str(e)}")
            raise
        finally:
            conn.close()
            
    def get_feeds(self, user_id: str) -> list:
        """Get all feeds for a user."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute(
                "SELECT feed_url FROM feeds WHERE user_id = ?",
                (user_id,)
            )
            feeds = [row[0] for row in c.fetchall()]
            return feeds
        finally:
            conn.close()
            
    def get_settings(self, user_id: str) -> dict:
        """Get user settings."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute(
                "SELECT language, schedule, summarize, translate FROM settings WHERE user_id = ?",
                (user_id,)
            )
            row = c.fetchone()
            if row:
                return {
                    'Language': row[0],
                    'Schedule': row[1],
                    'Summarize': 'Enabled' if row[2] else 'Disabled',
                    'Translate': 'Enabled' if row[3] else 'Disabled'
                }
            return {}
        finally:
            conn.close()
            
    def update_setting(self, user_id: str, setting: str, value: str):
        """Update a user setting."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            if setting == 'language':
                c.execute(
                    "UPDATE settings SET language = ? WHERE user_id = ?",
                    (value, user_id)
                )
            elif setting == 'schedule':
                c.execute(
                    "UPDATE settings SET schedule = ? WHERE user_id = ?",
                    (value, user_id)
                )
            elif setting == 'summarize':
                c.execute(
                    "UPDATE settings SET summarize = ? WHERE user_id = ?",
                    (1 if value == 'enable' else 0, user_id)
                )
            elif setting == 'translate':
                c.execute(
                    "UPDATE settings SET translate = ? WHERE user_id = ?",
                    (1 if value == 'enable' else 0, user_id)
                )
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error updating setting: {str(e)}")
            raise
        finally:
            conn.close()
            
    def get_latest_news(self, user_id: str) -> list:
        """Get latest news from all subscribed feeds."""
        feeds = self.get_feeds(user_id)
        news_items = []
        
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:  # Get latest 5 entries
                    news_items.append({
                        'title': entry.title,
                        'link': entry.link,
                        'summary': entry.summary if hasattr(entry, 'summary') else '',
                        'published': entry.published if hasattr(entry, 'published') else ''
                    })
            except Exception as e:
                self.logger.error(f"Error parsing feed {feed_url}: {str(e)}")
                
        return news_items 