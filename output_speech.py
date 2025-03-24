from typing import Optional, Dict
import pyttsx3
import threading
import logging
from dataclasses import dataclass

@dataclass
class TTSConfig:
    """Configuration for text-to-speech output"""
    rate: int = 150  # Speaking rate (words per minute)
    volume: float = 0.9  # Volume level (0.0 to 1.0)
    voice_gender: str = "female"  # "male" or "female"
    enabled: bool = True  # Toggle TTS on/off

class SpeechOutput:
    """Handles text-to-speech output for the AAC system"""
    
    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize the speech output module
        
        Args:
            config: Optional TTS configuration
        """
        self.config = config or TTSConfig()
        self.logger = logging.getLogger(__name__)
        
        try:
            self.engine = pyttsx3.init()
            self._configure_engine()
        except Exception as e:
            self.logger.error(f"Failed to initialize TTS engine: {str(e)}")
            self.engine = None

    def _configure_engine(self) -> None:
        """Configure TTS engine with current settings"""
        if not self.engine:
            return
            
        try:
            # Set rate and volume
            self.engine.setProperty('rate', self.config.rate)
            self.engine.setProperty('volume', self.config.volume)
            
            # Set voice
            voices = self.engine.getProperty('voices')
            if voices:
                # Usually index 0 is male, 1 is female
                voice_idx = 1 if self.config.voice_gender.lower() == "female" else 0
                if voice_idx < len(voices):
                    self.engine.setProperty('voice', voices[voice_idx].id)
                    
        except Exception as e:
            self.logger.error(f"Error configuring TTS engine: {str(e)}")

    def speak(self, text: str, block: bool = False) -> None:
        """
        Convert text to speech and play it
        
        Args:
            text: Text to be spoken
            block: If True, wait for speech to complete
        """
        if not self.engine or not self.config.enabled:
            return

        def speak_text():
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                self.logger.error(f"Error in speech synthesis: {str(e)}")

        if block:
            speak_text()
        else:
            threading.Thread(target=speak_text, daemon=True).start()

    def update_config(self, **kwargs) -> None:
        """
        Update TTS configuration
        
        Args:
            **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self._configure_engine()

    def toggle(self, enabled: Optional[bool] = None) -> bool:
        """
        Toggle TTS output on/off
        
        Args:
            enabled: Optional boolean to set specific state
            
        Returns:
            Current enabled state
        """
        if enabled is not None:
            self.config.enabled = enabled
        else:
            self.config.enabled = not self.config.enabled
        
        return self.config.enabled

    def get_status(self) -> Dict:
        """
        Get current TTS status
        
        Returns:
            Dictionary containing current TTS status
        """
        return {
            "enabled": self.config.enabled,
            "rate": self.config.rate,
            "volume": self.config.volume,
            "voice_gender": self.config.voice_gender,
            "engine_available": self.engine is not None
        }

# Example usage
if __name__ == "__main__":
    # Test the speech output module
    speech_output = SpeechOutput()
    
    # Test basic speech
    print("\n🗣️ Testing basic speech output...")
    speech_output.speak("Hello, I am your AAC system.", block=True)
    
    # Test configuration updates
    print("\n⚙️ Testing configuration updates...")
    speech_output.update_config(rate=180, volume=0.8, voice_gender="male")
    speech_output.speak("Now I'm speaking faster with a male voice.", block=True)
    
    # Test toggle
    print("\n🔄 Testing TTS toggle...")
    speech_output.toggle(False)
    speech_output.speak("This should not be spoken.")
    print("Status:", speech_output.get_status()) 