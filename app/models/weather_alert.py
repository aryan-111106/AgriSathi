from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class WeatherAlert(Base):
    __tablename__ = "weather_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmer_phone: Mapped[str] = mapped_column(String(30), ForeignKey("farmer_profiles.phone"), index=True)
    alert_type: Mapped[str] = mapped_column(String(30), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="Moderate")
    title_en: Mapped[str] = mapped_column(String(200))
    title_bn: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message_en: Mapped[str] = mapped_column(Text)
    message_bn: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(100), default="Open-Meteo Real-time Alert Engine")

    farmer: Mapped["FarmerProfile"] = relationship("FarmerProfile", back_populates="weather_alerts")
