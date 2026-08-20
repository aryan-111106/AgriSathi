from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    farmer_phone: Mapped[str] = mapped_column(String(30), ForeignKey("farmer_profiles.phone"), primary_key=True)
    weather_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    market_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    crop_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    disease_follow_up_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    max_per_day: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    quiet_hours_start: Mapped[int] = mapped_column(Integer, default=22, server_default="22")
    quiet_hours_end: Mapped[int] = mapped_column(Integer, default=6, server_default="6")

    farmer: Mapped["FarmerProfile"] = relationship("FarmerProfile", back_populates="notification_preferences")

