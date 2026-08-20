import pytest
from app.models import NotificationPreference
from app.services.notification_service import notification_service


@pytest.mark.asyncio
async def test_get_or_create_preferences_creates(test_db):
    from app.models import FarmerProfile
    farmer = FarmerProfile(
        phone="910000000001",
        preferred_language="bn",
        state="West Bengal",
        district="Hooghly"
    )
    test_db.add(farmer)
    await test_db.commit()
    await test_db.refresh(farmer)

    pref = await notification_service.get_or_create_preferences(test_db, farmer)
    assert isinstance(pref, NotificationPreference)
    assert pref.weather_alerts_enabled is True
    assert pref.market_alerts_enabled is True


@pytest.mark.asyncio
async def test_quiet_hours_inclusive():
    from datetime import datetime
    pref = NotificationPreference(farmer_phone="x", quiet_hours_start=22, quiet_hours_end=6)
    assert notification_service._in_quiet_hours(pref, datetime(2026, 1, 1, 23, 0)) is True
    assert notification_service._in_quiet_hours(pref, datetime(2026, 1, 1, 12, 0)) is False
    assert notification_service._in_quiet_hours(pref, datetime(2026, 1, 1, 3, 0)) is True


@pytest.mark.asyncio
async def test_evaluate_market_alerts_threshold(test_db):
    from app.models import FarmerProfile
    farmer = FarmerProfile(phone="910000000002", preferred_language="bn", state="West Bengal", district="Hooghly")
    test_db.add(farmer)
    await test_db.commit()
    await test_db.refresh(farmer)

    market_results = {
        "results": [
            {
                "commodity": "Potato",
                "commodity_bn": "আলু",
                "market": "Sheoraphuli Mandi",
                "market_bn": "শেওড়াফুলি পাইকারি বাজার",
                "district": "Hooghly",
                "state": "West Bengal",
                "modal_price": 1850,
                "trend_7d_percent": 9.5  # > 8% threshold
            }
        ]
    }
    alerts = await notification_service.evaluate_market_alerts(test_db, farmer, market_results, "Potato")
    assert len(alerts) == 1
    assert "📈" in alerts[0]["en"]
    assert "বেড়েছে" in alerts[0]["bn"]


@pytest.mark.asyncio
async def test_evaluate_market_alerts_below_threshold(test_db):
    from app.models import FarmerProfile
    farmer = FarmerProfile(phone="910000000003", preferred_language="en", state="West Bengal", district="Hooghly")
    test_db.add(farmer)
    await test_db.commit()
    await test_db.refresh(farmer)

    market_results = {
        "results": [
            {"market": "X", "district": "Hooghly", "state": "West Bengal", "modal_price": 1850, "trend_7d_percent": 2.0}
        ]
    }
    alerts = await notification_service.evaluate_market_alerts(test_db, farmer, market_results, "Potato")
    assert alerts == []
