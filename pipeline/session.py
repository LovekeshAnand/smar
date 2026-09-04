"""
pipeline/session.py
===================
Master session coordinator for SMAR:
Voice Input (Gnani STT) -> Context Layer (Memory) -> Epsilon Local LLM (core/) -> Voice Output (Gnani TTS)
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any

from voice.gnani_stt import GnaniSTT
from voice.gnani_tts import GnaniTTS
from voice.audio_io import AudioIO
from memory.context_manager import ContextManager
from core.epsilon_bridge import EpsilonBridge
from .intent import WorkIntentExtractor

logger = logging.getLogger("smar.pipeline.session")


class VoiceAgentSession:
    def __init__(
        self,
        stt: Optional[GnaniSTT] = None,
        tts: Optional[GnaniTTS] = None,
        audio_io: Optional[AudioIO] = None,
        context_mgr: Optional[ContextManager] = None,
        epsilon: Optional[EpsilonBridge] = None,
    ):
        self.stt = stt or GnaniSTT()
        self.tts = tts or GnaniTTS()
        self.audio = audio_io or AudioIO()
        self.context = context_mgr or ContextManager()
        self.epsilon = epsilon or EpsilonBridge()
        self.intent_extractor = WorkIntentExtractor()

    async def run_voice_turn(self, record_seconds: float = 5.0) -> Dict[str, Any]:
        """
        Executes a single voice interaction cycle:
        1. Capture audio from microphone
        2. Transcribe using Gnani STT
        3. Query Context Layer (KG + Vector Store)
        4. Pass prompt + context to Epsilon LLM
        5. Synthesize response via Gnani TTS and play through speaker
        6. Ingest turn into Context Layer memory
        7. Extract background Work Intent
        """
        print("\n[SMAR] Listening... Speak now.")
        audio_bytes = self.audio.record_seconds(duration_seconds=record_seconds)

        print("[SMAR] Transcribing audio via Gnani STT...")
        user_text = await self.stt.transcribe_audio_bytes(audio_bytes)
        print(f"[User]: {user_text}")

        return await self.process_text_turn(user_text)

    async def process_text_turn(self, user_text: str, speak_output: bool = True) -> Dict[str, Any]:
        """
        Processes text input through the cognitive & memory loop.
        Can be used both directly (for testing/CLI) and via the voice loop.
        """
        # 1. Retrieve persistent memory context (KG facts + semantic vector context)
        context = self.context.retrieve_context(user_text)
        if context:
            print(f"\n[Context Injected]:\n{context}")

        # 2. Check for decoupled background work intent (Section 4.3 & 6)
        work_intent = self.intent_extractor.extract_intent(user_text)
        if work_intent:
            print(f"[Work Intent Detected]: {work_intent['action']} -> {work_intent['target']}")

        # 3. Generate response from local Epsilon LLM
        print("[SMAR] Thinking (Epsilon Engine)...")
        reply = await self.epsilon.generate(
            prompt=user_text,
            context=context,
            max_tokens=256,
            temperature=0.2
        )
        print(f"[SMAR]: {reply}")

        # 4. Spoken output (Gnani TTS)
        tts_audio = None
        if speak_output and reply:
            try:
                print("[SMAR] Speaking (Gnani TTS)...")
                tts_audio = await self.tts.synthesize(reply)
                if tts_audio:
                    self.audio.play_wav_bytes(tts_audio)
            except Exception as e:
                logger.warning(f"TTS synthesis/playback failed: {e}")

        # 5. Ingest conversation turn into self-updating memory
        ingest_stats = self.context.ingest_turn(user_text, assistant_reply=reply)

        return {
            "user_text": user_text,
            "assistant_reply": reply,
            "context_used": context,
            "work_intent": work_intent,
            "ingest_stats": ingest_stats,
            "has_tts_audio": tts_audio is not None
        }
