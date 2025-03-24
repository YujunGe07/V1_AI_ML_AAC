from typing import List, Set, Tuple, Dict, Optional, Callable
import re
from difflib import SequenceMatcher
import string
from dataclasses import dataclass
import logging
from enum import Enum
import json
from datetime import datetime

@dataclass
class PostprocessingConfig:
    """Configuration for output postprocessing"""
    min_length: int = 10  # Minimum character length
    max_length: int = 100  # Maximum character length
    similarity_threshold: float = 0.85  # Threshold for duplicate detection
    min_unique_ratio: float = 0.5  # Minimum ratio of unique words
    max_outputs: int = 3  # Maximum number of outputs to return

class OutputMode(Enum):
    """Supported output modes"""
    TEXT = "text"
    SPEECH = "speech"
    BOTH = "both"
    CUSTOM_PLUGIN = "custom_plugin"

@dataclass
class OutputConfig:
    """Configuration for output processing"""
    mode: OutputMode = OutputMode.BOTH
    speech_enabled: bool = True
    text_format: str = "simple"  # "simple" or "detailed"
    plugin_config: Optional[Dict] = None

class OutputPostprocessor:
    """Handles postprocessing of generated text predictions"""
    
    def __init__(self, config: PostprocessingConfig = None):
        """
        Initialize postprocessor with configuration
        
        Args:
            config: Optional custom configuration
        """
        self.config = config or PostprocessingConfig()
        self.logger = logging.getLogger(__name__)

    def clean_text(self, text: str) -> str:
        """
        Clean and format text
        
        Args:
            text: Input text to clean
            
        Returns:
            Cleaned and formatted text
        """
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Ensure proper capitalization
        text = text.capitalize()
        
        # Ensure proper ending punctuation
        if text and text[-1] not in '.!?':
            text += '.'
            
        return text.strip()

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity ratio between two texts
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity ratio between 0 and 1
        """
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def is_duplicate(self, text: str, existing_texts: Set[str]) -> bool:
        """
        Check if text is too similar to existing texts
        
        Args:
            text: Text to check
            existing_texts: Set of existing texts to compare against
            
        Returns:
            True if text is a duplicate
        """
        return any(
            self.calculate_similarity(text, existing) >= self.config.similarity_threshold
            for existing in existing_texts
        )

    def calculate_uniqueness_ratio(self, text: str) -> float:
        """
        Calculate ratio of unique words to total words
        
        Args:
            text: Text to analyze
            
        Returns:
            Ratio of unique words
        """
        words = text.lower().split()
        return len(set(words)) / len(words) if words else 0

    def score_prediction(self, text: str, original_input: str = None) -> float:
        """
        Score a prediction based on various factors
        
        Args:
            text: Text to score
            original_input: Optional original input for relevance scoring
            
        Returns:
            Score between 0 and 1
        """
        # Base score starts at 1.0
        score = 1.0
        
        # Penalize based on length
        ideal_length = (self.config.min_length + self.config.max_length) / 2
        length_penalty = abs(len(text) - ideal_length) / ideal_length
        score -= length_penalty * 0.3
        
        # Consider uniqueness ratio
        uniqueness = self.calculate_uniqueness_ratio(text)
        if uniqueness < self.config.min_unique_ratio:
            score -= (self.config.min_unique_ratio - uniqueness)
        
        # Consider relevance to original input if provided
        if original_input:
            relevance = self.calculate_similarity(text, original_input)
            score += relevance * 0.2
            
        return max(0.0, min(1.0, score))

    def filter_predictions(
        self, 
        predictions: List[str], 
        original_input: str = None
    ) -> List[Tuple[str, float]]:
        """
        Filter and score predictions
        
        Args:
            predictions: List of predictions to filter
            original_input: Optional original input for relevance scoring
            
        Returns:
            List of (prediction, score) tuples
        """
        filtered = []
        seen_texts = set()
        
        for pred in predictions:
            # Clean the text
            cleaned = self.clean_text(pred)
            
            # Skip if too short/long
            if not (self.config.min_length <= len(cleaned) <= self.config.max_length):
                continue
                
            # Skip if duplicate
            if self.is_duplicate(cleaned, seen_texts):
                continue
                
            # Calculate score
            score = self.score_prediction(cleaned, original_input)
            
            filtered.append((cleaned, score))
            seen_texts.add(cleaned)
            
        return filtered

    def postprocess_outputs(
        self, 
        predictions: List[str], 
        original_input: str = None
    ) -> List[str]:
        """
        Process and filter generated predictions
        
        Args:
            predictions: List of generated predictions
            original_input: Optional original input for context
            
        Returns:
            List of processed and filtered predictions
        """
        try:
            # Filter and score predictions
            scored_predictions = self.filter_predictions(predictions, original_input)
            
            # Sort by score
            sorted_predictions = sorted(
                scored_predictions, 
                key=lambda x: x[1], 
                reverse=True
            )
            
            # Take top N predictions
            return [pred for pred, _ in sorted_predictions[:self.config.max_outputs]]
            
        except Exception as e:
            self.logger.error(f"Error in postprocessing: {str(e)}")
            return predictions[:self.config.max_outputs]

def postprocess_outputs(
    predictions: List[str], 
    original_input: str = None,
    config: PostprocessingConfig = None
) -> List[str]:
    """
    Convenience function for one-off postprocessing
    
    Args:
        predictions: List of predictions to process
        original_input: Optional original input for context
        config: Optional custom configuration
        
    Returns:
        List of processed predictions
    """
    processor = OutputPostprocessor(config)
    return processor.postprocess_outputs(predictions, original_input)

class OutputChannelManager:
    """Manages different output channels for AAC system"""
    
    def __init__(
        self, 
        config: Optional[OutputConfig] = None,
        speech_engine = None,
        custom_plugin: Optional[Callable] = None
    ):
        """
        Initialize output channel manager
        
        Args:
            config: Output configuration
            speech_engine: TTS engine instance
            custom_plugin: Optional custom output handler
        """
        self.config = config or OutputConfig()
        self.speech_engine = speech_engine
        self.custom_plugin = custom_plugin
        self.output_history = []

    def process_output(
        self, 
        result: Dict,
        mode: Optional[OutputMode] = None
    ) -> Dict:
        """
        Process and present output through selected channels
        
        Args:
            result: Processing result dictionary
            mode: Optional override for output mode
            
        Returns:
            Dictionary with output status
        """
        try:
            # Use provided mode or default from config
            active_mode = mode or self.config.mode
            
            # Extract predictions
            predictions = result.get("data", {}).get("predictions", [])
            if not predictions:
                return self._format_error("No predictions available")

            # Process according to mode
            output_result = {
                "timestamp": datetime.now().isoformat(),
                "mode": active_mode.value,
                "status": "success"
            }

            if active_mode in [OutputMode.TEXT, OutputMode.BOTH]:
                text_output = self._handle_text_output(result)
                output_result["text_output"] = text_output

            if active_mode in [OutputMode.SPEECH, OutputMode.BOTH]:
                speech_output = self._handle_speech_output(predictions[0])
                output_result["speech_output"] = speech_output

            if active_mode == OutputMode.CUSTOM_PLUGIN:
                plugin_output = self._handle_plugin_output(result)
                output_result["plugin_output"] = plugin_output

            # Store in history
            self.output_history.append(output_result)
            
            return output_result

        except Exception as e:
            return self._format_error(f"Output processing error: {str(e)}")

    def _handle_text_output(self, result: Dict) -> Dict:
        """Format and present text output"""
        try:
            if self.config.text_format == "simple":
                # Simple format with just predictions
                output = {
                    "predictions": result.get("data", {}).get("predictions", [])
                }
            else:
                # Detailed format with context and analysis
                output = {
                    "predictions": result.get("data", {}).get("predictions", []),
                    "context": result.get("data", {}).get("context"),
                    "entities": result.get("data", {}).get("entities", []),
                    "analysis": result.get("data", {}).get("analysis", {})
                }

            # Print output
            self._print_formatted_output(output)
            
            return {
                "status": "success",
                "format": self.config.text_format,
                "content": output
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _handle_speech_output(self, text: str) -> Dict:
        """Handle speech output using TTS"""
        if not self.speech_engine or not self.config.speech_enabled:
            return {
                "status": "error",
                "message": "Speech output not available"
            }

        try:
            # Use speech engine to speak text
            self.speech_engine.speak(text, block=False)
            
            return {
                "status": "success",
                "text": text
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _handle_plugin_output(self, result: Dict) -> Dict:
        """Handle custom plugin output"""
        if not self.custom_plugin:
            return {
                "status": "error",
                "message": "No custom plugin configured"
            }

        try:
            # Call custom plugin with result
            plugin_result = self.custom_plugin(result)
            
            return {
                "status": "success",
                "plugin_result": plugin_result
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _print_formatted_output(self, output: Dict) -> None:
        """Print formatted output to console"""
        print("\n📝 AAC System Output:")
        
        if "predictions" in output:
            print("\n💭 Predictions:")
            for i, pred in enumerate(output["predictions"], 1):
                print(f"  {i}. {pred}")

        if "context" in output:
            print(f"\n🔍 Context: {output['context']}")

        if "entities" in output:
            print("\n🏷️ Entities:")
            for entity in output["entities"]:
                print(f"  • {entity['text']} ({entity['type']})")

    def _format_error(self, message: str) -> Dict:
        """Format error response"""
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "message": message
        }

    def update_config(self, **kwargs) -> None:
        """Update output configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def get_output_history(self, limit: int = 10) -> List[Dict]:
        """Get recent output history"""
        return self.output_history[-limit:]

# Example custom plugin
def example_plugin(result: Dict) -> Dict:
    """Example custom output plugin"""
    return {
        "type": "custom_display",
        "content": result.get("data", {}).get("predictions", []),
        "timestamp": datetime.now().isoformat()
    }

# Example usage and tests
if __name__ == "__main__":
    # Test data
    test_predictions = [
        "let's schedule a meeting",
        "Let's schedule a meeting!",  # Near duplicate
        "we should meet soon",
        "hello",  # Too short
        "I think we should definitely schedule some time to meet and discuss this important topic in detail",  # Too long
        "we could meet tomorrow",
    ]
    
    original_input = "When should we schedule our meeting?"
    
    # Test with default configuration
    print("\n🧪 Testing with default configuration:")
    results = postprocess_outputs(test_predictions, original_input)
    print("\nProcessed outputs:")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result}")
        
    # Test with custom configuration
    custom_config = PostprocessingConfig(
        min_length=5,
        max_length=50,
        similarity_threshold=0.9,
        max_outputs=2
    )
    
    print("\n🧪 Testing with custom configuration:")
    results = postprocess_outputs(test_predictions, original_input, custom_config)
    print("\nProcessed outputs:")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result}") 