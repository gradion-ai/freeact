"""
Weather reporting functionality using Open-Meteo API
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict

import requests


def get_coordinates(city_name: str) -> tuple[float, float]:
    """Get latitude and longitude for a given city name using Nominatim geocoding service."""
    url = f"https://nominatim.openstreetmap.org/search?city={city_name}&format=json"
    response = requests.get(url, headers={"User-Agent": "weather-report-script"})
    response.raise_for_status()

    data = response.json()
    if not data:
        raise ValueError(f"Could not find coordinates for city: {city_name}")

    # Take the first result
    location = data[0]
    return float(location["lat"]), float(location["lon"])


def get_weather_report(city_name: str, n_days: int = 7) -> Dict[str, Any]:
    """
    Get current and historical weather report for a given city.

    Args:
        city_name: Name of the city to get weather for
        n_days: Number of past days to get historical data for (excluding current day)

    Returns:
        Dictionary containing:
        current:
            - temperature (float): Current temperature in Celsius
            - humidity (float): Current relative humidity in percent
            - measurement_time (datetime): Time of measurement
        historical:
            - dates (List[date]): List of dates
            - temperatures (List[float]): Daily average temperatures in Celsius
            - humidities (List[float]): Daily average relative humidities in percent
        metadata:
            - city (str): City name used in query
            - coordinates (tuple): (latitude, longitude) of the city
    """
    # Get coordinates for the city
    lat, lon = get_coordinates(city_name)

    # Calculate date range for historical data
    end_date = date.today() - timedelta(days=1)  # yesterday
    start_date = end_date - timedelta(days=n_days - 1)

    # Make API call for current weather
    current_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m&timezone=auto"
    current_response = requests.get(current_url)
    current_response.raise_for_status()
    current_data = current_response.json()

    # Make API call for historical weather
    historical_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_mean,relative_humidity_2m_mean&start_date={start_date}&end_date={end_date}&timezone=auto"
    historical_response = requests.get(historical_url)
    historical_response.raise_for_status()
    historical_data = historical_response.json()

    # Extract current weather
    current = current_data["current"]

    # Extract historical weather
    daily = historical_data["daily"]

    return {
        "current": {
            "temperature": current["temperature_2m"],
            "humidity": current["relative_humidity_2m"],
            "measurement_time": datetime.fromisoformat(current["time"]),
        },
        "historical": {
            "dates": [date.fromisoformat(d) for d in daily["time"]],
            "temperatures": daily["temperature_2m_mean"],
            "humidities": daily["relative_humidity_2m_mean"],
        },
        "metadata": {"city": city_name, "coordinates": (lat, lon)},
    }
