import pytest
from app.services.telegram_service import TelegramService


def test_split_buttons_default_two_per_row():
    buttons = [
        {"id": "a", "title": "Apple"},
        {"id": "b", "title": "Banana"},
        {"id": "c", "title": "Cherry"},
        {"id": "d", "title": "Date"},
        {"id": "e", "title": "Elderberry"},
    ]
    rows = TelegramService._split_buttons(buttons)
    assert len(rows) == 3
    assert len(rows[0]) == 2
    assert len(rows[1]) == 2
    assert len(rows[2]) == 1
    assert rows[0][0] == {"text": "Apple", "callback_data": "a"}


def test_split_buttons_truncates_long_values():
    buttons = [
        {
            "id": "x" * 100,
            "title": "T" * 200,
        }
    ]
    rows = TelegramService._split_buttons(buttons)
    assert len(rows[0][0]["text"]) == 64
    assert len(rows[0][0]["callback_data"]) == 64


def test_chunk_text_under_limit():
    text = "Hello world"
    chunks = TelegramService._chunk_text(text, 4096)
    assert chunks == ["Hello world"]


def test_chunk_text_over_limit():
    text = "a" * 5000
    chunks = TelegramService._chunk_text(text, 1000)
    assert len(chunks) >= 5
    for c in chunks:
        assert len(c) <= 1000


def test_chunk_text_preserves_lines():
    text = "\n".join(["line"] * 2000)  # ~10000 chars
    chunks = TelegramService._chunk_text(text, 2000)
    joined = "".join(chunks)
    assert joined == text


@pytest.mark.asyncio
async def test_send_text_mock_when_unconfigured():
    svc = TelegramService()
    svc.token = None
    res = await svc.send_text("123", "hello")
    assert res["status"] == "mock_sent"


@pytest.mark.asyncio
async def test_download_file_returns_none_when_unconfigured():
    svc = TelegramService()
    svc.token = None
    res = await svc.download_file("any_file_id")
    assert res is None
