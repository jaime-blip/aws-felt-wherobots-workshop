"""
Aurora / Weather Forecasting Tools
====================================

Tools for weather forecasting and climate risk assessment.

Aurora is Microsoft's 1.3B parameter foundation model for the atmosphere,
trained on >1M hours of weather simulations. It forecasts at 0.1° resolution
(~11km) — 5,000x faster than traditional numerical weather prediction.

For this workshop, we use Open-Meteo (free, no API key) as a practical
weather data source, with Aurora-style climate risk assessment logic.
When Aurora becomes available on SageMaker/Bedrock, swap in the model call.
"""

import json
import logging
from datetime import datetime, timedelta

import requests
from strands import tool

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_HISTORICAL = "https://archive-api.open-meteo.com/v1/archive"


@tool
def get_weather_forecast(lat: float, lon: float, days: int = 7) -> dict:
    """Get weather forecast for a location using Open-Meteo.

    Returns temperature, precipitation, wind speed, and weather codes
    for the next N days. Use this to assess near-term weather risks
    that could affect buildings and infrastructure.

    In production, this would call Aurora (Microsoft's atmospheric
    foundation model) for higher-resolution forecasts.

    Args:
        lat: Latitude of the location.
        lon: Longitude of the location.
        days: Number of forecast days (1-16). Default 7.

    Returns:
        dict with daily forecast data including temperature, rain, wind.
    """
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
                "weathercode",
            ],
            "timezone": "auto",
            "forecast_days": min(days, 16),
        }
        resp = requests.get(OPEN_METEO_FORECAST, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        forecast = []
        for i, date in enumerate(dates):
            forecast.append({
                "date": date,
                "temp_max_c": daily["temperature_2m_max"][i],
                "temp_min_c": daily["temperature_2m_min"][i],
                "precipitation_mm": daily["precipitation_sum"][i],
                "precip_probability_%": daily["precipitation_probability_max"][i],
                "wind_speed_max_kmh": daily["wind_speed_10m_max"][i],
                "wind_gusts_max_kmh": daily["wind_gusts_10m_max"][i],
                "weather_code": daily["weathercode"][i],
            })

        # Assess weather risk
        max_precip = max(d["precipitation_mm"] or 0 for d in forecast)
        max_wind = max(d["wind_gusts_max_kmh"] or 0 for d in forecast)
        weather_risk = "low"
        if max_precip > 50 or max_wind > 90:
            weather_risk = "critical"
        elif max_precip > 25 or max_wind > 60:
            weather_risk = "high"
        elif max_precip > 10 or max_wind > 40:
            weather_risk = "moderate"

        return {
            "location": {"lat": lat, "lon": lon},
            "timezone": data.get("timezone"),
            "forecast": forecast,
            "weather_risk_level": weather_risk,
            "max_precipitation_mm": max_precip,
            "max_wind_gusts_kmh": max_wind,
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_historical_weather(lat: float, lon: float, start_date: str, end_date: str) -> dict:
    """Get historical weather data for climate analysis.

    Use this to analyze past weather patterns for risk assessment.
    Helps identify areas prone to extreme events.

    Args:
        lat: Latitude of the location.
        lon: Longitude of the location.
        start_date: Start date (YYYY-MM-DD). Must be before yesterday.
        end_date: End date (YYYY-MM-DD). Must be before today.

    Returns:
        dict with historical daily weather data and climate statistics.
    """
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
            ],
            "timezone": "auto",
        }
        resp = requests.get(OPEN_METEO_HISTORICAL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        precip_values = [v or 0 for v in daily.get("precipitation_sum", [])]
        wind_values = [v or 0 for v in daily.get("wind_gusts_10m_max", [])]
        temp_max_values = [v for v in daily.get("temperature_2m_max", []) if v is not None]

        # Compute climate statistics
        extreme_rain_days = sum(1 for p in precip_values if p > 25)
        extreme_wind_days = sum(1 for w in wind_values if w > 60)

        return {
            "location": {"lat": lat, "lon": lon},
            "period": {"start": start_date, "end": end_date, "days": len(dates)},
            "statistics": {
                "avg_temp_max_c": round(sum(temp_max_values) / len(temp_max_values), 1) if temp_max_values else None,
                "total_precipitation_mm": round(sum(precip_values), 1),
                "avg_daily_precip_mm": round(sum(precip_values) / len(precip_values), 1) if precip_values else 0,
                "max_single_day_precip_mm": round(max(precip_values), 1) if precip_values else 0,
                "max_wind_gust_kmh": round(max(wind_values), 1) if wind_values else 0,
                "extreme_rain_days_gt25mm": extreme_rain_days,
                "extreme_wind_days_gt60kmh": extreme_wind_days,
            },
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_climate_risk_assessment(lat: float, lon: float) -> dict:
    """Comprehensive climate risk assessment for a location.

    Combines current forecast + historical climate data to produce
    a risk assessment. This is the "Aurora-powered" analysis tool —
    when Aurora is available on Bedrock/SageMaker, it would provide
    the atmospheric modeling backbone.

    Risk factors assessed:
    - Flood risk (precipitation patterns)
    - Wind/storm risk (wind speed patterns)
    - Heat risk (extreme temperature events)
    - Overall climate vulnerability

    Args:
        lat: Latitude of the location.
        lon: Longitude of the location.

    Returns:
        dict with comprehensive climate risk scores and narrative.
    """
    try:
        # Get current forecast
        forecast_resp = requests.get(OPEN_METEO_FORECAST, params={
            "latitude": lat, "longitude": lon,
            "daily": ["precipitation_sum", "wind_gusts_10m_max", "temperature_2m_max",
                       "precipitation_probability_max"],
            "timezone": "auto", "forecast_days": 14,
        }, timeout=15)
        forecast_resp.raise_for_status()
        forecast = forecast_resp.json().get("daily", {})

        # Get last 365 days of historical data
        today = datetime.now()
        hist_end = (today - timedelta(days=2)).strftime("%Y-%m-%d")
        hist_start = (today - timedelta(days=367)).strftime("%Y-%m-%d")

        hist_resp = requests.get(OPEN_METEO_HISTORICAL, params={
            "latitude": lat, "longitude": lon,
            "start_date": hist_start, "end_date": hist_end,
            "daily": ["precipitation_sum", "wind_gusts_10m_max", "temperature_2m_max"],
            "timezone": "auto",
        }, timeout=30)
        hist_resp.raise_for_status()
        hist = hist_resp.json().get("daily", {})

        # Compute risk scores (0-1)
        hist_precip = [v or 0 for v in hist.get("precipitation_sum", [])]
        hist_wind = [v or 0 for v in hist.get("wind_gusts_10m_max", [])]
        hist_temp = [v for v in hist.get("temperature_2m_max", []) if v is not None]

        # Flood risk: based on frequency and intensity of heavy rain
        heavy_rain_freq = sum(1 for p in hist_precip if p > 20) / max(len(hist_precip), 1)
        max_daily_rain = max(hist_precip) if hist_precip else 0
        flood_risk = min((heavy_rain_freq * 20) + (max_daily_rain / 200), 1.0)

        # Storm risk: based on wind extremes
        severe_wind_freq = sum(1 for w in hist_wind if w > 70) / max(len(hist_wind), 1)
        max_gust = max(hist_wind) if hist_wind else 0
        storm_risk = min((severe_wind_freq * 15) + (max_gust / 200), 1.0)

        # Heat risk: based on extreme heat days
        extreme_heat_days = sum(1 for t in hist_temp if t > 38) / max(len(hist_temp), 1)
        heat_risk = min(extreme_heat_days * 10, 1.0)

        # Composite
        composite = round(0.40 * flood_risk + 0.35 * storm_risk + 0.25 * heat_risk, 3)

        if composite >= 0.6:
            level = "critical"
        elif composite >= 0.35:
            level = "high"
        elif composite >= 0.15:
            level = "moderate"
        else:
            level = "low"

        # Upcoming threats from forecast
        upcoming_precip = [v or 0 for v in forecast.get("precipitation_sum", [])]
        upcoming_wind = [v or 0 for v in forecast.get("wind_gusts_10m_max", [])]
        upcoming_threat = "none"
        if any(p > 30 for p in upcoming_precip) or any(w > 80 for w in upcoming_wind):
            upcoming_threat = "severe weather expected in next 14 days"
        elif any(p > 15 for p in upcoming_precip) or any(w > 50 for w in upcoming_wind):
            upcoming_threat = "moderate weather activity expected"

        return {
            "location": {"lat": lat, "lon": lon},
            "risk_scores": {
                "flood_risk": round(flood_risk, 3),
                "storm_risk": round(storm_risk, 3),
                "heat_risk": round(heat_risk, 3),
                "composite_risk": composite,
            },
            "risk_level": level,
            "upcoming_threat": upcoming_threat,
            "historical_summary": {
                "period_days": len(hist_precip),
                "total_precipitation_mm": round(sum(hist_precip), 1),
                "max_daily_rain_mm": round(max_daily_rain, 1),
                "max_wind_gust_kmh": round(max_gust, 1),
                "extreme_heat_days": sum(1 for t in hist_temp if t > 38),
            },
            "note": "Powered by Open-Meteo. In production, Aurora foundation model provides higher-resolution atmospheric modeling.",
        }
    except Exception as e:
        return {"error": str(e)}
