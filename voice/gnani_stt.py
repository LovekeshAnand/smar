"""
voice/gnani_stt.py
==================
Gnani.ai Speech-to-Text (ASR) REST API client for SMAR.
"""

import os
import io
import json
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger("smar.voice.gnani_stt")


class GnaniSTT:
    """
    Speech-to-Text client for Gnani.ai REST service.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        language_code: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GNANI_API_KEY", "")
        self.token = token or os.getenv("GNANI_TOKEN", "")
        self.endpoint_url = endpoint_url or os.getenv("GNANI_STT_URL", "https://asr.gnani.ai/v1/recognize")
        self.language_code = language_code or os.getenv("GNANI_LANGUAGE_CODE", "en-IN")

    def _get_headers(self) -> Dict[str, str]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            headers["token"] = self.token
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language_code: Optional[str] = None,
        timeout: float = 20.0
    ) -> str:
        """
        Send audio bytes (WAV format) to Gnani STT REST API and return the transcript string.
        """
        lang = language_code or self.language_code

        # If credentials are not set, return simulated or prompt warning
        if not self.api_key and not self.token:
            logger.warning("Gnani STT API Key / Token not configured. Mocking transcription.")
            return "Hello SMAR, I like python programming and I need help with my tasks."

        files = {
            "audio": ("audio.wav", audio_bytes, "audio/wav")
        }
        data = {
            "language_code": lang,
            "sample_rate": str(sample_rate),
            "encoding": "LINEAR16",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.endpoint_url,
                    headers=self._get_headers(),
                    files=files,
                    data=data
                )
                response.raise_for_status()
                
                # Parse response payload
                res_data = response.json()
                return self._extract_transcript(res_data)

        except httpx.HTTPStatusError as e:
            logger.error(f"Gnani STT HTTP error ({e.response.status_code}): {e.response.text}")
            raise RuntimeError(f"Gnani STT service error: {e.response.text}")
        except Exception as e:
            logger.error(f"Gnani STT request failed: {e}")
            raise

    def _extract_transcript(self, res_data: Any) -> str:
        """Extract transcript string across common Gnani response schemas."""
        if isinstance(res_data, str):
            return res_data.strip()
        
        if isinstance(res_data, dict):
            # Direct keys
            for key in ["transcript", "transcription", "text", "asr_output"]:
                if key in res_data and isinstance(res_data[key], str):
                    return res_data[key].strip()
            
            # Nested in 'data' or 'result'
            nested = res_data.get("data") or res_data.get("result")
            if isinstance(nested, dict):
                return self._extract_transcript(nested)
            elif isinstance(nested, list) and len(nested) > 0:
                return self._extract_transcript(nested[0])

        return str(res_data)
