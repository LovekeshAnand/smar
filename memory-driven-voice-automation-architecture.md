# Memory-Driven Voice Intelligence Architecture

## Project Architecture & Design Document

---

## 1. Overview

This project is a **voice-first autonomous AI system built around a persistent, self-updating Context Layer and local LLM execution**. The core thesis is that today's voice AI and conversational assistants fail primarily because they don't remember — every interaction starts near-zero, context doesn't accumulate, and the system cannot maintain cognitive persistence across turns and sessions.

This architecture addresses that fundamental problem by combining:

1. A **real-time multilingual voice interface** (Gnani / Vachana.ai STT & TTS) as the primary natural input and output medium.
2. A **hybrid dual-store Context Layer** — a SQLite-backed Knowledge Graph (KG) for deterministic relational facts, and a Subword Hashing Vector Store for semantic recall — that updates itself dynamically via cognitive fact extraction.
3. A **private, local reasoning layer (LLM)** — powered by quantized Qwen 7B running on a dedicated local inference engine (Epsilon Engine / llama-server).
4. A **real-time web interface** built with Next.js, featuring dynamic audio spike visualizers, live conversation stream, and an interactive slide-over Memory Inspector drawer.

---

## 2. The Core Problem

Most current voice AI and LLM-based assistants share two structural weaknesses:

- **No durable memory.** Context resets between sessions, or is crudely reinjected as a growing transcript, which doesn't scale and doesn't support reasoning over past facts.
- **Vague, append-only storage.** Naive memory tools insert every utterance as an independent embedding, creating a "memory landfill" of redundant, outdated, and conflicting vectors.

SMAR treats memory as an active, structured cognition layer: facts about the user's world are extracted, normalized, and written into a hybrid KG + Vector store. Instead of just appending new nodes forever, the system detects when new information relates to something already stored and **updates** existing memory entries via **upsert-by-similarity**.

---

## 3. Core Architecture & Data Flow

```
[User Microphone] <--- Spoken Audio (WAV / WebAudio) ---> [Gnani STT / TTS]
                                                                  |
                                                               (Text)
                                                                  ▼
        ┌─────────────────────────────────────────────────────────┐
        │                 Cognitive Context Layer                 │
        │                                                         │
        │  ┌───────────────────────┐   ┌───────────────────────┐  │
        │  │ Knowledge Graph (KG)  │   │      Vector Store     │  │
        │  │   (Relational Facts)  │   │  (Semantic Memories)  │  │
        │  │ `(subject, pred, obj)`│   │ (Subword Hashing)     │  │
        │  └───────────┬───────────┘   └───────────┬───────────┘  │
        │              │                           │              │
        │              ▼                           ▼              │
        │          Hybrid RAG Query & Multi-Turn Buffer           │
        │         (Dynamic System Prompt with Context)            │
        └────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │            Local LLM Reasoning Engine (Epsilon)         │
        │             (Qwen2.5-Coder 7B via llama-server)         │
        └────────────────────────────┬────────────────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
        [Synthesized Spoken Reply]         [Cognitive Fact Formation]
                 │                                       │
                 ▼                                       ▼
        [Gnani Timbre TTS (SSE)]            [Upsert into KG & Vectors]
                 │
                 ▼
          [Speaker Audio]
```

### 3.1 Voice Interface Layer (User <-> Gnani / Vachana.ai)
- **Speech-to-Text (Prisma v2.5)**: Low-latency streaming transcription with support for Indian regional English (`en-IN`), Hindi (`hi-IN`), and multilingual code-switching. Includes 25s auto-chunking to stay safely within duration thresholds.
- **Text-to-Speech (Timbre v2.5)**: High-fidelity expressive neural speech synthesis via Server-Sent Events (SSE) streaming.

### 3.2 Cognitive Context Layer (`context_layer/`)
- **Knowledge Graph (`kg_entities`, `kg_triples`)**: Relational triple store with case-insensitive entity resolution and confidence scores. Allows deterministic answers to explicit relational questions ("What database do you use?").
- **Vector Store (`semantic_nodes`)**: Subword character n-gram hashing vectorizer (300 dimensions) with cosine similarity and **upsert-by-similarity** (Section 4) to maintain dense, non-redundant semantic knowledge.
- **Sliding Window Buffer (`conversation_turns`)**: Captures exact recent dialogue turns to provide prompt coherence and immediate conversational continuity.
- **Cognitive Fact Extractor (`extract_facts_llm`)**: Local Qwen 7B asynchronously processes each turn in the background to deduce verified relational triples and store them in the graph.

### 3.3 Reasoning Layer (Epsilon Engine)
- **Local Qwen 7B Instruct**: Runs locally on hardware with 0 external API costs, private data retention, and zero external network latency.
- **Dynamic Prompt Composition**: Synthesizes a fresh system prompt for every turn containing verified facts, semantic memories, and identity guidelines.

---

## 4. Memory System: Self-Updating Design

A key differentiator of this architecture is that memory is not purely additive:

- When new incoming data is found to have high cosine similarity (e.g. `similarity >= 0.85`) with an existing memory chunk, the system **updates the existing node's weights and content** rather than creating a duplicate.
- The Knowledge Graph uses unique constraints and case-insensitive entity linking to avoid duplicate nodes for identical real-world concepts.
- This keeps the memory store dense, current, and non-redundant over time.

---

## 5. End-to-End Spoken Turn Flow

1. **User speaks**: Audio captured via WebAudio script processor in 16kHz mono WAV format.
2. **STT Transcription**: Gnani STT returns user transcription text.
3. **Context Retrieval**: Context Layer queries KG triples and Vector embeddings matching user input.
4. **LLM Generation**: Epsilon Bridge queries local Qwen 7B with dynamic prompt, retrieved context, and recent conversation turns.
5. **Speech Synthesis**: LLM reply is converted to speech via Gnani TTS and streamed to browser for playback.
6. **Cognitive Memory Formation**: In the background, LLM extracts structured facts from the turn and upserts them into the Knowledge Graph and Vector database.
7. **Telemetry Broadcast**: Backend pushes real-time memory updates over WebSockets to update the frontend Memory Inspector drawer.
