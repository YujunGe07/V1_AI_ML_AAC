# AI/ML Augmentative & Alternative Communication (AAC) System

<div align="left">

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21F?style=flat&logo=huggingface&logoColor=black)
![OpenAI Whisper](https://img.shields.io/badge/Whisper-412991?style=flat&logo=openai&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat)

</div>

> **Real-time, context-aware communication assistance for users with speech or motor impairments.**
> Combines OpenAI Whisper for speech recognition, DistilGPT2 for predictive text generation, and TTS output — all in a modular, extensible pipeline.

---

## Overview

Traditional AAC devices are rigid and slow. This system uses ML to make communication *adaptive*: it recognizes speech or text input, infers the user's context (social, work, general), predicts likely next utterances, and delivers natural-sounding speech output — in real time.

---

## System Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌────────────────┐
│   Input Module  │────▶│  Processing Module   │────▶│ Output Module  │
│                 │     │                      │     │                │
│  • Text input   │     │  • Intent recognition│     │  • Postprocess │
│  • Mic (Whisper)│     │  • Context adaptation│     │  • TTS (speech)│
│  • Env data     │     │  • DistilGPT2 predict│     │                │
└─────────────────┘     └──────────────────────┘     └────────────────┘
                                   │
                        ┌──────────┴──────────┐
                        │   Storage (Planned) │
                        │  • User profiles    │
                        │  • Interaction log  │
                        └─────────────────────┘
```

---

## Features

| Module | Capability |
|--------|-----------|
| **Speech Input** | Real-time audio capture via PyAudio + Whisper ASR |
| **Noise Reduction** | `noisereduce` pre-processing for clean transcriptions |
| **Context Adaptation** | Switches prediction style across social / work / general contexts |
| **Predictive Text** | DistilGPT2 generates context-aware response suggestions |
| **Intent Recognition** | DistilBERT classifies user intent before generation |
| **TTS Output** | Converts final text to natural-sounding speech |
| **History Export** | SQLite-backed interaction log (`aac_history.db`) + export script |

---

## Tech Stack

- **Speech Recognition**: OpenAI Whisper
- **Language Models**: DistilGPT2, DistilBERT (HuggingFace Transformers)
- **Audio**: PyAudio, NumPy, SciPy, `noisereduce`
- **Backend**: Flask (Python 3.10)
- **Storage**: SQLite (`aac_history.db`)

---

## Repo Structure

```
V1_AI_ML_AAC/
├── app.py                  # Flask app entry point
├── input_module.py         # Audio capture + Whisper transcription
├── output_speech.py        # TTS output module
├── train_aac_model.py      # Model fine-tuning script
├── export_history.py       # Export interaction history
├── data.jsonl              # Training / interaction data
├── aac_history.db          # SQLite history store
├── static/                 # Frontend assets
├── templates/              # HTML templates
├── temp_audio/             # Temporary audio buffer
└── requirements.txt
```

---

## Quickstart

```bash
git clone https://github.com/YujunGe07/V1_AI_ML_AAC.git
cd V1_AI_ML_AAC
pip install -r requirements.txt
python app.py
```

> Requires a working microphone for speech input mode. Python 3.10 recommended.

---

## Roadmap

- [x] Speech input via Whisper
- [x] DistilGPT2 predictive text generation
- [x] Context adaptation (social / work / general)
- [x] TTS output
- [x] SQLite interaction history
- [ ] Web UI for text input + response display
- [ ] Per-user profiles and preference persistence
- [ ] Fine-tuned model on AAC-specific corpora
- [ ] Mobile-friendly interface

---

## Author

**Yujun Ge** · [GitHub](https://github.com/YujunGe07) · [Email](mailto:geyujunamy@gmail.com)
