"""Module for getting weather reports for cities."""

from datetime import datetime, timedelta
from typing import Any, Dict

import requests


def get_weather_report(city_name: str, n_days: int = 7) -> Dict[str, Any]:
    """Get current and historical weather report for a given city.

    Args:
        city_name: Name of the city to get weather for
        n_days: Number of past days to get historical data for (excluding current day)

    Returns:
        Dictionary containing:
        - temperature: Current temperature in Celsius
        - humidity: Current relative humidity percentage
        - cloud_cover: Current cloud coverage percentage
        - measurement_time: Timestamp of current measurement
        - coordinates: Dict with latitude and longitude
        - city: City name used for query
        - history: List of daily measurements for past n_days (excluding current day), each containing:
            - date: Date of measurement
            - temperature: Average daily temperature in Celsius
            - humidity: Average daily relative humidity percentage
            - cloud_cover: Average daily cloud coverage percentage
    """
    # First get coordinates using geocoding API
    geocoding_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=en&format=json"
    geo_response = requests.get(geocoding_url)
    geo_data = geo_response.json()

    if not geo_data.get("results"):
        raise ValueError(f"Could not find coordinates for city: {city_name}")

    location = geo_data["results"][0]
    lat = location["latitude"]
    lon = location["longitude"]

    # Calculate date range for historical data
    end_date = datetime.now().date() - timedelta(days=1)  # yesterday
    start_date = end_date - timedelta(days=n_days - 1)

    # Get current and historical weather data using coordinates
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,cloud_cover"
        f"&daily=temperature_2m_mean,relative_humidity_2m_mean,cloud_cover_mean"
        f"&timezone=auto"
        f"&start_date={start_date}&end_date={end_date}"
    )
    weather_response = requests.get(weather_url)
    weather_data = weather_response.json()

    current = weather_data["current"]
    daily = weather_data["daily"]

    # Process historical data
    history = []
    for i in range(len(daily["time"])):
        history.append(
            {
                "date": datetime.fromisoformat(daily["time"][i]).date(),
                "temperature": daily["temperature_2m_mean"][i],
                "humidity": daily["relative_humidity_2m_mean"][i],
                "cloud_cover": daily["cloud_cover_mean"][i],
            }
        )

    return {
        "temperature": current["temperature_2m"],
        "humidity": current["relative_humidity_2m"],
        "cloud_cover": current["cloud_cover"],
        "measurement_time": datetime.fromisoformat(current["time"]),
        "coordinates": {"latitude": lat, "longitude": lon},
        "city": location["name"],
        "history": history,
    }
