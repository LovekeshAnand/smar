"""
voice/audio_io.py
=================
Cross-platform microphone capture and audio playback for SMAR.
"""

import os
import io
import wave
import time
import logging
from typing import Optional

logger = logging.getLogger("smar.voice.audio_io")

try:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False


class AudioIO:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels

    def record_seconds(self, duration_seconds: float = 5.0) -> bytes:
        """
        Record audio from the default microphone for a fixed duration.
        Returns WAV-encoded audio bytes.
        """
        if not AUDIO_LIBS_AVAILABLE:
            raise RuntimeError("sounddevice and soundfile libraries are required for microphone capture.")

        logger.info(f"Recording microphone for {duration_seconds}s at {self.sample_rate}Hz...")
        recording = sd.rec(
            int(duration_seconds * self.sample_rate),
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16'
        )
        sd.wait()
        logger.info("Recording complete.")

        # Pack into WAV bytes in-memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit PCM = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(recording.tobytes())

        return wav_buffer.getvalue()

    def record_until_silence(self, max_seconds: float = 10.0, silence_threshold: int = 500) -> bytes:
        """
        Record audio until a period of silence is detected or max_seconds is reached.
        """
        # Fallback to record_seconds if dynamic VAD is not required yet
        return self.record_seconds(min(max_seconds, 5.0))

    def play_wav_bytes(self, wav_bytes: bytes) -> None:
        """
        Play WAV audio bytes through the default speaker output.
        """
        if not AUDIO_LIBS_AVAILABLE:
            logger.warning("sounddevice not available; cannot play audio to speakers.")
            return

        try:
            wav_buffer = io.BytesIO(wav_bytes)
            data, fs = sf.read(wav_buffer, dtype='float32')
            sd.play(data, fs)
            sd.wait()
        except Exception as e:
            logger.error(f"Error playing audio bytes: {e}")

    def save_wav(self, wav_bytes: bytes, output_path: str) -> str:
        """Save WAV bytes to a file on disk."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(wav_bytes)
        return output_path
