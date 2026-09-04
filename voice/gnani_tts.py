"""
voice/gnani_tts.py
==================
Gnani / Vachana.ai Text-to-Speech (TTS) SSE Client for SMAR.
Uses timbre-v2.5 streaming model via Server-Sent Events (SSE).
"""

import os
import json
import base64
import logging
from typing import Optional, Dict, Any, AsyncGenerator
import httpx

logger = logging.getLogger("smar.voice.gnani_tts")


class GnaniTTS:
    """
    Text-to-Speech client for Gnani / Vachana.ai SSE REST API.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        voice: Optional[str] = None,
        model: str = "timbre-v2.5",
        sample_rate: int = 16000,
    ):
        self.api_key = api_key or os.getenv("GNANI_API_KEY", "")
        self.endpoint_url = endpoint_url or os.getenv("GNANI_TTS_URL", "https://api.vachana.ai/api/v1/tts/sse")
        self.voice = voice or os.getenv("GNANI_VOICE_NAME", "Deepak")  # e.g. Deepak, Nalini, Bhavna
        self.model = model
        self.sample_rate = sample_rate

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["X-API-Key-ID"] = self.api_key
        return headers

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        timeout: float = 30.0
    ) -> Optional[bytes]:
        """
        Synthesizes text into complete WAV audio bytes by consuming the SSE stream.
        """
        if not text.strip():
            return None

        if not self.api_key:
            logger.warning("Gnani TTS API key not configured. Skipping synthesis.")
            return None

        selected_voice = voice or self.voice

        payload = {
            "audio_config": {
                "bitrate": "192k",
                "container": "wav",
                "encoding": "linear_pcm",
                "num_channels": 1,
                "sample_rate": self.sample_rate,
                "sample_width": 2
            },
            "model": self.model,
            "text": text.strip(),
            "voice": selected_voice
        }

        audio_chunks = []

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    self.endpoint_url,
                    headers=self._get_headers(),
                    json=payload
                ) as response:
                    if response.status_code != 200:
                        err_body = await response.aread()
                        logger.error(f"Gnani TTS HTTP error ({response.status_code}): {err_body.decode('utf-8', errors='ignore')}")
                        return None

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            raw_json = line[6:].strip()
                            try:
                                data = json.loads(raw_json)
                                b64_chunk = data.get("audio")
                                if b64_chunk:
                                    audio_chunks.append(base64.b64decode(b64_chunk))
                            except Exception:
                                continue

            if not audio_chunks:
                logger.warning("No audio chunks received from TTS SSE stream.")
                return None

            return b"".join(audio_chunks)

        except Exception as e:
            logger.error(f"Gnani TTS synthesis failed: {e}")
            return None

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        timeout: float = 30.0
    ) -> AsyncGenerator[bytes, None]:
        """
        Streams raw decoded audio bytes chunk-by-chunk for low latency playback.
        """
        if not text.strip() or not self.api_key:
            return

        payload = {
            "audio_config": {
                "bitrate": "192k",
                "container": "wav",
                "encoding": "linear_pcm",
                "num_channels": 1,
                "sample_rate": self.sample_rate,
                "sample_width": 2
            },
            "model": self.model,
            "text": text.strip(),
            "voice": voice or self.voice
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    self.endpoint_url,
                    headers=self._get_headers(),
                    json=payload
                ) as response:
                    if response.status_code == 200:
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    data = json.loads(line[6:].strip())
                                    chunk = data.get("audio")
                                    if chunk:
                                        yield base64.b64decode(chunk)
                                except Exception:
                                    continue
        except Exception as e:
            logger.error(f"TTS stream error: {e}")
