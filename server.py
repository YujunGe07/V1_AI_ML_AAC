from flask import Flask, request, jsonify
from flask_cors import CORS
from aac_system import AACSystem
from output_postprocessing import OutputChannelManager, OutputConfig, OutputMode
from typing import Dict
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

class AACServer:
    """Server wrapper for AAC system"""
    
    def __init__(self):
        """Initialize AAC system and output manager"""
        try:
            # Initialize core AAC system
            self.aac = AACSystem()
            
            # Initialize output manager for API responses
            output_config = OutputConfig(
                mode=OutputMode.TEXT,  # API only needs text output
                text_format="detailed"  # Include full analysis
            )
            self.output_manager = OutputChannelManager(
                config=output_config
            )
            
            logger.info("AAC System initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AAC system: {str(e)}")
            raise

    def process_input(self, data: Dict) -> Dict:
        """
        Process input data through AAC system
        
        Args:
            data: Dictionary containing input data
            
        Returns:
            Processed results as dictionary
        """
        try:
            # Extract input parameters
            input_text = data.get("text", "")
            input_type = data.get("type", "text")
            location = data.get("location")
            
            # Validate input
            if not input_text:
                return {
                    "status": "error",
                    "message": "No input text provided",
                    "timestamp": datetime.now().isoformat()
                }

            # Process through AAC system
            result = self.aac.process_user_input(
                input_type=input_type,
                text=input_text,
                location=location
            )
            
            # Format output using output manager
            output = self.output_manager.process_output(result)
            
            return output
            
        except Exception as e:
            logger.error(f"Error processing input: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }

# Initialize AAC server
aac_server = AACServer()

@app.route("/health", methods=["GET"])
def health_check() -> Dict:
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/process", methods=["POST"])
def process_input() -> Dict:
    """
    Process input text and return predictions
    
    Expected input JSON:
    {
        "text": "input text",
        "type": "text" | "speech",
        "location": "optional location"
    }
    """
    try:
        # Get input data
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No input data provided",
                "timestamp": datetime.now().isoformat()
            }), 400
            
        # Process input
        result = aac_server.process_input(data)
        
        # Return result
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in /process endpoint: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/config", methods=["GET", "POST"])
def manage_config() -> Dict:
    """
    Get or update output configuration
    
    POST body example:
    {
        "text_format": "simple" | "detailed",
        "mode": "text" | "speech" | "both" | "custom_plugin"
    }
    """
    if request.method == "POST":
        try:
            config_data = request.get_json()
            aac_server.output_manager.update_config(**config_data)
            
            return jsonify({
                "status": "success",
                "message": "Configuration updated",
                "config": vars(aac_server.output_manager.config)
            })
            
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Failed to update config: {str(e)}"
            }), 400
            
    # GET request - return current config
    return jsonify({
        "status": "success",
        "config": vars(aac_server.output_manager.config)
    })

if __name__ == "__main__":
    # Run the Flask app
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True  # Set to False in production
    ) 