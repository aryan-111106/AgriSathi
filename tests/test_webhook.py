import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings


@pytest.mark.asyncio
async def test_webhook_verification_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": settings.whatsapp_verify_token,
            "hub.challenge": "challenge_code_12345"
        }
        res = await ac.get("/webhook/whatsapp", params=params)
        assert res.status_code == 200
        assert res.text == "challenge_code_12345"


@pytest.mark.asyncio
async def test_webhook_verification_failure():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "challenge_code_12345"
        }
        res = await ac.get("/webhook/whatsapp", params=params)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_webhook_inbound_text_message():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"display_phone_number": "1234567890", "phone_number_id": "123456"},
                                "contacts": [{"profile": {"name": "Subhasis Mondal"}, "wa_id": "919876543210"}],
                                "messages": [
                                    {
                                        "from": "919876543210",
                                        "id": "wamid.HBgL...",
                                        "timestamp": "1724083200",
                                        "type": "text",
                                        "text": {"body": "আজ আলুর দাম কত?"}
                                    }
                                ]
                            },
                            "field": "messages"
                        }
                    ]
                }
            ]
        }
        res = await ac.post("/webhook/whatsapp", json=payload)
        assert res.status_code == 200
        assert res.json() == {"status": "success"}
