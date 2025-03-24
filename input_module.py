import json
import speech_recognition as sr
from datetime import datetime
from typing import Dict, Optional, Union, Generator, List
import whisper
from geopy.geocoders import Nominatim
import platform
import pyaudio
import wave
from pathlib import Path
import numpy as np
import noisereduce as nr
import threading
import queue
import scipy.io.wavfile as wavfile
from collections import deque

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

from stub_models import StubWhisperModel




class AudioProcessor:
    def __init__(self, sample_rate: int = 16000):
        self.audio_buffer = []  # Initialize an empty buffer
        self.sample_rate = sample_rate  # Use the provided sample rate

    def reduce_noise(self, audio_data):  # Add `self` as the first argument
        try:
            if isinstance(audio_data, str):  # If a file path is given, read it
                sample_rate, audio_data = wavfile.read(audio_data)

            if not isinstance(audio_data, np.ndarray):
                raise ValueError("Input audio is neither a file path nor a NumPy array.")

            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            if len(audio_data) == 0:
                raise ValueError("Empty audio data received.")

            cleaned_audio = nr.reduce_noise(
                y=audio_data,
                y_noise=audio_data[:5000],  # First 5000 samples as noise profile
                sr=self.sample_rate,  # Use instance sample rate
                stationary=False,
                prop_decrease=0.75
            )
            return cleaned_audio

        except Exception as e:
            print(f"⚠️ Error processing noise reduction: {str(e)}")
            return audio_data  # Return original audio instead of None



class InputModule:
    """Handles different types of input for the AAC system"""

    def __init__(self, use_whisper: bool = True, lightweight_mode: bool = False):
        """
        Initialize input module
        
        Args:
            use_whisper: Whether to use Whisper for speech recognition
            lightweight_mode: If True, use stub models for offline operation
        """
        self.lightweight_mode = lightweight_mode
        
        if lightweight_mode:
            self.model = StubWhisperModel()
            self.recognizer = None
            print("⚠️ Running in lightweight mode - speech recognition limited")
        else:
            try:
                self.recognizer = sr.Recognizer()
                if use_whisper:
                    import whisper
                    self.model = whisper.load_model("base")
                else:
                    self.model = None
            except Exception as e:
                print(f"⚠️ Error initializing speech recognition: {str(e)}")
                self.model = StubWhisperModel()
                self.recognizer = None
        
        # Initialize location services
        self.geolocator = Nominatim(user_agent="aac_system")
        
        # Audio recording settings
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.audio_interface = pyaudio.PyAudio()

        # Add new audio processing components
        self.audio_processor = AudioProcessor(sample_rate=self.sample_rate)
        self.is_listening = False
        self.audio_queue = queue.Queue()
        self.transcription_queue = queue.Queue()

    def get_text_input(self, prompt: str = "Enter your message: ") -> Dict:
        """Handle direct text input from user"""
        try:
            text = input(prompt).strip()
            return self._format_input(text, input_type="text")
        except Exception as e:
            return self._format_input(
                error=f"Error getting text input: {str(e)}"
            )

    def record_audio(self, duration: int = 5) -> Optional[str]:
        """
        Record audio from microphone
        Args:
            duration: Recording duration in seconds
        Returns:
            Path to the recorded audio file
        """
        try:
            # Create a temporary directory for audio files if it doesn't exist
            temp_dir = Path("temp_audio")
            temp_dir.mkdir(exist_ok=True)
            
            filename = temp_dir / f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            
            stream = self.audio_interface.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )

            print(f"Recording for {duration} seconds...")
            frames = []
            for _ in range(0, int(self.sample_rate / self.chunk_size * duration)):
                data = stream.read(self.chunk_size)
                frames.append(data)
            print("Recording finished")

            stream.stop_stream()
            stream.close()

            # Save the recorded audio
            with wave.open(str(filename), 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio_interface.get_sample_size(self.audio_format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(frames))

            return str(filename)

        except Exception as e:
            print(f"Error recording audio: {str(e)}")
            return None

    def start_continuous_listening(self) -> None:
        """Start continuous listening mode"""
        self.is_listening = True
        
        # Start the recording thread
        recording_thread = threading.Thread(target=self._continuous_recording)
        processing_thread = threading.Thread(target=self._process_audio_stream)
        
        recording_thread.start()
        processing_thread.start()
        
        return self.transcription_queue
        
    def stop_listening(self) -> None:
        """Stop continuous listening mode"""
        self.is_listening = False
        
    def _continuous_recording(self) -> None:
        """Continuously record audio in a separate thread"""
        stream = self.audio_interface.open(
            format=self.audio_format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        try:
            while self.is_listening:
                # Read audio chunk
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                # Convert to numpy array
                audio_chunk = np.frombuffer(data, dtype=np.int16)
                # Add to queue for processing
                self.audio_queue.put(audio_chunk)
                
        finally:
            stream.stop_stream()
            stream.close()
            
    def _process_audio_stream(self) -> None:
        """Process audio stream in real-time"""
        accumulated_chunks: List[np.ndarray] = []
        silence_threshold = 500  # Adjust based on your needs
        silence_duration = 0
        
        while self.is_listening:
            try:
                # Get audio chunk from queue
                audio_chunk = self.audio_queue.get(timeout=1)
                
                # Apply noise reduction
                cleaned_chunk = self.audio_processor.reduce_noise(audio_chunk)
                
                # Check if this is silence
                if np.max(np.abs(cleaned_chunk)) < silence_threshold:
                    silence_duration += len(cleaned_chunk) / self.sample_rate
                else:
                    silence_duration = 0
                
                accumulated_chunks.append(cleaned_chunk)
                
                # If we have enough audio or detected end of utterance
                if (len(accumulated_chunks) * self.chunk_size / self.sample_rate >= 2.0  # 2 seconds
                    or silence_duration >= 1):  
                    
                    # Combine chunks and transcribe
                    audio_data = np.concatenate(accumulated_chunks)
                    
                    if self.model:
                        # Save temporary file for Whisper
                        temp_file = Path("temp_audio") / f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                        wavfile.write(temp_file, self.sample_rate, audio_data)
                        
                        # Transcribe with Whisper
                        result = self.model.transcribe(str(temp_file))
                        text = result["text"].strip()
                        
                        # Clean up temporary file
                        temp_file.unlink()
                    else:
                        # Convert to audio data format for Google Speech Recognition
                        audio_data_bytes = audio_data.tobytes()
                        audio = sr.AudioData(
                            audio_data_bytes,
                            self.sample_rate,
                            self.audio_interface.get_sample_size(self.audio_format)
                        )
                        text = self.recognizer.recognize_google(audio)
                    
                    # Add transcription to queue if not empty
                    if text.strip():
                        self.transcription_queue.put(
                            self._format_input(text, input_type="speech")
                        )
                    
                    # Reset accumulated chunks
                    accumulated_chunks = []
                    silence_duration = 0
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing audio: {str(e)}")
                continue

    def get_speech_input(self, duration: int = 5) -> Dict:
        """Handle speech input using microphone (single recording)"""
        try:
            audio_file = self.record_audio(duration)
            if not audio_file:
                return self._format_input(error="Failed to record audio")

            # Read audio file
            sample_rate, audio_data = wavfile.read(audio_file)
            
            # Apply noise reduction
            cleaned_audio = self.audio_processor.reduce_noise(audio_data)
            
            # Save cleaned audio
            cleaned_file = Path(audio_file).parent / f"cleaned_{Path(audio_file).name}"
            wavfile.write(cleaned_file, sample_rate, cleaned_audio)

            if self.model:
                # Use Whisper for speech recognition
                result = self.model.transcribe(str(cleaned_file))
                text = result["text"].strip()
            else:
                # Use Google Speech Recognition
                with sr.AudioFile(str(cleaned_file)) as source:
                    audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio)

            # Clean up files
            Path(audio_file).unlink()
            cleaned_file.unlink()

            return self._format_input(text, input_type="speech")

        except Exception as e:
            return self._format_input(
                error=f"Error processing speech input: {str(e)}"
            )

    def get_location(self) -> Optional[Dict]:
        """Get current location information"""
        try:
            # For demo purposes, you might want to replace this with actual GPS coordinates
            # This is a placeholder implementation
            location = {
                "coordinates": {"latitude": 0.0, "longitude": 0.0},
                "place": "unknown"
            }
            
            # In a real implementation, you would use GPS or IP-based location:
            # import geocoder
            # g = geocoder.ip('me')
            # location["coordinates"] = {"latitude": g.lat, "longitude": g.lng}
            # location["place"] = self.geolocator.reverse(f"{g.lat}, {g.lng}").address

            return location
        except Exception as e:
            print(f"Error getting location: {str(e)}")
            return None

    def get_environment_data(self) -> Dict:
        """Collect environmental data"""
        env_data = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.system(),
            "location": self.get_location(),
            "time_of_day": datetime.now().hour
        }
        return env_data

    def _format_input(
        self, 
        text: str = "", 
        input_type: str = "text",
        error: Optional[str] = None
    ) -> Dict:
        """Format input data into standardized JSON object"""
        return {
            "input": {
                "text": text,
                "type": input_type,
                "timestamp": datetime.now().isoformat(),
                "error": error
            },
            "environment": self.get_environment_data()
        }

    def process_input(self, input_type: str = "text", **kwargs) -> Dict:
        """
        Main method to handle all types of input
        Args:
            input_type: Type of input to process ("text", "speech", or "both")
            **kwargs: Additional arguments for specific input types
        """
        if input_type == "text":
            return self.get_text_input(**kwargs)
        elif input_type == "speech":
            return self.get_speech_input(**kwargs)
        elif input_type == "both":
            # Get both text and speech input and combine them
            text_input = self.get_text_input(**kwargs)
            speech_input = self.get_speech_input(**kwargs)
            
            # Combine the inputs (prioritize non-error input)
            if not text_input.get("input", {}).get("error"):
                return text_input
            return speech_input
        else:
            return self._format_input(
                error=f"Invalid input type: {input_type}"
            )

    def process_speech(self, audio_file: str) -> Dict:
        """Process speech input with appropriate model"""
        if self.lightweight_mode:
            return self.model.transcribe(audio_file)
            
        try:
            if isinstance(self.model, StubWhisperModel):
                return self.model.transcribe(audio_file)
                
            # Use actual model
            if self.recognizer:
                with sr.AudioFile(audio_file) as source:
                    audio = self.recognizer.record(source)
                    text = self.recognizer.recognize_google(audio)
                    return {"text": text}
            else:
                return {"text": "", "error": "Speech recognition unavailable"}
                
        except Exception as e:
            return {"text": "", "error": str(e)}

# Example usage
if __name__ == "__main__":
    # Initialize the input module
    input_module = InputModule(use_whisper=True)
    
    # Example 1: Get text input
    text_result = input_module.process_input(input_type="text")
    print("\nText Input Result:")
    print(json.dumps(text_result, indent=2))
    
    # Example 2: Get speech input
    speech_result = input_module.process_input(input_type="speech", duration=5)
    print("\nSpeech Input Result:")
    print(json.dumps(speech_result, indent=2))

