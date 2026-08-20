import base64
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import FarmerProfile, Conversation, Message
from app.services.ai_orchestrator import ai_orchestrator

router = APIRouter(prefix="/api", tags=["Chat & Conversations"])


class ChatRequest(BaseModel):
    phone: str = "919876543210"
    message: str = ""
    language: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_base64: Optional[str] = None


@router.post("/chat")
async def chat_endpoint(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Direct Chat API endpoint to communicate with AgriSaathi.
    """
    image_bytes = None
    if req.image_base64:
        try:
            # Handle data URL prefix if present
            raw_b64 = req.image_base64.split(",")[-1]
            image_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 image: {e}")

    loc_data = None
    if req.latitude is not None and req.longitude is not None:
        loc_data = {"latitude": req.latitude, "longitude": req.longitude}

    result = await ai_orchestrator.process_message(
        db=db,
        from_phone=req.phone,
        message_text=req.message,
        image_bytes=image_bytes,
        location_data=loc_data
    )

    return result


@router.get("/conversations/{phone}")
async def get_conversation_history(
    phone: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve conversation messages for a farmer's phone number."""
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    stmt = select(Conversation).where(Conversation.farmer_phone == clean_phone)
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()

    if not conv:
        return {"messages": []}

    stmt_msgs = select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.asc())
    msgs_res = await db.execute(stmt_msgs)
    messages = msgs_res.scalars().all()

    return {
        "phone": clean_phone,
        "active_crop": conv.active_crop,
        "messages": [
            {
                "id": m.id,
                "sender": m.sender,
                "direction": m.direction,
                "type": m.message_type,
                "content": m.content,
                "intent": m.intent,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    }
