"""
wakeword.py — Wake word detection using OpenWakeWord
Free, no API key required. Uses built-in "hey_jarvis" model.
"""
import logging
import numpy as np
import subprocess
import threading
import time

log = logging.getLogger(__name__)

FIFINE_TARGET  = "77"       # PipeWire source node ID — update if it changes
SAMPLE_RATE    = 16000
CHUNK_DURATION = 0.08       # 80ms per chunk
CHUNK_SAMPLES  = int(SAMPLE_RATE * CHUNK_DURATION)
THRESHOLD      = 0.5        # detection confidence threshold
WAKE_WORD_PATH = "/home/pi/app/assistant/venv/lib/python3.13/site-packages/openwakeword/resources/models/hey_jarvis_v0.1.onnx"


class WakeWordDetector:
    def __init__(self, on_detected_callback):
        self.callback = on_detected_callback
        self.running  = False
        self._thread  = None
        self._model   = None

    def _load_model(self):
        from openwakeword.model import Model
        log.info(f"[WAKEWORD] Loading model: {WAKE_WORD_PATH}")
        self._model = Model(wakeword_model_paths=[WAKE_WORD_PATH])
        log.info("[WAKEWORD] Model loaded.")

    def _listen_loop(self):
        log.info("[WAKEWORD] Starting listen loop...")

        proc = subprocess.Popen(
            ["pw-record",
             "--target", FIFINE_TARGET,
             "--rate",    str(SAMPLE_RATE),
             "--channels", "1",
             "--format",  "s16",
             "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        bytes_per_chunk = CHUNK_SAMPLES * 2  # 16-bit = 2 bytes per sample

        try:
            while self.running:
                raw = proc.stdout.read(bytes_per_chunk)
                if not raw or len(raw) < bytes_per_chunk:
                    time.sleep(0.01)
                    continue

                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                prediction = self._model.predict(audio)

                for model_name, score in prediction.items():
                    if score >= THRESHOLD:
                        log.info(f"[WAKEWORD] Detected! model={model_name} score={score:.3f}")
                        time.sleep(0.3)
                        self.callback()
                        self._model.reset()
                        break

        except Exception as e:
            log.error(f"[WAKEWORD] Listen loop error: {e}")
        finally:
            proc.terminate()
            proc.wait()
            log.info("[WAKEWORD] Listen loop stopped.")

    def start(self):
        if self.running:
            return
        self._load_model()
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info("[WAKEWORD] Detector started.")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=3)
        log.info("[WAKEWORD] Detector stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def on_wake():
        print("\n*** Wake word detected! Say your command... ***\n")

    detector = WakeWordDetector(on_detected_callback=on_wake)
    detector.start()

    print(f"Listening for '{WAKE_WORD}'... (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        detector.stop()
