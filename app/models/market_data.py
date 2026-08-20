from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Float, DateTime, Date, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MarketPriceCache(Base):
    __tablename__ = "market_price_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commodity: Mapped[str] = mapped_column(String(100), index=True)
    commodity_bn: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    variety: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    market: Mapped[str] = mapped_column(String(150), index=True)
    market_bn: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    district: Mapped[str] = mapped_column(String(100), index=True)
    state: Mapped[str] = mapped_column(String(100), default="West Bengal", index=True)
    min_price: Mapped[float] = mapped_column(Float)  # INR per quintal
    max_price: Mapped[float] = mapped_column(Float)
    modal_price: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30), default="₹/Quintal")
    price_date: Mapped[date] = mapped_column(Date, default=date.today)
    trend_7d_percent: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(100), default="Agmarknet / State Agricultural Marketing Board")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
