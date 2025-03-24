# 🧠 AI/ML Augmentative and Alternative Communication (AAC) System

This project is a machine learning-powered Augmentative and Alternative Communication (AAC) system that enables users with speech or motor impairments to communicate using intelligent, context-aware speech suggestions and voice output.

## 🔍 Overview

The system captures text or speech input, interprets environmental data, detects user intent and context, and generates appropriate responses using LLMs. It is modular, extensible, and optimized for real-time assistive use.

## 🧱 System Architecture

The system is built around 5 core modules:

1. **Input Module**  
   - Handles text or microphone input  
   - Collects environment data (e.g., time, location)

2. **Processing Module**  
   - Intent recognition  
   - Context adaptation (social, work, general)  
   - Predictive text generation (DistilGPT2)

3. **Output Module**  
   - Postprocessing and cleaning of model output  
   - Converts text to natural-sounding speech using TTS

4. **Storage Module (Planned)**  
   - Profiles, preferences, and interaction history

5. **UI Module (Planned)**  
   - Web interface for text input and response display

## 🛠 Technologies Used

- Python 3.10  
- OpenAI Whisper (speech recognition)  
- Hugging Face Transformers (DistilGPT2, DistilBERT)  
- PyAudio, NumPy, SciPy  
- `noisereduce` (real-time audio cleaning)

## 👤 Author
Yujun Ge

