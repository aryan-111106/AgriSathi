from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, ForeignKey, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class DiseaseReport(Base):
    __tablename__ = "disease_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmer_phone: Mapped[str] = mapped_column(String(30), ForeignKey("farmer_profiles.phone"), index=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    media_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    crop_detected: Mapped[str] = mapped_column(String(100))
    disease_name: Mapped[str] = mapped_column(String(150))
    disease_name_bn: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # e.g., 0.85
    confidence_level: Mapped[str] = mapped_column(String(20), default="Medium")  # High, Medium, Low
    severity: Mapped[str] = mapped_column(String(20), default="Moderate")  # Mild, Moderate, Severe
    symptoms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    biological_control: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cultural_control: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chemical_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    safety_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requires_expert_consultation: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    farmer: Mapped["FarmerProfile"] = relationship("FarmerProfile", back_populates="disease_reports")
