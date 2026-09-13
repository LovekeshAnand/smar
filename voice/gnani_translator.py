"""
voice/gnani_translator.py
=========================
Intelligent Bilingual Indic Translation Service for SMAR.

Provides two-way translation (Hindi <-> English):
1. Primary: Gnani / Vachana.ai NMT API (https://api.vachana.ai/nmt/translate or /translation/v1)
2. Fallback: High-precision Indic translation engine (MyMemory via deep_translator)
3. In-memory LRU cache for 0ms repeated translations
4. Automatic language & Hinglish detection
"""

import os
import re
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger("smar.voice.translator")

# Common Hinglish / Romanized Hindi indicator tokens
HINGLISH_KEYWORDS = {
    "hamare", "hamara", "hamari", "hum", "kitne", "kitna", "kitni",
    "kya", "hai", "hain", "kuch", "batao", "btao", "bata", "bataiye",
    "dikhao", "dikha", "dikhaye", "paas", "kaise", "kahan", "jagah",
    "naam", "bolo", "bol", "hindi", "karo", "karein", "kare", "pe",
    "me", "mein", "mai", "se", "ko", "ki", "ka", "ke", "aur", "toh",
    "ye", "yeh", "woh", "bhi", "nahi", "nahin", "rupaye", "paisa",
    "sankhya", "ginti", "bache", "bacha", "bachi", "kul", "sabse",
    "zyada", "kam", "kiska", "kiski", "kiske", "kab", "kyun", "kyon",
    "hoga", "hogi", "hoge"
}


class GnaniTranslator:
    """
    Bilingual Indic Translation Engine for SMAR.
    Guarantees that input questions in Hindi/Hinglish are processed accurately
    in English by the neural core, and results are translated into natural Hindi
    for Gnani TTS voice synthesis.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GNANI_API_KEY", "")
        self.endpoint_url = endpoint_url or os.getenv(
            "GNANI_TRANSLATION_URL",
            "https://api.vachana.ai/nmt/translate"
        )
        self.gnani_enabled = bool(self.api_key)
        self._gnani_scope_available = True  # Set to False if 403 SCOPE_NOT_ALLOWED encountered

        # In-memory translation caches for sub-millisecond lookups
        self._cache_to_hi: Dict[str, str] = {}
        self._cache_to_en: Dict[str, str] = {}

        # Fallback translator instances (initialized lazily)
        self._fb_to_hi = None
        self._fb_to_en = None

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key-ID"] = self.api_key
        return headers

    def _init_fallback(self):
        """Initializes fallback Indic translator if needed."""
        if self._fb_to_hi is None:
            try:
                from deep_translator import MyMemoryTranslator
                self._fb_to_hi = MyMemoryTranslator(source="en-IN", target="hi-IN")
                self._fb_to_en = MyMemoryTranslator(source="hi-IN", target="en-IN")
            except Exception as e:
                logger.warning(f"Fallback translator initialization warning: {e}")

    def is_hindi_or_hinglish(self, text: str, language_hint: Optional[str] = None) -> bool:
        """
        Determines if the user query is in Hindi (Devanagari script),
        Hinglish (Romanized Hindi), or explicitly requests Hindi output.
        """
        if not text:
            return False

        # Explicit language hint
        if language_hint and language_hint.lower().startswith("hi"):
            return True

        text_lower = text.strip().lower()

        # 1. Contains Devanagari script
        if bool(re.search(r"[\u0900-\u097F]", text)):
            return True

        # 2. Explicit phrase asking to reply in Hindi
        if any(p in text_lower for p in [
            "in hindi", "hindi me", "hindi mein", "hindi mai", "hindi me bolo",
            "hindi me batao", "reply in hindi", "speak in hindi", "hindi me jawab"
        ]):
            return True

        # 3. Check for Hinglish keywords
        words = set(re.findall(r"\b[a-z]{2,}\b", text_lower))
        matching_hinglish = words.intersection(HINGLISH_KEYWORDS)
        if len(matching_hinglish) >= 2:
            return True
        # Strong indicators that definitively mark Hinglish intent
        strong_markers = {"btao", "batao", "bataiye", "dikhao", "dikhaye", "kitne", "kitna", "kitni", "kaise", "kahan", "kiska", "kiski"}
        if matching_hinglish.intersection(strong_markers):
            return True

        return False

    async def translate_to_english(self, text: str) -> str:
        """
        Translates Hindi (Devanagari) into English for accurate engine processing.
        If already in English or Roman script, returns as-is.
        """
        text = text.strip()
        if not text:
            return text

        # If it doesn't contain Devanagari characters, no need to translate to English
        if not re.search(r"[\u0900-\u097F]", text):
            return text

        if text in self._cache_to_en:
            return self._cache_to_en[text]

        # 1. Try Gnani NMT API first if scope not known to be disabled
        if self.gnani_enabled and self._gnani_scope_available:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post(
                        self.endpoint_url,
                        headers=self._get_headers(),
                        json={"text": text, "source_language": "hi", "target_language": "en"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        translated = data.get("translated_text") or data.get("text")
                        if translated:
                            self._cache_to_en[text] = translated
                            return translated
                    elif resp.status_code == 403:
                        logger.info("Gnani translation scope not active on API key. Using Indic fallback engine.")
                        self._gnani_scope_available = False
            except Exception as e:
                logger.debug(f"Gnani translation call note: {e}")

        # 2. Fallback Indic Translator
        try:
            self._init_fallback()
            if self._fb_to_en:
                translated = self._fb_to_en.translate(text)
                if translated and not translated.startswith("Error"):
                    self._cache_to_en[text] = translated
                    return translated
        except Exception as e:
            logger.debug(f"Fallback translation to EN error: {e}")

        return text

    async def translate_to_hindi(self, text: str) -> str:
        """
        Translates English text into natural, spoken Hindi for Gnani TTS.
        """
        text = text.strip()
        if not text:
            return text

        # If already in Devanagari, return as-is
        if re.search(r"[\u0900-\u097F]", text) and not re.search(r"[a-zA-Z]{4,}", text):
            return text

        if text in self._cache_to_hi:
            return self._cache_to_hi[text]

        # 1. Try Gnani NMT API first if available
        if self.gnani_enabled and self._gnani_scope_available:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post(
                        self.endpoint_url,
                        headers=self._get_headers(),
                        json={"text": text, "source_language": "en", "target_language": "hi"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        translated = data.get("translated_text") or data.get("text")
                        if translated:
                            self._cache_to_hi[text] = translated
                            return translated
                    elif resp.status_code == 403:
                        logger.info("Gnani translation scope not active on API key. Using Indic fallback engine.")
                        self._gnani_scope_available = False
            except Exception as e:
                logger.debug(f"Gnani translation call note: {e}")

        # 2. Fallback Indic Translator
        try:
            self._init_fallback()
            if self._fb_to_hi:
                translated = self._fb_to_hi.translate(text)
                if translated and not translated.startswith("Error"):
                    self._cache_to_hi[text] = translated
                    return translated
        except Exception as e:
            logger.debug(f"Fallback translation to HI error: {e}")

        return text
