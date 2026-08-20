import json
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings


def _make_update(chat_id: str = "12345", text: str = "Hi") -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": int(chat_id), "type": "private"},
            "from": {"id": int(chat_id), "is_bot": False, "first_name": "Test"},
            "text": text,
        }
    }


def _make_callback_update(chat_id: str = "12345", data: str = "diag_skip") -> dict:
    return {
        "update_id": 2,
        "callback_query": {
            "id": "cb_1",
            "from": {"id": int(chat_id), "is_bot": False, "first_name": "Test"},
            "chat_instance": "x",
            "data": data,
            "message": {
                "message_id": 5,
                "date": 0,
                "chat": {"id": int(chat_id), "type": "private"},
                "from": {"id": 999, "is_bot": True, "first_name": "Bot"},
                "text": "ignored",
            }
        }
    }


@pytest.mark.asyncio
async def test_telegram_webhook_rejects_bad_secret(monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "expected_secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/webhook/telegram",
            json=_make_update(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_telegram_webhook_accepts_text(monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "")  # disabled
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/webhook/telegram",
            json=_make_update(chat_id="555000111", text="Hi")
        )
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_telegram_webhook_accepts_callback(monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/webhook/telegram",
            json=_make_callback_update(chat_id="555000222", data="diag_skip")
        )
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_telegram_webhook_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/webhook/telegram/health")
        assert res.status_code == 200
        assert res.json()["channel"] == "telegram"


@pytest.mark.asyncio
async def test_telegram_webhook_ignores_unknown_update(monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/webhook/telegram",
            json={"update_id": 99, "inline_query": {"query": "x"}}
        )
        assert res.status_code == 200
        assert res.json()["status"] == "ignored"
