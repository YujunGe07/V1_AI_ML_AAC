import unittest
from processing_module import ProcessingModule
from aac_system import AACSystem
from datetime import datetime
from input_module import InputModule

class TestProcessingModule(unittest.TestCase):
    def setUp(self):
        self.aac = AACSystem()
        self.processor = ProcessingModule(self.aac)

    def test_input_validation(self):
        # Test invalid input
        invalid_input = {"type": "invalid"}
        result = self.processor.handle_input(invalid_input)
        self.assertEqual(result["status"], "error")

        # Test valid input
        valid_input = {
            "type": "text",
            "content": "Hello world"
        }
        result = self.processor.handle_input(valid_input)
        self.assertEqual(result["status"], "success")

    def test_entity_extraction(self):
        input_data = {
            "type": "text",
            "content": "John from Microsoft"
        }
        result = self.processor.handle_input(input_data)
        entities = result["data"]["output"]["entities"]
        self.assertTrue(any(e["text"] == "John" for e in entities))
        self.assertTrue(any(e["text"] == "Microsoft" for e in entities))

    def test_handle_input_processing(self):
        """Test the complete input handling pipeline"""
        input_data = {
            "input": {
                "text": "John from Microsoft wants to meet Sarah at Central Park tomorrow",
                "type": "text",
                "metadata": {"user_id": "123"}
            },
            "environment": {
                "location": {
                    "place": "office",
                    "coordinates": {"lat": 40.7128, "lng": -74.0060}
                },
                "time": 14
            }
        }
        
        result = self.processor.handle_input(input_data)
        
        # Check basic structure
        self.assertEqual(result["status"], "success")
        self.assertIn("timestamp", result)
        self.assertIn("data", result)
        
        # Check data contents
        data = result["data"]
        self.assertEqual(data["input"]["text"], input_data["input"]["text"])
        self.assertEqual(data["input"]["type"], "text")
        self.assertIn("context", data)
        self.assertIn("predictions", data)
        self.assertIn("entities", data)
        
        # Check entities extraction
        entities = data["entities"]
        self.assertTrue(any(e["text"] == "John" for e in entities))
        self.assertTrue(any(e["text"] == "Microsoft" for e in entities))
        self.assertTrue(any(e["text"] == "Sarah" for e in entities))
        self.assertTrue(any(e["text"] == "Central Park" for e in entities))

    def test_handle_input_missing_data(self):
        """Test handling of missing or incomplete input data"""
        # Test with minimal input
        minimal_input = {
            "input": {
                "text": "Hello world"
            },
            "environment": {}
        }
        
        result = self.processor.handle_input(minimal_input)
        self.assertEqual(result["status"], "success")
        self.assertIn("data", result)
        
        # Test with missing environment
        no_env_input = {
            "input": {
                "text": "Hello world",
                "type": "text"
            }
        }
        
        result = self.processor.handle_input(no_env_input)
        self.assertEqual(result["status"], "success")
        self.assertIsNone(
            result["data"]["environment"]["location"]
        )

    def test_handle_input_errors(self):
        """Test error handling in input processing"""
        # Test with invalid input type
        invalid_input = {
            "input": {
                "text": "Hello world",
                "type": "invalid_type"
            }
        }
        
        result = self.processor.handle_input(invalid_input)
        self.assertEqual(result["status"], "error")
        self.assertIn("message", result)

    def test_end_to_end_pipeline(self):
        """Test the complete processing pipeline from input to output"""
        # Initialize input module
        input_module = InputModule(use_whisper=True)
        
        # Get input (using text instead of speech for testing)
        test_text = "Let's schedule a meeting with John tomorrow"
        input_result = {
            "input": {
                "text": test_text,
                "type": "text",
                "timestamp": datetime.now().isoformat()
            },
            "environment": {
                "location": {"place": "office"},
                "time": 14
            }
        }
        
        # Process through processing module
        result = self.processor.handle_input(input_result)
        
        # Verify complete pipeline
        self.assertEqual(result["status"], "success")
        self.assertIn("data", result)
        self.assertEqual(result["data"]["input"]["text"], test_text)
        self.assertIn("context", result["data"])
        self.assertIn("predictions", result["data"])
        self.assertIn("entities", result["data"])
        
        # Verify entity extraction
        entities = result["data"]["entities"]
        self.assertTrue(any(e["text"] == "John" for e in entities))
        
        # Verify predictions
        self.assertTrue(len(result["data"]["predictions"]) > 0)

if __name__ == '__main__':
    unittest.main() 