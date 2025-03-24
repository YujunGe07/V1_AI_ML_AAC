import json
import queue
import time
from input_module import InputModule
from datetime import datetime

# Initialize Input Module
input_module = InputModule(use_whisper=True)

# ✅ **Test 1: Text Input Handling**
def test_text_input():
    print("\n🔹 Running Test: Text Input Handling")
    result = input_module.process_input(input_type="text")
    print(json.dumps(result, indent=2))

# ✅ **Test 2: Speech Input Handling**
def test_speech_input():
    print("\n🔹 Running Test: Speech Input Handling")
    result = input_module.process_input(input_type="speech", duration=5)
    print(json.dumps(result, indent=2))

# ✅ **Test 3: Continuous Listening Mode**
def test_continuous_listening():
    print("\n🔹 Running Test: Continuous Listening")
    transcription_queue = input_module.start_continuous_listening()

    try:
        print("🎤 Listening... Speak into the microphone. (Press Ctrl+C to stop)")
        for _ in range(5):  # Collect transcriptions for 5 seconds
            try:
                result = transcription_queue.get(timeout=3)
                with open("transcription_log.txt", "a") as f:
                    f.write(f"{datetime.now().isoformat()} - {result['input']['text']}\n")
                print(f"📝 Transcribed: {result['input']['text']}")
            except queue.Empty:
                print("⏳ Waiting for transcription...")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping Continuous Listening...")
        input_module.stop_listening()

# ✅ **Test 4: Noise Reduction**
def test_noise_reduction():
    print("\n🔹 Running Test: Noise Reduction")
    audio_file = input_module.record_audio(duration=5)  # Record noisy input
    if not audio_file:
        print("❌ Failed to record audio")
        return

    print("🔄 Processing noise reduction...")
    cleaned_audio = input_module.audio_processor.reduce_noise(audio_file)
    print("✅ Noise reduction complete.")

# ✅ **Test 5: Environmental Data Collection**
def test_environment_data():
    print("\n🔹 Running Test: Environmental Data Collection")
    result = input_module.get_environment_data()
    print(json.dumps(result, indent=2))

# ✅ **Run All Tests**
if __name__ == "__main__":
    test_text_input()           # Test Text Input
    test_speech_input()         # Test Speech Input
    test_continuous_listening() # Test Continuous Listening
    test_noise_reduction()      # Test Noise Reduction
    test_environment_data()     # Test Environmental Data Collection
