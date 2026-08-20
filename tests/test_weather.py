import pytest
from app.services.weather_service import weather_service


@pytest.mark.asyncio
async def test_weather_district_lookup():
    forecast = await weather_service.get_forecast(location_name="Hooghly", crop_name="Potato")
    assert forecast["status"] == "success"
    assert "Hooghly" in forecast["location"]
    assert "current" in forecast
    assert "temperature" in forecast["current"]
    assert "daily_forecast" in forecast
    assert len(forecast["daily_forecast"]) > 0
    assert "agri_advisory_bn" in forecast
    assert "agri_advisory_en" in forecast


@pytest.mark.asyncio
async def test_weather_gps_lookup():
    forecast = await weather_service.get_forecast(lat=23.2324, lon=87.8615, crop_name="Rice")
    assert forecast["status"] == "success"
    assert "current" in forecast
    assert forecast["current"]["temperature"] is not None
