"""
tests/test_voice_stt_tts.py
===========================
Unit test for Gnani STT and TTS clients.
"""

import unittest
from voice.gnani_stt import GnaniSTT
from voice.gnani_tts import GnaniTTS


class TestVoiceClients(unittest.TestCase):
    def test_stt_header_generation(self):
        stt = GnaniSTT(api_key="test_key")
        headers = stt._get_headers()
        self.assertEqual(headers.get("X-API-Key-ID"), "test_key")

    def test_stt_transcript_parsing(self):
        stt = GnaniSTT()
        # Direct string
        self.assertEqual(stt._extract_transcript("hello world"), "hello world")
        # Nested dict
        res1 = {"transcript": "send email to Sweta"}
        self.assertEqual(stt._extract_transcript(res1), "send email to Sweta")
        # Gnani data wrapper
        res2 = {"data": {"transcription": "I like python"}}
        self.assertEqual(stt._extract_transcript(res2), "I like python")

    def test_tts_header_generation(self):
        tts = GnaniTTS(api_key="tts_key")
        headers = tts._get_headers()
        self.assertEqual(headers.get("X-API-Key-ID"), "tts_key")
        self.assertEqual(headers.get("Content-Type"), "application/json")


if __name__ == "__main__":
    unittest.main()
