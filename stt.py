"""
stt.py — Speech-to-Text via OpenAI Whisper
"""
import subprocess
import tempfile
import os
import logging
import time

log = logging.getLogger(__name__)
WHISPER_MODEL = "base.en"

def _get_fifine():
    from audio_devices import get_fifine_source
    return get_fifine_source()

def record_until_silence(max_duration: int = 8) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    log.info(f"[STT] Recording for up to {max_duration}s...")
    try:
        proc = subprocess.Popen(
            ["pw-record", "--target", _get_fifine(),
             "--rate", "16000", "--channels", "1", wav_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(max_duration)
        proc.terminate()
        proc.wait(timeout=2)
    except Exception as e:
        log.error(f"[STT] Recording error: {e}")
    return wav_path

def transcribe(wav_path: str) -> str:
    import whisper
    log.info(f"[STT] Transcribing...")
    try:
        model = _get_model()
        result = model.transcribe(wav_path, language="en", fp16=False)
        text = result["text"].strip()
        log.info(f"[STT] Transcribed: {text!r}")
        return text
    except Exception as e:
        log.error(f"[STT] Error: {e}")
        return ""
    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass

_model_cache = None
def _get_model():
    global _model_cache
    if _model_cache is None:
        import whisper
        log.info(f"[STT] Loading Whisper model: {WHISPER_MODEL}")
        _model_cache = whisper.load_model(WHISPER_MODEL)
        log.info("[STT] Whisper model loaded.")
    return _model_cache

def listen_and_transcribe(duration: int = 6) -> str:
    wav_path = record_until_silence(duration)
    return transcribe(wav_path)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Say something (6 seconds)...")
    print(f"You said: {listen_and_transcribe(6)}")

def transcribe_raw(raw_bytes, input_rate=44100):
    """Transcribe raw PCM bytes, resampling from input_rate to 16000Hz."""
    import whisper
    import numpy as np
    from scipy.signal import resample_poly
    from math import gcd
    import tempfile, wave, os

    audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if input_rate != 16000:
        g = gcd(input_rate, 16000)
        audio = resample_poly(audio, 16000//g, input_rate//g).astype(np.float32)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    with wave.open(wav_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes((audio * 32768).astype(np.int16).tobytes())

    try:
        model = _get_model()
        result = model.transcribe(wav_path, language="en", fp16=False)
        return result["text"].strip()
    finally:
        try: os.unlink(wav_path)
        except: pass
