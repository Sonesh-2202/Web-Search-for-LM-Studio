"""Local current date/time from the machine clock, with timezone support."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones


CITY_TIMEZONES = {
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "chicago": "America/Chicago",
    "london": "Europe/London",
    "paris": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "tokyo": "Asia/Tokyo",
    "beijing": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai",
    "hong kong": "Asia/Hong_Kong",
    "singapore": "Asia/Singapore",
    "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne",
    "dubai": "Asia/Dubai",
    "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata",
    "bangalore": "Asia/Kolkata",
    "kolkata": "Asia/Kolkata",
    "chennai": "Asia/Kolkata",
    "moscow": "Europe/Moscow",
    "toronto": "America/Toronto",
    "vancouver": "America/Vancouver",
    "seoul": "Asia/Seoul",
    "bangkok": "Asia/Bangkok",
    "jakarta": "Asia/Jakarta",
    "cairo": "Africa/Cairo",
    "johannesburg": "Africa/Johannesburg",
    "sao paulo": "America/Sao_Paulo",
    "mexico city": "America/Mexico_City",
    "amsterdam": "Europe/Amsterdam",
    "madrid": "Europe/Madrid",
    "rome": "Europe/Rome",
    "zurich": "Europe/Zurich",
    "istanbul": "Europe/Istanbul",
    "tel aviv": "Asia/Jerusalem",
    "jerusalem": "Asia/Jerusalem",
}


def find_timezone(location: str) -> str | None:
    """Resolve a common city name or IANA timezone."""
    value = location.strip()
    if value.lower() in CITY_TIMEZONES:
        return CITY_TIMEZONES[value.lower()]
    if value in available_timezones():
        return value
    return None


def get_current_datetime(location: str = "local") -> str:
    """Return the local-clock timestamp for a city/timezone and in UTC."""
    location = location.strip()
    if not location or location.lower() in {"local", "system"}:
        local_now = datetime.now().astimezone()
        zone_name = local_now.tzname() or "local"
    else:
        timezone_name = find_timezone(location)
        if timezone_name is None:
            return f'Unable to find timezone for "{location}". Try a common city or IANA timezone such as Asia/Kolkata.'
        try:
            local_now = datetime.now(ZoneInfo(timezone_name))
        except Exception:
            return f'Unable to load timezone data for "{timezone_name}". Use the local timezone or install the Python tzdata package.'
        zone_name = timezone_name

    utc_now = local_now.astimezone(timezone.utc)
    return (
        f"{zone_name}: {local_now.isoformat(timespec='seconds')}\n"
        f"UTC: {utc_now.isoformat(timespec='seconds')}"
    )
