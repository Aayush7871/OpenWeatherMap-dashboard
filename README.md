# Weather App

A simple Flask weather app that fetches current weather by city using the OpenWeatherMap API.

## Features

- Search weather by city name
- Use current location with browser GPS
- View current temperature
- View humidity
- View wind speed
- Toggle between Celsius and Fahrenheit
- View a 5-day forecast
- See weather icons for current conditions and forecast
- Switch between light and dark mode
- Responsive card-based interface with loading feedback

## Setup

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root and add your OpenWeatherMap API key:

   ```env
   OPENWEATHER_API_KEY=your_api_key_here
   ```

   You can copy `.env.example` to `.env` and replace the placeholder value.

4. Run the app:

   ```powershell
   python app.py
   ```

5. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Notes

- The app loads `OPENWEATHER_API_KEY` from a local `.env` file automatically.
- Exported environment variables still work and take priority over `.env`.

## OpenWeatherMap

This app uses OpenWeather's Direct Geocoding API, Current Weather Data API, and 5 day / 3 hour Forecast API:

- [Geocoding API docs](https://openweathermap.org/api/geocoding-api)
- [Current Weather Data docs](https://openweathermap.org/current)
- [5 day / 3 hour forecast docs](https://openweathermap.org/forecast5)
- [Weather API overview](https://openweathermap.org/api)
