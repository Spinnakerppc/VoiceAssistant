#!/usr/bin/env python3
"""
assistant.py — CannaKit Voice Assistant (Push-to-Talk mode)
Press F12 to start recording, release to process and respond.
Run with: sudo ~/app/assistant/venv/bin/python3 ~/app/assistant.py
"""
import logging
import threading
import time
import sys
import os

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/home/pi/app/assistant/assistant.log"),
    ]
)
log = logging.getLogger("assistant")

sys.path.insert(0, os.path.dirname(__file__))
import tts
import stt
import intent
import keyboard
import subprocess
import numpy as np
import pyaudio

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HOTKEY        = "f12"
PYAUDIO_INDEX = 1  # hw:2,0 Fifine      # pulse device
SAMPLE_RATE   = 44100
MAX_RECORD_S  = 10     # max recording duration in seconds

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
STATE_IDLE       = "idle"
STATE_RECORDING  = "recording"
STATE_PROCESSING = "processing"
STATE_SPEAKING   = "speaking"

state      = STATE_IDLE
state_lock = threading.Lock()

def set_state(s):
    global state
    with state_lock:
        state = s
    log.info(f"[STATE] → {s}")

# ---------------------------------------------------------------------------
# Push-to-talk recording
# ---------------------------------------------------------------------------

def record_while_held(max_seconds=MAX_RECORD_S):
    """Record audio while F12 is held down using pw-record as pi user."""
    import tempfile
    import uuid
    wav_path = f"/tmp/cannakit_rec_{uuid.uuid4().hex[:8]}.wav"
    # Create as world-writable so pi user can write to it
    open(wav_path, 'wb').close()
    os.chmod(wav_path, 0o666)

    log.info("[PTT] Recording...")
    proc = subprocess.Popen(
        ["sudo", "-u", "pi", "env", "XDG_RUNTIME_DIR=/run/user/1000",
         "pw-record", "--target", "82",
         "--rate", "16000", "--channels", "1", wav_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    start = time.time()
    while keyboard.is_pressed(HOTKEY) and (time.time() - start) < max_seconds:
        time.sleep(0.05)
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except Exception:
        proc.kill()
    time.sleep(0.3)  # let pw-record flush and finalize WAV header
    duration = time.time() - start
    log.info(f"[PTT] Recorded {duration:.1f}s")
    return wav_path, duration
    return b"".join(frames), duration

def save_wav(raw_bytes, path):
    import wave
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(raw_bytes)

# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def on_f12_press():
    global state
    with state_lock:
        if state != STATE_IDLE:
            log.info("[PTT] Busy — ignoring keypress")
            return
    set_state(STATE_RECORDING)

    try:
        # 1. Record while key held
        wav_path, duration = record_while_held()

        if duration < 0.5:
            tts.speak("Too short — please hold F12 while speaking.")
            return

        # 2. Save to temp wav
        import tempfile

        # 3. Transcribe
        set_state(STATE_PROCESSING)
        tts.speak("Processing...")
        command = stt.transcribe(wav_path)

        if not command.strip():
            tts.speak("I didn't catch that. Please try again.")
            return

        log.info(f"[PTT] Command: {command!r}")

        # 4. Route intent
        response = intent.route(command)
        log.info(f"[PTT] Response: {response!r}")

        # 5. Speak response
        set_state(STATE_SPEAKING)
        tts.speak(response)

    except Exception as e:
        log.error(f"[PTT] Pipeline error: {e}")
        try:
            tts.speak("Sorry, something went wrong.")
        except Exception:
            pass
    finally:
        set_state(STATE_IDLE)
        log.info(f"[PTT] Ready — press {HOTKEY.upper()} to speak.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 50)
    log.info("  CannaKit Voice Assistant — Push-to-Talk")
    log.info("=" * 50)

    # Pre-load Whisper
    log.info("[ASSISTANT] Loading Whisper model...")
    stt._get_model()
    log.info("[ASSISTANT] Whisper ready.")

    tts.speak(f"CannaKit ready. Hold {HOTKEY.upper()} and speak your command.")

    # Register hotkey
    keyboard.on_press_key(HOTKEY, lambda _: threading.Thread(
        target=on_f12_press, daemon=True).start())

    log.info(f"[ASSISTANT] Listening for {HOTKEY.upper()} keypress. Ctrl+C to quit.")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        log.info("[ASSISTANT] Shutting down...")
        tts.speak("Goodbye.")

if __name__ == "__main__":
    main()
