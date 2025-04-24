# News RSS Bot

A Telegram bot that aggregates, processes, and delivers news from various RSS feeds with advanced features like translation and summarization.

## Features

- **RSS Feed Management**:
  - Add and remove RSS feeds
  - List subscribed feeds with IDs
  - Automatic feed updates
  - Feed status tracking

- **News Delivery**:
  - Automatic news delivery on schedule
  - Manual news retrieval
  - Customizable delivery intervals
  - News item tracking to avoid duplicates

- **Language Support**:
  - Automatic language detection
  - News translation to preferred language
  - Support for multiple languages:
    - English (en)
    - Spanish (es)
    - French (fr)
    - German (de)
    - Italian (it)
    - Portuguese (pt)
    - Russian (ru)
    - Chinese (zh)
    - Japanese (ja)
    - Arabic (ar)
    - Persian (fa)

- **User Preferences**:
  - Customizable language settings
  - Translation toggle
  - Maximum news items per delivery
  - Delivery schedule settings

## Requirements

- Python 3.8+
- SQLite3
- Required Python packages (see `requirements.txt`):
  - python-telegram-bot
  - feedparser
  - beautifulsoup4
  - requests
  - python-dotenv
  - langchain
  - langchain-openai
  - langchain-core

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd news-rss-bot
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the project root with the following variables:
```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
```

## Project Structure

```
news-rss-bot/
├── telegram_bot_v2.py    # Main Telegram bot implementation
├── news_manager.py       # Database and RSS feed management
├── llm_manager.py        # Language model operations
├── schema.sql           # Database schema
├── requirements.txt     # Project dependencies
├── .env                 # Environment variables
└── README.md           # This file
```

## Usage

### Telegram Bot Commands

- `/start` - Start the bot and register
- `/help` - Show help message
- `/status` - Show current settings
- `/addfeed <url>` - Add a new RSS feed
- `/listfeeds` - Show subscribed feeds with IDs
- `/removefeed <feed_id>` - Remove a feed using its ID
- `/settings` - Configure news delivery settings
- `/schedule` - Set news delivery schedule
- `/language` - Change preferred language
- `/getnews` - Get latest news manually

### Settings

The bot provides several customization options:

1. **Auto Delivery**:
   - Enable/disable automatic news delivery
   - Set delivery interval (30min, 1h, 3h, 24h)

2. **Language Preferences**:
   - Choose preferred language
   - Enable/disable translation
   - Set maximum news items per delivery

3. **Feed Management**:
   - Add multiple RSS feeds
   - Remove feeds using their IDs
   - View subscribed feeds and their status

## Database Schema

The system uses SQLite3 with the following main tables:

- `users` - User information
- `rss_feeds` - RSS feed details
- `news_items` - News content
- `user_feeds` - User-feed subscriptions
- `news_delivery` - Delivery tracking
- `user_schedule` - Delivery schedules
- `user_preferences` - User settings

## Security Notes

- Keep your `.env` file secure and never commit it to version control
- The `.env` file contains sensitive information like API keys
- Make sure to add `.env` to your `.gitignore` file
- Use different API keys for development and production environments

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.

## Acknowledgments

- python-telegram-bot library
- feedparser for RSS parsing
- BeautifulSoup for HTML processing
- LangChain for language model operations 