"""Telegram webhook handler.

Receives updates from the Telegram Bot API at `POST /webhook/telegram`,
parses them, and routes them to the AI orchestrator. Mirrors the role
of `app/api/webhook.py` (the WhatsApp equivalent) but is built around
the Telegram Bot API's update shape.

Security: Telegram signs webhook requests with an `X-Telegram-Bot-Api-Secret-Token`
header matching the `secret_token` passed to `setWebhook`. If
`telegram_webhook_secret` is set, we enforce that header here.
"""

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.ai_orchestrator import ai_orchestrator
from app.services.telegram_service import telegram_service

logger = logging.getLogger("agrisaathi.telegram_webhook")

router = APIRouter(prefix="/webhook", tags=["Telegram Webhook"])


def _secret_ok(provided: Optional[str]) -> bool:
    """Constant-time compare with the configured webhook secret."""
    expected = (settings.telegram_webhook_secret or "").encode()
    if not expected:
        return True  # secret not configured → don't enforce
    if not provided:
        return False
    return hmac.compare_digest(provided.encode(), expected)


def _extract_message(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pull the actual message-like payload from a Telegram Update."""
    if "message" in update and update["message"]:
        return update["message"]
    if "edited_message" in update and update["edited_message"]:
        return update["edited_message"]
    if "callback_query" in update and update["callback_query"]:
        # Treat button presses as messages with text = callback_data
        cq = update["callback_query"]
        return {
            "chat": cq.get("message", {}).get("chat", {}),
            "from": cq.get("from", {}),
            "text": cq.get("data", ""),
            "is_callback": True,
            "callback_id": cq.get("id"),
        }
    return None


def _largest_photo(photos: list) -> Optional[str]:
    """Telegram sends multiple sizes — pick the largest for diagnosis."""
    if not photos:
        return None
    return max(photos, key=lambda p: p.get("file_size", 0) or 0).get("file_id")


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Entry point for Telegram updates."""
    if not _secret_ok(x_telegram_bot_api_secret_token):
        logger.warning("Telegram webhook rejected: bad/missing secret token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret",
        )

    try:
        update = await request.json()
    except Exception as e:
        logger.error(f"Invalid JSON from Telegram: {e}")
        return {"status": "invalid_payload"}

    msg = _extract_message(update)
    if not msg:
        return {"status": "ignored"}

    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if not chat_id:
        return {"status": "no_chat_id"}

    sender = msg.get("from") or {}
    sender_name = (
        sender.get("first_name")
        or sender.get("username")
        or sender.get("id")
    )
    if sender.get("last_name"):
        sender_name = f"{sender_name} {sender['last_name']}".strip()

    message_text: str = msg.get("text") or msg.get("caption") or ""
    image_bytes: Optional[bytes] = None
    audio_bytes: Optional[bytes] = None
    location_data: Optional[Dict[str, float]] = None
    callback_id: Optional[str] = msg.get("callback_id")

    # Photos (Telegram delivers them as a list of sizes)
    photos = msg.get("photo") or []
    if photos:
        file_id = _largest_photo(photos)
        if file_id:
            image_bytes = await telegram_service.download_file(file_id)
            # Telegram message text is in 'caption' for photos (already covered above)

    # Voice / audio
    voice = msg.get("voice") or msg.get("audio")
    if voice:
        file_id = voice.get("file_id")
        if file_id:
            audio_bytes = await telegram_service.download_file(file_id)

    # Location
    loc = msg.get("location")
    if loc:
        location_data = {
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
        }

    # Typing indicator for nicer UX
    if not message_text == "/start":
        await telegram_service.send_typing(chat_id)

    # Answer the callback query immediately so Telegram stops the loading spinner
    if callback_id:
        await telegram_service.answer_callback(callback_id)

    # Route through orchestrator. `from_phone` here is the chat_id; the
    # orchestrator uses it as the primary key for `FarmerProfile.phone`.
    # If you want to keep `phone` strictly as a phone number, see the
    # `telegram_chat_id` column on FarmerProfile — orchestrator will fill
    # both when available.
    await ai_orchestrator.process_message(
        db=db,
        from_phone=chat_id,
        message_text=message_text,
        image_bytes=image_bytes,
        audio_bytes=audio_bytes,
        location_data=location_data,
        sender_name=str(sender_name) if sender_name else None,
        chat_id=chat_id,
        is_callback=bool(callback_id),
    )

    return {"status": "ok"}


@router.get("/telegram/health")
async def telegram_webhook_health():
    return {
        "status": "ok",
        "channel": "telegram",
        "configured": telegram_service.is_configured,
        "webhook_secret_set": bool(settings.telegram_webhook_secret),
    }
