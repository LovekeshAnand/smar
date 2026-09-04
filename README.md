# SMAR: Memory-Driven Autonomous Voice Automation System

> **A voice-first autonomous AI system built around a persistent, self-updating dual-store memory layer and local LLM execution.**

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue?style=flat-square)
![Status](https://img.shields.io/badge/Status-Phase%201%20Ready-green?style=flat-square)
![Inference](https://img.shields.io/badge/Inference-Local%20(Epsilon%20Engine)-purple?style=flat-square)
![Voice](https://img.shields.io/badge/Voice-Gnani.ai%20STT%20%26%20TTS-orange?style=flat-square)

---

## 1. Overview & Vision

Today's voice assistants fail primarily because **they do not remember**. Context resets between sessions, logs grow indefinitely without structure, and assistants wait passively rather than acting autonomously on past knowledge.

**SMAR** solves this with three core tenets:
1. **Speech as the Natural Interface**: Low-latency voice intake (STT) and voice feedback (TTS) using **Gnani.ai**.
2. **Persistent, Self-Updating Memory (Context Layer)**: A hybrid dual-store memory combining a **Knowledge Graph** (for relational facts) and a **Vector Store** (for semantic concept recall) that uses **upsert-by-similarity** rather than naive insert-only logging.
3. **Local, Long-Term LLM Reasoning**: Powered by the **Epsilon Engine v2** running in `core/` for private, hardware-safe, zero-cost local inference.
4. **Decoupled Background Execution**: Background automation tasks (Gmail, WhatsApp) run independently without stalling conversational voice latency.

---

## 2. Current Project Status (Phase 1)

### ✅ Completed in Phase 1:
- **Reasoning Layer (`core/`)**:
  - Integrated **Epsilon Engine v2** multi-tier local inference orchestrator.
  - Copied and configured the quantized **Qwen2.5-Coder 1.5B** model (`qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`, ~1.1 GB) into `core/models/`.
  - Built `core/epsilon_bridge.py` providing asynchronous ChatML prompting, context injection, and health monitoring.
- **Context Layer (`memory/`)**:
  - **Knowledge Graph Store (`memory/graph_store.py`)**: SQLite-backed relational triple store `(subject, predicate, object)`.
  - **Semantic Vector Store (`memory/vector_store.py`)**: Vector retrieval with **upsert-by-similarity** (Section 8 of architecture spec) to prevent memory landfill.
  - **Fact Extractor (`memory/extractor.py`)**: Automatic entity & relational extraction from spoken conversation turns.
  - **Context Manager (`memory/context_manager.py`)**: Hybrid coordinator that retrieves both relational facts and semantic context before querying the LLM.
- **Voice Interface Layer (`voice/`)**:
  - **Gnani STT (`voice/gnani_stt.py`)**: Speech-to-Text REST client for audio transcription.
  - **Gnani TTS (`voice/gnani_tts.py`)**: Text-to-Speech REST client for synthesized spoken audio.
  - **Audio I/O (`voice/audio_io.py`)**: Microphone recording and speaker playback using `sounddevice`.
- **Pipeline & CLI (`pipeline/` & `main.py`)**:
  - Master conversational and cognitive loop in `pipeline/session.py`.
  - Background Work Intent extraction in `pipeline/intent.py`.
  - Interactive CLI (`--cli`), continuous voice loop (`--voice`), and diagnostic mode (`--test`).
  - Unit test suite (`tests/`) with 100% pass rate.

---

## 3. Architecture & Data Flow

```
                     ┌─────────────────────────────┐
                     │   User Spoken Microphone    │
                     └──────────────┬──────────────┘
                                    │ (audio wav)
                                    ▼
                     ┌─────────────────────────────┐
                     │    Gnani Speech-to-Text     │
                     └──────────────┬──────────────┘
                                    │ (transcribed text)
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │                      Context Layer                      │
       │  ┌───────────────────────┐   ┌───────────────────────┐  │
       │  │ Knowledge Graph (KG)  │   │      Vector Store     │  │
       │  │  (Relational Triples) │   │  (Semantic Concepts)  │  │
       │  └───────────┬───────────┘   └───────────┬───────────┘  │
       └──────────────┼───────────────────────────┼──────────────┘
                      │ (retrieved memory context)│
                      ▼                           ▼
       ┌─────────────────────────────────────────────────────────┐
       │             Epsilon Local LLM Engine (core/)            │
       │           (Qwen2.5-Coder 1.5B / llama-server)           │
       └──────────────┬───────────────────────────┬──────────────┘
                      │                           │
  (synthesizes reply) │                           │ (auto-ingests new facts)
                      ▼                           ▼
       ┌─────────────────────────────┐   ┌────────────────────────┐
       │     Gnani Text-to-Speech    │   │ Memory Upsert-by-Sim   │
       └──────────────┬──────────────┘   └────────────────────────┘
                      │ (audio wav)
                      ▼
       ┌─────────────────────────────┐
       │      Speaker Playback       │
       └─────────────────────────────┘
```

---

## 4. Repository Structure

```
smar/
├── core/                                  # Local Epsilon LLM Subsystem
│   ├── config.yaml                        # Model tier and server settings
│   ├── epsilon_bridge.py                  # Async client bridge to Epsilon engine
│   ├── engine/
│   │   ├── tiers/                         # Model manager & router
│   │   ├── inference/                     # KV cache management
│   │   ├── memory/                        # Turn conversation buffer
│   │   └── main.py                        # Standalone Epsilon runner
│   └── models/
│       └── qwen2.5-coder-1.5b-instruct-q4_k_m.gguf  # 1.1 GB local model
│
├── voice/                                 # Voice Interface Layer
│   ├── gnani_stt.py                       # Gnani Speech-to-Text REST client
│   ├── gnani_tts.py                       # Gnani Text-to-Speech REST client
│   └── audio_io.py                        # Microphone capture & speaker playback
│
├── memory/                                # Context Layer (Self-updating Dual Store)
│   ├── graph_store.py                     # Knowledge Graph (triples: subject, predicate, object)
│   ├── vector_store.py                    # Semantic vector store with similarity upsert
│   ├── extractor.py                       # Conversational fact and entity extractor
│   └── context_manager.py                 # Hybrid memory query and auto-ingestion
│
├── pipeline/                              # Orchestration & Runtime Loop
│   ├── session.py                         # Master multi-turn session coordinator
│   └── intent.py                          # Work intent classifier (email, whatsapp, tasks)
│
├── tests/                                 # Unit & Integration Tests
│   ├── test_context_memory.py             # KG & Vector store tests
│   ├── test_epsilon_bridge.py             # Prompt formatting & context injection tests
│   └── test_voice_stt_tts.py              # Gnani client & parsing tests
│
├── data/                                  # Local SQLite databases (smar_memory.db)
├── .env.example                           # Environment variable template
├── requirements.txt                       # Project dependencies
├── memory-driven-voice-automation-architecture.md  # Core architectural design specification
└── main.py                                # Application entry point
```

---

## 5. Quick Start

### 5.1 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/LovekeshAnand/smar.git
   cd smar
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### 5.2 Configure Environment

Copy `.env.example` to `.env` and fill in your Gnani credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```env
# Gnani Voice API Configuration (REST)
GNANI_API_KEY=your_gnani_api_key_here
GNANI_TOKEN=your_gnani_token_here
GNANI_STT_URL=https://asr.gnani.ai/v1/recognize
GNANI_TTS_URL=https://tts.gnani.ai/v1/synthesize
GNANI_LANGUAGE_CODE=en-IN
GNANI_VOICE_GENDER=female

# Epsilon Local LLM Configuration
EPSILON_CONFIG_PATH=core/config.yaml
EPSILON_TIER=fast
EPSILON_HOST=127.0.0.1
EPSILON_PORT=8088

# Context Memory Store
SMAR_DB_PATH=data/smar_memory.db
```

### 5.3 Run Diagnostic Self-Test

Verify the context memory layer, fact extraction, and Epsilon bridge:
```bash
python main.py --test
```

Run unit tests:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 5.4 Launch SMAR

- **Interactive Text Mode (CLI)**:
  ```bash
  python main.py --cli
  ```
- **Voice Mode (Microphone & Speaker)**:
  ```bash
  python main.py --voice
  ```

---

## 6. Next Steps (Phase 2 Roadmap)

- [ ] **Universal Connector**: Common abstraction layer for third-party automation tools.
- [ ] **Gmail & WhatsApp Connectors**: Background execution dispatched via detected work intents.
- [ ] **Connector Normalization Pipeline**: Ingest connector data into the Knowledge Graph and Vector Store.
- [ ] **Hardcoded Verification Loop**: Independent code-level verification for completed tasks before vocal confirmation.
