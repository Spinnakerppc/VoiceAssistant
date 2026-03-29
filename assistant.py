"""
assistant.py — Main voice assistant loop
F12 key → STT → Intent → TTS
"""
import threading
import time
import sys
import os
import logging
import fcntl

# Module-level so all threads can access them
import sys as _sys
_sys.path.insert(0, '/home/pi/app')
import tts
import stt
import intent

STATE_IDLE       = "idle"
STATE_LISTENING  = "listening"
STATE_PROCESSING = "processing"
STATE_SPEAKING   = "speaking"

state      = STATE_IDLE
state_lock = threading.Lock()
log        = logging.getLogger("assistant")


def set_state(new_state: str):
    global state
    with state_lock:
        state = new_state
    log.info(f"[STATE] → {new_state}")


def on_trigger():
    import sys
    if "/home/pi/app" not in sys.path:
        sys.path.insert(0, "/home/pi/app")
    global state
    with state_lock:
        if state != STATE_IDLE:
            log.info("[ASSISTANT] Trigger ignored — not idle")
            return
        set_state(STATE_LISTENING)
    log.info("[ASSISTANT] F12 trigger — starting pipeline")
    try:
        set_state(STATE_SPEAKING)
        tts.speak("Yes?")
        set_state(STATE_LISTENING)
        log.info("[ASSISTANT] Listening for command...")
        command = stt.listen_and_transcribe(duration=6)
        if not command.strip():
            tts.speak("I didn't catch that. Please try again.")
            return
        log.info(f"[ASSISTANT] Command: {command!r}")
        set_state(STATE_PROCESSING)
        response = intent.route(command)
        log.info(f"[ASSISTANT] Response: {response!r}")
        set_state(STATE_SPEAKING)
        tts.speak(response)
    except Exception as e:
        import traceback
        log.error(f"[ASSISTANT] Pipeline error: {e}")
        log.error(traceback.format_exc())
        print(f"ERROR: {e}", flush=True)
        import traceback as tb; print(tb.format_exc(), flush=True)
        try:
            tts.speak("Sorry, something went wrong.")
        except Exception:
            pass
    finally:
        set_state(STATE_IDLE)
        log.info("[ASSISTANT] Ready.")


def f12_listener():
    import struct
    import glob
    import select
    KEY_F12   = 88
    EV_KEY    = 1
    KEY_PRESS = 1
    devices = glob.glob("/dev/input/event*")
    fds = []
    for dev in devices:
        try:
            fds.append(open(dev, "rb"))
        except PermissionError:
            pass
    if not fds:
        log.error("[F12] No readable input devices — check input group membership")
        return
    log.info(f"[F12] Monitoring {len(fds)} input device(s) for F12...")
    event_size = struct.calcsize("llHHI")
    while True:
        readable, _, _ = select.select(fds, [], [], 1.0)
        for f in readable:
            try:
                data = f.read(event_size)
                if len(data) < event_size:
                    continue
                _, _, ev_type, ev_code, ev_value = struct.unpack("llHHI", data)
                if ev_type == EV_KEY and ev_code == KEY_F12 and ev_value == KEY_PRESS:
                    with state_lock:
                        if state != STATE_IDLE: continue
                    log.info("[F12] F12 pressed — triggering assistant")
                    threading.Thread(target=on_trigger, daemon=True).start()
            except Exception:
                pass


LOCK_FILE = os.path.expanduser("~/app/assistant/assistant.lock")


def acquire_lock():
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[ASSISTANT] Another instance is already running. Exiting.", flush=True)
        sys.exit(1)
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def setup_logging():
    sys.stdout.reconfigure(line_buffering=True)
    log_dir = os.path.expanduser("~/app/assistant")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(log_dir, "assistant.log")),
        ],
        force=True,
    )


def main():
    _lock = acquire_lock()
    setup_logging()
    log.info("=" * 50)
    log.info("  CannaKit Voice Assistant Starting")
    log.info("=" * 50)
    log.info("[ASSISTANT] Loading Whisper model (first run may take a moment)...")
    stt._get_model()
    log.info("[ASSISTANT] Whisper ready.")
    tts.speak("CannaKit voice assistant ready. Press F12 to begin.")
    t = threading.Thread(target=f12_listener, daemon=True)
    t.start()
    log.info("[ASSISTANT] Listening for F12 keypress. Ctrl+C to quit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("[ASSISTANT] Shutting down...")
        tts.speak("Goodbye.")
        log.info("[ASSISTANT] Stopped.")


if __name__ == "__main__":
    main()
