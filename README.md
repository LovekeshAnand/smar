# SMAR: Memory-Driven Autonomous Voice Platform

> **A voice-first autonomous AI system built around a persistent, self-updating dual-store Context Layer and local LLM execution.**

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue?style=flat-square)
![Status](https://img.shields.io/badge/Status-Production%20Ready-green?style=flat-square)
![Inference](https://img.shields.io/badge/Inference-Local%20(Epsilon%20Engine%20%2F%20Qwen%207B)-purple?style=flat-square)
![Voice](https://img.shields.io/badge/Voice-Gnani.ai%20STT%20%26%20TTS-orange?style=flat-square)
![Frontend](https://img.shields.io/badge/Frontend-Next.js%20%2F%20Tailwind%20%2F%20WebAudio-black?style=flat-square)

---

## 1. Overview & Vision

Traditional voice assistants fail primarily because **they do not remember**. Context resets between sessions, logs grow indefinitely without structure, and assistants lack any cognitive persistence across turns.

**SMAR** solves this with three core tenets:
1. **Speech as the Natural Interface**: Real-time voice intake (STT) and voice feedback (TTS) using **Gnani.ai / Vachana.ai** (Prisma STT and Timbre TTS) with native multilingual support (Hindi, English, and Indian regional accents).
2. **Persistent, Self-Updating Context Layer (`context_layer/`)**: A hybrid dual-store memory combining a **Knowledge Graph** (for relational facts) and a **Vector Store** (for semantic concept recall) that uses **upsert-by-similarity** rather than naive append-only logging.
3. **Local, Long-Term LLM Reasoning**: Powered by the **Epsilon Engine** and local **Qwen2.5-Coder 7B** running via `llama-server` for private, zero-latency, zero-cost local inference.

---

## 2. Architecture & Data Flow

```
                     ┌─────────────────────────────┐
                     │   User Spoken Microphone    │
                     └──────────────┬──────────────┘
                                    │ (audio wav / WebAudio)
                                    ▼
                     ┌─────────────────────────────┐
                     │    Gnani Speech-to-Text     │
                     └──────────────┬──────────────┘
                                    │ (transcribed text)
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │                Cognitive Context Layer                  │
       │  ┌───────────────────────┐   ┌───────────────────────┐  │
       │  │ Knowledge Graph (KG)  │   │      Vector Store     │  │
       │  │  (Relational Triples) │   │  (Subword Embeddings) │  │
       │  └───────────┬───────────┘   └───────────┬───────────┘  │
       │              │                           │              │
       │              ▼                           ▼              │
       │         Dynamic System Prompt & Recalled Context        │
       └────────────────────────────┬────────────────────────────┘
                                    │ (prompt + multi-turn history)
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │             Epsilon Local LLM Engine (core/)            │
       │            (Qwen2.5-Coder 7B / llama-server)            │
       └──────────────┬───────────────────────────┬──────────────┘
                      │                           │
  (synthesizes reply) │                           │ (cognitive fact extraction)
                      ▼                           ▼
       ┌─────────────────────────────┐   ┌────────────────────────┐
       │     Gnani Text-to-Speech    │   │ Memory Upsert-by-Sim   │
       └──────────────┬──────────────┘   └────────────────────────┘
                      │ (audio wav / SSE)
                      ▼
       ┌─────────────────────────────┐
       │      Speaker Playback       │
       └─────────────────────────────┘
```

---

## 3. Repository Structure

```
smar/
├── context_layer/                         # Cognitive Context Layer Subsystem
│   ├── base.py                            # Context store abstract base interface
│   ├── native_hybrid.py                   # SQLite Knowledge Graph + Subword Hashing Vector Store
│   ├── knowledge_formation.py             # LLM-guided entity & fact extraction pipeline
│   ├── mem0_adapter.py                    # Pluggable adapter for external memory engines
│   └── engine.py                          # Unified coordinator for storage and retrieval
│
├── core/                                  # Local Epsilon LLM Subsystem
│   ├── config.yaml                        # Model tier and inference configuration
│   ├── epsilon_bridge.py                  # Async client bridge to local llama-server
│   └── models/
│       └── qwen2.5-coder-7b-instruct-q4_k_m.gguf  # High-performance 7B quantized model
│
├── voice/                                 # Multilingual Voice Interface Layer
│   ├── gnani_stt.py                       # Gnani / Vachana Speech-to-Text client
│   ├── gnani_tts.py                       # Gnani / Vachana Text-to-Speech client
│   └── audio_io.py                        # Standalone mic capture & speaker playback
│
├── frontend/                              # Real-Time Web Application (Next.js)
│   ├── src/
│   │   ├── app/                           # Next.js App Router (page, layout)
│   │   ├── components/
│   │   │   ├── AudioSpikesVisualizer.tsx  # Dynamic audio spike waveform visualizer
│   │   │   ├── ConversationStream.tsx     # Clean conversation message stream
│   │   │   ├── MemoryInspector.tsx        # Slide-over Knowledge Graph & Vector viewer
│   │   │   ├── VoiceController.tsx        # Push-to-talk & text input control bar
│   │   │   └── Header.tsx                 # System status & language selector
│   │   └── lib/audio.ts                   # WebAudio WAV encoding and PCM downsampling
│   └── package.json
│
├── tests/                                 # Unit & Integration Tests
│   ├── test_context_layer.py              # Context layer hybrid store tests
│   ├── test_context_memory.py             # Relational triple extraction tests
│   ├── test_epsilon_bridge.py             # Prompt formatting & context injection tests
│   └── test_voice_stt_tts.py              # Gnani client & parsing tests
│
├── data/                                  # Persistent SQLite databases (smar_context.db)
├── .env.example                           # Environment variable template
├── requirements.txt                       # Backend Python dependencies
├── server.py                              # FastAPI backend application server
└── main.py                                # Standalone CLI / Terminal entrypoint
```

---

## 4. Quick Start

### 4.1 Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- Local model server (`llama-server`) with Qwen 7B GGUF running on port 8088

### 4.2 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/LovekeshAnand/smar.git
   cd smar
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Frontend dependencies**:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

### 4.3 Configure Environment

Copy `.env.example` to `.env` and fill in your Gnani / Vachana API credentials:
```bash
cp .env.example .env
```

```env
# Gnani / Vachana.ai Voice API Configuration
GNANI_API_KEY=your_vachana_api_key_here
GNANI_STT_URL=https://api.vachana.ai/stt/v3
GNANI_TTS_URL=https://api.vachana.ai/api/v1/tts/sse
GNANI_LANGUAGE_CODE=en-IN
GNANI_VOICE_NAME=Nalini

# Epsilon Local LLM Configuration
EPSILON_HOST=127.0.0.1
EPSILON_PORT=8088

# Persistent Memory Store
SMAR_DB_PATH=data/smar_context.db
```

### 4.4 Launching the Application

1. **Start the Local Model Server** (if not already running):
   ```powershell
   llama-server.exe -m core/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf -c 2048 --port 8088 -ngl 20
   ```

2. **Start the FastAPI Backend**:
   ```powershell
   python server.py
   ```
   Backend runs at `http://127.0.0.1:5000`.

3. **Start the Next.js Frontend**:
   ```powershell
   cd frontend
   npm run dev
   ```
   Open `http://localhost:3000` in your browser.

---

## 5. Verification & Tests

Run the test suite to verify the Context Layer and LLM reasoning pipeline:
```bash
python -m unittest tests/test_context_layer.py tests/test_context_memory.py tests/test_epsilon_bridge.py
```
