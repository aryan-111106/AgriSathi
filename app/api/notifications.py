from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import FarmerProfile, NotificationPreference

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class NotificationPreferenceUpdate(BaseModel):
    weather_alerts_enabled: Optional[bool] = None
    market_alerts_enabled: Optional[bool] = None
    crop_reminders_enabled: Optional[bool] = None
    disease_follow_up_enabled: Optional[bool] = None
    max_per_day: Optional[int] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None


def _serialize(pref: NotificationPreference) -> dict:
    return {
        "farmer_phone": pref.farmer_phone,
        "weather_alerts_enabled": bool(pref.weather_alerts_enabled),
        "market_alerts_enabled": bool(pref.market_alerts_enabled),
        "crop_reminders_enabled": bool(pref.crop_reminders_enabled),
        "disease_follow_up_enabled": bool(pref.disease_follow_up_enabled),
        "max_per_day": int(pref.max_per_day or 3),
        "quiet_hours_start": int(pref.quiet_hours_start or 22),
        "quiet_hours_end": int(pref.quiet_hours_end or 6)
    }


@router.get("/preferences/{phone}")
async def get_preferences(
    phone: str,
    db: AsyncSession = Depends(get_db)
):
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    stmt = select(FarmerProfile).where(FarmerProfile.phone == clean_phone)
    res = await db.execute(stmt)
    farmer = res.scalar_one_or_none()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    if farmer.notification_preferences:
        return _serialize(farmer.notification_preferences)
    pref = NotificationPreference(farmer_phone=clean_phone)
    pref.weather_alerts_enabled = True
    pref.market_alerts_enabled = True
    pref.crop_reminders_enabled = False
    pref.disease_follow_up_enabled = True
    pref.max_per_day = 3
    pref.quiet_hours_start = 22
    pref.quiet_hours_end = 6
    return _serialize(pref)


@router.put("/preferences/{phone}")
async def update_preferences(
    phone: str,
    update: NotificationPreferenceUpdate,
    db: AsyncSession = Depends(get_db)
):
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    stmt = select(NotificationPreference).where(
        NotificationPreference.farmer_phone == clean_phone
    )
    res = await db.execute(stmt)
    pref = res.scalar_one_or_none()
    if not pref:
        farmer_stmt = select(FarmerProfile).where(FarmerProfile.phone == clean_phone)
        farmer_res = await db.execute(farmer_stmt)
        farmer = farmer_res.scalar_one_or_none()
        if not farmer:
            raise HTTPException(status_code=404, detail="Farmer not found")
        pref = NotificationPreference(farmer_phone=clean_phone)
        db.add(pref)

    for field, val in update.model_dump(exclude_unset=True).items():
        setattr(pref, field, val)

    await db.commit()
    await db.refresh(pref)
    return {"status": "success", "preferences": _serialize(pref)}
