import pytest
from app.services.rag_service import rag_service


def test_rag_crop_lookup():
    info = rag_service.get_crop_info("potato")
    assert info is not None
    assert info["name_bn"] == "আলু"
    assert "fertilizer_recommendation" in info
    assert "growth_stages" in info


def test_fertilizer_dosage_bigha():
    fert = rag_service.get_fertilizer_guidance("Potato", area=3.0, unit="bigha")
    assert fert is not None
    assert fert["crop"] == "Potato"
    assert fert["recommended_doses"]["urea_kg"] > 0
    assert fert["recommended_doses"]["ssp_single_super_phosphate_kg"] > 0


def test_government_schemes_search():
    schemes = rag_service.search_schemes("কৃষক বন্ধু")
    assert len(schemes) > 0
    assert any("Krishak Bandhu" in s["name_en"] for s in schemes)

    bsb = rag_service.search_schemes("shasya bima")
    assert len(bsb) > 0
