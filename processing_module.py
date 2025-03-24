from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime
import json
import spacy
from spacy.tokens import Doc
import re
import logging
from stub_models import StubSpacyModel, StubGPT2Model

class IntentAnalyzer:
    """Analyzes user intent and extracts entities from text"""
    
    def __init__(self):
        """Initialize the intent analyzer with spaCy"""
        try:
            self.nlp = spacy.load("en_core_web_sm")
            self.logger = logging.getLogger(__name__)
            
            # Define intent patterns
            self.intent_patterns = {
                "request": [
                    r"(?i)can you|could you|please|help|would you",
                    r"(?i)^(show|tell|give|find|schedule)",
                    r"(?i)i need|i want|i would like"
                ],
                "question": [
                    r"(?i)^(what|when|where|who|why|how)",
                    r"(?i)\?$",
                    r"(?i)do you know|can you tell"
                ],
                "inform": [
                    r"(?i)^(i am|i'm|i have|i've)",
                    r"(?i)just wanted to|letting you know",
                    r"(?i)^(yes|no|maybe|okay|sure)"
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Failed to initialize spaCy: {str(e)}")
            self.nlp = None

    def detect_intent(self, text: str) -> str:
        """
        Detect the primary intent of the input text
        
        Args:
            text: Input text to analyze
            
        Returns:
            Intent label ("request", "question", "inform", or "unknown")
        """
        # Default intent
        intent = "unknown"
        max_matches = 0
        
        # Check each intent pattern
        for intent_type, patterns in self.intent_patterns.items():
            matches = sum(1 for pattern in patterns if re.search(pattern, text))
            if matches > max_matches:
                max_matches = matches
                intent = intent_type
                
        return intent

    def extract_entities(self, doc: Doc) -> List[Dict]:
        """
        Extract named entities from spaCy Doc
        
        Args:
            doc: spaCy Doc object
            
        Returns:
            List of entity dictionaries
        """
        entities = []
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "type": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char
            })
        return entities

    def extract_time_expressions(self, doc: Doc) -> List[Dict]:
        """
        Extract time-related expressions
        
        Args:
            doc: spaCy Doc object
            
        Returns:
            List of time expression dictionaries
        """
        time_expressions = []
        for token in doc:
            if token.like_num and any(temp in token.nbor().text.lower() 
                                    for temp in ["am", "pm", "hour", "minute"]):
                time_expressions.append({
                    "text": f"{token.text} {token.nbor().text}",
                    "type": "TIME"
                })
        return time_expressions

    def analyze_intent_and_entities(self, text: str) -> Dict:
        """
        Analyze text for intent and entities
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dictionary containing intent and entities
        """
        if not self.nlp:
            return {
                "intent": "unknown",
                "entities": [],
                "time_expressions": [],
                "error": "NLP engine not available"
            }
            
        try:
            # Process text with spaCy
            doc = self.nlp(text)
            
            # Detect intent
            intent = self.detect_intent(text)
            
            # Extract entities and time expressions
            entities = self.extract_entities(doc)
            time_expressions = self.extract_time_expressions(doc)
            
            # Extract additional insights
            analysis = {
                "intent": intent,
                "entities": entities,
                "time_expressions": time_expressions,
                "sentiment": self.analyze_sentiment(doc),
                "urgency": self.detect_urgency(text),
                "timestamp": datetime.now().isoformat()
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error in intent analysis: {str(e)}")
            return {
                "intent": "unknown",
                "entities": [],
                "time_expressions": [],
                "error": str(e)
            }

    def analyze_sentiment(self, doc: Doc) -> str:
        """
        Basic sentiment analysis using spaCy
        
        Args:
            doc: spaCy Doc object
            
        Returns:
            Sentiment label ("positive", "negative", or "neutral")
        """
        # Simple rule-based sentiment analysis
        positive_tokens = sum(1 for token in doc 
                            if token.pos_ == "ADJ" and token.is_stop == False)
        negative_tokens = sum(1 for token in doc 
                            if token.pos_ == "ADJ" and token.is_stop == False 
                            and any(neg in token.text.lower() 
                                   for neg in ["not", "n't", "never"]))
        
        if positive_tokens > negative_tokens:
            return "positive"
        elif negative_tokens > positive_tokens:
            return "negative"
        return "neutral"

    def detect_urgency(self, text: str) -> str:
        """
        Detect urgency level in text
        
        Args:
            text: Input text
            
        Returns:
            Urgency level ("high", "medium", or "low")
        """
        urgent_patterns = [
            r"(?i)urgent|asap|emergency|immediately|right now",
            r"(?i)as soon as possible|critical|crucial"
        ]
        
        medium_patterns = [
            r"(?i)soon|today|tomorrow|this week",
            r"(?i)need.*(by|before)"
        ]
        
        if any(re.search(pattern, text) for pattern in urgent_patterns):
            return "high"
        elif any(re.search(pattern, text) for pattern in medium_patterns):
            return "medium"
        return "low"

class ProcessingModule:
    """Handles processing pipeline and data formatting"""
    
    def __init__(self, aac_system, lightweight_mode: bool = False):
        """
        Initialize processing module
        
        Args:
            aac_system: Instance of AACSystem
            lightweight_mode: If True, use stub models for offline operation
        """
        self.aac_system = aac_system
        self.lightweight_mode = lightweight_mode
        
        # Initialize NLP components
        if lightweight_mode:
            self.nlp = StubSpacyModel()
            self.text_generator = StubGPT2Model()
            print("⚠️ Running in lightweight mode - using simplified models")
        else:
            try:
                import spacy
                self.nlp = spacy.load("en_core_web_sm")
                # Assume text_generator is initialized in AACSystem
                self.text_generator = None
            except Exception as e:
                print(f"⚠️ Error initializing NLP: {str(e)}")
                self.nlp = StubSpacyModel()
                self.text_generator = StubGPT2Model()

    def validate_input(self, input_data: Dict) -> Optional[str]:
        """
        Validate the input data structure
        
        Args:
            input_data: Dictionary containing input data
            
        Returns:
            Error message if validation fails, None if successful
        """
        if not isinstance(input_data, dict):
            return "Input must be a dictionary"
            
        required_fields = ["input", "environment"]
        for field in required_fields:
            if field not in input_data:
                return f"Missing required field: {field}"
                
        if input_data["input"].get("type") not in ["text", "speech"]:
            return f"Unsupported input type: {input_data['input'].get('type')}"
            
        return None

    def format_input(self, input_data: Dict) -> Dict:
        """
        Format raw input data into standardized structure
        
        Args:
            input_data: Raw input dictionary
            
        Returns:
            Formatted input dictionary
        """
        return {
            "input": {
                "type": input_data.get("input", {}).get("type", "text"),
                "text": input_data.get("input", {}).get("text", ""),
                "timestamp": datetime.now().isoformat(),
                "metadata": input_data.get("input", {}).get("metadata", {})
            },
            "environment": input_data.get("environment", {
                "location": None,
                "time": datetime.now().hour
            })
        }

    def handle_input(self, input_data: Dict) -> Dict:
        """Process input data through pipeline"""
        try:
            # Validate input
            error = self.validate_input(input_data)
            if error:
                return {
                    "status": "error",
                    "message": error,
                    "timestamp": datetime.now().isoformat()
                }

            # Extract text
            text = input_data.get("input", {}).get("text", "")

            intent_analyzer = IntentAnalyzer()
            analysis = intent_analyzer.analyze_intent_and_entities(text)


            # Generate predictions
            if self.lightweight_mode:
                predictions = self.text_generator.generate(num_return_sequences=3)
            elif self.aac_system.text_generator is None or self.aac_system.tokenizer is None:
                predictions = []
            else:
                predictions = self.aac_system.generate_predictions(text)

            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "input": {
                        "text": text,
                        "type": input_data.get("input", {}).get("type", "text"),
                        "timestamp": datetime.now().isoformat()
                    },
                    "analysis": analysis,
                    "predictions": predictions,
                    "mode": "lightweight" if self.lightweight_mode else "full"
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Processing error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def _lightweight_analysis(self, text: str) -> Dict:
        """Perform simplified analysis for lightweight mode"""
        return {
            "intent": "unknown",
            "entities": [],
            "sentiment": "neutral",
            "urgency": "low"
        }

    def _full_analysis(self, text: str) -> Dict:
        return self.aac_system.context_manager.get_context_confidence(text)


    def get_processing_status(self) -> Dict:
        """
        Get current status of the processing module
        
        Returns:
            Dictionary containing module status information
        """
        return {
            "status": "active",
            "supported_input_types": ["text", "speech"],
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    from input_module import InputModule
    from aac_system import AACSystem
    import json

    def run_end_to_end_test():
        """Run end-to-end test of the complete processing pipeline"""
        print("\n🔄 Running end-to-end AAC system test...")
        
        try:
            # Initialize components
            print("\n1️⃣ Initializing systems...")
            aac_system = AACSystem()
            input_module = InputModule(use_whisper=True)
            processor = ProcessingModule(aac_system)
            
            # Get input from user
            print("\n2️⃣ Recording speech input (5 seconds)...")
            input_result = input_module.process_input(input_type="speech", duration=5)
            
            if input_result.get("input", {}).get("error"):
                print(f"❌ Error getting input: {input_result['input']['error']}")
                return
                
            # Format input for processing
            formatted_input = {
                "input": {
                    "text": input_result["input"]["text"],
                    "type": "speech",
                    "metadata": {
                        "timestamp": input_result["input"]["timestamp"]
                    }
                },
                "environment": input_result["environment"]
            }
            
            # Process through processing module
            print("\n3️⃣ Processing input through AAC system...")
            result = processor.handle_input(formatted_input)
            
            # Print results
            print("\n4️⃣ Processing Results:")
            print("=" * 50)
            print("📥 Input Text:", result["data"]["input"]["text"])
            print("🔍 Detected Context:", result["data"]["analysis"]["context"])
            
            if result["data"]["analysis"].get("entities"):
                print("\n🏷️ Detected Entities:")
                for entity in result["data"]["analysis"]["entities"]:
                    print(f"  • {entity['text']} ({entity['type']})")
            
            print("\n💭 Generated Predictions:")
            for i, pred in enumerate(result["data"]["predictions"], 1):
                print(f"  {i}. {pred}")
            
            print("\n📋 Complete JSON Output:")
            print(json.dumps(result, indent=2))
            
            print("\n✅ End-to-end test completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Error during end-to-end test: {str(e)}")

    # Run the test
    run_end_to_end_test()

# Example usage:
"""
from aac_system import AACSystem

# Initialize the system
aac = AACSystem()
processor = ProcessingModule(aac)

# Example input data
input_data = {
    "type": "text",
    "content": "John from Microsoft wants to meet Sarah at Central Park tomorrow",
    "metadata": {
        "user_id": "12345",
        "device_type": "mobile"
    },
    "environment": {
        "location": "office",
        "time": 14
    }
}

# Process the input
result = processor.handle_input(input_data)

# Print the result
print(json.dumps(result, indent=2))

# Expected output structure:
{
    "status": "success",
    "timestamp": "2024-01-20T14:30:00.123456",
    "data": {
        "input": {
            "type": "text",
            "text": "John from Microsoft wants to meet Sarah at Central Park tomorrow",
            "timestamp": "2024-01-20T14:30:00.123456"
        },
        "environment": {
            "location": "office",
            "time": 14
        },
        "output": {
            "context": "work",
            "formality_level": "high",
            "entities": [
                {"text": "John", "type": "PERSON"},
                {"text": "Microsoft", "type": "ORG"},
                {"text": "Sarah", "type": "PERSON"},
                {"text": "Central Park", "type": "GPE"}
            ],
            "predictions": [
                "I'll help schedule the meeting with John and Sarah.",
                "Would you like me to send calendar invites?",
                "What time works best for the meeting?"
            ]
        }
    }
}
"""

# Test the intent analyzer
analyzer = IntentAnalyzer()

test_inputs = [
    "Can you help me schedule a meeting with John tomorrow?",
    "What time is the presentation?",
    "I'm running late for the meeting.",
    "Please send the report ASAP.",
    "I need to meet Sarah at Central Park at 3pm."
]

print("\n🧪 Testing Intent Analysis:")
for text in test_inputs:
    analysis = analyzer.analyze_intent_and_entities(text)
    print(f"\n📝 Input: {text}")
    print(f"🎯 Intent: {analysis['intent']}")
    print(f"🏷️ Entities: {analysis['entities']}")
    print(f"⏰ Time Expressions: {analysis['time_expressions']}")
    print(f"😊 Sentiment: {analysis['sentiment']}")
    print(f"🚨 Urgency: {analysis['urgency']}") 