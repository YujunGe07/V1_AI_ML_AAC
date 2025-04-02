from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
import tempfile
from input_module import InputModule

app = Flask(__name__)
CORS(app)

# Store current context
current_context = {
    'timeOfDay': '',
    'dayType': '',
    'place': '',
    'city': ''
}

@app.route("/")
def index():
    return render_template("index.html")


@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file uploaded'}), 400

    file = request.files['audio']

    # Save temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
        file.save(temp.name)
        input_module = InputModule()
        result = input_module.process_speech(temp.name)
    
    return jsonify(result)

@app.route("/update-context", methods=["POST"])
def update_context():
    try:
        context_update = request.json
        current_context.update(context_update)
        return jsonify({
            "status": "success",
            "context": current_context
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route("/get-context")
def get_context():
    return jsonify(current_context)

if __name__ == "__main__":
    app.run(port=5001, debug=True)

    