from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Integer, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class MarketWatch(Base):
    __tablename__ = "market_watches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmer_phone: Mapped[str] = mapped_column(String(30), ForeignKey("farmer_profiles.phone"), index=True)
    commodity: Mapped[str] = mapped_column(String(100), index=True)
    district: Mapped[str] = mapped_column(String(100), index=True)
    state: Mapped[str] = mapped_column(String(100), default="West Bengal")
    baseline_price: Mapped[float] = mapped_column(Float, default=0.0)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    change_percent: Mapped[float] = mapped_column(Float, default=0.0)
    last_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    farmer: Mapped["FarmerProfile"] = relationship("FarmerProfile", back_populates="market_watches")
