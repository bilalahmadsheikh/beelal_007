"""
voice_tools.py — BilalAgent v2.0 Voice Input
Uses OpenAI Whisper (tiny model) for voice-to-text transcription.
Optional — requires: pip install openai-whisper sounddevice numpy
"""

import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

_whisper_model = None


def load_whisper_model():
    """Load the Whisper tiny model (39MB, loads once)."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    try:
        import whisper
        print("[VOICE] Loading Whisper tiny model...")
        _whisper_model = whisper.load_model("tiny")
        print("[VOICE] Whisper model loaded")
        return _whisper_model
    except ImportError:
        print("[VOICE] Whisper not installed. Run: pip install openai-whisper")
        return None
    except Exception as e:
        print(f"[VOICE] Failed to load Whisper: {e}")
        return None


def listen_and_transcribe(seconds: int = 5) -> str:
    """
    Record audio for `seconds` and transcribe with Whisper.

    Returns:
        Transcribed text or empty string on failure.
    """
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        print("[VOICE] sounddevice/numpy not installed. Run: pip install sounddevice numpy")
        return ""

    model = load_whisper_model()
    if model is None:
        return ""

    sample_rate = 16000

    try:
        print(f"[VOICE] 🎤 Listening for {seconds} seconds...")
        audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate,
                       channels=1, dtype="float32")
        sd.wait()
        print("[VOICE] Recording complete, transcribing...")

        # Flatten to 1D
        audio_flat = audio.flatten()

        # Transcribe
        result = model.transcribe(audio_flat, fp16=False, language="en")
        text = result.get("text", "").strip()

        print(f"[VOICE] Transcribed: \"{text}\"")
        return text

    except Exception as e:
        print(f"[VOICE] Error: {e}")
        return ""


def activate_voice() -> str:
    """
    Show "Listening..." prompt, record, transcribe, and return text.
    Can be used by agent.py or dashboard.
    """
    print("\n" + "=" * 40)
    print("  🎤 Voice Input — Say your command")
    print("=" * 40)

    text = listen_and_transcribe(seconds=5)

    if text:
        print(f"\n  Heard: \"{text}\"")
        return text
    else:
        print("\n  No speech detected.")
        return ""


if __name__ == "__main__":
    text = activate_voice()
    if text:
        print(f"\nWould run: python agent.py \"{text}\"")
