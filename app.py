from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import logging
import os

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route("/")
def index():
    return render_template("index.html")  # ✅ updated to match the new filename

@app.route("/process", methods=["POST"])
def process():
    try:
        data = request.json
        text = data.get("text", "")
        
        # Mock response for now
        response = {
            "status": "success",
            "data": {
                "predictions": ["Hello", "Hi there", "How are you"],
                "context": {
                    "label": "greeting",
                    "confidence": 0.9
                }
            }
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=True)
