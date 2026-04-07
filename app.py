import json
import os
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from flask import Flask, jsonify, render_template, request


def load_env_file(filename=".env"):
    env_path = os.path.join(os.path.dirname(__file__), filename)

    if not os.path.exists(env_path):
        return

    with open(env_path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            if line.startswith("export "):
                line = line[7:].strip()

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")

            if key:
                os.environ.setdefault(key, value)


load_env_file()


app = Flask(__name__)

GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

UNIT_MAP = {
    "metric": {"temperature": "C", "wind_speed": "m/s"},
    "imperial": {"temperature": "F", "wind_speed": "mph"},
}


class WeatherApiError(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_units(value):
    return value if value in UNIT_MAP else "metric"


def fetch_openweather_json(base_url, params):
    url = f"{base_url}?{urlencode(params)}"

    try:
        with urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 404:
            raise WeatherApiError("Location not found.", 404) from error
        if error.code == 401:
            raise WeatherApiError(
                "Weather service rejected the request. Check your OpenWeatherMap API key.",
                502,
            ) from error
        raise WeatherApiError("Weather service returned an unexpected response.", 502) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise WeatherApiError("Unable to reach OpenWeatherMap right now.", 502) from error


def resolve_location(city, api_key):
    results = fetch_openweather_json(
        GEOCODING_URL,
        {"q": city, "limit": 1, "appid": api_key},
    )

    if not results:
        raise WeatherApiError(f'No weather data found for "{city}".', 404)

    return results[0]


def get_location_params(api_key):
    city = request.args.get("city", "").strip()
    lat = request.args.get("lat", "").strip()
    lon = request.args.get("lon", "").strip()

    if city:
        resolved = resolve_location(city, api_key)
        return {
            "lat": resolved["lat"],
            "lon": resolved["lon"],
            "resolved_location": {
                "name": resolved.get("name", city),
                "state": resolved.get("state", ""),
                "country": resolved.get("country", ""),
            },
        }

    if lat and lon:
        try:
            return {
                "lat": float(lat),
                "lon": float(lon),
                "resolved_location": None,
            }
        except ValueError as error:
            raise WeatherApiError("Latitude and longitude must be valid numbers.", 400) from error

    raise WeatherApiError("Please enter a city name or use your current location.", 400)


def format_local_datetime(timestamp, timezone_offset):
    return datetime.fromtimestamp(timestamp, tz=timezone.utc) + timedelta(
        seconds=timezone_offset
    )


def summarize_forecast(forecast_data):
    timezone_offset = forecast_data.get("city", {}).get("timezone", 0)
    grouped = {}

    for entry in forecast_data.get("list", []):
        local_dt = format_local_datetime(entry["dt"], timezone_offset)
        date_key = local_dt.date().isoformat()
        grouped.setdefault(date_key, []).append((local_dt, entry))

    daily_forecast = []

    for items in grouped.values():
        selected_dt, selected_entry = min(
            items,
            key=lambda item: abs((item[0].hour + item[0].minute / 60) - 12),
        )
        weather = selected_entry.get("weather", [{}])[0]
        min_temps = [
            entry.get("main", {}).get("temp_min")
            for _, entry in items
            if isinstance(entry.get("main", {}).get("temp_min"), (int, float))
        ]
        max_temps = [
            entry.get("main", {}).get("temp_max")
            for _, entry in items
            if isinstance(entry.get("main", {}).get("temp_max"), (int, float))
        ]

        daily_forecast.append(
            {
                "day": selected_dt.strftime("%a"),
                "date": selected_dt.strftime("%b %d"),
                "description": weather.get("description", "").title(),
                "icon": weather.get("icon", ""),
                "temp_min": min(min_temps) if min_temps else None,
                "temp_max": max(max_temps) if max_temps else None,
            }
        )

        if len(daily_forecast) == 5:
            break

    return daily_forecast


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/weather")
def get_weather():
    api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
    units = normalize_units(request.args.get("units", "metric").strip())

    if not api_key:
        return jsonify(
            {
                "error": (
                    "OpenWeatherMap API key is missing. "
                    "Set the OPENWEATHER_API_KEY environment variable."
                )
            }
        ), 500

    try:
        location_params = get_location_params(api_key)
        base_params = {
            "lat": location_params["lat"],
            "lon": location_params["lon"],
            "appid": api_key,
            "units": units,
        }
        current_data = fetch_openweather_json(CURRENT_WEATHER_URL, base_params)
        forecast_data = fetch_openweather_json(FORECAST_URL, base_params)
    except WeatherApiError as error:
        return jsonify({"error": error.message}), error.status_code

    weather = current_data.get("weather", [{}])[0]
    main = current_data.get("main", {})
    wind = current_data.get("wind", {})
    sys_data = current_data.get("sys", {})
    coord = current_data.get("coord", {})
    timezone_offset = current_data.get("timezone", 0)
    resolved_location = location_params["resolved_location"] or {}
    local_time = format_local_datetime(current_data.get("dt", 0), timezone_offset)

    return jsonify(
        {
            "location": {
                "city": current_data.get("name")
                or resolved_location.get("name")
                or request.args.get("city", "").strip(),
                "state": resolved_location.get("state", ""),
                "country": sys_data.get("country", "") or resolved_location.get("country", ""),
                "lat": coord.get("lat", location_params["lat"]),
                "lon": coord.get("lon", location_params["lon"]),
                "local_time": local_time.strftime("%I:%M %p").lstrip("0"),
            },
            "current": {
                "condition": weather.get("main", ""),
                "description": weather.get("description", "").title(),
                "icon": weather.get("icon", ""),
                "temperature": main.get("temp"),
                "feels_like": main.get("feels_like"),
                "humidity": main.get("humidity"),
                "wind_speed": wind.get("speed"),
            },
            "forecast": summarize_forecast(forecast_data),
            "units": {
                "system": units,
                "temperature": UNIT_MAP[units]["temperature"],
                "wind_speed": UNIT_MAP[units]["wind_speed"],
            },
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
