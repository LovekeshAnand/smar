"""
voice/gnani_tts.py
==================
Gnani.ai Text-to-Speech (TTS) REST API client for SMAR.
"""

import os
import base64
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger("smar.voice.gnani_tts")


class GnaniTTS:
    """
    Text-to-Speech client for Gnani.ai REST service.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        language_code: Optional[str] = None,
        voice_gender: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GNANI_API_KEY", "")
        self.token = token or os.getenv("GNANI_TOKEN", "")
        self.endpoint_url = endpoint_url or os.getenv("GNANI_TTS_URL", "https://tts.gnani.ai/v1/synthesize")
        self.language_code = language_code or os.getenv("GNANI_LANGUAGE_CODE", "en-IN")
        self.voice_gender = voice_gender or os.getenv("GNANI_VOICE_GENDER", "female")

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            headers["token"] = self.token
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def synthesize(
        self,
        text: str,
        language_code: Optional[str] = None,
        voice_gender: Optional[str] = None,
        timeout: float = 20.0
    ) -> Optional[bytes]:
        """
        Synthesize text into WAV audio bytes using Gnani TTS REST API.
        """
        if not text.strip():
            return None

        # Fallback simulation if no keys provided yet
        if not self.api_key and not self.token:
            logger.warning("Gnani TTS credentials not configured. Skipping synthesis.")
            return None

        payload = {
            "text": text,
            "language": language_code or self.language_code,
            "voice": voice_gender or self.voice_gender,
            "audio_format": "wav"
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.endpoint_url,
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()

                # Check content type
                content_type = response.headers.get("content-type", "")
                if "audio" in content_type or "octet-stream" in content_type:
                    return response.content

                # Could be JSON response with base64 audio
                try:
                    res_json = response.json()
                    b64_audio = (
                        res_json.get("audio_content") or
                        res_json.get("audio") or
                        res_json.get("data", {}).get("audio")
                    )
                    if b64_audio:
                        return base64.b64decode(b64_audio)
                except Exception:
                    pass

                return response.content

        except Exception as e:
            logger.error(f"Gnani TTS synthesis failed: {e}")
            return None
