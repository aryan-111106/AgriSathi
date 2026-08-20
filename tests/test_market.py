import pytest
from app.services.market_service import market_service, haversine_km


def test_haversine_zero():
    assert haversine_km(22.5, 88.3, 22.5, 88.3) == 0.0


def test_haversine_known_distance():
    # Kolkata to Howrah is ~10 km
    d = haversine_km(22.5726, 88.3639, 22.5958, 88.2636)
    assert 5 < d < 20


def test_market_price_search_bengali_alias():
    res = market_service.search_prices(commodity="আলু", district="Hooghly")
    assert res["status"] == "success"
    assert res["total_markets_found"] > 0
    first_result = res["results"][0]
    assert first_result["commodity"] == "Potato"
    assert "modal_price" in first_result
    assert first_result["modal_price"] > 0


def test_market_price_search_paddy():
    res = market_service.search_prices(commodity="Paddy", district="Purba Bardhaman")
    assert res["status"] == "success"
    assert res["total_markets_found"] > 0


def test_market_summary_formatting():
    res = market_service.search_prices(commodity="Potato", district="Hooghly")
    formatted_bn = market_service.format_market_summary(res, lang="bn")
    assert "বাজার দর" in formatted_bn
    assert "₹" in formatted_bn

    formatted_en = market_service.format_market_summary(res, lang="en")
    assert "Mandi Market Rates" in formatted_en


def test_market_distance_sort_with_gps():
    # Kolkata GPS should sort Kolkata markets first
    res = market_service.search_prices(
        commodity="Potato",
        district=None,
        farmer_lat=22.5726,
        farmer_lon=88.3639
    )
    assert res["sorted_by"] == "distance"
    assert all("distance_km" in r for r in res["results"])
    # First result should be a Kolkata or nearby market
    first_dist = res["results"][0].get("distance_km")
    assert first_dist is not None
    last_dist = res["results"][-1].get("distance_km")
    assert first_dist <= last_dist


def test_market_distance_omitted_without_gps():
    res = market_service.search_prices(commodity="Potato", district="Hooghly")
    assert res["sorted_by"] == "modal_price"
    for r in res["results"]:
        assert r.get("distance_km") is None


def test_market_summary_includes_distance_when_available():
    res = market_service.search_prices(
        commodity="Potato",
        farmer_lat=22.5726,
        farmer_lon=88.3639
    )
    formatted = market_service.format_market_summary(res, lang="en")
    assert "km away" in formatted

