import io
import pytest
from PIL import Image
from app.services.vision_service import vision_service


@pytest.mark.asyncio
async def test_vision_diagnosis_sample_image():
    img = Image.new("RGB", (100, 100), color="green")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    raw_bytes = img_byte_arr.getvalue()

    result = await vision_service.diagnose_crop_image(raw_bytes, crop_hint="Potato", farmer_lang="bn")
    assert result["status"] == "success"
    assert "crop_detected" in result
    assert "disease_name" in result
    assert "confidence_score" in result
    assert "summary_text_bn" in result
    assert "image_quality" in result
    assert "requires_more_info" in result


def test_image_quality_high_resolution():
    img = Image.new("RGB", (1200, 1200), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    q = vision_service._validate_image_quality(buf.getvalue())
    assert q["quality_score"] >= 0.8
    assert q["is_acceptable"] is True


def test_image_quality_tiny_image():
    img = Image.new("RGB", (50, 50), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    q = vision_service._validate_image_quality(buf.getvalue())
    assert q["quality_score"] < 0.5
    assert q["is_acceptable"] is False
    assert len(q["reasons"]) > 0


def test_image_quality_extreme_aspect_ratio():
    img = Image.new("RGB", (3000, 100), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    q = vision_service._validate_image_quality(buf.getvalue())
    assert any("elongated" in r for r in q["reasons"])


def test_image_quality_invalid_bytes():
    q = vision_service._validate_image_quality(b"not an image at all")
    assert q["quality_score"] == 0.0
    assert q["is_acceptable"] is False


@pytest.mark.asyncio
async def test_low_confidence_triggers_followup():
    img = Image.new("RGB", (50, 50), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw_bytes = buf.getvalue()
    result = await vision_service.diagnose_crop_image(raw_bytes, crop_hint="Unknown", farmer_lang="en")
    assert result["requires_more_info"] is True
