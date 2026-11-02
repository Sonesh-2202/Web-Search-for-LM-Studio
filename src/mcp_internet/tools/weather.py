"""
Weather Tool - Get weather information using Open-Meteo API.

Open-Meteo is a free, open-source weather API that doesn't require an API key.
"""

import logging

from ..utils.http_client import fetch_json

logger = logging.getLogger(__name__)

# Open-Meteo API endpoints
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Weather code descriptions
WEATHER_CODES = {
    0: "☀️ Clear sky",
    1: "🌤️ Mainly clear",
    2: "⛅ Partly cloudy",
    3: "☁️ Overcast",
    45: "🌫️ Foggy",
    48: "🌫️ Depositing rime fog",
    51: "🌧️ Light drizzle",
    53: "🌧️ Moderate drizzle",
    55: "🌧️ Dense drizzle",
    61: "🌧️ Slight rain",
    63: "🌧️ Moderate rain",
    65: "🌧️ Heavy rain",
    71: "🌨️ Slight snow",
    73: "🌨️ Moderate snow",
    75: "🌨️ Heavy snow",
    77: "🌨️ Snow grains",
    80: "🌦️ Slight rain showers",
    81: "🌦️ Moderate rain showers",
    82: "🌦️ Violent rain showers",
    85: "🌨️ Slight snow showers",
    86: "🌨️ Heavy snow showers",
    95: "⛈️ Thunderstorm",
    96: "⛈️ Thunderstorm with slight hail",
    99: "⛈️ Thunderstorm with heavy hail",
}


def get_weather_description(code: int) -> str:
    """Get human-readable weather description from code."""
    return WEATHER_CODES.get(code, f"🌡️ Weather code {code}")


def get_wind_direction(degrees: float) -> str:
    """Convert wind direction degrees to cardinal direction."""
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    index = round(degrees / 22.5) % 16
    return directions[index]


async def geocode_location(location: str) -> dict | None:
    """Convert location name to coordinates."""
    if not location.strip() or len(location) > 200:
        return None
    params = {"name": location, "count": 1, "language": "en", "format": "json"}
    data = await fetch_json(GEOCODING_URL, params=params)
    if not data or "results" not in data or not data["results"]:
        return None
    
    result = data["results"][0]
    return {
        "name": result.get("name", location),
        "country": result.get("country", ""),
        "admin": result.get("admin1", ""),  # State/Province
        "lat": result["latitude"],
        "lon": result["longitude"],
        "timezone": result.get("timezone", "UTC"),
    }


async def get_weather(location: str) -> str:
    """
    Get current weather and forecast for a location.
    
    Args:
        location: City name, address, or place name
        
    Returns:
        Formatted weather report
    """
    if not location.strip() or len(location) > 200:
        return "❌ Error: Please provide a location."
    
    # Geocode the location
    geo = await geocode_location(location)
    if not geo:
        return f"❌ Error: Unable to find location '{location}'. Please try a different city or be more specific."
    
    # Fetch weather data
    weather_params = {
        "latitude": geo["lat"], "longitude": geo["lon"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": geo["timezone"], "forecast_days": 4,
    }
    weather_data = await fetch_json(WEATHER_URL, params=weather_params)
    if not weather_data:
        return f"❌ Error: Unable to fetch weather data for {location}."
    
    try:
        current = weather_data.get("current", {})
        daily = weather_data.get("daily", {})
        
        # Format location name
        location_parts = [geo["name"]]
        if geo["admin"]:
            location_parts.append(geo["admin"])
        if geo["country"]:
            location_parts.append(geo["country"])
        location_display = ", ".join(location_parts)
        
        # Current weather
        weather_desc = get_weather_description(current.get("weather_code", -1))
        wind_value = current.get("wind_direction_10m")
        wind_dir = get_wind_direction(wind_value) if isinstance(wind_value, (int, float)) else ""
        
        output = f"""🌍 **Weather for {location_display}**
{'=' * 50}

**Current Conditions**
{weather_desc}
Observation time: {current.get('time', 'not provided')} ({weather_data.get('timezone', geo['timezone'] )})
🌡️ Temperature: {current.get('temperature_2m', 'unknown')}°C (feels like {current.get('apparent_temperature', 'unknown')}°C)
💨 Wind: {current.get('wind_speed_10m', 'unknown')} km/h {wind_dir}
💧 Humidity: {current.get('relative_humidity_2m', 'unknown')}%

**3-Day Forecast**
"""
        
        # Daily forecast (skip today, show next 3 days)
        times = daily.get("time", [])
        for i in range(1, min(4, len(times))):
            date = times[i]
            code = daily.get("weather_code", [None] * len(times))[i]
            max_temp = daily.get("temperature_2m_max", ["?"] * len(times))[i]
            min_temp = daily.get("temperature_2m_min", ["?"] * len(times))[i]
            precip = daily.get("precipitation_probability_max", [0] * len(times))[i]
            
            weather_emoji = get_weather_description(code).split()[0]
            output += f"\n📅 **{date}**: {weather_emoji} {min_temp}°C - {max_temp}°C"
            if isinstance(precip, (int, float)) and precip > 0:
                output += f" | 🌧️ {precip}% rain"
        
        return output
        
    except KeyError as e:
        logger.error(f"Missing weather data key: {e}")
        return "❌ Error: Incomplete weather data received. Please try again."
    except Exception as e:
        logger.error(f"Error processing weather data: {e}")
        return "❌ Error: Unable to process weather data. Please try again."
