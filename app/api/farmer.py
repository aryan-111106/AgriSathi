from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import FarmerProfile, Crop

router = APIRouter(prefix="/api/farmer", tags=["Farmer Profile"])


class FarmerProfileUpdate(BaseModel):
    name: Optional[str] = None
    preferred_language: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    block: Optional[str] = None
    village: Optional[str] = None
    farm_size: Optional[float] = None
    farm_size_unit: Optional[str] = None
    soil_type: Optional[str] = None
    irrigation_source: Optional[str] = None


class CropCreate(BaseModel):
    crop_name: str
    crop_name_bn: Optional[str] = None
    variety: Optional[str] = None
    area: Optional[float] = None
    area_unit: str = "bigha"
    growth_stage: Optional[str] = "Vegetative"


@router.get("/{phone}")
async def get_farmer_profile(
    phone: str,
    db: AsyncSession = Depends(get_db)
):
    """Get farmer profile and registered crops."""
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    stmt = select(FarmerProfile).where(FarmerProfile.phone == clean_phone)
    res = await db.execute(stmt)
    farmer = res.scalar_one_or_none()

    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer profile not found")

    return {
        "phone": farmer.phone,
        "name": farmer.name,
        "preferred_language": farmer.preferred_language,
        "state": farmer.state,
        "district": farmer.district,
        "block": farmer.block,
        "village": farmer.village,
        "farm_size": farmer.farm_size,
        "farm_size_unit": farmer.farm_size_unit,
        "is_onboarded": farmer.is_onboarded,
        "crops": [
            {
                "id": c.id,
                "name": c.crop_name,
                "name_bn": c.crop_name_bn,
                "variety": c.variety,
                "area": c.area,
                "growth_stage": c.growth_stage
            }
            for c in farmer.crops
        ]
    }


@router.put("/{phone}")
async def update_farmer_profile(
    phone: str,
    update_data: FarmerProfileUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update farmer profile details."""
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    stmt = select(FarmerProfile).where(FarmerProfile.phone == clean_phone)
    res = await db.execute(stmt)
    farmer = res.scalar_one_or_none()

    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer profile not found")

    for field, val in update_data.model_dump(exclude_unset=True).items():
        setattr(farmer, field, val)

    await db.commit()
    await db.refresh(farmer)
    return {"status": "success", "farmer": farmer.phone}


@router.post("/{phone}/crops")
async def add_crop_to_farmer(
    phone: str,
    crop_data: CropCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a new crop to farmer profile."""
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    stmt = select(FarmerProfile).where(FarmerProfile.phone == clean_phone)
    res = await db.execute(stmt)
    farmer = res.scalar_one_or_none()

    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer profile not found")

    new_crop = Crop(
        farmer_phone=clean_phone,
        crop_name=crop_data.crop_name,
        crop_name_bn=crop_data.crop_name_bn,
        variety=crop_data.variety,
        area=crop_data.area or farmer.farm_size,
        area_unit=crop_data.area_unit or farmer.farm_size_unit,
        growth_stage=crop_data.growth_stage
    )
    db.add(new_crop)
    await db.commit()
    await db.refresh(new_crop)

    return {"status": "success", "crop_id": new_crop.id}


@router.delete("/{phone}")
async def delete_farmer_profile(
    phone: str,
    db: AsyncSession = Depends(get_db)
):
    """Permanently delete a farmer profile and all associated data
    (crops, conversations, disease reports, alerts, watches, preferences).
    Implements PRD §54 (User-controlled deletion).
    """
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    stmt = select(FarmerProfile).where(FarmerProfile.phone == clean_phone)
    res = await db.execute(stmt)
    farmer = res.scalar_one_or_none()

    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer profile not found")

    await db.delete(farmer)
    await db.commit()
    return {"status": "deleted", "farmer_phone": clean_phone}


@router.delete("/{phone}/data/images")
async def delete_farmer_images(
    phone: str,
    db: AsyncSession = Depends(get_db)
):
    """Wipe stored disease-report images for a farmer. Keeps diagnosis
    metadata (text only) but removes image_url/media_id references.
    """
    from app.models import DiseaseReport

    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    stmt = select(DiseaseReport).where(DiseaseReport.farmer_phone == clean_phone)
    res = await db.execute(stmt)
    reports = res.scalars().all()

    count = 0
    for r in reports:
        if r.image_url or r.media_id:
            r.image_url = None
            r.media_id = None
            count += 1

    await db.commit()
    return {"status": "success", "images_wiped": count}
