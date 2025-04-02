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
        import io, time, os, pyttsx3
        from pydub import AudioSegment
        from flask import send_file
        import tempfile

        data = request.get_json()
        text = data.get("text", "")
        voice_gender = data.get("voice", "male")
        if not text:
            return jsonify({"error": "No text provided"}), 400

        # 1. Initialize engine fresh every time
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        if voice_gender == "female" and len(voices) > 1:
            engine.setProperty("voice", voices[1].id)
        else:
            engine.setProperty("voice", voices[0].id)
        engine.setProperty("rate", 150)

        # 2. Save to guaranteed file path
        temp_wav_path = os.path.join(tempfile.gettempdir(), f"tts_{int(time.time()*1000)}.wav")
        engine.save_to_file(text, temp_wav_path)
        engine.runAndWait()
        engine.stop()

        # 3. Ensure file is valid
        for _ in range(10):
            if os.path.exists(temp_wav_path) and os.path.getsize(temp_wav_path) > 44:
                break
            time.sleep(0.1)

        if not os.path.exists(temp_wav_path) or os.path.getsize(temp_wav_path) <= 44:
            raise ValueError("Generated file is invalid or empty")

        # 4. Convert to standard WAV using ffmpeg (via pydub)
        audio = AudioSegment.from_file(temp_wav_path, format="wav")
        output = io.BytesIO()
        audio.export(output, format="wav")
        output.seek(0)

        os.remove(temp_wav_path)
        return send_file(output, mimetype="audio/wav")

    except Exception as e:
        print("❌ TTS ERROR:", e)
        return jsonify({"error": f"Text-to-speech conversion failed: {str(e)}"}), 500



    
if __name__ == "__main__":
    app.run(port=5001, debug=True)