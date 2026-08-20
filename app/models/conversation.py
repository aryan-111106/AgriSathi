from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmer_phone: Mapped[str] = mapped_column(String(30), ForeignKey("farmer_profiles.phone"), index=True)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    active_crop: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    context_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    pending_diagnosis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    farmer: Mapped["FarmerProfile"] = relationship("FarmerProfile", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", lazy="selectin")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), index=True)
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    sender: Mapped[str] = mapped_column(String(20))  # "farmer" or "bot"
    direction: Mapped[str] = mapped_column(String(10), default="inbound")  # "inbound" or "outbound"
    message_type: Mapped[str] = mapped_column(String(20), default="text")  # text, image, audio, location, interactive, button
    content: Mapped[str] = mapped_column(Text)
    media_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    media_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="bn")
    intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tool_calls: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
