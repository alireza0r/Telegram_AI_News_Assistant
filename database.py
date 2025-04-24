import sqlite3
import datetime
from typing import List, Dict, Optional

class Database:
    def __init__(self, db_path: str = "news_database.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist"""
        with open('schema.sql', 'r') as f:
            schema = f.read()
        self.cursor.executescript(schema)
        self.conn.commit()

    def add_user(self, username: str, email: str) -> int:
        """Add a new user to the database"""
        self.cursor.execute(
            "INSERT INTO users (username, email) VALUES (?, ?)",
            (username, email)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def add_rss_feed(self, feed_url: str, feed_name: str) -> int:
        """Add a new RSS feed to the database"""
        self.cursor.execute(
            "INSERT INTO rss_feeds (feed_url, feed_name) VALUES (?, ?)",
            (feed_url, feed_name)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def subscribe_user_to_feed(self, user_id: int, feed_id: int):
        """Subscribe a user to an RSS feed"""
        self.cursor.execute(
            "INSERT INTO user_feeds (user_id, feed_id) VALUES (?, ?)",
            (user_id, feed_id)
        )
        self.conn.commit()

    def add_news_item(self, feed_id: int, title: str, link: str, description: str, pub_date: datetime.datetime) -> int:
        """Add a new news item to the database"""
        self.cursor.execute(
            """INSERT INTO news_items 
               (feed_id, title, link, description, pub_date) 
               VALUES (?, ?, ?, ?, ?)""",
            (feed_id, title, link, description, pub_date)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def mark_news_delivered(self, user_id: int, news_id: int):
        """Mark a news item as delivered to a user"""
        self.cursor.execute(
            "INSERT INTO news_delivery (user_id, news_id) VALUES (?, ?)",
            (user_id, news_id)
        )
        self.conn.commit()

    def get_undelivered_news(self, user_id: int) -> List[Dict]:
        """Get all undelivered news items for a user"""
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

    def get_user_feeds(self, user_id: int) -> List[Dict]:
        """Get all RSS feeds a user is subscribed to"""
        self.cursor.execute("""
            SELECT rf.feed_id, rf.feed_url, rf.feed_name, rf.last_updated
            FROM rss_feeds rf
            JOIN user_feeds uf ON rf.feed_id = uf.feed_id
            WHERE uf.user_id = ?
        """, (user_id,))
        
        columns = [description[0] for description in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def update_feed_last_updated(self, feed_id: int):
        """Update the last_updated timestamp for a feed"""
        self.cursor.execute(
            "UPDATE rss_feeds SET last_updated = CURRENT_TIMESTAMP WHERE feed_id = ?",
            (feed_id,)
        )
        self.conn.commit()

    def close(self):
        """Close the database connection"""
        self.conn.close() 