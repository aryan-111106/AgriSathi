from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Float, DateTime, Date, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Crop(Base):
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmer_phone: Mapped[str] = mapped_column(String(30), ForeignKey("farmer_profiles.phone"), index=True)
    crop_name: Mapped[str] = mapped_column(String(100))  # e.g., "Potato", "Rice / Paddy", "Mustard", "Tomato"
    crop_name_bn: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "আলু", "ধান"
    variety: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "Kufri Jyoti", "Swarna"
    area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_unit: Mapped[str] = mapped_column(String(20), default="bigha")
    sowing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    growth_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Nursery, Tillering, Flowering, Harvesting
    soil_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Alluvial, Clay Loam, Sandy Loam
    irrigation_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Canal, Tube-well, Rainfed, Drip
    expected_harvest_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    farmer: Mapped["FarmerProfile"] = relationship("FarmerProfile", back_populates="crops")
    events: Mapped[list["CropEvent"]] = relationship("CropEvent", back_populates="crop", cascade="all, delete-orphan", lazy="selectin")


class CropEvent(Base):
    __tablename__ = "crop_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crop_id: Mapped[int] = mapped_column(Integer, ForeignKey("crops.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    event_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    crop: Mapped["Crop"] = relationship("Crop", back_populates="events")
