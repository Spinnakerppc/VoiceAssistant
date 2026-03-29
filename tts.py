"""
tts.py — Text-to-Speech via Piper + PipeWire
"""
import subprocess
import tempfile
import os
import logging

log = logging.getLogger(__name__)

PIPER_BIN   = "/home/pi/config/piper/piper/piper"
PIPER_MODEL = "/home/pi/config/piper/models/en_US-lessac-medium.onnx"

def _get_jabra():
    # Run wpctl as pi user since we may be running as root
    import subprocess
    result = subprocess.run(
        ["sudo", "-u", "pi", "wpctl", "status"],
        capture_output=True, text=True
    )
    import re
    for line in result.stdout.splitlines():
        if "Jabra" in line and "Analog Stereo" in line:
            m = re.search(r'(\d+)\.', line)
            if m:
                return m.group(1)
    # fallback: use wpctl get-default
    try:
        r2 = subprocess.run(
            ["sudo", "-u", "pi", "env", "XDG_RUNTIME_DIR=/run/user/1000",
             "wpctl", "get-default", "audio/sink"],
            capture_output=True, text=True
        )
        m = re.search(r"(\d+)\.", r2.stdout)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "57"  # hardcoded fallback

def speak(text: str) -> bool:
    log.info(f"[TTS] Speaking: {text!r}")
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="/tmp") as f:
            wav_path = f.name
        os.chmod(wav_path, 0o644)

        piper_proc = subprocess.run(
            [PIPER_BIN, "--model", PIPER_MODEL, "--output_file", wav_path],
            input=text.encode(), capture_output=True, timeout=30,
        )
        if piper_proc.returncode != 0:
            log.error(f"[TTS] Piper error: {piper_proc.stderr.decode()}")
            return False

        play_proc = subprocess.run(
            ["sudo", "-u", "pi", "-E", "XDG_RUNTIME_DIR=/run/user/1000", "pw-play", "--target", _get_jabra(), wav_path],
            capture_output=True, timeout=30,
        )
        if play_proc.returncode != 0:
            log.error(f"[TTS] pw-play error: {play_proc.stderr.decode()}")
            return False

        return True
    except Exception as e:
        log.error(f"[TTS] Error: {e}")
        return False
    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass

if __name__ == "__main__":
    speak("Hello, I am your CannaKit voice assistant. I am ready.")
