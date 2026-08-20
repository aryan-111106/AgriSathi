from typing import Optional, List
from fastapi import APIRouter, Query, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from app.services.weather_service import weather_service
from app.services.market_service import market_service
from app.services.vision_service import vision_service
from app.services.rag_service import rag_service
from app.services.economics_service import economics_service

router = APIRouter(prefix="/api/tools", tags=["Agricultural Tools"])


class BudgetRequest(BaseModel):
    crop: str = "Potato"
    area: float = 3.0
    unit: str = "bigha"


class CropComparisonRequest(BaseModel):
    crop1: str = "Potato"
    crop2: str = "Mustard"
    area: float = 3.0
    unit: str = "bigha"


@router.get("/weather")
async def get_weather(
    district: Optional[str] = Query("Hooghly"),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    crop: Optional[str] = Query("Potato")
):
    """Get real-time weather, 7-day forecast, and agricultural advisory."""
    return await weather_service.get_forecast(location_name=district, lat=lat, lon=lon, crop_name=crop)


@router.get("/market")
async def get_market_prices(
    commodity: Optional[str] = Query("Potato"),
    district: Optional[str] = Query(None),
    state: Optional[str] = Query("West Bengal"),
    lat: Optional[float] = Query(None, description="Farmer latitude for distance sort"),
    lon: Optional[float] = Query(None, description="Farmer longitude for distance sort")
):
    """Search mandi prices and price trends.

    When lat/lon are supplied, results include `distance_km` per market and
    are sorted by proximity ascending; otherwise by modal price descending.
    """
    return market_service.search_prices(
        commodity=commodity,
        district=district,
        state=state,
        farmer_lat=lat,
        farmer_lon=lon
    )


@router.post("/vision/diagnose")
async def diagnose_crop(
    file: UploadFile = File(...),
    crop_hint: Optional[str] = Form(None),
    language: str = Form("bn")
):
    """Diagnose crop disease from uploaded photograph."""
    content = await file.read()
    return await vision_service.diagnose_crop_image(content, crop_hint=crop_hint, farmer_lang=language)


@router.get("/schemes")
async def get_schemes(
    query: str = Query("agriculture")
):
    """Search agricultural government schemes."""
    return rag_service.search_schemes(query)


@router.post("/economics/budget")
async def calculate_budget(req: BudgetRequest):
    """Calculate farm budget, input costs, and estimated profit."""
    res = economics_service.calculate_budget(req.crop, req.area, req.unit)
    if not res:
        raise HTTPException(status_code=400, detail="Crop not supported for economics benchmark")
    return res


@router.post("/economics/compare")
async def compare_crops(req: CropComparisonRequest):
    """Compare two crops economics side by side."""
    res = economics_service.compare_crops(req.crop1, req.crop2, req.area, req.unit)
    if not res:
        raise HTTPException(status_code=400, detail="Could not compare requested crops")
    return res
