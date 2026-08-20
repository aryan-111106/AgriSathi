from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Float, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class FarmerProfile(Base):
    __tablename__ = "farmer_profiles"

    phone: Mapped[str] = mapped_column(String(30), primary_key=True, index=True)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="bn")  # 'bn' or 'en'
    state: Mapped[str] = mapped_column(String(100), default="West Bengal")
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    block: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    village: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    farm_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    farm_size_unit: Mapped[str] = mapped_column(String(20), default="bigha")  # acre, bigha, hectare
    soil_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    irrigation_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_step: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    crops: Mapped[List["Crop"]] = relationship("Crop", back_populates="farmer", cascade="all, delete-orphan", lazy="selectin")
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="farmer", cascade="all, delete-orphan", lazy="selectin")
    disease_reports: Mapped[List["DiseaseReport"]] = relationship("DiseaseReport", back_populates="farmer", cascade="all, delete-orphan", lazy="selectin")
    weather_alerts: Mapped[List["WeatherAlert"]] = relationship("WeatherAlert", back_populates="farmer", cascade="all, delete-orphan", lazy="selectin")
    market_watches: Mapped[List["MarketWatch"]] = relationship("MarketWatch", back_populates="farmer", cascade="all, delete-orphan", lazy="selectin")
    notification_preferences: Mapped[Optional["NotificationPreference"]] = relationship(
        "NotificationPreference",
        back_populates="farmer",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin"
    )
