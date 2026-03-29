"""
wakeword.py — Wake word detection using Porcupine (Picovoice)
Reliable ARM64/Python 3.13 compatible wake word detection.
Wake word: "jarvis" (say "jarvis" or "hey jarvis")
"""
import logging
import numpy as np
import pyaudio
import threading
import time
import pvporcupine

log = logging.getLogger(__name__)

WAKE_WORD     = "jarvis"   # change to "alexa" if preferred
PYAUDIO_INDEX = 8          # pulse device — routes through PipeWire
SENSITIVITY   = 0.7        # 0.0-1.0, higher = more sensitive but more false positives

class WakeWordDetector:
    def __init__(self, on_detected_callback):
        self.callback = on_detected_callback
        self.running  = False
        self._thread  = None
        self._porcupine = None

    def _load_model(self):
        self._porcupine = pvporcupine.create(
            keywords=[WAKE_WORD],
            sensitivities=[SENSITIVITY]
        )
        log.info(f"[WAKEWORD] Porcupine ready — wake word: '{WAKE_WORD}'")
        log.info(f"[WAKEWORD] Sample rate: {self._porcupine.sample_rate} "
                 f"Frame length: {self._porcupine.frame_length}")

    def _listen_loop(self):
        pa = pyaudio.PyAudio()
        stream = pa.open(
            rate=self._porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            input_device_index=PYAUDIO_INDEX,
            frames_per_buffer=self._porcupine.frame_length,
        )
        log.info("[WAKEWORD] Listening...")
        try:
            while self.running:
                raw = stream.read(
                    self._porcupine.frame_length,
                    exception_on_overflow=False
                )
                pcm = np.frombuffer(raw, dtype=np.int16)
                result = self._porcupine.process(pcm)
                if result >= 0:
                    log.info(f"[WAKEWORD] *** '{WAKE_WORD}' detected! ***")
                    time.sleep(0.2)
                    self.callback()
        except Exception as e:
            log.error(f"[WAKEWORD] Error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            self._porcupine.delete()

    def start(self):
        if self.running:
            return
        self._load_model()
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=3)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    def on_wake():
        print("\n*** WAKE WORD DETECTED! ***\n")
    detector = WakeWordDetector(on_detected_callback=on_wake)
    detector.start()
    print(f"Say '{WAKE_WORD}'... (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        detector.stop()
