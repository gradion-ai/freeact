"""Weather forecast tool."""


def run(city: str, days: int = 3) -> dict:
    """Get weather forecast for a city.

    Args:
        city: City name.
        days: Number of forecast days.

    Returns:
        Weather forecast data.
    """
    return {"city": city, "days": days}
