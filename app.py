from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

app = Flask(__name__)

DEFAULT_CITY = "Dhaka"

WMO_CODES = {
    0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    61: "Light Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    71: "Light Snow", 73: "Moderate Snow", 75: "Heavy Snow",
    77: "Snow Grains",
    80: "Rain Showers", 81: "Showers", 82: "Violent Showers",
    85: "Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm + Hail", 99: "Heavy Thunderstorm"
}


def geocode_city(city_name):
    """Use Nominatim to get lat/lon for a city."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city_name, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "WeatherNow/1.0 (education project)"}
    resp = requests.get(url, params=params, headers=headers, timeout=8)
    data = resp.json()
    if not data:
        return None
    place = data[0]
    addr = place.get("address", {})
    city = (addr.get("city") or addr.get("town") or addr.get("village")
            or addr.get("municipality") or place["display_name"].split(",")[0])
    country = addr.get("country", "")
    return {
        "lat": float(place["lat"]),
        "lon": float(place["lon"]),
        "city": city,
        "country": country,
    }


def get_timezone(lat, lon):
    """Get timezone string from timeapi.io."""
    try:
        url = f"https://timeapi.io/api/timezone/coordinate?latitude={lat}&longitude={lon}"
        resp = requests.get(url, timeout=6)
        return resp.json().get("timeZone", "UTC")
    except Exception:
        return "UTC"


def get_weather(lat, lon):
    """Fetch current weather from Open-Meteo."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
        "wind_speed_unit": "kmh",
        "forecast_days": 1,
    }
    resp = requests.get(url, params=params, timeout=8)
    cur = resp.json().get("current", {})
    return {
        "temp": round(cur.get("temperature_2m", 0)),
        "feels": round(cur.get("apparent_temperature", 0)),
        "humidity": cur.get("relative_humidity_2m", 0),
        "wind": round(cur.get("wind_speed_10m", 0)),
        "condition": WMO_CODES.get(cur.get("weather_code", 0), "Unknown"),
    }


def get_local_time(timezone_str):
    """Return formatted local time and date for a timezone."""
    try:
        tz = ZoneInfo(timezone_str)
        now = datetime.now(tz)
        return now.strftime("%H:%M:%S"), now.strftime("%a, %d %b %Y")
    except (ZoneInfoNotFoundError, Exception):
        now = datetime.utcnow()
        return now.strftime("%H:%M:%S"), now.strftime("%a, %d %b %Y") + " (UTC)"


@app.route("/")
def index():
    return render_template("index.html", default_city=DEFAULT_CITY)


@app.route("/weather", methods=["POST"])
def weather():
    global DEFAULT_CITY
    data = request.get_json()
    city_input = data.get("city", "").strip()
    action = data.get("action", "search")

    # Set default city action
    if action == "set_default":
        if city_input:
            DEFAULT_CITY = city_input
            return jsonify({"status": "ok", "default_city": DEFAULT_CITY})
        return jsonify({"status": "error", "message": "Empty city name"})

    # If blank/spaces → use default
    if not city_input:
        city_input = DEFAULT_CITY

    # Geocode
    try:
        geo = geocode_city(city_input)
    except Exception:
        return jsonify({"status": "error", "message": "Connection error. Check internet."})

    if not geo:
        return jsonify({"status": "not_found", "query": city_input})

    # Timezone + weather + time
    try:
        tz_str = get_timezone(geo["lat"], geo["lon"])
        weather_data = get_weather(geo["lat"], geo["lon"])
        local_time, local_date = get_local_time(tz_str)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Data fetch failed: {str(e)}"})

    return jsonify({
        "status": "ok",
        "city": geo["city"],
        "country": geo["country"],
        "time": local_time,
        "date": local_date,
        "timezone": tz_str,
        **weather_data,
    })


@app.route("/default_city")
def get_default():
    return jsonify({"default_city": DEFAULT_CITY})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)