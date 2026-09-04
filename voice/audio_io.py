"""
voice/audio_io.py
=================
Cross-platform microphone capture and audio playback for SMAR.
Uses native Windows multimedia (winsound) for instant playback when on Windows,
with sounddevice / soundfile as cross-platform audio engine.
"""

import os
import io
import wave
import sys
import logging
from typing import Optional

logger = logging.getLogger("smar.voice.audio_io")

# Check native Windows audio
HAVE_WINSOUND = False
if sys.platform == "win32":
    try:
        import winsound
        HAVE_WINSOUND = True
    except ImportError:
        pass

# Check cross-platform sounddevice & soundfile
HAVE_SOUNDDEVICE = False
try:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
    HAVE_SOUNDDEVICE = True
except ImportError:
    pass


class AudioIO:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels

    def record_seconds(self, duration_seconds: float = 5.0) -> bytes:
        """
        Record audio from the default microphone for a fixed duration.
        Returns WAV-encoded audio bytes.
        """
        if not HAVE_SOUNDDEVICE:
            raise RuntimeError("sounddevice is required for microphone recording.")

        logger.info(f"Recording microphone for {duration_seconds}s at {self.sample_rate}Hz...")
        recording = sd.rec(
            int(duration_seconds * self.sample_rate),
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16'
        )
        sd.wait()
        logger.info("Recording complete.")

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit PCM = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(recording.tobytes())

        return wav_buffer.getvalue()

    def play_wav_bytes(self, wav_bytes: bytes) -> None:
        """
        Play WAV audio bytes through the default speaker output.
        Uses native winsound on Windows for instantaneous playback.
        """
        if not wav_bytes:
            return

        # 1. Native Windows fast audio playback
        if HAVE_WINSOUND:
            try:
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
                return
            except Exception as e:
                logger.debug(f"winsound failed ({e}), falling back to sounddevice")

        # 2. sounddevice / soundfile playback
        if HAVE_SOUNDDEVICE:
            try:
                wav_buffer = io.BytesIO(wav_bytes)
                data, fs = sf.read(wav_buffer, dtype='float32')
                sd.play(data, fs)
                sd.wait()
                return
            except Exception as e:
                logger.error(f"sounddevice audio playback failed: {e}")
                return

        logger.warning("No audio playback driver available (winsound or sounddevice required).")

    def save_wav(self, wav_bytes: bytes, output_path: str) -> str:
        """Save WAV bytes to a file on disk."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(wav_bytes)
        return output_path
