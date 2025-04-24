-- Users table to store user information
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RSS feeds table to store RSS feed information
CREATE TABLE IF NOT EXISTS rss_feeds (
    feed_id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_url TEXT NOT NULL UNIQUE,
    feed_name TEXT NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User-RSS mapping table to track which users subscribe to which feeds
CREATE TABLE IF NOT EXISTS user_feeds (
    user_id INTEGER,
    feed_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, feed_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (feed_id) REFERENCES rss_feeds(feed_id) ON DELETE CASCADE
);

-- News items table to store news articles
CREATE TABLE IF NOT EXISTS news_items (
    news_id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id INTEGER,
    title TEXT NOT NULL,
    link TEXT NOT NULL UNIQUE,
    description TEXT,
    pub_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feed_id) REFERENCES rss_feeds(feed_id) ON DELETE CASCADE
);

-- User news delivery tracking
CREATE TABLE IF NOT EXISTS news_delivery (
    delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    news_id INTEGER,
    delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (news_id) REFERENCES news_items(news_id) ON DELETE CASCADE,
    UNIQUE(user_id, news_id)
);

-- User delivery schedule
CREATE TABLE IF NOT EXISTS user_schedule (
    user_id INTEGER PRIMARY KEY,
    enabled BOOLEAN DEFAULT FALSE,
    interval_minutes INTEGER DEFAULT 60,
    last_delivery TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- User preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY,
    preferred_language TEXT DEFAULT 'en',
    enable_translation BOOLEAN DEFAULT TRUE,
    max_news_items INTEGER DEFAULT 5,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
); 