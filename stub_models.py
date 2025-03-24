"""Stub models for lightweight/offline operation"""
from typing import List, Dict
import random
from datetime import datetime

class StubWhisperModel:
    """Lightweight stub replacement for Whisper"""
    
    def transcribe(self, audio_file: str) -> Dict:
        """Simulate transcription with placeholder response"""
        return {
            "text": "Speech transcription unavailable in offline mode",
            "timestamp": datetime.now().isoformat()
        }

class StubGPT2Model:
    """Lightweight stub replacement for GPT-2"""
    
    def __init__(self):
        self.fallback_responses = [
            "I understand and will help with that.",
            "Could you please provide more details?",
            "I'll assist you with this request.",
            "Let me help you with that task."
        ]
    
    def generate(self, *args, **kwargs) -> List[str]:
        """Simulate text generation with placeholder responses"""
        num_responses = kwargs.get('num_return_sequences', 1)
        return random.sample(self.fallback_responses, 
                           min(num_responses, len(self.fallback_responses)))

class StubSpacyModel:
    """Lightweight stub replacement for spaCy"""
    
    def __call__(self, text: str) -> 'StubDoc':
        return StubDoc(text)
    
    def pipe(self, texts: List[str]):
        for text in texts:
            yield self(text)

class StubDoc:
    """Stub spaCy Doc object"""
    
    def __init__(self, text: str):
        self.text = text
        self.ents = []
        
    def __iter__(self):
        yield from [] 