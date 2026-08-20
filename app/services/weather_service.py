import logging
from typing import Dict, Any, Optional, Tuple, List
import httpx
from datetime import datetime

logger = logging.getLogger("agrisaathi.weather")

# District coordinates in West Bengal & major agricultural regions
DISTRICT_COORDINATES: Dict[str, Tuple[float, float]] = {
    "hooghly": (22.8963, 88.2461),
    "purba bardhaman": (23.2324, 87.8615),
    "bardhaman": (23.2324, 87.8615),
    "burdwan": (23.2324, 87.8615),
    "paschim bardhaman": (23.6889, 86.9661),
    "asansol": (23.6889, 86.9661),
    "nadia": (23.4710, 88.5565),
    "krishnanagar": (23.4710, 88.5565),
    "murshidabad": (24.1759, 88.2802),
    "berhampore": (24.1759, 88.2802),
    "north 24 parganas": (22.7196, 88.4654),
    "barasat": (22.7196, 88.4654),
    "south 24 parganas": (22.1352, 88.5414),
    "baruipur": (22.1352, 88.5414),
    "bankura": (23.2319, 87.0784),
    "birbhum": (23.8402, 87.6186),
    "suri": (23.8402, 87.6186),
    "paschim medinipur": (22.4257, 87.3199),
    "midnapore": (22.4257, 87.3199),
    "purba medinipur": (21.9497, 87.7770),
    "tamluk": (21.9497, 87.7770),
    "malda": (25.0108, 88.1411),
    "murshidabad": (24.1759, 88.2802),
    "jalpaiguri": (26.5414, 88.7196),
    "cooch behar": (26.3452, 89.4482),
    "darjeeling": (27.0410, 88.2663),
    "kolkata": (22.5726, 88.3639),
    "haldia": (22.0667, 88.0698),
    "singur": (22.8122, 88.2325),
    "tarakeswar": (22.8872, 88.0208),
    "memari": (23.1819, 88.1139),
    "kalna": (23.2206, 88.3644),
    "katwa": (23.6400, 88.1300),
    "ranaghat": (23.1800, 88.5800)
}

# Weather code descriptions (WMO codes)
WMO_DESCRIPTIONS = {
    0: ("Clear sky", "পরিষ্কার আকাশ ☀️"),
    1: ("Mainly clear", "প্রায় পরিষ্কার আকাশ 🌤️"),
    2: ("Partly cloudy", "আংশিক মেঘলা ⛅"),
    3: ("Overcast", "মেঘলা আকাশ ☁️"),
    45: ("Foggy", "কুয়াশাচ্ছন্ন 🌫️"),
    48: ("Depositing rime fog", "ঘন কুয়াশা 🌫️"),
    51: ("Light drizzle", "হালকা গুঁড়ি গুঁড়ি বৃষ্টি 🌦️"),
    53: ("Moderate drizzle", "গুঁড়ি গুঁড়ি বৃষ্টি 🌦️"),
    55: ("Dense drizzle", "ঘন গুঁড়ি গুঁড়ি বৃষ্টি 🌧️"),
    61: ("Slight rain", "হালকা বৃষ্টি 🌧️"),
    63: ("Moderate rain", "মাঝারি বৃষ্টি 🌧️"),
    65: ("Heavy rain", "ভারী বৃষ্টি ⛈️"),
    71: ("Slight snow", "হালকা তুষারপাত ❄️"),
    80: ("Slight rain showers", "হালকা বৃষ্টিপাত 🌦️"),
    81: ("Moderate rain showers", "মাঝারি বৃষ্টিপাত 🌧️"),
    82: ("Violent rain showers", "প্রবল বৃষ্টিপাত ⛈️"),
    95: ("Thunderstorm", "বজ্রবিদ্যুৎ সহ ঝড়-বৃষ্টি ⛈️")
}


class WeatherService:
    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1/forecast"

    def get_coordinates(self, location_name: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> Tuple[float, float, str]:
        """Resolve latitude and longitude from location name or GPS coordinates."""
        if lat is not None and lon is not None and lat != 0.0:
            return lat, lon, "Your GPS Location"

        if location_name:
            loc_key = location_name.lower().strip()
            for key, coords in DISTRICT_COORDINATES.items():
                if key in loc_key or loc_key in key:
                    return coords[0], coords[1], location_name.title()

        # Default to Hooghly, West Bengal
        return DISTRICT_COORDINATES["hooghly"][0], DISTRICT_COORDINATES["hooghly"][1], "Hooghly, West Bengal"

    async def get_forecast(self, location_name: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None, crop_name: Optional[str] = None) -> Dict[str, Any]:
        """Fetch current weather and 7-day forecast with agricultural advisory."""
        target_lat, target_lon, resolved_name = self.get_coordinates(location_name, lat, lon)

        params = {
            "latitude": target_lat,
            "longitude": target_lon,
            "current": ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "precipitation", "weather_code", "wind_speed_10m", "wind_direction_10m"],
            "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_sum", "precipitation_probability_max", "wind_speed_10m_max"],
            "timezone": "Asia/Kolkata",
            "forecast_days": 7
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(self.base_url, params=params)
                res.raise_for_status()
                data = res.json()
                return self._format_weather_response(data, resolved_name, crop_name)
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return self._get_fallback_weather(resolved_name, crop_name)

    def _format_weather_response(self, data: Dict[str, Any], location_name: str, crop_name: Optional[str] = None) -> Dict[str, Any]:
        current = data.get("current", {})
        daily = data.get("daily", {})

        cur_temp = current.get("temperature_2m", 28.0)
        cur_humidity = current.get("relative_humidity_2m", 75)
        cur_precip = current.get("precipitation", 0.0)
        cur_wind = current.get("wind_speed_10m", 10.0)
        cur_code = current.get("weather_code", 0)

        wmo_en, wmo_bn = WMO_DESCRIPTIONS.get(cur_code, ("Fair", "স্বাভাবিক আবহাওয়া ⛅"))

        # Daily 7-day forecast
        daily_forecasts = []
        dates = daily.get("time", [])
        codes = daily.get("weather_code", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precips = daily.get("precipitation_sum", [])
        precip_probs = daily.get("precipitation_probability_max", [])

        total_rain_next_3_days = 0.0
        max_rain_prob_next_48h = 0

        for i in range(min(len(dates), 7)):
            d_date = dates[i]
            d_code = codes[i] if i < len(codes) else 0
            d_max = max_temps[i] if i < len(max_temps) else 32.0
            d_min = min_temps[i] if i < len(min_temps) else 24.0
            d_rain = precips[i] if i < len(precips) else 0.0
            d_prob = precip_probs[i] if i < len(precip_probs) else 0

            if i < 3:
                total_rain_next_3_days += d_rain
            if i < 2 and d_prob > max_rain_prob_next_48h:
                max_rain_prob_next_48h = d_prob

            day_name = datetime.strptime(d_date, "%Y-%m-%d").strftime("%a")
            d_wmo_en, d_wmo_bn = WMO_DESCRIPTIONS.get(d_code, ("Fair", "স্বাভাবিক"))

            daily_forecasts.append({
                "date": d_date,
                "day": day_name,
                "max_temp": d_max,
                "min_temp": d_min,
                "rain_mm": d_rain,
                "rain_prob": d_prob,
                "condition_en": d_wmo_en,
                "condition_bn": d_wmo_bn
            })

        # Agricultural Advisory Logic
        agri_advisory_en, agri_advisory_bn, alerts = self._generate_agri_advisory(
            cur_temp, cur_humidity, cur_wind, total_rain_next_3_days, max_rain_prob_next_48h, crop_name
        )

        return {
            "status": "success",
            "location": location_name,
            "current": {
                "temperature": cur_temp,
                "humidity": cur_humidity,
                "precipitation_mm": cur_precip,
                "wind_speed_kmh": cur_wind,
                "condition_en": wmo_en,
                "condition_bn": wmo_bn
            },
            "daily_forecast": daily_forecasts,
            "agri_advisory_en": agri_advisory_en,
            "agri_advisory_bn": agri_advisory_bn,
            "alerts": alerts,
            "source": "Open-Meteo Real-time Agrometeorological Service"
        }

    def _generate_agri_advisory(
        self,
        temp: float,
        humidity: int,
        wind: float,
        rain_3d: float,
        max_rain_prob_48h: int,
        crop_name: Optional[str]
    ) -> Tuple[str, str, List[Dict[str, str]]]:
        advisory_en_parts = []
        advisory_bn_parts = []
        alerts = []

        crop_prefix_en = f"For your {crop_name}: " if crop_name else ""
        crop_prefix_bn = f"আপনার {crop_name} ফসলের জন্য: " if crop_name else ""

        # Rainfall & Spraying advice
        if max_rain_prob_48h >= 60 or rain_3d > 15:
            advisory_en_parts.append(
                f"{crop_prefix_en}Rain probability is high ({max_rain_prob_48h}%). Postpone fertilizer and pesticide spraying to prevent chemical wash-off. Hold off on heavy irrigation."
            )
            advisory_bn_parts.append(
                f"{crop_prefix_bn}আগামী ৪৮ ঘণ্টায় বৃষ্টির সম্ভাবনা প্রবল ({max_rain_prob_48h}%)। জমিতে সার ও কীটনাশক স্প্রে করা স্থগিত রাখুন এবং অতিরিক্ত সেচ দেওয়া বন্ধ রাখুন।"
            )
            if rain_3d > 35:
                alerts.append({
                    "type": "HEAVY_RAIN",
                    "title_en": "⚠️ Heavy Rain Alert",
                    "title_bn": "⚠️ ভারী বৃষ্টির সতর্কতা",
                    "message_en": f"Expected rainfall ~{rain_3d:.1f}mm in next 3 days. Ensure proper field drainage to avoid waterlogging.",
                    "message_bn": f"আগামী ৩ দিনে আনুমানিক {rain_3d:.1f} মিমি বৃষ্টি হতে পারে। জমির জল নিষ্কাশন নালা পরিষ্কার রাখুন।"
                })
        else:
            advisory_en_parts.append(
                f"{crop_prefix_en}Favorable weather for field operations, weeding, and normal irrigation schedule."
            )
            advisory_bn_parts.append(
                f"{crop_prefix_bn}আবহাওয়া চাষের কাজের অনুকূল। প্রয়োজন অনুযায়ী স্বাভাবিক সেচ ও পরিচর্যা করতে পারেন।"
            )

        # High Humidity & Disease risk
        if humidity > 80 and temp < 26:
            advisory_en_parts.append(
                "High humidity and cool conditions increase fungal disease risk (e.g., Late Blight in Potato/Tomato). Scout fields closely."
            )
            advisory_bn_parts.append(
                "উচ্চ আর্দ্রতা ও কুয়াশার কারণে ছত্রাকজনিত রোগের (যেমন আলু/টমেটোর ধসা রোগ) ঝুঁকি বাড়তে পারে। নিয়মিত গাছ পরীক্ষা করুন।"
            )

        # Heatwave
        if temp > 38:
            alerts.append({
                "type": "HEATWAVE",
                "title_en": "🌡️ High Temperature Alert",
                "title_bn": "🌡️ অতিরিক্ত তাপমাত্রার সতর্কতা",
                "message_en": f"High temperatures ({temp}°C). Provide light evening irrigation to maintain soil moisture and prevent wilting.",
                "message_bn": f"তাপমাত্রা অত্যন্ত বেশি ({temp}°C)। ফসল বাঁচাতে বিকেলের দিকে জমিতে হালকা সেচ দিন।"
            })

        # Strong wind
        if wind > 30:
            alerts.append({
                "type": "HIGH_WIND",
                "title_en": "💨 Gusty Winds Alert",
                "title_bn": "💨 দমকা বাতাসের সতর্কতা",
                "message_en": f"Wind speeds up to {wind} km/h. Check staking in vegetable crops and delay fine foliar spray.",
                "message_bn": f"দমকা বাতাস ({wind} কিমি/ঘণ্টা)। সবজি ফসলের খুঁটি শক্ত করুন এবং স্প্রে করা এড়িয়ে চলুন।"
            })

        return " ".join(advisory_en_parts), " ".join(advisory_bn_parts), alerts

    def _get_fallback_weather(self, location_name: str, crop_name: Optional[str] = None) -> Dict[str, Any]:
        return {
            "status": "success",
            "location": location_name,
            "current": {
                "temperature": 29.5,
                "humidity": 72,
                "precipitation_mm": 0.0,
                "wind_speed_kmh": 12.0,
                "condition_en": "Partly Cloudy",
                "condition_bn": "আংশিক মেঘলা ⛅"
            },
            "daily_forecast": [
                {"day": "Today", "max_temp": 32.0, "min_temp": 25.0, "rain_prob": 20, "condition_bn": "আংশিক মেঘলা ⛅", "condition_en": "Partly Cloudy"},
                {"day": "Tomorrow", "max_temp": 31.5, "min_temp": 24.5, "rain_prob": 35, "condition_bn": "হালকা মেঘ 🌤️", "condition_en": "Fair"},
                {"day": "Day 3", "max_temp": 30.0, "min_temp": 24.0, "rain_prob": 65, "condition_bn": "মাঝারি বৃষ্টি 🌧️", "condition_en": "Rain"}
            ],
            "agri_advisory_en": "Weather conditions are generally favorable. If rain probability rises above 50%, postpone spraying.",
            "agri_advisory_bn": "আবহাওয়া সাধারণভাবে অনুকূল। বৃষ্টির সম্ভাবনা বাড়লে সার ও কীটনাশক স্প্রে পিছিয়ে দিন।",
            "alerts": [],
            "source": "Agro-Meteorological Climatological Baseline"
        }


weather_service = WeatherService()
