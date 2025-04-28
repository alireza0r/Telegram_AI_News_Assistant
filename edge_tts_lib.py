import asyncio
import edge_tts
import os
from typing import Optional, Callable, Any

class EdgeTTS:
    def __init__(self, voice: str = "en-US-AriaNeural", rate: str = "+0%", volume: str = "+0%"):
        """
        Initialize EdgeTTS with voice, rate, and volume settings.
        
        Args:
            voice (str): Voice to use for synthesis (default: "en-US-AriaNeural")
            rate (str): Speaking rate adjustment (default: "+0%")
            volume (str): Volume adjustment (default: "+0%")
        """
        self.voice = voice
        self.rate = rate
        self.volume = volume

    async def synthesize_async(self, text: str, output_file: str, voice: Optional[str] = None, stream_callback: Optional[Callable[[bytes], Any]] = None) -> bool:
        """
        Synthesize speech from text asynchronously and optionally stream the audio.
        
        Args:
            text (str): Text to synthesize
            output_file (str): Path to save the output audio file
            voice (Optional[str]): Voice to use for synthesis (overrides default)
            stream_callback (Optional[Callable[[bytes], Any]]): Callback function to handle streaming audio chunks
            
        Returns:
            bool: True if synthesis was successful, False otherwise
        """
        try:
            # Use provided voice or default
            voice_to_use = voice if voice else self.voice
            
            communicate = edge_tts.Communicate(text, voice_to_use, rate=self.rate, volume=self.volume)
            
            if stream_callback:
                # Create a temporary file to store the audio
                with open(output_file, 'wb') as file:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_data = chunk["data"]
                            file.write(audio_data)
                            if stream_callback:
                                await stream_callback(audio_data)
            else:
                await communicate.save(output_file)
                
            return True
        except Exception as e:
            print(f"Error during synthesis: {str(e)}")
            return False

    def synthesize(self, text: str, output_file: str, voice: Optional[str] = None, stream_callback: Optional[Callable[[bytes], Any]] = None) -> bool:
        """
        Synthesize speech from text (synchronous wrapper for async function).
        
        Args:
            text (str): Text to synthesize
            output_file (str): Path to save the output audio file
            voice (Optional[str]): Voice to use for synthesis (overrides default)
            stream_callback (Optional[Callable[[bytes], Any]]): Callback function to handle streaming audio chunks
            
        Returns:
            bool: True if synthesis was successful, False otherwise
        """
        return asyncio.run(self.synthesize_async(text, output_file, voice, stream_callback))

def get_available_voices() -> list:
    """
    Get a list of available voices.
    
    Returns:
        list: List of available voice names
    """
    return asyncio.run(edge_tts.list_voices())

# https://gist.github.com/BettyJJ/17cbaa1de96235a7f5773b8690a20462
if __name__ == "__main__":
    # Example usage
    tts = EdgeTTS()
    # text = "Hello, this is a test of the Edge TTS system."
    text = "من یک سیگار خوشمزه دارم"
    output_file = "edge_tts_output.mp3"
    
    if tts.synthesize(text, output_file):
        print(f"Successfully synthesized speech to {output_file}")
    else:
        print("Failed to synthesize speech") 