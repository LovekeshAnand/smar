"""
voice/gnani_stt.py
==================
Gnani / Vachana Speech-to-Text (ASR) REST API client (v3) for SMAR.
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
    Speech-to-Text client for Gnani / Vachana.ai REST API (v3).
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        language_code: Optional[str] = None,
    ):
        self.api_key = api_key or token or os.getenv("GNANI_API_KEY", "")
        self.endpoint_url = endpoint_url or os.getenv("GNANI_STT_URL", "https://api.vachana.ai/stt/v3")
        self.language_code = language_code or os.getenv("GNANI_LANGUAGE_CODE", "en-IN")

    def _get_headers(self) -> Dict[str, str]:
        headers = {}
        if self.api_key:
            headers["X-API-Key-ID"] = self.api_key
        return headers

    async def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language_code: Optional[str] = None,
        timeout: float = 30.0
    ) -> str:
        """
        Send audio bytes (WAV format) to Gnani/Vachana STT REST API and return the transcript string.
        """
        lang = language_code or self.language_code

        if not self.api_key:
            logger.warning("Gnani STT API Key not configured. Returning fallback mock transcript.")
            return "Hello SMAR, I like python programming and I need help with my tasks."

        files = {
            "audio_file": ("audio.wav", audio_bytes, "audio/wav")
        }
        data = {
            "language_code": lang,
            "preferred_language": lang,
            "format": "transcribe",
            "itn_native_numerals": "true",
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
                
                res_data = response.json()
                return self._extract_transcript(res_data)

        except httpx.HTTPStatusError as e:
            logger.error(f"Gnani STT HTTP error ({e.response.status_code}): {e.response.text}")
            raise RuntimeError(f"Gnani STT service error: {e.response.text}")
        except Exception as e:
            logger.error(f"Gnani STT request failed: {e}")
            raise

    def _extract_transcript(self, res_data: Any) -> str:
        """Extract transcript string across response schemas."""
        if isinstance(res_data, str):
            return res_data.strip()
        
        if isinstance(res_data, dict):
            # Direct key 'transcript' in v3 response
            if "transcript" in res_data and isinstance(res_data["transcript"], str):
                return res_data["transcript"].strip()
            
            for key in ["transcription", "text", "asr_output"]:
                if key in res_data and isinstance(res_data[key], str):
                    return res_data[key].strip()
            
            nested = res_data.get("data") or res_data.get("result")
            if isinstance(nested, dict):
                return self._extract_transcript(nested)
            elif isinstance(nested, list) and len(nested) > 0:
                return self._extract_transcript(nested[0])

        return str(res_data)
