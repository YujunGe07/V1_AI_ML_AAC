import unittest
from aac_system import AACSystem
import json

class TestAACSystem(unittest.TestCase):
    def setUp(self):
        self.aac = AACSystem(use_whisper=True)

    def test_complete_pipeline(self):
        """Test the complete AAC pipeline with text input"""
        result = self.aac.process_user_input(
            input_type="text",
            text="Schedule a meeting with John at Microsoft tomorrow"
        )
        
        # Check basic structure
        self.assertEqual(result["status"], "success")
        self.assertIn("data", result)
        
        # Check processing results
        data = result["data"]
        self.assertIn("input", data)
        self.assertIn("context", data)
        self.assertIn("predictions", data)
        self.assertIn("entities", data)
        
        # Check entity extraction
        entities = data["entities"]
        self.assertTrue(any(e["text"] == "John" for e in entities))
        self.assertTrue(any(e["text"] == "Microsoft" for e in entities))
        
        # Check predictions
        self.assertTrue(len(data["predictions"]) > 0)

    def test_error_handling(self):
        """Test error handling in the pipeline"""
        # Test with invalid input type
        result = self.aac.process_user_input(input_type="invalid")
        self.assertEqual(result["status"], "error")
        self.assertIn("message", result)

if __name__ == '__main__':
    unittest.main() 