"""
Weather Service — Open-Meteo API (Free, No API Key Required)
============================================================
Fetches weather forecast/current conditions for IPL match venues.
Uses geocoding to convert city names to coordinates.
"""
import logging
import httpx
from typing import Optional, Dict

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# IPL venue city coordinates (pre-cached for speed)
VENUE_COORDS = {
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "mumbai": (19.0760, 72.8777),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "hyderabad": (17.3850, 78.4867),
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "jaipur": (26.9124, 75.7873),
    "ahmedabad": (23.0225, 72.5714),
    "lucknow": (26.8467, 80.9462),
    "guwahati": (26.1445, 91.7362),
    "new chandigarh": (30.7333, 76.7794),
    "chandigarh": (30.7333, 76.7794),
    "mohali": (30.7046, 76.7179),
    "dharamshala": (32.2190, 76.3234),
    "raipur": (21.2514, 81.6296),
    "visakhapatnam": (17.6868, 83.2185),
    "pune": (18.5204, 73.8567),
    "indore": (22.7196, 75.8577),
    "nagpur": (21.1458, 79.0882),
    "rajkot": (22.3039, 70.8022),
    "ranchi": (23.3441, 85.3096),
    "dehradun": (30.3165, 78.0322),
    "thiruvananthapuram": (8.5241, 76.9366),
    "cuttack": (20.4625, 85.8830),
}


async def _geocode_city(city: str) -> Optional[tuple]:
    """Geocode a city name to lat/lon using Open-Meteo."""
    city_lower = city.lower().strip()

    # Check pre-cached coordinates first
    for key, coords in VENUE_COORDS.items():
        if key in city_lower or city_lower in key:
            return coords

    # Fallback: live geocoding
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(GEOCODING_URL, params={
                "name": city,
                "count": 1,
                "language": "en",
                "format": "json",
            })
            data = resp.json()
            results = data.get("results", [])
            if results:
                return (results[0]["latitude"], results[0]["longitude"])
    except Exception as e:
        logger.error(f"Geocoding failed for {city}: {e}")

    return None


async def fetch_weather_for_venue(city: str, match_date: str = None) -> Dict:
    """
    Fetch weather conditions for an IPL venue city.
    
    Args:
        city: City name (e.g., "Mumbai", "Bengaluru")
        match_date: Optional ISO date string for specific date forecast
    
    Returns:
        Dict with temperature, humidity, wind, rain probability, conditions
    """
    coords = await _geocode_city(city)
    if not coords:
        return {
            "available": False,
            "city": city,
            "error": f"Could not geocode city: {city}",
        }

    lat, lon = coords

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,wind_speed_10m,wind_direction_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
        "timezone": "Asia/Kolkata",
        "forecast_days": 3,
    }

    # If a specific date is provided, request hourly data for that date
    if match_date:
        params["hourly"] = "temperature_2m,relative_humidity_2m,precipitation_probability,wind_speed_10m,weather_code"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(FORECAST_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        # Parse current conditions
        current = data.get("current", {})
        daily = data.get("daily", {})

        weather_code = current.get("weather_code", 0)
        condition = _weather_code_to_text(weather_code)

        result = {
            "available": True,
            "city": city,
            "coordinates": {"lat": lat, "lon": lon},
            "current": {
                "temperature": current.get("temperature_2m"),
                "feels_like": current.get("apparent_temperature"),
                "humidity": current.get("relative_humidity_2m"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "wind_direction": current.get("wind_direction_10m"),
                "precipitation_mm": current.get("precipitation", 0),
                "rain_mm": current.get("rain", 0),
                "weather_code": weather_code,
                "condition": condition,
            },
            "forecast": [],
            "cricket_impact": _assess_cricket_impact(current, condition),
        }

        # Parse daily forecast
        if daily.get("time"):
            for i, date in enumerate(daily["time"]):
                result["forecast"].append({
                    "date": date,
                    "temp_max": daily.get("temperature_2m_max", [None])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                    "temp_min": daily.get("temperature_2m_min", [None])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                    "precipitation_mm": daily.get("precipitation_sum", [0])[i] if i < len(daily.get("precipitation_sum", [])) else 0,
                    "rain_probability": daily.get("precipitation_probability_max", [0])[i] if i < len(daily.get("precipitation_probability_max", [])) else 0,
                    "max_wind_kmh": daily.get("wind_speed_10m_max", [0])[i] if i < len(daily.get("wind_speed_10m_max", [])) else 0,
                })

        # Extract match-time weather if hourly data & date provided
        if match_date and data.get("hourly"):
            hourly = data["hourly"]
            match_hour_weather = _extract_match_hour_weather(hourly, match_date)
            if match_hour_weather:
                result["match_time_weather"] = match_hour_weather

        return result

    except Exception as e:
        logger.error(f"Weather fetch failed for {city}: {e}")
        return {
            "available": False,
            "city": city,
            "error": str(e),
        }


def _extract_match_hour_weather(hourly: dict, match_date: str) -> Optional[Dict]:
    """Extract weather at typical IPL match times (7:30 PM IST = index 19-22)."""
    times = hourly.get("time", [])
    match_hours = []
    for i, t in enumerate(times):
        if match_date in t:
            hour = int(t.split("T")[1].split(":")[0])
            if 15 <= hour <= 23:  # Match window: 3:30 PM to 11 PM
                match_hours.append(i)

    if not match_hours:
        return None

    # Average conditions during match window
    temps = [hourly.get("temperature_2m", [0])[i] for i in match_hours if i < len(hourly.get("temperature_2m", []))]
    humids = [hourly.get("relative_humidity_2m", [0])[i] for i in match_hours if i < len(hourly.get("relative_humidity_2m", []))]
    rain_probs = [hourly.get("precipitation_probability", [0])[i] for i in match_hours if i < len(hourly.get("precipitation_probability", []))]
    winds = [hourly.get("wind_speed_10m", [0])[i] for i in match_hours if i < len(hourly.get("wind_speed_10m", []))]

    def _avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else 0

    return {
        "avg_temperature": _avg(temps),
        "avg_humidity": _avg(humids),
        "max_rain_probability": max(rain_probs) if rain_probs else 0,
        "avg_wind_kmh": _avg(winds),
        "hours_covered": len(match_hours),
    }


def _weather_code_to_text(code: int) -> str:
    """Convert WMO weather code to human-readable text."""
    codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return codes.get(code, f"Unknown ({code})")


def _assess_cricket_impact(current: dict, condition: str) -> Dict:
    """Assess how weather conditions affect cricket play."""
    rain = current.get("rain", 0) or current.get("precipitation", 0) or 0
    humidity = current.get("relative_humidity_2m", 50) or 50
    wind = current.get("wind_speed_10m", 0) or 0
    temp = current.get("temperature_2m", 30) or 30

    impact = {
        "play_likely": True,
        "dew_factor": "none",
        "swing_conditions": "normal",
        "batting_conditions": "normal",
        "summary": "",
    }

    factors = []

    # Rain assessment
    if rain > 5:
        impact["play_likely"] = False
        factors.append("Heavy rain - match likely delayed/abandoned")
    elif rain > 1:
        factors.append("Light rain - possible interruptions")
    elif "rain" in condition.lower() or "drizzle" in condition.lower():
        factors.append("Rain expected - DLS may come into play")

    # Dew assessment (evening matches in India)
    if humidity > 75:
        impact["dew_factor"] = "heavy"
        factors.append("High humidity - heavy dew likely (advantage chasing team)")
    elif humidity > 60:
        impact["dew_factor"] = "moderate"
        factors.append("Moderate humidity - some dew expected in 2nd innings")

    # Swing conditions
    if humidity > 70 and temp < 28:
        impact["swing_conditions"] = "favorable"
        factors.append("Overcast + humid - swing bowling favored")
    elif humidity < 40:
        impact["swing_conditions"] = "unfavorable"

    # Wind impact
    if wind > 30:
        factors.append(f"Strong wind ({wind} km/h) - may affect short balls and lofted shots")
    elif wind > 20:
        factors.append(f"Moderate wind ({wind} km/h) - minor batting adjustment needed")

    # Temperature
    if temp > 40:
        factors.append(f"Extreme heat ({temp}C) - player fatigue factor")
    elif temp < 20:
        factors.append(f"Cool conditions ({temp}C) - ball may grip more")

    # Batting conditions
    if "clear" in condition.lower() or "sunny" in condition.lower():
        impact["batting_conditions"] = "good"
        if not factors:
            factors.append("Clear skies - good batting conditions")
    elif "overcast" in condition.lower() or "cloudy" in condition.lower():
        impact["batting_conditions"] = "tricky"
        factors.append("Overcast - bowlers may get assistance")

    if not factors:
        factors.append("Normal playing conditions expected")

    impact["summary"] = ". ".join(factors)
    return impact
