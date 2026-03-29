"""
intent.py — Intent detection and action routing
Parses transcribed text and returns a spoken response.
"""
import logging
import datetime
import sqlite3
import os

log = logging.getLogger(__name__)

# IoT database path (from iot_env_config_10.py)
IOT_DB = os.path.expanduser("~/iot_app_data/database/sensor_data.db")


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

def handle_time(_: str) -> str:
    now = datetime.datetime.now()
    return f"It's {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d')}."


def handle_date(_: str) -> str:
    now = datetime.datetime.now()
    return f"Today is {now.strftime('%A, %B %d, %Y')}."


def handle_sensor(text: str) -> str:
    """Query the IoT database for the latest sensor reading."""
    sensor_map = {
        "temperature": "Temperature",
        "temp":        "Temperature",
        "humidity":    "Humidity",
        "pressure":    "Pressure",
        "bilge":       "Bilge",
        "motion":      "Motion",
        "sound":       "Sound",
        "battery":     "Battery",
    }

    matched = None
    for keyword, col in sensor_map.items():
        if keyword in text.lower():
            matched = col
            break

    if not matched:
        return "I'm not sure which sensor you mean. Try asking about temperature, humidity, or pressure."

    try:
        conn = sqlite3.connect(IOT_DB)
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {matched}, timestamp FROM sensor_data ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            value, timestamp = row
            return f"The latest {matched.lower()} reading is {value}, recorded at {timestamp}."
        else:
            return f"No {matched.lower()} data found in the database."
    except Exception as e:
        log.error(f"[INTENT] Database error: {e}")
        return f"I couldn't read the {matched.lower()} sensor right now."


def handle_status(_: str) -> str:
    """Report overall system status."""
    try:
        import subprocess
        services = ["iot-dev", "iot-anomaly", "cloudflared"]
        results = []
        for svc in services:
            result = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True
            )
            status = "running" if result.stdout.strip() == "active" else "stopped"
            results.append(f"{svc} is {status}")
        return "System status: " + ", ".join(results) + "."
    except Exception as e:
        log.error(f"[INTENT] Status check error: {e}")
        return "I couldn't check the system status right now."


def handle_help(_: str) -> str:
    return (
        "You can ask me: what time is it, what's the temperature, "
        "what's the humidity, system status, or just say hey cannakit "
        "followed by your question."
    )


def handle_unknown(text: str) -> str:
    return f"I heard you say: {text}. I'm not sure how to help with that yet."


# ---------------------------------------------------------------------------
# Intent routing table
# ---------------------------------------------------------------------------

INTENTS = [
    (["what time", "what's the time", "current time"],          handle_time),
    (["what day", "what date", "today's date", "what's today"], handle_date),
    (["temperature", "temp", "humidity", "pressure",
      "bilge", "motion", "sound", "battery", "sensor"],         handle_sensor),
    (["status", "how are you", "everything okay",
      "systems", "services running"],                            handle_status),
    (["help", "what can you do", "commands"],                    handle_help),
]


def route(text: str) -> str:
    """Match text to an intent and return a response string."""
    text_lower = text.lower().strip()

    if not text_lower:
        return "I didn't catch that. Could you repeat?"

    for keywords, handler in INTENTS:
        for kw in keywords:
            if kw in text_lower:
                log.info(f"[INTENT] Matched '{kw}' → {handler.__name__}")
                return handler(text)

    return handle_unknown(text)


if __name__ == "__main__":
    # Quick test
    tests = [
        "what time is it",
        "what's the temperature",
        "system status",
        "tell me a joke",
    ]
    for t in tests:
        print(f"Q: {t}")
        print(f"A: {route(t)}\n")
