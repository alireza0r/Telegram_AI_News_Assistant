import logging
import os
from typing import Dict, Optional, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from langchain.cache import InMemoryCache
import langchain
from langchain.callbacks import get_openai_callback
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Load environment variables
load_dotenv()

# Enable caching
langchain.llm_cache = InMemoryCache()

class LLMManager:
    """Manager for LLM-based operations using LangChain."""
    
    def __init__(self):
        """Initialize LLM manager with LangChain components."""
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Setup logging
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize the language model
        self.llm = ChatOpenAI(
            temperature=0.3,
            model_name="gpt-3.5-turbo",
            openai_api_key=self.api_key
        )
        
        # Initialize output parser
        self.output_parser = StrOutputParser()
        
        # Initialize prompt templates
        self.translation_prompt = ChatPromptTemplate.from_template(
            "Translate the following text from {source_lang} to {target_lang}. "
            "Maintain the original meaning and tone:\n\n{text}"
        )
        
        self.summarization_prompt = ChatPromptTemplate.from_template(
            "Summarize the following text in about {max_length} characters. "
            "Focus on the main points and key information:\n\n{text}"
        )
        
        self.language_detection_prompt = ChatPromptTemplate.from_template(
            "Identify the language of the following text and respond with just the ISO 639-1 language code "
            "(e.g., 'en' for English):\n\n{text}"
        )
        
        self.news_digest_prompt = ChatPromptTemplate.from_template(
            "Create a brief news digest in {target_lang} based on these news items:\n\n{news_text}\n\n"
            "Format the digest as a concise summary of the main developments."
        )
        
        # Initialize chains using RunnablePassthrough
        self.translation_chain = (
            self.translation_prompt 
            | self.llm 
            | self.output_parser
        )
        
        self.summarization_chain = (
            self.summarization_prompt 
            | self.llm 
            | self.output_parser
        )
        
        self.language_detection_chain = (
            self.language_detection_prompt 
            | self.llm 
            | self.output_parser
        )
        
        self.news_digest_chain = (
            self.news_digest_prompt 
            | self.llm 
            | self.output_parser
        )
    
    async def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source language to target language using LangChain."""
        if source_lang == target_lang:
            return text
            
        try:
            with get_openai_callback() as cb:
                result = await self.translation_chain.ainvoke({
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "text": text
                })
                self.logger.info(f"Translation cost: {cb.total_cost}")
                return result.strip()
        except Exception as e:
            self.logger.error(f"Translation error: {e}")
            return text
    
    async def summarize_text(self, text: str, max_length: int = 200) -> str:
        """Generate a concise summary of the text using LangChain."""
        try:
            with get_openai_callback() as cb:
                result = await self.summarization_chain.ainvoke({
                    "text": text,
                    "max_length": max_length
                })
                self.logger.info(f"Summarization cost: {cb.total_cost}")
                return result.strip()
        except Exception as e:
            self.logger.error(f"Summarization error: {e}")
            return text[:max_length] + "..."
    
    async def detect_language(self, text: str) -> str:
        """Detect the language of a text using LangChain."""
        try:
            with get_openai_callback() as cb:
                result = await self.language_detection_chain.ainvoke({"text": text})
                self.logger.info(f"Language detection cost: {cb.total_cost}")
                
                # Clean and validate the response
                lang_code = result.strip().lower()
                if len(lang_code) <= 5:  # Valid language codes are short
                    return lang_code
                return "en"  # Default to English
        except Exception as e:
            self.logger.error(f"Language detection error: {e}")
            return "en"  # Default to English
    
    async def generate_news_digest(self, news_items: List[Dict], target_lang: str) -> str:
        """Generate a digest of multiple news items using LangChain."""
        try:
            # Create a formatted list of news items
            news_text = ""
            for i, item in enumerate(news_items, 1):
                news_text += f"{i}. {item['title']}\n"
                news_text += f"{item['description'][:150]}...\n\n"
            
            with get_openai_callback() as cb:
                result = await self.news_digest_chain.ainvoke({
                    "news_text": news_text,
                    "target_lang": target_lang
                })
                self.logger.info(f"News digest cost: {cb.total_cost}")
                return result.strip()
        except Exception as e:
            self.logger.error(f"News digest error: {e}")
            return "Failed to generate news digest."
    
    def get_usage_stats(self) -> Dict:
        """Get usage statistics for the LLM operations."""
        return {
            "model": self.llm.model_name,
            "temperature": self.llm.temperature,
            "cache_enabled": isinstance(langchain.llm_cache, InMemoryCache)
        }