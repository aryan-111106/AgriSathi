import pytest
from app.services.ai_orchestrator import ai_orchestrator


def test_intent_classification():
    assert ai_orchestrator.classify_intent("আগামীকাল কি বৃষ্টি হবে?") == "WEATHER"
    assert ai_orchestrator.classify_intent("What is today's potato price in Burdwan?") == "MARKET_PRICE"
    assert ai_orchestrator.classify_intent("আলুতে কত সার লাগবে?") == "FERTILIZER_SOIL"
    assert ai_orchestrator.classify_intent("Which is better potato or mustard?") == "FARM_ECONOMICS"
    assert ai_orchestrator.classify_intent("কৃষক বন্ধু প্রকল্পের সুবিধা কি?") == "GOVERNMENT_SCHEME"
    assert ai_orchestrator.classify_intent("menu") == "MENU"


def test_intent_classification_banglish():
    """PRD §30 — Bengali-English code-switching must classify correctly."""
    assert ai_orchestrator.classify_intent("কাল weather কেমন থাকবে?") == "WEATHER"
    assert ai_orchestrator.classify_intent("ধানের জন্য fertilizer কখন দেব?") == "FERTILIZER_SOIL"
    assert ai_orchestrator.classify_intent("Potato তে এই disease কেন হচ্ছে?") == "DISEASE_DIAGNOSIS"
    assert ai_orchestrator.classify_intent("আলুর dam koto?") == "MARKET_PRICE"


def test_intent_classification_followup_buttons():
    assert ai_orchestrator.classify_intent("diag_more_photo") == "DISEASE_FOLLOWUP"
    assert ai_orchestrator.classify_intent("diag_expert") == "DISEASE_FOLLOWUP"
    assert ai_orchestrator.classify_intent("diag_skip") == "DISEASE_FOLLOWUP"


def test_language_detection():
    assert ai_orchestrator.detect_language("আজকের আবহাওয়া কেমন?") == "bn"
    assert ai_orchestrator.detect_language("What will be the weather tomorrow?") == "en"


def test_quality_metrics_internal():
    q = ai_orchestrator._compute_quality_metrics(
        intent="WEATHER",
        tool_data={"weather": {"source": "Open-Meteo"}},
        response_text="আজ আবহাওয়া ভালো"
    )
    assert q["answer_confidence"] == "high"
    assert q["source_quality"] == "official"
    assert q["safety_risk"] == "low"


@pytest.mark.asyncio
async def test_full_orchestrator_flow(test_db):
    # Test market price flow
    res = await ai_orchestrator.process_message(
        db=test_db,
        from_phone="919876543210",
        message_text="আজ আলুর দাম কত?"
    )
    assert res["status"] in ["success", "onboarding", "onboarding_started"]
    assert "response" in res


@pytest.mark.asyncio
async def test_onboarding_block_and_village_collection(test_db):
    """PRD §10 — block + village must be captured during onboarding."""
    phone = "919876543211"

    # Step 0: language
    r1 = await ai_orchestrator.process_message(test_db, phone, "English")
    assert r1["status"] in ["onboarding", "success"]

    # Step 1: district
    r2 = await ai_orchestrator.process_message(test_db, phone, "Hooghly")
    assert r2["status"] == "onboarding"

    # Step 2: block
    r3 = await ai_orchestrator.process_message(test_db, phone, "Arambagh")
    assert r3["status"] == "onboarding"

    # Step 3: village
    r4 = await ai_orchestrator.process_message(test_db, phone, "Singur")
    assert r4["status"] == "onboarding"

    # Step 4: farm area
    r5 = await ai_orchestrator.process_message(test_db, phone, "3 bigha")
    assert r5["status"] == "onboarding"

    # Step 5: crop
    r6 = await ai_orchestrator.process_message(test_db, phone, "Potato")
    assert r6["status"] == "onboarding"

    # Step 6: phone (skip)
    r7 = await ai_orchestrator.process_message(test_db, phone, "skip")
    assert r7["status"] == "onboarding"
    assert r7.get("completed") is True

    # Verify persisted
    from sqlalchemy import select
    from app.models import FarmerProfile
    stmt = select(FarmerProfile).where(FarmerProfile.phone == phone)
    res = await test_db.execute(stmt)
    farmer = res.scalar_one()
    assert farmer.district == "Hooghly"
    assert farmer.block == "Arambagh"
    assert farmer.village == "Singur"
    assert farmer.is_onboarded is True


@pytest.mark.asyncio
async def test_onboarding_skip_block_and_village(test_db):
    phone = "919876543212"
    await ai_orchestrator.process_message(test_db, phone, "বাংলা")
    await ai_orchestrator.process_message(test_db, phone, "Nadia")
    await ai_orchestrator.process_message(test_db, phone, "skip")
    await ai_orchestrator.process_message(test_db, phone, "skip")
    await ai_orchestrator.process_message(test_db, phone, "2 bigha")
    await ai_orchestrator.process_message(test_db, phone, "Rice")
    await ai_orchestrator.process_message(test_db, phone, "skip")

    from sqlalchemy import select
    from app.models import FarmerProfile
    stmt = select(FarmerProfile).where(FarmerProfile.phone == phone)
    res = await test_db.execute(stmt)
    farmer = res.scalar_one()
    assert farmer.block is None
    assert farmer.village is None
    assert farmer.is_onboarded is True


@pytest.mark.asyncio
async def test_onboarding_phone_normalization(test_db):
    """10-digit Indian mobile should be prefixed with 91 and stored."""
    phone = "910000000099"
    await ai_orchestrator.process_message(test_db, phone, "English")
    await ai_orchestrator.process_message(test_db, phone, "Hooghly")
    await ai_orchestrator.process_message(test_db, phone, "Arambagh")
    await ai_orchestrator.process_message(test_db, phone, "Singur")
    await ai_orchestrator.process_message(test_db, phone, "2 bigha")
    await ai_orchestrator.process_message(test_db, phone, "Potato")

    r = await ai_orchestrator.process_message(test_db, phone, "9876543210")
    assert r["status"] == "onboarding"

    from sqlalchemy import select
    from app.models import FarmerProfile
    # After phone update the PK is mutated, so look up by the new value
    stmt = select(FarmerProfile).where(FarmerProfile.phone == "919876543210")
    res = await test_db.execute(stmt)
    farmer = res.scalar_one()
    assert farmer.phone.startswith("91")
    assert farmer.is_onboarded is True


@pytest.mark.asyncio
async def test_telegram_chat_id_persisted(test_db):
    """When the telegram webhook provides chat_id, it must be persisted."""
    phone = "123456789"  # telegram chat_id format
    r = await ai_orchestrator.process_message(
        test_db,
        from_phone=phone,
        message_text="Hi",
        chat_id=phone
    )
    from sqlalchemy import select
    from app.models import FarmerProfile
    stmt = select(FarmerProfile).where(FarmerProfile.phone == phone)
    res = await test_db.execute(stmt)
    farmer = res.scalar_one()
    assert farmer.telegram_chat_id == phone

