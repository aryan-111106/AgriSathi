import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Response, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.whatsapp_service import whatsapp_service
from app.services.ai_orchestrator import ai_orchestrator

logger = logging.getLogger("agrisaathi.webhook")

router = APIRouter(prefix="/webhook", tags=["WhatsApp Webhook"])


@router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    """
    Meta WhatsApp Webhook Verification Endpoint.
    Meta sends a GET request to verify the webhook URL with the configured verification token.
    """
    logger.info(f"Received WhatsApp webhook verification request: mode={hub_mode}, token={hub_verify_token}")

    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("WhatsApp webhook verified successfully!")
        return Response(content=hub_challenge, media_type="text/plain", status_code=status.HTTP_200_OK)

    logger.warning("WhatsApp webhook verification failed: Invalid verify token")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


@router.post("/whatsapp")
async def receive_whatsapp_message(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Meta WhatsApp Inbound Event Webhook.
    Receives incoming WhatsApp messages (Text, Image, Audio, Location, Interactive Button/List replies).
    """
    try:
        body: Dict[str, Any] = await request.json()
    except Exception as e:
        logger.error(f"Invalid JSON payload: {e}")
        return {"status": "invalid_payload"}

    # Meta WhatsApp payload format validation
    entry = body.get("entry", [])
    if not entry:
        return {"status": "no_entry"}

    for change_entry in entry:
        changes = change_entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])

            if not messages:
                continue

            # Extract sender info
            sender_name = None
            if contacts:
                sender_name = contacts[0].get("profile", {}).get("name")

            for message in messages:
                from_phone = message.get("from")
                msg_id = message.get("id")
                msg_type = message.get("type")

                # Mark as read
                if msg_id:
                    await whatsapp_service.mark_as_read(msg_id)

                message_text = ""
                image_bytes = None
                audio_bytes = None
                location_data = None

                # 1. Text Message
                if msg_type == "text":
                    message_text = message.get("text", {}).get("body", "")

                # 2. Interactive Reply (Buttons or Lists)
                elif msg_type == "interactive":
                    interactive = message.get("interactive", {})
                    i_type = interactive.get("type")
                    if i_type == "button_reply":
                        btn_reply = interactive.get("button_reply", {})
                        message_text = btn_reply.get("id") or btn_reply.get("title", "")
                    elif i_type == "list_reply":
                        list_reply = interactive.get("list_reply", {})
                        message_text = list_reply.get("id") or list_reply.get("title", "")

                # 3. Image Message (Crop Disease Detection)
                elif msg_type == "image":
                    image_info = message.get("image", {})
                    media_id = image_info.get("id")
                    caption = image_info.get("caption", "")
                    message_text = caption
                    if media_id:
                        image_bytes = await whatsapp_service.download_media(media_id)

                # 4. Audio Voice Note Message
                elif msg_type == "audio" or msg_type == "voice":
                    audio_info = message.get("audio", {}) or message.get("voice", {})
                    media_id = audio_info.get("id")
                    if media_id:
                        audio_bytes = await whatsapp_service.download_media(media_id)

                # 5. Location Sharing Message
                elif msg_type == "location":
                    loc = message.get("location", {})
                    location_data = {
                        "latitude": loc.get("latitude"),
                        "longitude": loc.get("longitude")
                    }

                # Process message through AI Orchestrator
                if from_phone and (message_text or image_bytes or audio_bytes or location_data):
                    logger.info(f"Processing WhatsApp message from {from_phone}, type={msg_type}")
                    await ai_orchestrator.process_message(
                        db=db,
                        from_phone=from_phone,
                        message_text=message_text,
                        image_bytes=image_bytes,
                        audio_bytes=audio_bytes,
                        location_data=location_data,
                        sender_name=sender_name,
                        media_id=msg_id if msg_type == "image" else None
                    )

    return {"status": "success"}
