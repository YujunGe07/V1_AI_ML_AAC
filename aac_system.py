import torch
from transformers import (
    GPT2LMHeadModel, 
    GPT2Tokenizer,
    DistilBertForSequenceClassification, 
    DistilBertTokenizer,
    pipeline
)
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from input_module import InputModule
from processing_module import ProcessingModule
import spacy
import pyttsx3
import threading
import json
from collections import deque, Counter
from output_postprocessing import postprocess_outputs
from stub_models import StubGPT2Model
import torch.nn.functional as F
from difflib import SequenceMatcher

class ContextManager:
    """Manages context detection and switching for the AAC system"""
    
    def __init__(self, model_path: str = "distilbert-base-uncased"):
        """
        Initialize the context manager with ML model
        
        Args:
            model_path: Path to pretrained or fine-tuned model
        """
        self.work_hours = range(9, 18)
        self.work_locations = ["office", "conference room", "meeting room"]
        self.context_history = deque(maxlen=5)
        
        # Initialize ML components
        try:
            self.tokenizer = DistilBertTokenizer.from_pretrained(model_path)
            self.model = DistilBertForSequenceClassification.from_pretrained(
                model_path,
                num_labels=3  # work, social, general
            )
            self.model.eval()  # Set to evaluation mode
            
            # Map numeric labels to context names
            self.label_map = {
                0: "work",
                1: "social",
                2: "general"
            }
            
            self.ml_available = True
            
        except Exception as e:
            print(f"⚠️ Error loading context classification model: {str(e)}")
            print("⚠️ Falling back to rule-based context detection")
            self.ml_available = False
        
        # Context vocabulary (existing code)
        self.context_vocabulary = {
            "work": {
                "common_phrases": [
                    "Could you please clarify",
                    "I'll follow up on that",
                    "Let's schedule a meeting",
                ],
                "formality_level": "high",
                "max_length": 15
            },
            "social": {
                "common_phrases": [
                    "How are you doing",
                    "Want to grab coffee",
                    "That sounds fun",
                ],
                "formality_level": "casual",
                "max_length": 25
            },
            "general": {
                "common_phrases": [
                    "I need help with",
                    "Could you please",
                    "Thank you",
                ],
                "formality_level": "medium",
                "max_length": 20
            }
        }

    def get_recent_context(self) -> Optional[str]:
        """
        Get the most frequent context from recent history
        
        Returns:
            Most frequent context if it appears at least 3 times, None otherwise
        """
        if not self.context_history:
            return None
            
        # Count context frequencies
        context_counts = Counter(self.context_history)
        most_common = context_counts.most_common(1)[0]
        
        # Return context only if it appears at least 3 times
        context, count = most_common
        return context if count >= 3 else None

    def add_to_history(self, context: str) -> None:
        """Add a context decision to history"""
        self.context_history.append(context)

    def predict_context_ml(self, text: str) -> Tuple[str, float]:
        """
        Predict context using ML model
        
        Args:
            text: Input text to classify
            
        Returns:
            Tuple of (predicted_context, confidence_score)
        """
        try:
            # Tokenize input
            inputs = self.tokenizer(
                text,
                truncation=True,
                padding=True,
                return_tensors="pt"
            )
            
            # Get model prediction
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                
                # Apply softmax to get probabilities
                probs = F.softmax(logits, dim=1)
                
                # Get predicted label and confidence
                pred_label = torch.argmax(probs, dim=1).item()
                confidence = probs[0][pred_label].item()
                
                # Map numeric label to context name
                predicted_context = self.label_map[pred_label]
                
                return predicted_context, confidence
                
        except Exception as e:
            print(f"⚠️ Error in ML prediction: {str(e)}")
            return "general", 0.0

    def detect_context(self, text: str, location: Optional[str] = None) -> str:
        """
        Detect context using ML model, history, and rules
        
        Args:
            text: Input text to analyze
            location: Optional location information
            
        Returns:
            Detected context: "work", "social", or "general"
        """
        # Check recent history first (existing logic)
        recent_context = self.get_recent_context()
        if recent_context:
            self.add_to_history(recent_context)
            return recent_context
        
        # Use ML model if available
        if self.ml_available:
            predicted_context, confidence = self.predict_context_ml(text)
            
            # If confidence is high enough, use ML prediction
            if confidence > 0.7:  # Confidence threshold
                self.add_to_history(predicted_context)
                return predicted_context
        
        # Fall back to rule-based detection if ML fails or confidence is low
        if location and location.lower() in self.work_locations:
            context = "work"
        elif datetime.now().hour in self.work_hours:
            context = "work"
        else:
            context = "general"
        
        self.add_to_history(context)
        return context

    def get_context_confidence(self, text: str) -> Dict:
        """
        Get confidence scores for each context
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dictionary with confidence scores for each context
        """
        if not self.ml_available:
            return {
                "work": 0.0,
                "social": 0.0,
                "general": 1.0,
                "method": "fallback"
            }
            
        try:
            # Tokenize and get model predictions
            inputs = self.tokenizer(
                text,
                truncation=True,
                padding=True,
                return_tensors="pt"
            )
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = F.softmax(outputs.logits, dim=1)[0]
                
                return {
                    "work": probs[0].item(),
                    "social": probs[1].item(),
                    "general": probs[2].item(),
                    "method": "ml"
                }
                
        except Exception as e:
            print(f"⚠️ Error getting context confidence: {str(e)}")
            return {
                "work": 0.0,
                "social": 0.0,
                "general": 1.0,
                "method": "error"
            }

class UserMemoryManager:
    """Manages user interaction history for context-aware suggestions"""
    
    def __init__(self, max_entries: int = 50):
        """
        Initialize memory manager
        
        Args:
            max_entries: Maximum number of entries to store
        """
        self.memory = deque(maxlen=max_entries)
        self.similarity_threshold = 0.3  # Threshold for finding similar inputs

    def add_interaction(
        self, 
        text: str, 
        context: str,
        entities: List[Dict] = None,
        predictions: List[str] = None
    ) -> None:
        """
        Add new interaction to memory
        
        Args:
            text: User input text
            context: Detected context
            entities: Optional list of extracted entities
            predictions: Optional list of generated predictions
        """
        self.memory.append({
            "text": text,
            "context": context,
            "entities": entities or [],
            "predictions": predictions or [],
            "timestamp": datetime.now().isoformat(),
            "used_count": 0  # Track how often this entry influences predictions
        })

    def get_recent_contextual_inputs(
        self, 
        context: str, 
        limit: int = 5,
        max_age_hours: int = 24
    ) -> List[Dict]:
        """
        Get recent inputs with matching context
        
        Args:
            context: Context to match
            limit: Maximum number of entries to return
            max_age_hours: Maximum age of entries to consider
            
        Returns:
            List of relevant memory entries
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        # Filter and sort relevant entries
        relevant_entries = [
            entry for entry in self.memory
            if (entry["context"] == context and
                datetime.fromisoformat(entry["timestamp"]) > cutoff_time)
        ]
        
        # Sort by recency
        relevant_entries.sort(
            key=lambda x: datetime.fromisoformat(x["timestamp"]),
            reverse=True
        )
        
        return relevant_entries[:limit]

    def find_similar_interactions(
        self, 
        text: str, 
        context: str = None,
        limit: int = 3
    ) -> List[Dict]:
        """
        Find similar past interactions
        
        Args:
            text: Input text to compare
            context: Optional context to filter by
            limit: Maximum number of results
            
        Returns:
            List of similar interactions
        """
        similar_entries = []
        
        for entry in self.memory:
            # Skip if context doesn't match (when specified)
            if context and entry["context"] != context:
                continue
                
            # Calculate similarity
            similarity = SequenceMatcher(
                None,
                text.lower(),
                entry["text"].lower()
            ).ratio()
            
            if similarity > self.similarity_threshold:
                similar_entries.append({
                    **entry,
                    "similarity_score": similarity
                })
        
        # Sort by similarity and recency
        similar_entries.sort(
            key=lambda x: (
                x["similarity_score"],
                datetime.fromisoformat(x["timestamp"])
            ),
            reverse=True
        )
        
        return similar_entries[:limit]

    def get_context_history(self, context: str) -> Dict:
        """
        Get statistics about a specific context
        
        Args:
            context: Context to analyze
            
        Returns:
            Dictionary with context statistics
        """
        context_entries = [e for e in self.memory if e["context"] == context]
        
        if not context_entries:
            return {"count": 0}
            
        return {
            "count": len(context_entries),
            "last_used": max(
                datetime.fromisoformat(e["timestamp"]) 
                for e in context_entries
            ).isoformat(),
            "common_entities": self._get_common_entities(context_entries),
            "frequent_patterns": self._get_frequent_patterns(context_entries)
        }

    def _get_common_entities(self, entries: List[Dict]) -> List[Dict]:
        """Extract commonly mentioned entities from entries"""
        entity_counts = {}
        
        for entry in entries:
            for entity in entry.get("entities", []):
                key = (entity["text"], entity["type"])
                entity_counts[key] = entity_counts.get(key, 0) + 1
        
        # Return most common entities
        return [
            {"text": text, "type": type_, "count": count}
            for (text, type_), count in sorted(
                entity_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        ]

    def _get_frequent_patterns(self, entries: List[Dict]) -> List[str]:
        """Extract frequent text patterns from entries"""
        # Simple implementation - could be enhanced with proper pattern mining
        return [entry["text"] for entry in entries[:3]]

class AACSystem:
    def __init__(self, context_model_path: str = "distilbert-base-uncased", lightweight_mode: bool = False):
        """Initialize AAC system with ML context detection"""
        self.lightweight_mode = lightweight_mode
        self.tts_engine = pyttsx3.init()
        self.nlp = spacy.load("en_core_web_sm")

        
        # Initialize components
        self.input_module = InputModule(lightweight_mode=lightweight_mode)
        self.context_manager = ContextManager(model_path=context_model_path)
        self.processor = ProcessingModule(self, lightweight_mode=lightweight_mode)
        
        if lightweight_mode:
            self.text_generator = StubGPT2Model()
            self.tokenizer = None
            print("⚠️ Running AAC system in lightweight mode")
        else:
            try:
                self.gen_model = GPT2LMHeadModel.from_pretrained("distilgpt2")
                self.gen_tokenizer = GPT2Tokenizer.from_pretrained("distilgpt2")
                self.text_generator = self.gen_model
                self.tokenizer = self.gen_tokenizer

            except Exception as e:
                print(f"⚠️ Error loading models: {str(e)}")
                self.gen_model = StubGPT2Model()
                self.gen_tokenizer = None
                self.text_generator = self.gen_model
                self.tokenizer = self.gen_tokenizer


        self.memory_manager = UserMemoryManager()

    def process_user_input(self, input_type: str = "text", **kwargs) -> Dict:
        """
        Process user input through the complete AAC pipeline
        
        Args:
            input_type: Type of input ("text" or "speech")
            **kwargs: Additional arguments for input processing
            
        Returns:
            Dictionary containing processed and formatted results
        """
        try:
            # Get input from the input module
            input_data = self.input_module.process_input(input_type, **kwargs)
            
            if input_data["input"].get("error"):
                return input_data
            
            # Format input for processing
            formatted_input = {
                "input": {
                    "text": input_data["input"]["text"],
                    "type": input_type,
                    "metadata": {
                        "timestamp": input_data["input"]["timestamp"]
                    }
                },
                "environment": input_data["environment"]
            }
            
            # Process through processing module
            result = self.processor.handle_input(formatted_input)
            
            # Speak the first prediction if available
            if (result["status"] == "success" and 
                result["data"]["predictions"] and 
                len(result["data"]["predictions"]) > 0):
                self.speak_output(result["data"]["predictions"][0], block=False)
            
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error in processing pipeline: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def speak_output(self, text: str, block: bool = False) -> None:
        """
        Convert text to speech and play it
        
        Args:
            text: Text to be spoken
            block: If True, wait for speech to complete
        """
        if not self.tts_engine:
            return

        def speak():
            try:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e:
                print(f"Error in speech synthesis: {str(e)}")

        if block:
            speak()
        else:
            threading.Thread(target=speak, daemon=True).start()

    def set_manual_context(self, context: str):
        """Manually override automatic context detection"""
        if context in self.context_manager.context_vocabulary:
            self.manual_context = context
            self.current_context = context

    def generate_predictions(
            
        self, 
        input_text: str,
        location: Optional[str] = None,
        num_return_sequences: int = 3,
        temperature: float = 0.7,
        top_p: float = 0.9,
        use_memory: bool = True
    ) -> List[str]:
        """Generate context-aware text predictions using memory"""
        context = self.context_manager.detect_context(input_text, location)
        context_settings = self.context_manager.context_vocabulary[context]
        print("⚙️ generate_predictions() was called")
        # Get similar past interactions
        if use_memory:
            similar_interactions = self.memory_manager.find_similar_interactions(
                input_text,
                context=context
            )
            
            # Enhance input with relevant history
            if similar_interactions:
                # Add most relevant past interaction as context
                enhanced_input = (
                    f"Previous: {similar_interactions[0]['text']}\n"
                    f"Current: {input_text}"
                )
            else:
                enhanced_input = input_text
        else:
            enhanced_input = input_text
        
        # Generate predictions
        inputs = self.gen_tokenizer.encode(enhanced_input, return_tensors="pt")
        attention_mask = torch.ones(inputs.shape, dtype=torch.long)

        outputs = self.gen_model.generate(
            inputs,
            attention_mask=attention_mask,
            max_length=context_settings["max_length"],
            num_return_sequences=num_return_sequences,
            no_repeat_ngram_size=2,
            early_stopping=True,
            num_beams=3,
            pad_token_id=self.gen_tokenizer.eos_token_id,
            temperature=temperature,
            top_p=top_p,
            do_sample=True
        )

        predictions = [
            self.gen_tokenizer.decode(
                output, 
                skip_special_tokens=True, 
                clean_up_tokenization_spaces=True
            ) for output in outputs
        ]
        
        # Store interaction in memory
        self.memory_manager.add_interaction(
            text=input_text,
            context=context,
            entities=self.extract_entities(input_text),
            predictions=predictions
        )
        
        print("🧪 Generated predictions:", predictions)
        return predictions

    def extract_entities(self, text: str) -> List[Dict[str, str]]:
        """
        Extract named entities from input text.
        
        Args:
            text: Input text to process
            
        Returns:
            List of dictionaries containing entity text and label
        """
        doc = self.nlp(text)
        # Extract relevant entity types (PERSON, ORG, GPE)
        entities = [
            {
                "text": ent.text,
                "type": ent.label_
            }
            for ent in doc.ents
            if ent.label_ in ["PERSON", "ORG", "GPE"]
        ]
        return entities

    def process_input(self, text: str, location: Optional[str] = None) -> Dict:
        """Process input text with memory-enhanced predictions"""
        result = super().process_input(text, location)
        
        # Add memory-related information to output
        context = result["context"]["label"]
        context_history = self.memory_manager.get_context_history(context)
        
        result["memory"] = {
            "context_history": context_history,
            "similar_interactions": self.memory_manager.find_similar_interactions(text)
        }
        
        return result

    def change_voice(self, gender: str = "female") -> bool:
        """
        Change the TTS voice based on gender preference
        
        Args:
            gender: "male" or "female"
            
        Returns:
            bool: True if voice was changed successfully
        """
        if not self.tts_engine:
            return False

        try:
            voices = self.tts_engine.getProperty('voices')
            if not voices:
                return False

            # Usually index 0 is male, 1 is female
            voice_idx = 1 if gender.lower() == "female" else 0
            if voice_idx < len(voices):
                self.tts_engine.setProperty('voice', voices[voice_idx].id)
                return True
            return False
        except Exception:
            return False

    def adjust_speech(self, rate: Optional[int] = None, volume: Optional[float] = None) -> None:
        """
        Adjust speech properties
        
        Args:
            rate: Speaking rate (words per minute)
            volume: Volume level (0.0 to 1.0)
        """
        if not self.tts_engine:
            return

        if rate is not None:
            self.tts_engine.setProperty('rate', max(50, min(300, rate)))
        if volume is not None:
            self.tts_engine.setProperty('volume', max(0.0, min(1.0, volume)))

# Example usage:
if __name__ == "__main__":
    # Initialize the system
    aac = AACSystem()
    
    # Test with speech input
    print("\n🎤 Testing speech input...")
    speech_result = aac.process_user_input(
        input_type="speech",
        duration=5
    )
    print("\n📋 Speech Input Results:")
    print(json.dumps(speech_result, indent=2))
    
    # Test with text input
    print("\n⌨️ Testing text input...")
    text_result = aac.process_user_input(
        input_type="text",
        text="Let's schedule a meeting with John at Microsoft tomorrow"
    )
    print("\n📋 Text Input Results:")
    print(json.dumps(text_result, indent=2))

# Add tests to verify the context memory functionality
def test_context_memory():
    """Test the context memory functionality"""
    context_manager = ContextManager()
    
    # Test sequence of contexts
    contexts = ["work", "work", "work", "social", "work"]
    
    print("\n🧪 Testing Context Memory")
    print("Adding sequence:", contexts)
    
    for ctx in contexts:
        context_manager.add_to_history(ctx)
        
    recent = context_manager.get_recent_context()
    print(f"Most frequent recent context: {recent}")
    print(f"Full history: {list(context_manager.context_history)}")
    
    # Test context detection with history
    new_context = context_manager.detect_context(
        "Let's have a meeting", 
        location="office"
    )
    print(f"New detected context: {new_context}")
    print(f"Updated history: {list(context_manager.context_history)}")

def test_memory_system():
    """Test the memory system functionality"""
    aac = AACSystem()
    
    # Test sequence of inputs
    test_inputs = [
        "Schedule a meeting with John",
        "Send the report to Sarah",
        "Let's have coffee tomorrow",
        "Schedule another meeting with John",
    ]
    
    print("\n🧪 Testing Memory System")
    
    for text in test_inputs:
        result = aac.process_input(text)
        print(f"\n📝 Input: {text}")
        print(f"🔍 Context: {result['context']['label']}")
        print(f"💭 Predictions: {result['predictions']}")
        print(f"🧠 Similar past interactions: {len(result['memory']['similar_interactions'])}")

if __name__ == "__main__":
    test_context_memory()
    test_memory_system()
