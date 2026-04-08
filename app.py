import json
import os
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from flask import Flask, jsonify, render_template, request, url_for


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


def build_openapi_spec():
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Weather App API",
            "version": "1.0.0",
            "description": (
                "Get live weather conditions and a summarized 5-day forecast "
                "from OpenWeatherMap. Provide either a city name or a latitude "
                "and longitude pair."
            ),
        },
        "servers": [
            {
                "url": request.url_root.rstrip("/"),
                "description": "Current server",
            }
        ],
        "tags": [
            {
                "name": "Weather",
                "description": "Fetch current weather and a short forecast.",
            }
        ],
        "paths": {
            "/api/weather": {
                "get": {
                    "tags": ["Weather"],
                    "summary": "Get current weather and 5-day forecast",
                    "description": (
                        "Provide `city`, or provide both `lat` and `lon`. "
                        "If both city and coordinates are sent, city lookup "
                        "takes precedence."
                    ),
                    "parameters": [
                        {
                            "name": "city",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "City name to resolve before fetching weather.",
                            "example": "Mumbai",
                        },
                        {
                            "name": "lat",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "number", "format": "float"},
                            "description": "Latitude for coordinate-based lookup.",
                            "example": 19.076,
                        },
                        {
                            "name": "lon",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "number", "format": "float"},
                            "description": "Longitude for coordinate-based lookup.",
                            "example": 72.8777,
                        },
                        {
                            "name": "units",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "enum": ["metric", "imperial"],
                                "default": "metric",
                            },
                            "description": "Temperature and wind-speed unit system.",
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Weather returned successfully.",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/WeatherResponse"
                                    },
                                    "examples": {
                                        "cityLookup": {
                                            "summary": "Successful city search",
                                            "value": {
                                                "location": {
                                                    "city": "Mumbai",
                                                    "state": "Maharashtra",
                                                    "country": "IN",
                                                    "lat": 19.08,
                                                    "lon": 72.88,
                                                    "local_time": "6:45 PM",
                                                },
                                                "current": {
                                                    "condition": "Clouds",
                                                    "description": "Broken Clouds",
                                                    "icon": "04d",
                                                    "temperature": 31.4,
                                                    "feels_like": 35.2,
                                                    "humidity": 66,
                                                    "wind_speed": 4.1,
                                                },
                                                "forecast": [
                                                    {
                                                        "day": "Wed",
                                                        "date": "Apr 08",
                                                        "description": "Light Rain",
                                                        "icon": "10d",
                                                        "temp_min": 27.1,
                                                        "temp_max": 32.0,
                                                    }
                                                ],
                                                "units": {
                                                    "system": "metric",
                                                    "temperature": "C",
                                                    "wind_speed": "m/s",
                                                },
                                            },
                                        }
                                    },
                                }
                            },
                        },
                        "400": {
                            "description": "Missing location input or invalid coordinates.",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ErrorResponse"
                                    },
                                    "example": {
                                        "error": "Please enter a city name or use your current location."
                                    },
                                }
                            },
                        },
                        "404": {
                            "description": "No weather data found for the requested location.",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ErrorResponse"
                                    },
                                    "example": {
                                        "error": 'No weather data found for "Atlantis".'
                                    },
                                }
                            },
                        },
                        "500": {
                            "description": "The server is missing the OpenWeatherMap API key.",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ErrorResponse"
                                    },
                                    "example": {
                                        "error": (
                                            "OpenWeatherMap API key is missing. "
                                            "Set the OPENWEATHER_API_KEY environment variable."
                                        )
                                    },
                                }
                            },
                        },
                        "502": {
                            "description": "OpenWeatherMap could not be reached or returned an unexpected response.",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ErrorResponse"
                                    },
                                    "example": {
                                        "error": "Unable to reach OpenWeatherMap right now."
                                    },
                                }
                            },
                        },
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "Location": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "example": "Mumbai"},
                        "state": {"type": "string", "example": "Maharashtra"},
                        "country": {"type": "string", "example": "IN"},
                        "lat": {"type": "number", "format": "float", "example": 19.076},
                        "lon": {"type": "number", "format": "float", "example": 72.8777},
                        "local_time": {"type": "string", "example": "6:45 PM"},
                    },
                    "required": ["city", "state", "country", "lat", "lon", "local_time"],
                },
                "CurrentWeather": {
                    "type": "object",
                    "properties": {
                        "condition": {"type": "string", "example": "Clouds"},
                        "description": {"type": "string", "example": "Broken Clouds"},
                        "icon": {"type": "string", "example": "04d"},
                        "temperature": {"type": "number", "format": "float", "example": 31.4},
                        "feels_like": {"type": "number", "format": "float", "example": 35.2},
                        "humidity": {"type": "integer", "example": 66},
                        "wind_speed": {"type": "number", "format": "float", "example": 4.1},
                    },
                    "required": [
                        "condition",
                        "description",
                        "icon",
                        "temperature",
                        "feels_like",
                        "humidity",
                        "wind_speed",
                    ],
                },
                "ForecastDay": {
                    "type": "object",
                    "properties": {
                        "day": {"type": "string", "example": "Wed"},
                        "date": {"type": "string", "example": "Apr 08"},
                        "description": {"type": "string", "example": "Light Rain"},
                        "icon": {"type": "string", "example": "10d"},
                        "temp_min": {"type": "number", "format": "float", "example": 27.1},
                        "temp_max": {"type": "number", "format": "float", "example": 32.0},
                    },
                    "required": ["day", "date", "description", "icon", "temp_min", "temp_max"],
                },
                "Units": {
                    "type": "object",
                    "properties": {
                        "system": {"type": "string", "enum": ["metric", "imperial"]},
                        "temperature": {"type": "string", "example": "C"},
                        "wind_speed": {"type": "string", "example": "m/s"},
                    },
                    "required": ["system", "temperature", "wind_speed"],
                },
                "WeatherResponse": {
                    "type": "object",
                    "properties": {
                        "location": {"$ref": "#/components/schemas/Location"},
                        "current": {"$ref": "#/components/schemas/CurrentWeather"},
                        "forecast": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ForecastDay"},
                        },
                        "units": {"$ref": "#/components/schemas/Units"},
                    },
                    "required": ["location", "current", "forecast", "units"],
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string"},
                    },
                    "required": ["error"],
                },
            }
        },
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/openapi.json")
def openapi_spec():
    return jsonify(build_openapi_spec())


@app.route("/swagger")
@app.route("/docs")
def swagger_ui():
    return render_template("swagger.html", spec_url=url_for("openapi_spec"))


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
