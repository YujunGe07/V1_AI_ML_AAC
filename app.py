from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
from datetime import datetime
import tempfile
from input_module import InputModule
import pyttsx3
from flask import send_file
from pydub import AudioSegment
import os
import io
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import re
AudioSegment.converter = "/opt/homebrew/bin/ffmpeg"



app = Flask(__name__)

CORS(app, resources={
    r"/speak": {
        "origins": ["http://127.0.0.1:5001", "http://localhost:5001"],
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    },
    r"/transcribe": {
        "origins": ["http://127.0.0.1:5001", "http://localhost:5001"],
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})


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


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://127.0.0.1:5001')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    return response



@app.route('/transcribe-audio', methods=['POST'])
def transcribe_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file uploaded'}), 400

    file = request.files['audio']
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
        file.save(temp.name)
        input_module = InputModule()
        result = input_module.process_speech(temp.name)

    print("📥 Audio received:", file.filename)
    print("📝 Transcription result:", result)
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

@app.route("/speak", methods=["POST", "OPTIONS"])
def speak():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        return response

    try:
        import time
        from gtts import gTTS
        from pydub import AudioSegment
        from flask import send_file
        import io
        import os
        import tempfile
        from shutil import which

        data = request.get_json()
        text = data.get("text", "").strip()
        voice_gender = data.get("voice", "male")  # optional, not used by gTTS

        if not text:
            return jsonify({"error": "No text provided"}), 400

        # Create a temporary mp3 path
        temp_mp3_path = os.path.join(tempfile.gettempdir(), f"tts_{int(time.time()*1000)}.mp3")

        # Generate TTS using gTTS
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(temp_mp3_path)

        # Convert MP3 to WAV using pydub
        AudioSegment.converter = which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
        audio = AudioSegment.from_file(temp_mp3_path, format="mp3")
        output = io.BytesIO()
        audio.export(output, format="wav")
        output.seek(0)

        os.remove(temp_mp3_path)
        return send_file(output, mimetype="audio/wav")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("❌ TTS ERROR:", e)
        return jsonify({"error": f"TTS failed: {str(e)}"}), 500

# Load model and tokenizer once at startup
try:
    tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
    model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")
    print("✅ Model loaded successfully")
except Exception as e:
    print(f"❌ Error loading model: {str(e)}")
    model = None
    tokenizer = None

def clean_and_split_suggestions(text, input_text):
    # Remove the input text from the beginning
    if text.startswith(input_text):
        text = text[len(input_text):].strip()
    
    # Split on periods and clean each suggestion
    suggestions = [s.strip() for s in text.split('.') if s.strip()]
    
    # Additional cleaning
    cleaned = []
    for s in suggestions:
        # Remove special characters and multiple spaces
        s = re.sub(r'[^\w\s.,!?]', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        if s and len(s.split()) <= 10:  # Limit to 10 words
            cleaned.append(s)
    
    return list(dict.fromkeys(cleaned))  # Remove duplicates while preserving order

@app.route('/predict-suggestions', methods=['POST'])
def predict_suggestions():
    try:
        # Check if model loaded successfully
        if model is None or tokenizer is None:
            return jsonify({
                'error': 'Model not initialized',
                'suggestions': []
            }), 500

        # Get input text
        data = request.get_json()
        if not data or 'transcript' not in data:
            return jsonify({
                'error': 'Missing transcript in request',
                'suggestions': []
            }), 400

        transcript = data['transcript'].strip()
        if not transcript:
            return jsonify({
                'error': 'Empty transcript',
                'suggestions': []
            }), 400

        # Tokenize input
        inputs = tokenizer.encode(transcript + tokenizer.eos_token, return_tensors='pt')
        
        # Generate response with higher temperature for more variety
        outputs = model.generate(
            inputs,
            max_length=100,
            num_return_sequences=3,
            temperature=0.9,
            top_k=50,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            no_repeat_ngram_size=2
        )

        # Decode and process suggestions
        suggestions = []
        for output in outputs:
            decoded = tokenizer.decode(output, skip_special_tokens=True)
            suggestions.extend(clean_and_split_suggestions(decoded, transcript))

        # Return top 5 unique suggestions
        suggestions = suggestions[:5]
        
        return jsonify({
            'suggestions': suggestions
        })

    except Exception as e:
        print(f"Error generating suggestions: {str(e)}")
        return jsonify({
            'error': 'Error generating suggestions',
            'suggestions': []
        }), 500

if __name__ == "__main__":
    app.run(port=5001, debug=True)