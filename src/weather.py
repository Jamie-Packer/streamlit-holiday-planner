"""Open-Meteo weather and climate fetching."""

from __future__ import annotations   # helps type hints
import openmeteo_requests
import pandas as pd
import requests

_USER_AGENT = "HolidayPlanner/1.0 (Rockborne training project)"
_session = requests.Session()
_session.headers.update({"User-Agent": _USER_AGENT})
openmeteo = openmeteo_requests.Client(session=_session)

# --- fetch_forecast function ---

def fetch_forecast(lat: float, lng: float) -> dict:
    """Fetch current and 7-day forecast from Open-Meteo.
    Returns an Open-Meteo forecast payload dict. Expected keys include
    daily time, temperature, and precipitation series under nested objects
    such as "daily" and "current".
    """
    # create url that will request necessary information
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,   # inputs 
        "longitude": lng,  # inputs 
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "cloud_cover",
            "wind_speed_10m"
        ],
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum"
        ],
        "forecast_days": 7
    }

    responses = openmeteo.weather_api(url, params=params)   # call for the information
    response = responses[0]   # access first response (one location)

    # extract current information - order must match params
    current = response.Current()
    current_weather = {
        "temperature": current.Variables(0).Value(),
        "humidity": current.Variables(1).Value(),
        "cloud_cover": current.Variables(2).Value(),
        "wind_speed": current.Variables(3).Value(),
    }

    # extract daily information for forecast - order must match params
    daily = response.Daily()
    daily_forecast = {
        "date": pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left"
        ),
        "temperature_max": daily.Variables(0).ValuesAsNumpy(),
        "temperature_min": daily.Variables(1).ValuesAsNumpy(),
        "precipitation": daily.Variables(2).ValuesAsNumpy(),
    }

    daily_dataframe = pd.DataFrame(daily_forecast)

    return {
        "latitude": response.Latitude(),
        "longitude": response.Longitude(),
        "current": current_weather,
        "daily": daily_dataframe
    }

# --- fetch_climate function ---

def fetch_climate(lat: float, lng: float)  -> pd.DataFrame:
    """Fetch historical daily climate from Open-Meteo across the last 3 full
    calendar years and return a DataFrame suitable for seasonal averaging.

    Returns a DataFrame with one row per day across the requested span, with
    ``date``, ``temperature_mean`` and ``precipitation`` columns. The dashboard
    groups by month and averages, so multiple years are folded together into a
    single "typical year" profile in one API call.
    """
    # create url that will request necessary information for weather
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,   # inputs
        "longitude": lng,   # inputs
        # last 3 full calendar years — averaged downstream by month
        "start_date": "2023-01-01",   # start of 2023
        "end_date": "2025-12-31",   # through to the end of 2025
        # average temperature and rainfall
        "daily": [
            "temperature_2m_mean",
            "precipitation_sum"
    ]
    }

    responses = openmeteo.weather_api(url, params=params)   # send API request
    response = responses[0]   # get first (and only) location

    # extract daily weather block
    daily = response.Daily()
    daily_temperature = daily.Variables(0).ValuesAsNumpy()   # average daily temperature
    daily_precipitation = daily.Variables(1).ValuesAsNumpy()   # daily rainfall

    # build DataFrame - date part, mean temperature part, precipitation part
    daily_data = {
        "date": pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left"
        ),
        "temperature_mean": daily_temperature,
        "precipitation": daily_precipitation
    }
    # create and return DataFrame
    daily_dataframe = pd.DataFrame(daily_data)
    return daily_dataframe
