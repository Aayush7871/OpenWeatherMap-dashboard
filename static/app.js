const form = document.getElementById("weather-form");
const cityInput = document.getElementById("city-input");
const searchButton = document.getElementById("search-button");
const locationButton = document.getElementById("location-button");
const refreshButton = document.getElementById("refresh-button");
const themeToggle = document.getElementById("theme-toggle");
const themeIcon = document.getElementById("theme-icon");
const themeLabel = document.getElementById("theme-label");
const loadingIndicator = document.getElementById("loading-indicator");
const loadingText = document.getElementById("loading-text");
const statusMessage = document.getElementById("status-message");
const resultsEl = document.getElementById("results");
const locationChipEl = document.getElementById("location-chip");
const locationNameEl = document.getElementById("location-name");
const localTimeEl = document.getElementById("local-time");
const currentIconEl = document.getElementById("current-icon");
const currentDescriptionEl = document.getElementById("current-description");
const currentTemperatureEl = document.getElementById("current-temperature");
const feelsLikeEl = document.getElementById("feels-like");
const humidityEl = document.getElementById("humidity");
const windSpeedEl = document.getElementById("wind-speed");
const coordinatesEl = document.getElementById("coordinates");
const unitSystemEl = document.getElementById("unit-system");
const forecastListEl = document.getElementById("forecast-list");
const unitButtons = [...document.querySelectorAll(".unit-button")];

const WEATHER_THEMES = {
  Clear: "clear",
  Clouds: "clouds",
  Rain: "rain",
  Drizzle: "rain",
  Thunderstorm: "storm",
  Snow: "snow",
  Mist: "mist",
  Haze: "mist",
  Fog: "mist",
  Smoke: "mist",
};

const state = {
  units: localStorage.getItem("weatherUnits") || "metric",
  theme: localStorage.getItem("weatherTheme") || getPreferredTheme(),
  lastQuery: null,
};

function getPreferredTheme() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}

function setLoading(isLoading, message = "Loading weather...") {
  loadingText.textContent = message;
  loadingIndicator.classList.toggle("hidden", !isLoading);

  [searchButton, locationButton, refreshButton, ...unitButtons].forEach((control) => {
    control.disabled = isLoading;
  });
}

function buildIconUrl(iconCode, size = "4x") {
  return `https://openweathermap.org/img/wn/${iconCode}@${size}.png`;
}

function formatTemperature(value, symbol) {
  return typeof value === "number" ? `${Math.round(value)}\u00B0${symbol}` : "N/A";
}

function formatPercentage(value) {
  return typeof value === "number" ? `${value}%` : "N/A";
}

function formatWindSpeed(value, symbol) {
  return typeof value === "number" ? `${value.toFixed(1)} ${symbol}` : "N/A";
}

function formatCoordinate(value) {
  return typeof value === "number" ? value.toFixed(2) : "N/A";
}

function setTheme(theme) {
  state.theme = theme;
  localStorage.setItem("weatherTheme", theme);
  document.documentElement.dataset.theme = theme;
  themeToggle.setAttribute("aria-pressed", String(theme === "dark"));
  themeIcon.textContent = theme === "dark" ? "\u2600\uFE0F" : "\uD83C\uDF19";
  themeLabel.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
}

function toggleTheme() {
  setTheme(state.theme === "dark" ? "light" : "dark");
}

function setUnits(units) {
  state.units = units;
  localStorage.setItem("weatherUnits", units);

  unitButtons.forEach((button) => {
    const isActive = button.dataset.unit === units;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

function applyWeatherTheme(condition) {
  document.documentElement.dataset.weather = WEATHER_THEMES[condition] || "default";
}

function renderForecastItems(forecast, units) {
  forecastListEl.replaceChildren();

  forecast.forEach((day) => {
    const item = document.createElement("article");
    item.className = "forecast-item";

    const dateWrap = document.createElement("div");
    dateWrap.className = "forecast-date";

    const dayLabel = document.createElement("p");
    dayLabel.className = "forecast-day";
    dayLabel.textContent = day.day;

    const dateLabel = document.createElement("p");
    dateLabel.className = "forecast-date-label";
    dateLabel.textContent = day.date;

    dateWrap.append(dayLabel, dateLabel);

    const icon = document.createElement("img");
    icon.className = "forecast-icon";
    icon.src = buildIconUrl(day.icon, "2x");
    icon.alt = day.description || "Forecast icon";

    const tempWrap = document.createElement("div");
    tempWrap.className = "forecast-temps";

    const maxTemp = document.createElement("p");
    maxTemp.className = "forecast-temp-high";
    maxTemp.textContent = formatTemperature(day.temp_max, units.temperature);

    const minTemp = document.createElement("p");
    minTemp.className = "forecast-temp-low";
    minTemp.textContent = formatTemperature(day.temp_min, units.temperature);

    tempWrap.append(maxTemp, minTemp);

    const description = document.createElement("p");
    description.className = "forecast-description";
    description.textContent = day.description || "Forecast";

    item.append(dateWrap, icon, tempWrap, description);
    forecastListEl.append(item);
  });
}

function renderWeather(data) {
  const region = [data.location.state, data.location.country].filter(Boolean).join(", ");

  locationChipEl.textContent = region || "Current conditions";
  locationNameEl.textContent = data.location.city || "Unknown location";
  localTimeEl.textContent = `Local time ${data.location.local_time}`;
  currentDescriptionEl.textContent = data.current.description || data.current.condition;
  currentTemperatureEl.textContent = formatTemperature(
    data.current.temperature,
    data.units.temperature,
  );
  feelsLikeEl.textContent = `Feels like ${formatTemperature(
    data.current.feels_like,
    data.units.temperature,
  )}`;
  humidityEl.textContent = formatPercentage(data.current.humidity);
  windSpeedEl.textContent = formatWindSpeed(
    data.current.wind_speed,
    data.units.wind_speed,
  );
  coordinatesEl.textContent = `${formatCoordinate(data.location.lat)}, ${formatCoordinate(
    data.location.lon,
  )}`;
  unitSystemEl.textContent =
    data.units.system === "metric" ? "Metric (Celsius)" : "Imperial (Fahrenheit)";

  currentIconEl.src = buildIconUrl(data.current.icon);
  currentIconEl.alt = data.current.description || "Weather icon";

  applyWeatherTheme(data.current.condition);
  renderForecastItems(data.forecast, data.units);
  resultsEl.classList.remove("hidden");
}

function buildRequestUrl(query) {
  const params = new URLSearchParams({ units: state.units });

  if (query.type === "city") {
    params.set("city", query.city);
  } else {
    params.set("lat", query.lat);
    params.set("lon", query.lon);
  }

  return `/api/weather?${params.toString()}`;
}

async function fetchWeather(query) {
  state.lastQuery = query;
  setLoading(true, query.type === "coords" ? "Finding weather for your location..." : "Fetching weather...");
  setStatus("Loading the latest weather...");

  try {
    const response = await fetch(buildRequestUrl(query));
    const data = await response.json();

    if (!response.ok) {
      resultsEl.classList.add("hidden");
      setStatus(data.error || "Unable to fetch weather data.", true);
      return;
    }

    renderWeather(data);
    setStatus(
      `Showing live weather for ${data.location.city} in ${
        state.units === "metric" ? "Celsius" : "Fahrenheit"
      }.`,
    );
  } catch (error) {
    resultsEl.classList.add("hidden");
    setStatus("Network error. Please try again in a moment.", true);
  } finally {
    setLoading(false);
  }
}

function requestCurrentLocation() {
  if (!navigator.geolocation) {
    setStatus("Geolocation is not supported in this browser.", true);
    return;
  }

  setLoading(true, "Requesting your location...");
  setStatus("Waiting for GPS permission...");

  navigator.geolocation.getCurrentPosition(
    (position) => {
      fetchWeather({
        type: "coords",
        lat: String(position.coords.latitude),
        lon: String(position.coords.longitude),
      });
    },
    (error) => {
      setLoading(false);

      if (error.code === error.PERMISSION_DENIED) {
        setStatus("Location access was denied. Please allow GPS or search by city.", true);
        return;
      }

      setStatus("Unable to determine your current location.", true);
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 300000,
    },
  );
}

form.addEventListener("submit", (event) => {
  event.preventDefault();

  const city = cityInput.value.trim();
  if (!city) {
    setStatus("Please enter a city name.", true);
    resultsEl.classList.add("hidden");
    return;
  }

  fetchWeather({ type: "city", city });
});

locationButton.addEventListener("click", requestCurrentLocation);

refreshButton.addEventListener("click", () => {
  if (state.lastQuery) {
    fetchWeather(state.lastQuery);
  }
});

unitButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const nextUnits = button.dataset.unit;

    if (nextUnits === state.units) {
      return;
    }

    setUnits(nextUnits);

    if (state.lastQuery) {
      fetchWeather(state.lastQuery);
    }
  });
});

themeToggle.addEventListener("click", toggleTheme);

setTheme(state.theme);
setUnits(state.units);
