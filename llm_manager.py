import logging
import os
import aiohttp
import json
from typing import Dict, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class LLMManager:
    """Manager for LLM-based operations like translation and summarization."""
    
    def __init__(self):
        """Initialize LLM manager with API credentials."""
        self.api_key = os.getenv('LLM_API_KEY')  # API key for the LLM service
        self.api_url = os.getenv('LLM_API_URL', 'https://api.openai.com/v1/chat/completions')
        self.model = os.getenv('LLM_MODEL', 'gpt-4')
        
        # Setup logging
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)
        
        # Translation cache to avoid repeat translations
        self.translation_cache = {}
        
    async def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source language to target language."""
        # Create a cache key
        cache_key = f"{source_lang}:{target_lang}:{hash(text)}"
        
        # Check if translation is in cache
        if cache_key in self.translation_cache:
            self.logger.info(f"Using cached translation for {source_lang} -> {target_lang}")
            return self.translation_cache[cache_key]
        
        # Early return if source and target languages are the same
        if source_lang == target_lang:
            return text
            
        try:
            # Prepare prompt for translation
            prompt = f"Translate the following text from {source_lang} to {target_lang}:\n\n{text}"
            
            # Call LLM API
            response = await self._call_llm_api(prompt)
            
            if response:
                # Cache the translation
                self.translation_cache[cache_key] = response
                return response
            else:
                self.logger.error(f"Translation failed from {source_lang} to {target_lang}")
                return text
                
        except Exception as e:
            self.logger.error(f"Translation error: {e}")
            return text
    
    async def summarize_text(self, text: str, max_length: int = 200) -> str:
        """Generate a concise summary of the text."""
        try:
            # Prepare prompt for summarization
            prompt = f"Summarize the following text in about {max_length} characters:\n\n{text}"
            
            # Call LLM API
            response = await self._call_llm_api(prompt)
            
            if response:
                return response
            else:
                self.logger.error("Summarization failed")
                return text[:max_length] + "..."
                
        except Exception as e:
            self.logger.error(f"Summarization error: {e}")
            return text[:max_length] + "..."
    
    async def detect_language(self, text: str) -> str:
        """Detect the language of a text using LLM."""
        try:
            # Prepare prompt for language detection
            prompt = f"Identify the language of the following text and respond with just the ISO 639-1 language code (e.g., 'en' for English):\n\n{text}"
            
            # Call LLM API
            response = await self._call_llm_api(prompt)
            
            if response and len(response) <= 5:  # Valid language codes are short
                return response.strip().lower()
            else:
                self.logger.error("Language detection failed")
                return "en"  # Default to English
                
        except Exception as e:
            self.logger.error(f"Language detection error: {e}")
            return "en"  # Default to English
    
    async def _call_llm_api(self, prompt: str) -> Optional[str]:
        """Make API call to the LLM service."""
        if not self.api_key:
            self.logger.error("LLM API key not set")
            return None
            
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that translates and summarizes text accurately."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,  # Lower temperature for more deterministic outputs
                "max_tokens": 1000
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, headers=headers, json=data) as response:
                    if response.status == 200:
                        response_json = await response.json()
                        return response_json["choices"][0]["message"]["content"].strip()
                    else:
                        error_text = await response.text()
                        self.logger.error(f"API error: {response.status}, {error_text}")
                        return None
                        
        except Exception as e:
            self.logger.error(f"API call error: {e}")
            return None
    
    async def generate_news_digest(self, news_items: List[Dict], target_lang: str) -> str:
        """Generate a digest of multiple news items."""
        try:
            # Create a formatted list of news items
            news_text = ""
            for i, item in enumerate(news_items, 1):
                news_text += f"{i}. {item['title']}\n"
                news_text += f"{item['description'][:150]}...\n\n"
            
            # Prepare prompt for digest generation
            prompt = (
                f"Create a brief news digest in {target_lang} based on these news items:\n\n"
                f"{news_text}\n\n"
                "Format the digest as a concise summary of the main developments."
            )
            
            # Call LLM API
            response = await self._call_llm_api(prompt)
            
            if response:
                return response
            else:
                self.logger.error("News digest generation failed")
                return "Failed to generate news digest."
                
        except Exception as e:
            self.logger.error(f"News digest error: {e}")
            return "Failed to generate news digest."