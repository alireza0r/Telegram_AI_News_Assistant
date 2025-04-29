import logging
import feedparser
import sqlite3
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import langdetect
from edge_tts_lib import EdgeTTS

# Load environment variables
load_dotenv()

class NewsManager:
    def __init__(self, db_path: str = "news_database.db"):
        """Initialize the News Manager."""
        # Setup logging
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing News Manager")
        
        # Initialize database
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._init_db()
        
        # Create voice files directory if it doesn't exist
        self.voice_dir = "voice_files"
        if not os.path.exists(self.voice_dir):
            os.makedirs(self.voice_dir)
            
        # Initialize EdgeTTS
        self.tts = EdgeTTS()
        
    def _init_db(self):
        """Initialize the SQLite database."""
        try:
            with open('schema.sql', 'r') as f:
                schema = f.read()
            self.cursor.executescript(schema)
            self.conn.commit()
            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing database: {str(e)}")
            raise
        
    def add_user(self, user_id: str, username: str, email: str = None):
        """Add a new user to the database."""
        try:
            # Use telegram user_id as username if not provided
            if not username:
                username = f"user_{user_id}"
            
            # Use placeholder email if not provided
            if not email:
                email = f"{user_id}@telegram.user"
            
            # First check if user already exists
            self.cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            existing_user = self.cursor.fetchone()
            
            if existing_user:
                db_user_id = existing_user[0]
                self.logger.info(f"User {username} already exists with ID {db_user_id}")
            else:
                # Add new user
                self.cursor.execute(
                    "INSERT INTO users (username, email) VALUES (?, ?)",
                    (username, email)
                )
                self.conn.commit()
                db_user_id = self.cursor.lastrowid
                self.logger.info(f"User {username} added successfully with ID {db_user_id}")
            
            # Initialize user settings in user_schedule table if not exists
            self.cursor.execute(
                "INSERT OR IGNORE INTO user_schedule (user_id, enabled, interval_minutes) VALUES (?, ?, ?)",
                (db_user_id, False, 60)  # Default: disabled, hourly
            )
            
            # Initialize user preferences if not exists
            self.cursor.execute(
                "INSERT OR IGNORE INTO user_preferences (user_id, preferred_language, enable_translation, max_news_items) VALUES (?, ?, ?, ?)",
                (db_user_id, 'en', True, 5)  # Default: English, translation enabled, 5 items
            )
            
            self.conn.commit()
            return db_user_id
        except Exception as e:
            self.logger.error(f"Error adding user: {str(e)}")
            self.conn.rollback()
            raise
            
    def add_feed(self, feed_url: str, feed_name: str = None) -> int:
        """Add a new RSS feed to the database."""
        try:
            # Verify feed URL
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                self.logger.warning(f"Invalid or empty RSS feed: {feed_url}")
                return 0
            
            # Extract feed name from feed if not provided
            if not feed_name:
                feed_name = feed.feed.title if hasattr(feed.feed, 'title') else self._extract_feed_name(feed_url)
            
            # Check if feed already exists
            self.cursor.execute("SELECT feed_id FROM rss_feeds WHERE feed_url = ?", (feed_url,))
            existing = self.cursor.fetchone()
            
            if existing:
                self.logger.info(f"Feed already exists: {feed_url}")
                return existing[0]  # Return existing feed_id
            
            # Add the feed
            self.cursor.execute(
                "INSERT INTO rss_feeds (feed_url, feed_name) VALUES (?, ?)",
                (feed_url, feed_name)
            )
            self.conn.commit()
            
            feed_id = self.cursor.lastrowid
            self.logger.info(f"Feed {feed_name} added successfully with ID {feed_id}")
            
            # Fetch initial items
            self._fetch_feed_items(feed_id, feed_url)
            
            return feed_id
        except Exception as e:
            self.logger.error(f"Error adding feed: {str(e)}")
            self.conn.rollback()
            return 0
            
    def subscribe_user_to_feed(self, user_id: str, feed_id: int):
        """Subscribe a user to an RSS feed."""
        try:
            # Convert telegram user_id to database user_id
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                self.logger.error(f"User {user_id} not found in database")
                return False
            
            # Check if already subscribed
            self.cursor.execute(
                "SELECT * FROM user_feeds WHERE user_id = ? AND feed_id = ?",
                (db_user_id, feed_id)
            )
            if self.cursor.fetchone():
                self.logger.info(f"User {user_id} already subscribed to feed {feed_id}")
                return True
            
            # Subscribe user
            self.cursor.execute(
                "INSERT INTO user_feeds (user_id, feed_id) VALUES (?, ?)",
                (db_user_id, feed_id)
            )
            self.conn.commit()
            self.logger.info(f"User {user_id} subscribed to feed {feed_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error subscribing user to feed: {str(e)}")
            self.conn.rollback()
            return False
            
    def unsubscribe_user_from_feed(self, user_id: str, feed_id: int):
        """Unsubscribe a user from an RSS feed."""
        try:
            # Convert telegram user_id to database user_id
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return False
            
            self.cursor.execute(
                "DELETE FROM user_feeds WHERE user_id = ? AND feed_id = ?",
                (db_user_id, feed_id)
            )
            self.conn.commit()
            self.logger.info(f"User {user_id} unsubscribed from feed {feed_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error unsubscribing user: {str(e)}")
            self.conn.rollback()
            return False
            
    def get_user_feeds(self, user_id: str):
        """Get all RSS feeds a user is subscribed to."""
        try:
            # Convert telegram user_id to database user_id
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return []
            
            self.cursor.execute("""
                SELECT rf.feed_id, rf.feed_url, rf.feed_name, rf.last_updated
                FROM rss_feeds rf
                JOIN user_feeds uf ON rf.feed_id = uf.feed_id
                WHERE uf.user_id = ?
            """, (db_user_id,))
            
            columns = [description[0] for description in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting user feeds: {str(e)}")
            return []
            
    def check_feeds(self):
        """Check all feeds for new content."""
        try:
            self.cursor.execute("SELECT feed_id, feed_url FROM rss_feeds")
            feeds = self.cursor.fetchall()
            
            total_added = 0
            for feed_id, feed_url in feeds:
                added = self._fetch_feed_items(feed_id, feed_url)
                total_added += added
                
            self.logger.info(f"Checked {len(feeds)} feeds, added {total_added} new items")
            return total_added
        except Exception as e:
            self.logger.error(f"Error checking feeds: {str(e)}")
            return 0
            
    def _fetch_feed_items(self, feed_id: int, feed_url: str) -> int:
        """Fetch and store items from a feed."""
        try:
            feed = feedparser.parse(feed_url)
            added_count = 0
            
            for entry in feed.entries:
                # Extract entry data
                title = entry.title if hasattr(entry, 'title') else "No title"
                link = entry.link if hasattr(entry, 'link') else ""
                
                # Extract description (handle different formats)
                if hasattr(entry, 'description'):
                    description = entry.description
                elif hasattr(entry, 'summary'):
                    description = entry.summary
                elif hasattr(entry, 'content'):
                    description = entry.content[0].value
                else:
                    description = "No description available"
                
                # Parse publication date
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6])
                else:
                    pub_date = datetime.now()
                
                # Check if item already exists (by link)
                self.cursor.execute("SELECT news_id FROM news_items WHERE link = ?", (link,))
                if self.cursor.fetchone():
                    continue
                
                # Add news item
                self.cursor.execute(
                    """INSERT INTO news_items 
                       (feed_id, title, link, description, pub_date) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (feed_id, title, link, description, pub_date)
                )
                added_count += 1
            
            # Update last_updated timestamp
            self.cursor.execute(
                "UPDATE rss_feeds SET last_updated = CURRENT_TIMESTAMP WHERE feed_id = ?",
                (feed_id,)
            )
            self.conn.commit()
            
            if added_count > 0:
                self.logger.info(f"Added {added_count} new items from feed {feed_id}")
            
            return added_count
        except Exception as e:
            self.logger.error(f"Error fetching feed items: {str(e)}")
            self.conn.rollback()
            return 0
            
    def get_undelivered_news(self, user_id: str):
        """Get all undelivered news items for a user."""
        try:
            # Convert telegram user_id to database user_id
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return []
            
            # Get user preferences
            preferences = self.get_user_preferences(user_id)
            max_items = preferences.get('max_news_items', 5)
            
            self.cursor.execute("""
                SELECT ni.news_id, ni.title, ni.link, ni.description, ni.pub_date, rf.feed_name
                FROM news_items ni
                JOIN rss_feeds rf ON ni.feed_id = rf.feed_id
                JOIN user_feeds uf ON rf.feed_id = uf.feed_id
                LEFT JOIN news_delivery nd ON ni.news_id = nd.news_id AND nd.user_id = ?
                WHERE uf.user_id = ? AND nd.delivery_id IS NULL
                ORDER BY ni.pub_date DESC
                LIMIT ?
            """, (db_user_id, db_user_id, max_items))
            
            columns = [description[0] for description in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting undelivered news: {str(e)}")
            return []
            
    def mark_news_delivered(self, user_id: str, news_id: int):
        """Mark a news item as delivered to a user."""
        try:
            # Convert telegram user_id to database user_id
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return False
            
            self.cursor.execute(
                "INSERT OR IGNORE INTO news_delivery (user_id, news_id) VALUES (?, ?)",
                (db_user_id, news_id)
            )
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error marking news as delivered: {str(e)}")
            self.conn.rollback()
            return False
            
    def get_user_schedule(self, user_id: str):
        """Get user's news delivery schedule."""
        try:
            # Convert telegram user_id to database user_id
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return None
            
            self.cursor.execute("""
                SELECT enabled, interval_minutes, last_delivery
                FROM user_schedule
                WHERE user_id = ?
            """, (db_user_id,))
            
            result = self.cursor.fetchone()
            if result:
                return {
                    'enabled': bool(result[0]),
                    'interval_minutes': result[1],
                    'last_delivery': result[2]
                }
            
            # If no schedule exists, create default
            self.cursor.execute("""
                INSERT INTO user_schedule (user_id, enabled, interval_minutes)
                VALUES (?, ?, ?)
            """, (db_user_id, False, 60))
            self.conn.commit()
            
            return {
                'enabled': False,
                'interval_minutes': 60,
                'last_delivery': None
            }
        except Exception as e:
            self.logger.error(f"Error getting user schedule: {str(e)}")
            return None
            
    def set_schedule(self, user_id: str, interval_minutes: int):
        """Set user's news delivery schedule interval."""
        try:
            # Convert telegram user_id to database user_id
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return False
            
            # Validate interval
            if interval_minutes not in [30, 60, 180, 1440]:
                self.logger.warning(f"Invalid interval: {interval_minutes}")
                return False
            
            self.cursor.execute("""
                UPDATE user_schedule
                SET interval_minutes = ?
                WHERE user_id = ?
            """, (interval_minutes, db_user_id))
            
            if self.cursor.rowcount == 0:
                self.cursor.execute("""
                    INSERT INTO user_schedule (user_id, interval_minutes, enabled)
                    VALUES (?, ?, ?)
                """, (db_user_id, interval_minutes, False))
                
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error setting schedule: {str(e)}")
            self.conn.rollback()
            return False
            
    def enable_auto_delivery(self, user_id: str):
        """Enable automatic news delivery for a user."""
        try:
            # Convert telegram user_id to database user_id
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return False
            
            self.cursor.execute("""
                UPDATE user_schedule
                SET enabled = 1,
                    last_delivery = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (db_user_id,))
            
            if self.cursor.rowcount == 0:
                self.cursor.execute("""
                    INSERT INTO user_schedule (user_id, enabled, interval_minutes, last_delivery)
                    VALUES (?, 1, 60, CURRENT_TIMESTAMP)
                """, (db_user_id,))
                
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error enabling auto delivery: {str(e)}")
            self.conn.rollback()
            return False
            
    def disable_auto_delivery(self, user_id: str):
        """Disable automatic news delivery for a user."""
        try:
            # Convert telegram user_id to database user_id
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return False
            
            self.cursor.execute("""
                UPDATE user_schedule
                SET enabled = 0
                WHERE user_id = ?
            """, (db_user_id,))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error disabling auto delivery: {str(e)}")
            self.conn.rollback()
            return False
            
    def update_last_delivery(self, user_id: str):
        """Update the last delivery timestamp for a user."""
        try:
            # Convert telegram user_id to database user_id
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return False
            
            self.cursor.execute("""
                UPDATE user_schedule
                SET last_delivery = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (db_user_id,))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating last delivery: {str(e)}")
            self.conn.rollback()
            return False
            
    def _get_db_user_id(self, telegram_user_id: str):
        """Convert Telegram user ID to database user ID."""
        try:
            # First try to find by username that matches the telegram_user_id
            self.cursor.execute("SELECT user_id FROM users WHERE username = ?", (f"user_{telegram_user_id}",))
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            # If not found by username, try with the email placeholder
            self.cursor.execute("SELECT user_id FROM users WHERE email = ?", (f"{telegram_user_id}@telegram.user",))
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            # If still not found, try to add the user
            try:
                return self.add_user(telegram_user_id, f"user_{telegram_user_id}")
            except Exception as e:
                self.logger.error(f"Error adding user in _get_db_user_id: {str(e)}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting DB user ID: {str(e)}")
            return None
            
    def _extract_feed_name(self, url: str) -> str:
        """Extract a readable feed name from URL."""
        # Remove protocol
        import re
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
            
    async def get_voice_file(self, news_id: int, text: str, language: str) -> str:
        """Get or generate voice file for a news item."""
        try:
            print("Getting voice file for news_id:", news_id)
            print("Text length:", len(text))
            print("Language:", language)
            
            # Check if voice file already exists
            self.cursor.execute("""
                SELECT file_path FROM voice_files 
                WHERE news_id = ? AND language = ?
            """, (news_id, language))
            
            result = self.cursor.fetchone()
            if result:
                print("Found existing voice file:", result[0])
                return result[0]
            
            # Generate voice file
            voice_file = os.path.join(self.voice_dir, f"news_{news_id}_{language}.mp3")
            print("Generating voice file at:", voice_file)
            
            # Get appropriate voice for the language
            voice = self._get_voice_for_language(language)
            print("Using voice:", voice)
            
            # Synthesize voice using async
            success = await self.tts.synthesize_async(text, voice_file, voice=voice)
            if success:
                print("Voice synthesis successful")
                # Store voice file info in database
                self.cursor.execute("""
                    INSERT INTO voice_files (news_id, language, file_path)
                    VALUES (?, ?, ?)
                """, (news_id, language, voice_file))
                self.conn.commit()
                return voice_file
            print("Voice synthesis failed")
            return None
            
        except Exception as e:
            print("Error in get_voice_file:", str(e))
            self.logger.error(f"Error getting/generating voice file: {str(e)}")
            return None
            
    def _get_voice_for_language(self, language: str) -> str:
        """Get appropriate voice for the given language."""
        # Map of language codes to EdgeTTS voices
        # https://gist.github.com/BettyJJ/17cbaa1de96235a7f5773b8690a20462
        voice_map = {
            'en': 'en-US-AriaNeural',  # English
            'es': 'es-ES-AlvaroNeural',  # Spanish
            'fr': 'fr-FR-DeniseNeural',  # French
            'de': 'de-DE-KatjaNeural',  # German
            'it': 'it-IT-ElsaNeural',  # Italian
            'pt': 'pt-BR-FranciscaNeural',  # Portuguese
            'ru': 'ru-RU-SvetlanaNeural',  # Russian
            'zh': 'zh-CN-XiaoxiaoNeural',  # Chinese
            'ja': 'ja-JP-NanamiNeural',  # Japanese
            'ar': 'ar-SA-ZariyahNeural',  # Arabic
            'fa': 'fa-IR-FaridNeural',  # Persian
        }
        return voice_map.get(language, 'en-US-AriaNeural')  # Default to English if language not supported

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def get_user_language(self, user_id: str) -> str:
        """Get user's preferred language."""
        try:
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return 'en'
            
            self.cursor.execute(
                "SELECT preferred_language FROM user_preferences WHERE user_id = ?",
                (db_user_id,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else 'en'
        except Exception as e:
            self.logger.error(f"Error getting user language: {str(e)}")
            return 'en'

    def set_user_language(self, user_id: str, language_code: str) -> bool:
        """Set user's preferred language."""
        try:
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return False
            
            self.cursor.execute(
                "UPDATE user_preferences SET preferred_language = ? WHERE user_id = ?",
                (language_code, db_user_id)
            )
            
            if self.cursor.rowcount == 0:
                self.cursor.execute(
                    "INSERT INTO user_preferences (user_id, preferred_language) VALUES (?, ?)",
                    (db_user_id, language_code)
                )
            
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error setting user language: {str(e)}")
            self.conn.rollback()
            return False

    def get_user_preferences(self, user_id: str) -> dict:
        """Get user preferences."""
        try:
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return {
                    'preferred_language': 'en',
                    'enable_translation': False,
                    'max_news_items': 5,
                    'enable_voice': False,
                    'voice_language': 'auto'
                }
            
            self.cursor.execute("""
                SELECT preferred_language, enable_translation, max_news_items, enable_voice, voice_language
                FROM user_preferences WHERE user_id = ?
            """, (db_user_id,))
            result = self.cursor.fetchone()
            
            if result:
                return {
                    'preferred_language': result[0],
                    'enable_translation': bool(result[1]),
                    'max_news_items': result[2],
                    'enable_voice': bool(result[3]),
                    'voice_language': result[4] if result[4] else 'auto'
                }
            return {
                'preferred_language': 'en',
                'enable_translation': False,
                'max_news_items': 5,
                'enable_voice': False,
                'voice_language': 'auto'
            }
        except Exception as e:
            self.logger.error(f"Error getting user preferences: {str(e)}")
            return {
                'preferred_language': 'en',
                'enable_translation': False,
                'max_news_items': 5,
                'enable_voice': False,
                'voice_language': 'auto'
            }

    def update_user_preferences(self, user_id: str, preferences: dict) -> bool:
        """Update user preferences."""
        try:
            db_user_id = self._get_db_user_id(user_id)
            if not db_user_id:
                return False
            
            self.cursor.execute("""
                UPDATE user_preferences 
                SET preferred_language = ?,
                    enable_translation = ?,
                    max_news_items = ?,
                    enable_voice = ?,
                    voice_language = ?
                WHERE user_id = ?
            """, (
                preferences.get('preferred_language', 'en'),
                preferences.get('enable_translation', True),
                preferences.get('max_news_items', 5),
                preferences.get('enable_voice', True),
                preferences.get('voice_language', 'auto'),
                db_user_id
            ))
            
            if self.cursor.rowcount == 0:
                self.cursor.execute("""
                    INSERT INTO user_preferences 
                    (user_id, preferred_language, enable_translation, max_news_items, enable_voice, voice_language)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    db_user_id,
                    preferences.get('preferred_language', 'en'),
                    preferences.get('enable_translation', True),
                    preferences.get('max_news_items', 5),
                    preferences.get('enable_voice', True),
                    preferences.get('voice_language', 'auto')
                ))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating user preferences: {str(e)}")
            self.conn.rollback()
            return False

    def set_voice_enabled(self, user_id: str, enabled: bool) -> bool:
        """Enable or disable voice messages for a user."""
        try:
            preferences = self.get_user_preferences(user_id)
            preferences['enable_voice'] = enabled
            return self.update_user_preferences(user_id, preferences)
        except Exception as e:
            self.logger.error(f"Error setting voice enabled: {str(e)}")
            return False

    def set_voice_language(self, user_id: str, language: str) -> bool:
        """Set voice language preference for a user."""
        try:
            preferences = self.get_user_preferences(user_id)
            preferences['voice_language'] = language
            return self.update_user_preferences(user_id, preferences)
        except Exception as e:
            self.logger.error(f"Error setting voice language: {str(e)}")
            return False