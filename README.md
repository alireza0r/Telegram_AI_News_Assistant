# News Management System

A powerful news management system that aggregates, processes, and delivers news from various RSS feeds to users through multiple platforms (currently supporting Telegram).

## Features

- **Multi-platform Support**: Easily integrate with different platforms (Telegram support included)
- **RSS Feed Management**: Add, remove, and manage multiple RSS feeds
- **Automatic News Delivery**: Schedule news delivery at custom intervals
- **Language Support**: 
  - Automatic language detection
  - News translation to preferred language
  - Support for multiple languages (English, Spanish, French, German, Italian, Portuguese, Russian, Chinese, Japanese, Persian)
- **News Processing**:
  - Automatic news summarization
  - HTML content cleaning
  - Duplicate detection
- **User Management**:
  - User registration and preferences
  - Custom delivery schedules
  - Feed subscription management
  - Translation preferences

## Requirements

- Python 3.8+
- SQLite3
- Required Python packages (see `requirements.txt`):
  - python-telegram-bot
  - feedparser
  - beautifulsoup4
  - requests
  - python-dotenv

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd news-management-system
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

# LLM API Configuration
LLM_API_KEY=your_llm_api_key_here
LLM_API_URL=https://api.example.com/v1  # Replace with actual LLM API URL if needed
```

Make sure to:
- Replace `your_telegram_bot_token_here` with your actual Telegram bot token
- Replace `your_llm_api_key_here` with your actual LLM API key
- Replace the LLM API URL with the actual endpoint if needed
- Never commit the `.env` file to version control

## Project Structure

```
news-management-system/
├── telegram_bot_v2.py    # Telegram bot implementation
├── news_manager.py       # Core news management functionality
├── llm_manager.py        # Language and content processing
├── schema.sql           # Database schema
├── requirements.txt     # Project dependencies
├── .env                 # Environment variables (not in version control)
└── README.md           # This file
```

## Usage

### Telegram Bot Commands

- `/start` - Start the bot and register
- `/help` - Show help message
- `/status` - Show current settings
- `/addfeed <url>` - Add a new RSS feed
- `/listfeeds` - Show subscribed feeds
- `/removefeed <url>` - Remove a feed
- `/settings` - Configure news delivery settings
- `/schedule` - Set news delivery schedule
- `/language` - Change preferred language
- `/getnews` - Get latest news

### Settings

The bot provides several customization options:

1. **Auto Delivery**:
   - Enable/disable automatic news delivery
   - Set delivery interval (15min to 8 hours)

2. **Language Preferences**:
   - Choose preferred language
   - Enable/disable translation

3. **Feed Management**:
   - Add multiple RSS feeds
   - Remove unwanted feeds
   - View subscribed feeds

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