import sqlite3
import feedparser
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any

class NewsManager:
    def __init__(self, db_path: str = "news_database.db"):
        """Initialize the news manager with database connection."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)

    def _create_tables(self):
        """Create database tables if they don't exist."""
        with open('schema.sql', 'r') as f:
            schema = f.read()
        self.cursor.executescript(schema)
        self.conn.commit()

    # User Management
    def add_user(self, user_id: str, username: str) -> int:
        """Add a new user to the database."""
        try:
            self.cursor.execute(
                "INSERT INTO users (username, email) VALUES (?, ?)",
                (username, user_id)
            )
            self.conn.commit()
            
            # Initialize schedule
            self.cursor.execute(
                "INSERT INTO user_schedule (user_id, enabled, interval_minutes) VALUES (?, FALSE, 60)",
                (user_id,)
            )
            self.conn.commit()
            
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            self.logger.info(f"User {user_id} already exists")
            return -1

    def remove_user(self, user_id: str) -> bool:
        """Remove a user and all their data."""
        try:
            # Remove user's subscriptions
            self.cursor.execute("DELETE FROM user_feeds WHERE user_id = ?", (user_id,))
            # Remove user's delivery records
            self.cursor.execute("DELETE FROM news_delivery WHERE user_id = ?", (user_id,))
            # Remove user's schedule
            self.cursor.execute("DELETE FROM user_schedule WHERE user_id = ?", (user_id,))
            # Remove user
            self.cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error removing user {user_id}: {e}")
            return False

    # Feed Management
    def add_feed(self, feed_url: str, feed_name: str) -> int:
        """Add a new RSS feed to the database."""
        try:
            self.cursor.execute(
                "INSERT INTO rss_feeds (feed_url, feed_name) VALUES (?, ?)",
                (feed_url, feed_name)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            self.logger.info(f"Feed {feed_url} already exists")
            return -1

    def subscribe_user_to_feed(self, user_id: str, feed_id: int) -> bool:
        """Subscribe a user to an RSS feed."""
        try:
            self.cursor.execute(
                "INSERT INTO user_feeds (user_id, feed_id) VALUES (?, ?)",
                (user_id, feed_id)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            self.logger.info(f"User {user_id} already subscribed to feed {feed_id}")
            return False

    def unsubscribe_user_from_feed(self, user_id: str, feed_id: int) -> bool:
        """Unsubscribe a user from an RSS feed."""
        try:
            self.cursor.execute(
                "DELETE FROM user_feeds WHERE user_id = ? AND feed_id = ?",
                (user_id, feed_id)
            )
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error unsubscribing user {user_id} from feed {feed_id}: {e}")
            return False

    # Schedule Management
    def set_schedule(self, user_id: str, interval_minutes: int) -> bool:
        """Set the automatic news delivery interval for a user."""
        try:
            self.cursor.execute(
                "UPDATE user_schedule SET interval_minutes = ? WHERE user_id = ?",
                (interval_minutes, user_id)
            )
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error setting schedule for user {user_id}: {e}")
            return False

    def enable_auto_delivery(self, user_id: str) -> bool:
        """Enable automatic news delivery for a user."""
        try:
            self.cursor.execute(
                "UPDATE user_schedule SET enabled = TRUE WHERE user_id = ?",
                (user_id,)
            )
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error enabling auto delivery for user {user_id}: {e}")
            return False

    def disable_auto_delivery(self, user_id: str) -> bool:
        """Disable automatic news delivery for a user."""
        try:
            self.cursor.execute(
                "UPDATE user_schedule SET enabled = FALSE WHERE user_id = ?",
                (user_id,)
            )
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error disabling auto delivery for user {user_id}: {e}")
            return False

    def get_user_schedule(self, user_id: str) -> Optional[Dict]:
        """Get a user's schedule settings."""
        try:
            self.cursor.execute(
                "SELECT enabled, interval_minutes, last_delivery FROM user_schedule WHERE user_id = ?",
                (user_id,)
            )
            result = self.cursor.fetchone()
            if result:
                return {
                    'enabled': bool(result[0]),
                    'interval_minutes': result[1],
                    'last_delivery': result[2]
                }
            return None
        except Exception as e:
            self.logger.error(f"Error getting schedule for user {user_id}: {e}")
            return None

    # News Management
    def check_feeds(self) -> List[Dict]:
        """Check all feeds for new content."""
        new_items = []
        try:
            self.cursor.execute("SELECT feed_id, feed_url FROM rss_feeds")
            feeds = self.cursor.fetchall()
            
            for feed_id, feed_url in feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    if not feed.entries:
                        continue
                    
                    for entry in feed.entries:
                        self.cursor.execute(
                            "SELECT news_id FROM news_items WHERE link = ?",
                            (entry.link,)
                        )
                        if not self.cursor.fetchone():
                            news_id = self.add_news_item(
                                feed_id,
                                entry.title,
                                entry.link,
                                entry.description if hasattr(entry, 'description') else '',
                                datetime.now()
                            )
                            new_items.append({
                                'news_id': news_id,
                                'feed_id': feed_id,
                                'title': entry.title,
                                'link': entry.link,
                                'description': entry.description if hasattr(entry, 'description') else ''
                            })
                    
                    self.update_feed_last_updated(feed_id)
                    
                except Exception as e:
                    self.logger.error(f"Error checking feed {feed_id}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error in check_feeds: {e}")
        
        return new_items

    def add_news_item(self, feed_id: int, title: str, link: str, description: str, pub_date: datetime) -> int:
        """Add a new news item to the database."""
        try:
            self.cursor.execute(
                """INSERT INTO news_items 
                   (feed_id, title, link, description, pub_date) 
                   VALUES (?, ?, ?, ?, ?)""",
                (feed_id, title, link, description, pub_date)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Error adding news item: {e}")
            return -1

    def get_undelivered_news(self, user_id: str) -> List[Dict]:
        """Get all undelivered news items for a user."""
        try:
            self.cursor.execute("""
                SELECT ni.news_id, ni.title, ni.link, ni.description, ni.pub_date, rf.feed_name
                FROM news_items ni
                JOIN rss_feeds rf ON ni.feed_id = rf.feed_id
                JOIN user_feeds uf ON rf.feed_id = uf.feed_id
                LEFT JOIN news_delivery nd ON ni.news_id = nd.news_id AND nd.user_id = ?
                WHERE uf.user_id = ? AND nd.delivery_id IS NULL
                ORDER BY ni.pub_date DESC
            """, (user_id, user_id))
            
            columns = [description[0] for description in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting undelivered news for user {user_id}: {e}")
            return []

    def mark_news_delivered(self, user_id: str, news_id: int) -> bool:
        """Mark a news item as delivered to a user."""
        try:
            self.cursor.execute(
                "INSERT INTO news_delivery (user_id, news_id) VALUES (?, ?)",
                (user_id, news_id)
            )
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error marking news {news_id} as delivered to user {user_id}: {e}")
            return False

    def get_user_feeds(self, user_id: str) -> List[Dict]:
        """Get all RSS feeds a user is subscribed to."""
        try:
            self.cursor.execute("""
                SELECT rf.feed_id, rf.feed_url, rf.feed_name, rf.last_updated
                FROM rss_feeds rf
                JOIN user_feeds uf ON rf.feed_id = uf.feed_id
                WHERE uf.user_id = ?
            """, (user_id,))
            
            columns = [description[0] for description in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting feeds for user {user_id}: {e}")
            return []

    def update_feed_last_updated(self, feed_id: int) -> bool:
        """Update the last_updated timestamp for a feed."""
        try:
            self.cursor.execute(
                "UPDATE rss_feeds SET last_updated = CURRENT_TIMESTAMP WHERE feed_id = ?",
                (feed_id,)
            )
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating feed {feed_id} timestamp: {e}")
            return False

    def get_users_for_delivery(self) -> List[Dict]:
        """Get all users who should receive news based on their schedule."""
        try:
            self.cursor.execute("""
                SELECT us.user_id, us.interval_minutes, us.last_delivery, us.enabled
                FROM user_schedule us
                WHERE us.enabled = TRUE
            """)
            
            users = []
            for user_id, interval, last_delivery, enabled in self.cursor.fetchall():
                self.logger.info(f"Checking user {user_id}: interval={interval}min, last_delivery={last_delivery}, enabled={enabled}")
                
                if last_delivery:
                    last_delivery = datetime.fromisoformat(last_delivery)
                    next_delivery = last_delivery + timedelta(minutes=interval)
                    self.logger.info(f"Next delivery for user {user_id} should be at {next_delivery}")
                    if datetime.now() < next_delivery:
                        self.logger.info(f"Skipping user {user_id} - next delivery not due yet")
                        continue
                
                users.append({
                    'user_id': user_id,
                    'interval_minutes': interval,
                    'last_delivery': last_delivery
                })
                self.logger.info(f"Added user {user_id} to delivery list")
            
            self.logger.info(f"Found {len(users)} users eligible for delivery")
            return users
        except Exception as e:
            self.logger.error(f"Error getting users for delivery: {e}")
            return []

    def update_last_delivery(self, user_id: str) -> bool:
        """Update the last delivery timestamp for a user."""
        try:
            self.cursor.execute(
                "UPDATE user_schedule SET last_delivery = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating last delivery for user {user_id}: {e}")
            return False

    def get_news_by_id(self, news_id: int) -> Optional[Dict]:
        """Get news item by ID."""
        try:
            self.cursor.execute("""
                SELECT title, description, link, language
                FROM news_items
                WHERE news_id = ?
            """, (news_id,))
            
            result = self.cursor.fetchone()
            if not result:
                return None
                
            return {
                'title': result[0],
                'description': result[1],
                'link': result[2],
                'language': result[3]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting news {news_id}: {e}")
            return None

    def close(self):
        """Close the database connection."""
        self.conn.close() 