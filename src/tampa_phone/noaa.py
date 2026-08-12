from __future__ import annotations

import asyncio
import math
import os
import re
from datetime import date
from typing import Any

import httpx

COOPS_DATA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
COOPS_STATIONS_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
NWS_BASE_URL = "https://api.weather.gov"
DEFAULT_LATITUDE = 27.75
DEFAULT_LONGITUDE = -82.63


class NOAAError(RuntimeError):
    pass


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_miles * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _validate_date(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Dates must use YYYY-MM-DD format")
    return date.fromisoformat(value)


def _compact_series(series: dict[str, Any], limit: int = 8) -> dict[str, Any]:
    return {
        "unit": series.get("uom"),
        "values": [
            {"valid_time": item.get("validTime"), "value": item.get("value")}
            for item in series.get("values", [])[:limit]
        ],
    }


class NOAAClient:
    def __init__(self) -> None:
        self.headers = {
            "User-Agent": os.getenv("NOAA_USER_AGENT", "TampaPhoneDemo/0.1"),
            "Accept": "application/geo+json, application/json",
        }

    async def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=self.headers) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise NOAAError(f"NOAA request failed: {error}") from error
        if isinstance(payload, dict) and payload.get("error"):
            message = payload["error"].get("message", "Unknown NOAA error")
            raise NOAAError(message)
        if not isinstance(payload, dict):
            raise NOAAError("NOAA returned an unexpected response")
        return payload

    async def find_tide_stations(
        self,
        location_query: str = "",
        latitude: float = DEFAULT_LATITUDE,
        longitude: float = DEFAULT_LONGITUDE,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        payload = await self._get_json(COOPS_STATIONS_URL, params={"type": "waterlevels"})
        stations = [station for station in payload.get("stations", []) if station.get("tidal")]
        query_words = location_query.casefold().replace("bay", "").split()
        if query_words and "tampa" not in query_words:
            named = [
                station
                for station in stations
                if all(
                    word in f"{station.get('name', '')} {station.get('state', '')}".casefold()
                    for word in query_words
                )
            ]
            if named:
                stations = named
        for station in stations:
            station["distance_miles"] = _haversine_miles(
                latitude,
                longitude,
                float(station["lat"]),
                float(station["lng"]),
            )
        stations.sort(key=lambda station: station["distance_miles"])
        return [
            {
                "station_id": station["id"],
                "name": station["name"],
                "state": station["state"],
                "latitude": station["lat"],
                "longitude": station["lng"],
                "distance_miles": round(station["distance_miles"], 1),
            }
            for station in stations[: max(1, min(limit, 8))]
        ]

    async def tide_predictions(
        self, station_id: str, begin_date: str, end_date: str
    ) -> dict[str, Any]:
        start = _validate_date(begin_date)
        end = _validate_date(end_date)
        if end < start:
            raise ValueError("End date must not be before begin date")
        if (end - start).days > 10:
            raise ValueError("Tide requests are limited to 10 days")
        payload = await self._get_json(
            COOPS_DATA_URL,
            params={
                "begin_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
                "station": station_id,
                "product": "predictions",
                "datum": "MLLW",
                "time_zone": "lst_ldt",
                "interval": "hilo",
                "units": "english",
                "application": "TampaPhone",
                "format": "json",
            },
        )
        return {
            "station_id": station_id,
            "datum": "MLLW",
            "units": "feet",
            "time_zone": "station local time",
            "predictions": payload.get("predictions", []),
        }

    async def latest_station_conditions(self, station_id: str) -> dict[str, Any]:
        products = ("water_level", "wind", "water_temperature", "air_temperature")

        async def fetch_product(product: str) -> tuple[str, dict[str, Any] | None]:
            params: dict[str, Any] = {
                "date": "latest",
                "station": station_id,
                "product": product,
                "time_zone": "lst_ldt",
                "units": "english",
                "application": "TampaPhone",
                "format": "json",
            }
            if product == "water_level":
                params["datum"] = "MLLW"
            try:
                payload = await self._get_json(COOPS_DATA_URL, params=params)
            except NOAAError:
                return product, None
            values = payload.get("data", [])
            return product, values[-1] if values else None

        results = await asyncio.gather(*(fetch_product(product) for product in products))
        return {
            "station_id": station_id,
            "units": {
                "water_level": "feet above MLLW",
                "wind_speed_and_gust": "knots",
                "temperatures": "degrees Fahrenheit",
            },
            "latest": {product: value for product, value in results if value is not None},
        }

    async def marine_forecast(
        self,
        latitude: float = 27.65,
        longitude: float = -82.75,
    ) -> dict[str, Any]:
        point = await self._get_json(f"{NWS_BASE_URL}/points/{latitude},{longitude}")
        properties = point.get("properties", {})
        grid_url = properties.get("forecastGridData")
        if not grid_url:
            raise NOAAError("NWS did not return marine grid data for that point")
        grid = await self._get_json(grid_url)
        forecast = grid.get("properties", {})
        fields = (
            "windSpeed",
            "windDirection",
            "windGust",
            "waveHeight",
            "wavePeriod",
            "probabilityOfThunder",
            "probabilityOfPrecipitation",
        )
        return {
            "source": "National Weather Service digital forecast grid",
            "point_type": properties.get("type"),
            "forecast_zone": properties.get("forecastZone"),
            "time_zone": properties.get("timeZone"),
            "updated": forecast.get("updateTime"),
            "forecast": {
                field: _compact_series(forecast.get(field, {}))
                for field in fields
                if forecast.get(field, {}).get("values")
            },
            "weather": forecast.get("weather", {}).get("values", [])[:6],
        }

    async def active_alerts(
        self,
        latitude: float = DEFAULT_LATITUDE,
        longitude: float = DEFAULT_LONGITUDE,
    ) -> dict[str, Any]:
        payload = await self._get_json(
            f"{NWS_BASE_URL}/alerts/active", params={"point": f"{latitude},{longitude}"}
        )
        alerts = []
        for feature in payload.get("features", [])[:8]:
            properties = feature.get("properties", {})
            alerts.append(
                {
                    "event": properties.get("event"),
                    "severity": properties.get("severity"),
                    "urgency": properties.get("urgency"),
                    "headline": properties.get("headline"),
                    "onset": properties.get("onset"),
                    "ends": properties.get("ends") or properties.get("expires"),
                    "area": properties.get("areaDesc"),
                    "instruction": properties.get("instruction"),
                }
            )
        return {
            "source": "National Weather Service active alerts",
            "updated": payload.get("updated"),
            "alerts": alerts,
        }
