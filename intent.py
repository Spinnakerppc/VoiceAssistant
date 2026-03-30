"""
intent.py — Intent detection and action routing
Parses transcribed text and returns a spoken response.
"""
import logging
import datetime
import sqlite3
import os
import urllib.request
import json

log = logging.getLogger(__name__)

# IoT database path
IOT_DB = os.path.expanduser("~/iot_app_data/database/sensor_data.db")

# Default location for weather (Open-Meteo — free, no API key)
WEATHER_LAT  = 34.7304
WEATHER_LON  = -86.5861
WEATHER_CITY = "Huntsville, AL"


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

def handle_time(_: str) -> str:
    now = datetime.datetime.now()
    return f"It's {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d')}."


def handle_date(_: str) -> str:
    now = datetime.datetime.now()
    return f"Today is {now.strftime('%A, %B %d, %Y')}."


def handle_weather(text: str) -> str:
    """Fetch current weather from Open-Meteo (free, no API key needed)."""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
            f"&current_weather=true"
            f"&hourly=relativehumidity_2m,apparent_temperature,precipitation_probability,weathercode"
            f"&temperature_unit=fahrenheit&windspeed_unit=mph&forecast_days=1"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "CannaKitAssistant/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())

        cw       = data["current_weather"]
        temp_f   = round(cw["temperature"])
        wind_mph = round(cw["windspeed"])
        wcode    = cw["weathercode"]

        # Humidity and feels-like from first hourly slot
        humidity   = data["hourly"]["relativehumidity_2m"][0]
        feels_like = round(data["hourly"]["apparent_temperature"][0])
        precip_pct = data["hourly"]["precipitation_probability"][0]

        # Human-readable condition from WMO weather code
        CONDITIONS = {
            0: "clear skies", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "icy fog",
            51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
            61: "light rain", 63: "rain", 65: "heavy rain",
            71: "light snow", 73: "snow", 75: "heavy snow",
            80: "rain showers", 81: "showers", 82: "heavy showers",
            95: "thunderstorms", 96: "thunderstorms with hail",
        }
        condition = CONDITIONS.get(wcode, f"weather code {wcode}")

        text_lower = text.lower()

        # Specific sub-queries
        if "rain" in text_lower or "umbrella" in text_lower:
            if precip_pct >= 50:
                return f"Yes, there's a {precip_pct}% chance of rain in {WEATHER_CITY}. Bring an umbrella."
            else:
                return f"Probably not — only a {precip_pct}% chance of rain in {WEATHER_CITY}."

        if "wind" in text_lower:
            return f"Wind speed in {WEATHER_CITY} is {wind_mph} miles per hour."

        if "humid" in text_lower:
            return f"Humidity in {WEATHER_CITY} is {humidity}%."

        # Full conditions (default)
        return (
            f"Current weather in {WEATHER_CITY}: {condition}, "
            f"{temp_f} degrees, feels like {feels_like}. "
            f"Humidity {humidity}%, wind {wind_mph} miles per hour. "
            f"Chance of rain: {precip_pct}%."
        )

    except Exception as e:
        log.error(f"[INTENT] Weather error: {e}")
        return "I couldn't fetch the weather right now. Check your internet connection."


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


def handle_nas_search(text: str) -> str:
    """Delegate to nas_search module."""
    try:
        from nas_search import handle_nas_search as _search
        return _search(text)
    except ImportError:
        log.error("[INTENT] nas_search.py not found — place it alongside intent.py")
        return "NAS search module is not installed."
    except Exception as e:
        log.error(f"[INTENT] NAS search error: {e}")
        return "Something went wrong while searching the NAS."


def handle_help(_: str) -> str:
    return (
        "You can ask me: what time is it, what's the weather, "
        "what's the temperature inside, humidity, system status, "
        "find a file on the NAS, or say hey Jarvis followed by your question."
    )


def handle_unknown(text: str) -> str:
    try:
        import urllib.request, json
        payload = json.dumps({
            "model": "qwen2.5:1.5b",
            "prompt": f"You are a helpful voice assistant. Answer briefly in 1-2 sentences: {text}",
            "stream": False
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("response", "I am not sure how to help with that.").strip()
    except Exception as e:
        log.error(f"[INTENT] LLM error: {e}")
        return f"I heard you say: {text}. I am not sure how to help with that yet."


# ---------------------------------------------------------------------------
# Intent routing table
# NOTE: weather is checked BEFORE sensor so "temperature outside" / "how hot
# is it" routes to weather, not the IoT database.
# ---------------------------------------------------------------------------

INTENTS = [
    (["what time", "what's the time", "current time"],              handle_time),
    (["what day", "what date", "today's date", "what's today"],     handle_date),
    (["weather", "forecast", "outside", "raining", "umbrella",
      "wind speed", "how hot", "how cold", "what's it like"],       handle_weather),
    (["temperature", "temp", "humidity", "pressure",
      "bilge", "motion", "sound", "battery", "sensor"],             handle_sensor),
    (["status", "how are you", "everything okay",
      "systems", "services running"],                                handle_status),
    (["find", "search for", "look for", "locate",
      "do you have", "is there a file", "open the file",
      "show me the file"],                                           handle_nas_search),
    (["help", "what can you do", "commands"],                       handle_help),
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
    tests = [
        "what time is it",
        "what's the weather",
        "is it raining",
        "wind speed",
        "what's the temperature",
        "system status",
        "find the lease agreement",
        "tell me a joke",
    ]
    for t in tests:
        print(f"Q: {t}")
        print(f"A: {route(t)}\n")
