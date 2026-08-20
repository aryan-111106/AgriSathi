import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_api_chat_weather_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "phone": "919933001122",
            "message": "আজ আলুর দাম কত?"
        }
        res = await ac.post("/api/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "response" in data
        assert data["from_phone"] == "919933001122"


@pytest.mark.asyncio
async def test_api_tools_weather():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/tools/weather?district=Hooghly&crop=Potato")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "current" in data


@pytest.mark.asyncio
async def test_api_tools_market():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/tools/market?commodity=Potato&district=Hooghly")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert len(data["results"]) > 0


@pytest.mark.asyncio
async def test_api_tools_economics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/tools/economics/budget", json={"crop": "Potato", "area": 3.0, "unit": "bigha"})
        assert res.status_code == 200
        data = res.json()
        assert data["crop"] == "Potato"
        assert data["total_input_cost"] > 0


@pytest.mark.asyncio
async def test_api_farmer_profile():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First send a message to create farmer
        await ac.post("/api/chat", json={"phone": "919988776655", "message": "Hi"})

        # Query farmer profile
        res = await ac.get("/api/farmer/919988776655")
        assert res.status_code == 200
        farmer_data = res.json()
        assert farmer_data["phone"] == "919988776655"


@pytest.mark.asyncio
async def test_api_delete_farmer_cascade():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create farmer
        await ac.post("/api/chat", json={"phone": "919900000111", "message": "Hello"})

        # Delete profile
        res = await ac.delete("/api/farmer/919900000111")
        assert res.status_code == 200
        assert res.json()["status"] == "deleted"

        # Profile should be gone
        res = await ac.get("/api/farmer/919900000111")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_api_notification_preferences_crud():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/api/chat", json={"phone": "919900000222", "message": "Hi"})

        # Defaults
        res = await ac.get("/api/notifications/preferences/919900000222")
        assert res.status_code == 200
        assert res.json()["weather_alerts_enabled"] is True

        # Update
        res = await ac.put(
            "/api/notifications/preferences/919900000222",
            json={"weather_alerts_enabled": False, "max_per_day": 5}
        )
        assert res.status_code == 200
        body = res.json()["preferences"]
        assert body["weather_alerts_enabled"] is False
        assert body["max_per_day"] == 5

