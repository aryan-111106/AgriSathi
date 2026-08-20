import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    FarmerProfile,
    Crop,
    CropEvent,
    Conversation,
    Message,
    DiseaseReport,
    WeatherAlert,
    MarketWatch,
    NotificationPreference,
)
from app.services.message_bus import get_message_bus
from app.services.weather_service import weather_service
from app.services.market_service import market_service
from app.services.rag_service import rag_service
from app.services.economics_service import economics_service
from app.services.safety_service import safety_service
from app.services.vision_service import vision_service

logger = logging.getLogger("agrisaathi.orchestrator")


def _bus():
    return get_message_bus()

# Initialize Gemini Client if available
gemini_client = None
if settings.gemini_api_key:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=settings.gemini_api_key)
    except Exception as e:
        logger.warning(f"Could not initialize Google GenAI Client: {e}")


class AIOrchestrator:
    def __init__(self):
        self.model_name = settings.gemini_model or "gemini-3.7-flash"

    async def get_or_create_farmer(self, db: AsyncSession, phone: str, name: Optional[str] = None) -> FarmerProfile:
        """Fetch existing farmer profile or initialize a new profile."""
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        stmt = select(FarmerProfile).where(FarmerProfile.phone == clean_phone)
        result = await db.execute(stmt)
        farmer = result.scalar_one_or_none()

        if not farmer:
            farmer = FarmerProfile(
                phone=clean_phone,
                name=name or "Farmer",
                preferred_language=settings.default_language or "bn",
                state="West Bengal",
                district="Hooghly",
                farm_size=2.0,
                farm_size_unit="bigha",
                is_onboarded=False,
                onboarding_step=0
            )
            db.add(farmer)
            await db.commit()
            await db.refresh(farmer)

        return farmer

    async def get_or_create_conversation(self, db: AsyncSession, farmer: FarmerProfile) -> Conversation:
        """Fetch active conversation or create new session."""
        stmt = select(Conversation).where(
            Conversation.farmer_phone == farmer.phone,
            Conversation.is_active == True
        ).order_by(Conversation.updated_at.desc())
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if not conversation:
            import uuid
            session_id = f"sess_{farmer.phone}_{uuid.uuid4().hex[:8]}"
            conversation = Conversation(
                farmer_phone=farmer.phone,
                session_id=session_id,
                active_crop=farmer.crops[0].crop_name if farmer.crops else "Potato",
                context_data={"messages_count": 0}
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

        return conversation

    def detect_language(self, text: str, default_lang: str = "bn") -> str:
        """Detect if input is primarily Bengali, English, or Code-mixed."""
        bengali_chars = len(re.findall(r"[\u0980-\u09FF]", text))
        english_words = len(re.findall(r"[a-zA-Z]+", text))

        if bengali_chars > 3:
            return "bn"
        elif english_words > 3:
            return "en"
        return default_lang

    BN_TRANSLITERATION_HINTS = {
        "কাল": "kal", "আজ": "aj", "আগামীকাল": "agami kal", "পরশু": "parshu",
        "আবহাওয়া": "weather", "বৃষ্টি": "rain bristi", "ঝড়": "storm jhor",
        "তাপমাত্রা": "temperature", "দাম": "dam price", "দর": "dor rate",
        "বাজার": "bajar market", "বিক্রি": "bikri sell", "মান্ডি": "mandi",
        "সার": "sar fertilizer", "ইউরিয়া": "urea", "পটাশ": "potash",
        "ডিএপি": "dap", "মাটি": "mati soil", "ফসল": "fashol crop",
        "ধান": "dhan rice paddy", "আলু": "alu potato", "সরিষা": "sorisha mustard",
        "টমেটো": "tomato", "বেগুন": "begun brinjal", "পাট": "pat jute",
        "লঙ্কা": "lanka chilli", "পেঁয়াজ": "peyaj onion",
        "রোগ": "rog disease", "পোকা": "poka pest insect", "দাগ": "dag spot",
        "ধসা": "dhosha blight", "পাতা": "pata leaf", "হলুদ": "holud yellow",
        "লাভ": "lav profit", "খরচ": "khoroch cost", "তুলনা": "tulna compare",
        "ভালো": "bhalo better", "প্রকল্প": "prokolpo scheme", "ভর্তুকি": "bhurtuki subsidy",
        "বীমা": "bima insurance", "কৃষক": "krishak farmer", "বন্ধু": "bondhu",
        "আধিকারিক": "adhikarik officer", "বিশেষজ্ঞ": "bisheshogjo expert",
        "কখন": "kokhon when", "কোথায়": "kothay where", "কেন": "ken why",
        "কিভাবে": "kivabe how", "কত": "koto how much", "কোন": "kon which",
        "এই": "ei this", "সেই": "sei that", "আমার": "amar my",
        "তোমার": "tomar your", "ফলন": "folon yield", "চাষ": "chash cultivation",
        "জমি": "jomi land", "বীজ": "bij seed", "কীটনাশক": "kitnashak pesticide",
        "ছত্রাকনাশক": "chhotraknashak fungicide", "সেচ": "sech irrigation",
        "বৃষ্টির": "brishti rain", "সম্ভাবনা": "somvhabona probability",
    }

    def _banglish_normalize(self, text: str) -> str:
        """Transliterate common Bengali words to Latin so the same keyword
        matcher used for English can also catch Banglish (Bengali-in-Latin) input."""
        out = text
        for bn, lat in self.BN_TRANSLITERATION_HINTS.items():
            out = out.replace(bn, " " + lat + " ")
        return out

    # BotFather Menu Button command → intent mapping
    COMMAND_INTENT_MAP = {
        "/start": "GREETING",
        "/language": "LANGUAGE_PICK",
        "/menu": "MENU",
        "/weather": "WEATHER",
        "/mandi": "MARKET_PRICE",
        "/crop": "CROP_ADVICE",
        "/disease": "DISEASE_DIAGNOSIS",
        "/pest": "PEST_IDENTIFICATION",
        "/fertilizer": "FERTILIZER_SOIL",
        "/economy": "FARM_ECONOMICS",
        "/schemes": "GOVERNMENT_SCHEME",
        "/expert": "EXPERT_HELP",
    }

    def classify_intent(self, text: str, has_image: bool = False) -> str:
        """Fast rule-based + semantic intent classification with Banglish support."""
        if has_image:
            return "DISEASE_DIAGNOSIS"

        t = text.lower().strip()

        # BotFather menu commands (e.g. /weather, /mandi)
        if t in self.COMMAND_INTENT_MAP:
            return self.COMMAND_INTENT_MAP[t]

        # Persistent reply-keyboard button text (3x3 grid)
        KEYBOARD_BTN_MAP = {
            "🌦️ আবহাওয়া": "WEATHER",
            "🌦️ weather": "WEATHER",
            "💰 বাজার দর": "MARKET_PRICE",
            "💰 mandi prices": "MARKET_PRICE",
            "🌱 ফসল পরামর্শ": "CROP_ADVICE",
            "🌱 crop advice": "CROP_ADVICE",
            "📷 রোগ নির্ণয়": "DISEASE_DIAGNOSIS",
            "📷 disease diagnosis": "DISEASE_DIAGNOSIS",
            "🐛 পোকা নিয়ন্ত্রণ": "PEST_IDENTIFICATION",
            "🐛 pest control": "PEST_IDENTIFICATION",
            "🧪 সারের হিসাব": "FERTILIZER_SOIL",
            "🧪 fertilizer": "FERTILIZER_SOIL",
            "📊 চাষের খরচ-লাভ": "FARM_ECONOMICS",
            "📊 farm economics": "FARM_ECONOMICS",
            "🏛️ সরকারি প্রকল্প": "GOVERNMENT_SCHEME",
            "🏛️ govt schemes": "GOVERNMENT_SCHEME",
            "👨‍🌾 বিশেষজ্ঞ": "EXPERT_HELP",
            "👨‍🌾 expert": "EXPERT_HELP",
        }
        if t in KEYBOARD_BTN_MAP:
            return KEYBOARD_BTN_MAP[t]

        # Menu requests
        if t in ["menu", "help", "সাহায্য", "মেনু", "তালিকা", "1", "2", "3", "4", "5", "6", "7", "8", "9", "hi", "hello", "নমস্কার"]:
            if t in ["hi", "hello", "নমস্কার", "hey", "halo"]:
                return "GREETING"
            if t in ["menu", "help", "সাহায্য", "মেনু", "তালিকা"]:
                return "MENU"
            if t == "1": return "WEATHER"
            if t == "2": return "MARKET_PRICE"
            if t == "3": return "CROP_ADVICE"
            if t == "4": return "DISEASE_DIAGNOSIS"
            if t == "5": return "PEST_IDENTIFICATION"
            if t == "6": return "FERTILIZER_SOIL"
            if t == "7": return "FARM_ECONOMICS"
            if t == "8": return "GOVERNMENT_SCHEME"
            if t == "9": return "EXPERT_HELP"

        # Interactive disease follow-up buttons
        if t in ["diag_more_photo", "diag_expert", "diag_skip"]:
            return "DISEASE_FOLLOWUP"

        # Weather
        if any(w in t for w in ["weather", "rain", "বৃষ্টি", "আবহাওয়া", "forecast", "তাপমাত্রা", "temperature", "storm", "ঝড়"]):
            return "WEATHER"

        # Market prices
        if any(w in t for w in ["price", "rate", "mandi", "দাম", "দর", "বাজার", "বিক্রি", "market", "টাকা/কুইন্টাল"]):
            return "MARKET_PRICE"

        # Fertilizer / Soil
        if any(w in t for w in ["fertilizer", "urea", "সার", "ইউরিয়া", "পটাশ", "potash", "ssp", "dap", "মাটি", "soil", "সার লাগবে"]):
            return "FERTILIZER_SOIL"

        # Economics, Costs & Crop Comparison
        if any(w in t for w in ["cost", "profit", "budget", "লাভ", "খরচ", "তুলনা", "compare", "আয়", "economics", "কত খরচ", "which is better", "better", " vs ", "versus"]):
            return "FARM_ECONOMICS"

        # Government Schemes
        if any(w in t for w in ["scheme", "prakalpa", "prokolpo", "প্রকল্প", "ভর্তুকি", "subsidy", "krishak bandhu", "কৃষক বন্ধু", "pm kisan", "shasya bima", "শস্য বীমা"]):
            return "GOVERNMENT_SCHEME"

        # Disease & Pests
        if any(w in t for w in ["disease", "রোগ", "ধসা", "blight", "পাতা হলুদ", "yellow leaf", "দাগ", "spot", "পোকা", "pest", "insect", "মাজরা"]):
            return "DISEASE_DIAGNOSIS" if "রোগ" in t or "disease" in t or "দাগ" in t else "PEST_IDENTIFICATION"

        # Expert Help
        if any(w in t for w in ["expert", "officer", "ডাক্তার", "ada", "আধিকারিক", "call center", "হেল্পলাইন"]):
            return "EXPERT_HELP"

        # Banglish / code-switched retry
        bn_norm = self._banglish_normalize(text).lower()
        if bn_norm != t:
            if any(w in bn_norm for w in ["weather", "rain", "bristi", "jhor", "temperature"]):
                return "WEATHER"
            if any(w in bn_norm for w in ["price", "dam", "rate", "mandi", "bajar"]):
                return "MARKET_PRICE"
            if any(w in bn_norm for w in ["fertilizer", "urea", "sar", "potash", "dap", "soil", "mati"]):
                return "FERTILIZER_SOIL"
            if any(w in bn_norm for w in ["cost", "profit", "khoroch", "lav", "compare", "tulna"]):
                return "FARM_ECONOMICS"
            if any(w in bn_norm for w in ["scheme", "prokolpo", "bhurtuki", "bima", "krishak", "bondhu"]):
                return "GOVERNMENT_SCHEME"
            if any(w in bn_norm for w in ["disease", "rog", "dhosha", "blight", "poka", "pest", "insect"]):
                return "DISEASE_DIAGNOSIS"
            if any(w in bn_norm for w in ["expert", "officer", "adhikarik", "bisheshogjo"]):
                return "EXPERT_HELP"

        return "GENERAL_AGRICULTURE"

    async def handle_onboarding_step(
        self,
        db: AsyncSession,
        farmer: FarmerProfile,
        user_text: str
    ) -> Tuple[str, Optional[List[Dict[str, str]]], bool]:
        """Progressive conversational onboarding for new farmers."""
        step = farmer.onboarding_step
        t = user_text.strip()

        if step == 0:
            # Language selection
            if "english" in t.lower() or t == "btn_lang_en":
                farmer.preferred_language = "en"
            else:
                farmer.preferred_language = "bn"
            farmer.onboarding_step = 1
            await db.commit()

            if farmer.preferred_language == "bn":
                msg = (
                    "🌾 *AgriSaathi (কৃষি সাথী)-তে আপনাকে স্বাগতম!*\n\n"
                    "আপনার খামারের জন্য সঠিক পরামর্শ দিতে আপনার এলাকা জানা প্রয়োজন।\n\n"
                    "📍 আপনার খামার বা জমি *কোন জেলায় (District)* অবস্থিত? (যেমন: হুগলি, বর্ধমান, নদীয়া, মেদিনীপুর ইত্যাদি)"
                )
            else:
                msg = (
                    "🌾 *Welcome to AgriSaathi! Your AI Farming Partner.*\n\n"
                    "To give you accurate local weather, mandi rates, and crop advice:\n\n"
                    "📍 Which *District* is your farm located in? (e.g., Hooghly, Burdwan, Nadia, Midnapore)"
                )
            return msg, None, False

        elif step == 1:
            # District collection
            farmer.district = t.title()
            farmer.onboarding_step = 2
            await db.commit()

            if farmer.preferred_language == "bn":
                msg = (
                    f"✅ আপনার জেলা *{farmer.district}* সংরক্ষিত হয়েছে।\n\n"
                    "🗺️ আপনার খামার কোন *ব্লকে (Block)* অবস্থিত? (যেমন: আরামবাগ, ডানকুনি, পাণ্ডুয়া)।"
                    "\n\n_অথবা 'skip' লিখুন যদি জানা না থাকে।_"
                )
            else:
                msg = (
                    f"✅ Saved your location: *{farmer.district}*.\n\n"
                    "🗺️ Which *Block* is your farm in? (e.g., Arambagh, Dankuni, Pandua)."
                    "\n\n_Type 'skip' if you don't know._"
                )
            return msg, None, False

        elif step == 2:
            # Block collection (optional)
            if t.lower() != "skip":
                farmer.block = t.title()
            farmer.onboarding_step = 3
            await db.commit()

            if farmer.preferred_language == "bn":
                msg = (
                    f"✅ ব্লক: *{farmer.block or 'উল্লেখ নেই'}*।\n\n"
                    "🏘️ আপনার গ্রাম বা এলাকার নাম কী? (যেমন: সিংহুর, তারকেশ্বর)"
                    "\n\n_অথবা 'skip' লিখুন যদি জানা না থাকে।_"
                )
            else:
                msg = (
                    f"✅ Block: *{farmer.block or 'not specified'}*.\n\n"
                    "🏘️ What is your *Village* or locality name? (e.g., Singur, Tarakeswar)"
                    "\n\n_Type 'skip' if you don't know._"
                )
            return msg, None, False

        elif step == 3:
            # Village collection (optional)
            if t.lower() != "skip":
                farmer.village = t.title()
            farmer.onboarding_step = 4
            await db.commit()

            if farmer.preferred_language == "bn":
                msg = (
                    f"✅ গ্রাম: *{farmer.village or 'উল্লেখ নেই'}*।\n\n"
                    "📏 আপনার চাষযোগ্য জমির পরিমাণ কত? (যেমন: ৩ বিঘা / 2 Acres / ১ হেক্টর)"
                )
            else:
                msg = (
                    f"✅ Village: *{farmer.village or 'not specified'}*.\n\n"
                    "📏 What is your total farm area? (e.g., 3 Bigha / 2 Acres / 1 Hectare)"
                )
            return msg, None, False

        elif step == 4:
            # Land size collection
            size_match = re.search(r"(\d+(\.\d+)?)", t)
            if size_match:
                farmer.farm_size = float(size_match.group(1))
            if "acre" in t.lower() or "একর" in t:
                farmer.farm_size_unit = "acre"
            elif "hectare" in t.lower() or "হেক্টর" in t:
                farmer.farm_size_unit = "hectare"
            else:
                farmer.farm_size_unit = "bigha"

            farmer.onboarding_step = 5
            await db.commit()

            if farmer.preferred_language == "bn":
                msg = (
                    f"✅ জমির পরিমাণ: *{farmer.farm_size} {farmer.farm_size_unit}*。\n\n"
                    "🌱 আপনি বর্তমানে কোন প্রধান ফসল চাষ করছেন বা করতে চান? (যেমন: আলু, ধান, সরিষা, টমেটো, পাট)"
                )
            else:
                msg = (
                    f"✅ Farm Area: *{farmer.farm_size} {farmer.farm_size_unit}*。\n\n"
                    "🌱 What main crop are you currently growing or planning to grow? (e.g., Potato, Rice/Paddy, Mustard, Tomato, Jute)"
                )
            return msg, None, False

        elif step == 5:
            # Crop registration
            crop_name = t.title()
            new_crop = Crop(
                farmer_phone=farmer.phone,
                crop_name=crop_name,
                area=farmer.farm_size,
                area_unit=farmer.farm_size_unit,
                growth_stage="Vegetative"
            )
            db.add(new_crop)
            farmer.onboarding_step = 6
            await db.commit()

            if farmer.preferred_language == "bn":
                msg = (
                    "✅ ফসল নিবন্ধন সম্পন্ন হয়েছে।\n\n"
                    "📱 পরবর্তী সহায়তা ও জরুরি পরামর্শের জন্য আপনার *মোবাইল নম্বর* দিন। "
                    "(যেমন: 9876543210)\n\n_অথবা 'skip' লিখুন যদি দিতে না চান।_"
                )
            else:
                msg = (
                    "✅ Crop registered.\n\n"
                    "📱 Please share your *mobile number* for follow-up support "
                    "and urgent advisories. (e.g., 9876543210)\n\n"
                    "_Type 'skip' if you prefer not to share._"
                )
            return msg, None, False

        elif step == 6:
            # Optional phone number collection
            if t.lower() != "skip":
                digits = re.sub(r"\D", "", t)
                if len(digits) >= 10:
                    if digits.startswith("91") and len(digits) == 12:
                        farmer.phone = digits
                    elif len(digits) == 10:
                        farmer.phone = "91" + digits
                    else:
                        farmer.phone = digits[-12:] if len(digits) >= 12 else digits
                else:
                    if farmer.preferred_language == "bn":
                        return (
                            "⚠️ মোবাইল নম্বরটি সঠিক নয়। ১০ সংখ্যার নম্বর দিন বা 'skip' লিখুন।",
                            None,
                            False
                        )
                    return (
                        "⚠️ That doesn't look like a valid 10-digit mobile number. "
                        "Please try again or type 'skip'.",
                        None,
                        False
                    )

            farmer.is_onboarded = True
            farmer.onboarding_step = 7
            await db.commit()

            pref = NotificationPreference(farmer_phone=farmer.phone)
            db.add(pref)
            await db.commit()

            return self.get_main_menu(farmer.preferred_language, farmer.name), None, True

        return self.get_main_menu(farmer.preferred_language, farmer.name), None, True

    def get_main_menu(self, lang: str = "bn", farmer_name: Optional[str] = None) -> str:
        """Short welcome line — the actual menu is the Telegram persistent
        reply keyboard + BotFather Menu Button, not a text dump."""
        name_part = f", {farmer_name}" if farmer_name and farmer_name != "Farmer" else ""
        if lang == "bn":
            return (
                "🌾 *AgriSaathi (কৃষি সাথী)-তে আবার স্বাগতম!*{name}\n\n"
                "নিচের বাটনগুলো ব্যবহার করুন অথবা সরাসরি বাংলা/ইংরেজিতে প্রশ্ন লিখুন।\n"
                "_ভয়েস মেসেজ, ছবি, বা GPS লোকেশনও পাঠাতে পারেন।_"
            ).format(name=name_part)
        return (
            "🌾 *Welcome back to AgriSaathi!*{name}\n\n"
            "Use the buttons below or type your question in English/Bengali.\n"
            "_You can also send voice notes, photos, or GPS location._"
        ).format(name=name_part)

    async def process_message(
        self,
        db: AsyncSession,
        from_phone: str,
        message_text: str = "",
        image_bytes: Optional[bytes] = None,
        audio_bytes: Optional[bytes] = None,
        location_data: Optional[Dict[str, float]] = None,
        sender_name: Optional[str] = None,
        media_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        is_callback: bool = False,
    ) -> Dict[str, Any]:
        """
        Main Agent Execution Pipeline:
        1. Farmer & Conversation retrieval
        2. Media handling (transcription / vision)
        3. Intent classification & Language detection
        4. Tool calling & Knowledge grounding
        5. Multilingual formatting & Safety checks
        6. Outbound WhatsApp message dispatch
        """
        farmer = await self.get_or_create_farmer(db, from_phone, sender_name)
        if chat_id and not farmer.telegram_chat_id:
            farmer.telegram_chat_id = chat_id
            await db.commit()
            await db.refresh(farmer)
        conv = await self.get_or_create_conversation(db, farmer)

        # Handle Location sharing
        if location_data:
            farmer.latitude = location_data.get("latitude")
            farmer.longitude = location_data.get("longitude")
            await db.commit()
            message_text = f"Weather and Mandi rates for my shared GPS location ({farmer.latitude:.4f}, {farmer.longitude:.4f})"

        # Handle Voice Notes
        if audio_bytes:
            from app.services.voice_service import voice_service
            trans_res = await voice_service.transcribe_audio(audio_bytes, expected_lang=farmer.preferred_language)
            message_text = trans_res.get("transcript", message_text)

        # Language resolution priority:
        #   1. Already-onboarded farmer → respect their stored preference
        #   2. New farmer → auto-detect from their first message
        if farmer.is_onboarded and farmer.preferred_language in ("bn", "en"):
            lang = farmer.preferred_language
        else:
            lang = self.detect_language(message_text, default_lang=settings.default_language)
            if farmer.preferred_language != lang:
                farmer.preferred_language = lang
                await db.commit()

        # Handle Onboarding Flow if farmer is not yet onboarded
        if not farmer.is_onboarded and not image_bytes:
            trigger = message_text.lower().strip()
            if trigger in ["/start", "/menu", "hi", "hello", "নমস্কার", "start", "শুরু"] and farmer.onboarding_step == 0:
                welcome_text = (
                    "🌾 *নমস্কার! AgriSaathi (কৃষি সাথী)-তে আপনাকে স্বাগতম।*\n"
                    "আপনার পছন্দের ভাষা বেছে নিন / Choose your preferred language:"
                )
                buttons = [
                    {"id": "btn_lang_bn", "title": "বাংলা 🇧🇩"},
                    {"id": "btn_lang_en", "title": "English 🇬🇧"}
                ]
                await _bus().send_buttons(farmer.phone, welcome_text, buttons)
                return {"status": "onboarding_started", "from_phone": farmer.phone, "step": 0, "response": welcome_text}

            # Step progression
            reply_text, buttons, completed = await self.handle_onboarding_step(db, farmer, message_text)
            if buttons:
                await _bus().send_buttons(farmer.phone, reply_text, buttons)
            else:
                await _bus().send_text(farmer.phone, reply_text)
            # When onboarding just completed, attach the persistent reply keyboard
            if completed and farmer.is_onboarded:
                from app.services.telegram_service import telegram_service
                await telegram_service.send_main_keyboard(
                    farmer.phone, farmer.preferred_language
                )
            return {"status": "onboarding", "from_phone": farmer.phone, "completed": completed, "response": reply_text}

        # Intent classification
        intent = self.classify_intent(message_text, has_image=bool(image_bytes))
        conv.last_intent = intent
        await db.commit()

        active_crop_name = farmer.crops[0].crop_name if farmer.crops else "Potato"

        # Record incoming message
        in_msg = Message(
            conversation_id=conv.id,
            sender="farmer",
            direction="inbound",
            message_type="image" if image_bytes else ("audio" if audio_bytes else "text"),
            content=message_text or "[Image Upload]",
            language=lang,
            intent=intent
        )
        db.add(in_msg)
        await db.commit()

        # ROUTE INTENTS TO SPECIALIZED TOOLS
        final_response_text = ""
        tool_data = {}

        # 1. GREETING (from /start)
        # /start ALWAYS re-prompts language picker, regardless of history.
        # This makes /start behave like a true "reset / restart" affordance
        # and avoids the surprise of getting stuck in the wrong language.
        if intent == "GREETING":
            farmer.is_onboarded = False
            farmer.onboarding_step = 0
            await db.commit()
            # Fall through to onboarding handler below by sending the picker
            # and returning early (the rest of the routing is irrelevant).
            from app.services.telegram_service import telegram_service
            welcome_text = (
                "🌾 *নমস্কার! AgriSaathi (কৃষি সাথী)-তে আপনাকে স্বাগতম।*\n"
                "আপনার পছন্দের ভাষা বেছে নিন / Choose your preferred language:"
            )
            buttons = [
                {"id": "btn_lang_bn", "title": "বাংলা 🇧🇩"},
                {"id": "btn_lang_en", "title": "English 🇬🇧"},
            ]
            await telegram_service.send_buttons(farmer.phone, welcome_text, buttons)
            # Hide any persistent keyboard during language picker so it doesn't
            # confuse the user with buttons that route to features they haven't
            # been onboarded for yet.
            await telegram_service.remove_keyboard(farmer.phone)
            final_response_text = welcome_text
            # Short-circuit: do not let the rest of the routing run.
            out_msg = Message(
                conversation_id=conv.id,
                sender="bot",
                direction="outbound",
                message_type="text",
                content=final_response_text,
                language=lang,
                intent=intent,
                tool_calls=[{"_quality": {"answer_confidence": "high", "data_freshness_minutes": 0, "source_quality": "system", "safety_risk": "low", "intent": intent}}],
            )
            db.add(out_msg)
            await db.commit()
            return {
                "status": "onboarding_started",
                "from_phone": farmer.phone,
                "intent": intent,
                "language": lang,
                "response": final_response_text,
                "tool_data": {},
            }

        # 1b. LANGUAGE_PICK (/language) — re-prompt language without losing profile
        elif intent == "LANGUAGE_PICK":
            farmer.is_onboarded = False
            farmer.onboarding_step = 0
            farmer.preferred_language = settings.default_language or "bn"
            await db.commit()
            from app.services.telegram_service import telegram_service
            welcome_text = (
                "🌾 *ভাষা পরিবর্তন / Change Language*\n\n"
                "আপনার পছন্দের ভাষা বেছে নিন / Choose your preferred language:"
            )
            buttons = [
                {"id": "btn_lang_bn", "title": "বাংলা 🇧🇩"},
                {"id": "btn_lang_en", "title": "English 🇬🇧"},
            ]
            await telegram_service.send_buttons(farmer.phone, welcome_text, buttons)
            await telegram_service.remove_keyboard(farmer.phone)
            final_response_text = welcome_text
            out_msg = Message(
                conversation_id=conv.id,
                sender="bot",
                direction="outbound",
                message_type="text",
                content=final_response_text,
                language=lang,
                intent=intent,
                tool_calls=[{"_quality": {"answer_confidence": "high", "data_freshness_minutes": 0, "source_quality": "system", "safety_risk": "low", "intent": intent}}],
            )
            db.add(out_msg)
            await db.commit()
            return {
                "status": "language_pick",
                "from_phone": farmer.phone,
                "intent": intent,
                "language": lang,
                "response": final_response_text,
                "tool_data": {},
            }

        # 2. MENU
        elif intent == "MENU":
            final_response_text = self.get_main_menu(lang, farmer.name)
            # Keyboard is resent centrally at the end of process_message()

        # 3. WEATHER
        elif intent == "WEATHER":
            weather_data = await weather_service.get_forecast(
                location_name=farmer.district or "Hooghly",
                lat=farmer.latitude,
                lon=farmer.longitude,
                crop_name=active_crop_name
            )
            tool_data["weather"] = weather_data

            if lang == "bn":
                cur = weather_data["current"]
                lines = [
                    f"🌦️ *{weather_data['location']} — আজকের আবহাওয়া ও পূর্বাভাস:*\n",
                    f"🌡️ তাপমাত্রা: *{cur['temperature']}°C* (অনুভূতি: {cur['temperature']}°C)",
                    f"💧 আর্দ্রতা: *{cur['humidity']}%* | 💨 বাতাস: *{cur['wind_speed_kmh']} km/h*",
                    f"☁️ অবস্থা: *{cur['condition_bn']}*\n",
                    "📅 *আগামী ৭ দিনের পূর্বাভাস:*"
                ]
                for d in weather_data["daily_forecast"][:4]:
                    lines.append(f"• {d['day']}: {d['max_temp']}°C / {d['min_temp']}°C — {d['condition_bn']} (বৃষ্টির সম্ভাবনা: {d['rain_prob']}%)")

                lines.append(f"\n🌾 *কৃষি পরামর্শ:* {weather_data['agri_advisory_bn']}")

                # Alerts
                for alert in weather_data.get("alerts", []):
                    lines.append(f"\n{alert['title_bn']}\n{alert['message_bn']}")

                lines.append(f"\n_উৎস: {weather_data['source']}_")
                final_response_text = "\n".join(lines)
            else:
                cur = weather_data["current"]
                lines = [
                    f"🌦️ *{weather_data['location']} — Weather & Agrometeorological Forecast:*\n",
                    f"🌡️ Temperature: *{cur['temperature']}°C*",
                    f"💧 Humidity: *{cur['humidity']}%* | 💨 Wind: *{cur['wind_speed_kmh']} km/h*",
                    f"☁️ Condition: *{cur['condition_en']}*\n",
                    "📅 *Upcoming Forecast:*"
                ]
                for d in weather_data["daily_forecast"][:4]:
                    lines.append(f"• {d['day']}: {d['max_temp']}°C / {d['min_temp']}°C — {d['condition_en']} (Rain Prob: {d['rain_prob']}%)")

                lines.append(f"\n🌾 *Agricultural Advisory:* {weather_data['agri_advisory_en']}")

                for alert in weather_data.get("alerts", []):
                    lines.append(f"\n{alert['title_en']}\n{alert['message_en']}")

                lines.append(f"\n_Source: {weather_data['source']}_")
                final_response_text = "\n".join(lines)

        # 4. MARKET PRICE
        elif intent == "MARKET_PRICE":
            # Extract crop query or use active crop
            crop_query = active_crop_name
            for c in ["potato", "alu", "আলু", "rice", "paddy", "dhan", "ধান", "mustard", "sarson", "সরিষা", "tomato", "টমেটো", "brinjal", "begun", "বেগুন", "jute", "pat", "পাট", "lanka", "লঙ্কা", "onion", "পেঁয়াজ"]:
                if c in message_text.lower():
                    crop_query = c
                    break

            market_results = market_service.search_prices(
                commodity=crop_query,
                district=farmer.district or "Hooghly",
                state=farmer.state,
                farmer_lat=farmer.latitude,
                farmer_lon=farmer.longitude
            )
            tool_data["market"] = market_results
            final_response_text = market_service.format_market_summary(market_results, lang=lang)

        # 5. DISEASE DIAGNOSIS (IMAGE / TEXT)
        elif intent == "DISEASE_DIAGNOSIS":
            if image_bytes:
                diag = await vision_service.diagnose_crop_image(image_bytes, crop_hint=active_crop_name, farmer_lang=lang)
                tool_data["diagnosis"] = diag

                # If confidence is low or image quality poor, ask follow-up via interactive buttons
                if diag.get("requires_more_info"):
                    quality = diag.get("image_quality", {})
                    quality_reasons = ", ".join(quality.get("reasons", [])) or "low clarity"
                    confidence_score = diag.get("confidence_score", 0.0)
                    follow_up_questions = diag.get("follow_up_questions", []) or []

                    if lang == "bn":
                        body = (
                            f"📷 ছবি বিশ্লেষণে নিশ্চয়তা কম ({confidence_score:.0%}) এবং ছবির মান: {quality_reasons}।\n\n"
                            "আরও ভালো পরামর্শ দিতে আমার একটু বেশি তথ্য দরকার:\n\n"
                        )
                        for i, q in enumerate(follow_up_questions[:3], start=1):
                            body += f"{i}. {q}\n"
                        body += "\n_অথবা আরও কাছ থেকে পাতার ছবি পাঠান।_"
                        buttons = [
                            {"id": "diag_more_photo", "title": "📷 নতুন ছবি পাঠাব"},
                            {"id": "diag_expert", "title": "👨‍🌾 বিশেষজ্ঞের সাহায্য"},
                            {"id": "diag_skip", "title": "⏭️ এগিয়ে যান"}
                        ]
                    else:
                        body = (
                            f"📷 The image gave me only {confidence_score:.0%} confidence and the photo quality is: {quality_reasons}.\n\n"
                            "To give you better advice I need a bit more context:\n\n"
                        )
                        for i, q in enumerate(follow_up_questions[:3], start=1):
                            body += f"{i}. {q}\n"
                        body += "\n_Or upload a closer photo of the affected leaf._"
                        buttons = [
                            {"id": "diag_more_photo", "title": "📷 Send New Photo"},
                            {"id": "diag_expert", "title": "👨‍🌾 Ask Expert"},
                            {"id": "diag_skip", "title": "⏭️ Skip"}
                        ]

                    conv.pending_diagnosis = {
                        "diagnosis_id": None,
                        "image_quality": quality,
                        "confidence_score": confidence_score,
                        "follow_up_questions": follow_up_questions[:3],
                        "crop_hint": active_crop_name,
                        "language": lang
                    }
                    await db.commit()

                    await _bus().send_buttons(farmer.phone, body, buttons)
                    final_response_text = body
                else:
                    final_response_text = diag.get(
                        f"summary_text_{lang}", diag.get("summary_text_bn", "")
                    )

                    # Store report in DB only when diagnosis is confident
                    requires_expert = diag.get("requires_expert_consultation", False)
                    # Per PRD §54 retention policy: only persist the image
                    # reference when an expert may need to review it later.
                    report = DiseaseReport(
                        farmer_phone=farmer.phone,
                        media_id=media_id if requires_expert else None,
                        crop_detected=diag.get("crop_detected", active_crop_name),
                        disease_name=diag.get("disease_name", "Unknown Issue"),
                        disease_name_bn=diag.get("disease_name_bn"),
                        confidence=diag.get("confidence_score", 0.8),
                        confidence_level=diag.get("confidence_level", "Medium"),
                        severity=diag.get("severity", "Moderate"),
                        symptoms=diag.get(f"symptoms_{lang}"),
                        biological_control=diag.get(f"cultural_control_{lang}"),
                        chemical_guidance=diag.get(f"ipm_chemical_{lang}"),
                        requires_expert_consultation=requires_expert
                    )
                    db.add(report)
                    await db.commit()

                    # Add safety disclaimer
                    final_response_text += safety_service.get_safety_disclaimer(lang=lang)
            else:
                # Text-based disease query
                rag_context = rag_service.get_relevant_knowledge_chunk(message_text, crop_name=active_crop_name)
                final_response_text = await self._generate_ai_response(message_text, rag_context, farmer, lang)
                final_response_text += safety_service.get_safety_disclaimer(lang=lang)

        # 5b. DISEASE_FOLLOWUP — handle interactive button replies from low-confidence diagnoses
        elif intent == "DISEASE_FOLLOWUP":
            pending = conv.pending_diagnosis or {}
            if message_text == "diag_expert":
                final_response_text = safety_service.get_expert_escalation(lang=lang)
                conv.pending_diagnosis = None
                await db.commit()
            elif message_text == "diag_more_photo":
                if lang == "bn":
                    final_response_text = (
                        "📷 ঠিক আছে — অনুগ্রহ করে আক্রান্ত পাতাটির *খুব কাছ থেকে*, "
                        "ভালো আলোতে আরেকটি ছবি পাঠান। পুরো গাছের একটি ছবিও পাঠালে ভালো হয়।"
                    )
                else:
                    final_response_text = (
                        "📷 Sure — please send another photo of the affected leaf, "
                        "*close-up*, in good light. A wider shot of the whole plant also helps."
                    )
                # keep pending_diagnosis so the next image still has context
            elif message_text == "diag_skip":
                if lang == "bn":
                    final_response_text = (
                        "⚠️ আমি এখন নিশ্চিত নয়, তা�ে নিরাপদ থাকতে স্থানীয় কৃষি আধিকারিক বা KVK-এর পরামর্শ নিন।\n\n"
                        + safety_service.get_expert_escalation(lang=lang)
                    )
                else:
                    final_response_text = (
                        "⚠️ I'm not confident enough to advise safely. Please consult your local ADA or KVK.\n\n"
                        + safety_service.get_expert_escalation(lang=lang)
                    )
                conv.pending_diagnosis = None
                await db.commit()
            else:
                # Free-text answer to the follow-up question
                if pending:
                    questions = pending.get("follow_up_questions", [])
                    questions_text = "\n".join(f"- {q}" for q in questions) if questions else "(none)"
                    rag_context = rag_service.get_relevant_knowledge_chunk(
                        message_text + "\n" + questions_text,
                        crop_name=pending.get("crop_hint")
                    )
                    final_response_text = await self._generate_ai_response(
                        f"Farmer's follow-up answer: {message_text}\nOriginal questions:\n{questions_text}",
                        rag_context,
                        farmer,
                        lang
                    )
                    final_response_text += safety_service.get_safety_disclaimer(lang=lang)
                    conv.pending_diagnosis = None
                    await db.commit()
                else:
                    final_response_text = self.get_main_menu(lang, farmer.name)

        # 6. FERTILIZER & SOIL
        elif intent == "FERTILIZER_SOIL":
            # Extract area if mentioned, otherwise use farmer's registered land size
            area = farmer.farm_size or 2.0
            unit = farmer.farm_size_unit or "bigha"
            size_match = re.search(r"(\d+(\.\d+)?)\s*(bigha|বিঘা|acre|একর|hectare|হেক্টর)?", message_text.lower())
            if size_match:
                try:
                    area = float(size_match.group(1))
                    if size_match.group(3):
                        unit = size_match.group(3)
                except Exception:
                    pass

            fert_data = rag_service.get_fertilizer_guidance(active_crop_name, area=area, unit=unit)
            if fert_data:
                tool_data["fertilizer"] = fert_data
                doses = fert_data["recommended_doses"]
                if lang == "bn":
                    final_response_text = (
                        f"🧪 *{fert_data['crop_bn']} চাষে সারের সঠিক হিসাব ({area} {unit} জমির জন্য):*\n\n"
                        f"• 🌾 *ইউরিয়া (Urea):* {doses['urea_kg']} কেজি\n"
                        f"• 🌿 *সিঙ্গেল সুপার ফসফেট (SSP):* {doses['ssp_single_super_phosphate_kg']} কেজি (বা সমপরিমাণ DAP)\n"
                        f"• 🥔 *মিউরেট অফ পটাশ (MOP):* {doses['mop_potash_kg']} কেজি\n\n"
                        f"📌 *প্রয়োগ পদ্ধতি:*\n"
                        f"১. সম্পূর্ণ ফসফেট এবং অর্ধেক পটাশ জমি তৈরির সময় (Basal dose) প্রয়োগ করুন।\n"
                        f"২. ইউরিয়া সার ২-৩ কিস্তিতে উপরিপ্রয়োগ (Top dressing) করুন।\n\n"
                        f"_{fert_data['source']}_"
                    )
                else:
                    final_response_text = (
                        f"🧪 *Scientific Fertilizer Dosage for {fert_data['crop']} ({area} {unit}):*\n\n"
                        f"• 🌾 *Urea:* {doses['urea_kg']} kg\n"
                        f"• 🌿 *Single Super Phosphate (SSP):* {doses['ssp_single_super_phosphate_kg']} kg\n"
                        f"• 🥔 *Muriate of Potash (MOP):* {doses['mop_potash_kg']} kg\n\n"
                        f"📌 *Application Schedule:*\n"
                        f"1. Apply all SSP and 50% MOP during final land preparation (Basal).\n"
                        f"2. Split Urea into 2-3 top dressings at critical vegetative stages.\n\n"
                        f"_{fert_data['source']}_"
                    )
            else:
                rag_context = rag_service.get_relevant_knowledge_chunk(message_text, crop_name=active_crop_name)
                final_response_text = await self._generate_ai_response(message_text, rag_context, farmer, lang)

        # 7. FARM ECONOMICS & CROP COMPARISON
        elif intent == "FARM_ECONOMICS":
            if "তুলনা" in message_text or "compare" in message_text.lower() or "versus" in message_text.lower() or " vs " in message_text.lower():
                comp = economics_service.compare_crops("potato", "mustard", area=farmer.farm_size or 3.0, unit=farmer.farm_size_unit or "bigha")
                if comp:
                    tool_data["economics"] = comp
                    c1 = comp["crop_1"]
                    c2 = comp["crop_2"]
                    if lang == "bn":
                        final_response_text = (
                            f"📊 *ফসল তুলনা: {c1['crop_bn']} বনাম {c2['crop_bn']} ({farmer.farm_size} {farmer.farm_size_unit}):*\n\n"
                            f"🥔 *{c1['crop_bn']}:*\n"
                            f"• আনুমানিক মোট খরচ: *₹{c1['total_input_cost']:,}*\n"
                            f"• সম্ভাব্য ফলন: *{c1['expected_yield_quintals']} কুইন্টাল*\n"
                            f"• সম্ভাব্য নিট লাভ: *₹{c1['estimated_net_profit']:,}* (ROI: {c1['roi_percent']}%)\n"
                            f"• ঝুঁকি: {c1['risk_level']}\n\n"
                            f"🌱 *{c2['crop_bn']}:*\n"
                            f"• আনুমানিক মোট খরচ: *₹{c2['total_input_cost']:,}*\n"
                            f"• সম্ভাব্য ফলন: *{c2['expected_yield_quintals']} কুইন্টাল*\n"
                            f"• সম্ভাব্য নিট লাভ: *₹{c2['estimated_net_profit']:,}* (ROI: {c2['roi_percent']}%)\n"
                            f"• ঝুঁকি: {c2['risk_level']}\n\n"
                            f"💡 *পরামর্শ:* {comp['comparison_summary_bn']}\n\n"
                            f"{c1['disclaimer_bn']}"
                        )
                    else:
                        final_response_text = (
                            f"📊 *Crop Comparison: {c1['crop']} vs {c2['crop']} ({farmer.farm_size} {farmer.farm_size_unit}):*\n\n"
                            f"🥔 *{c1['crop']}:*\n"
                            f"• Total Input Cost: *₹{c1['total_input_cost']:,}*\n"
                            f"• Estimated Yield: *{c1['expected_yield_quintals']} Q*\n"
                            f"• Estimated Net Profit: *₹{c1['estimated_net_profit']:,}* (ROI: {c1['roi_percent']}%)\n"
                            f"• Risk Level: {c1['risk_level']}\n\n"
                            f"🌱 *{c2['crop']}:*\n"
                            f"• Total Input Cost: *₹{c2['total_input_cost']:,}*\n"
                            f"• Estimated Yield: *{c2['expected_yield_quintals']} Q*\n"
                            f"• Estimated Net Profit: *₹{c2['estimated_net_profit']:,}* (ROI: {c2['roi_percent']}%)\n"
                            f"• Risk Level: {c2['risk_level']}\n\n"
                            f"💡 *Summary:* {comp['comparison_summary_en']}\n\n"
                            f"{c1['disclaimer_en']}"
                        )
            else:
                budget = economics_service.calculate_budget(active_crop_name, area=farmer.farm_size or 2.0, unit=farmer.farm_size_unit or "bigha")
                if budget:
                    tool_data["budget"] = budget
                    costs = budget["itemized_costs"]
                    if lang == "bn":
                        final_response_text = (
                            f"📊 *{budget['crop_bn']} চাষের আনুমানিক বাজেট ও লাভ-ক্ষতির হিসাব ({budget['area_requested']}):*\n\n"
                            f"💰 *খরচের হিসাব (Input Costs):*\n"
                            f"• বীজ / চারা: ₹{costs.get('seeds', 0):,}\n"
                            f"• রাসায়নিক ও জৈব সার: ₹{costs.get('fertilizers', 0):,}\n"
                            f"• বালাইনাশক ও ছত্রাকনাশক: ₹{costs.get('pesticides_fungicides', 0):,}\n"
                            f"• সেচ খরচ: ₹{costs.get('irrigation', 0):,}\n"
                            f"• মজুর ও জমি তৈরি: ₹{costs.get('labor_and_machinery', 0):,}\n"
                            f"• পরিবহন ও অন্যান্য: ₹{costs.get('transport_storage', 0):,}\n"
                            f"👉 *মোট আনুমানিক খরচ:* *₹{budget['total_input_cost']:,}*\n\n"
                            f"📈 *আয়ের সম্ভাবনা (Revenue & Profit):*\n"
                            f"• সম্ভাব্য ফলন: *{budget['expected_yield_quintals']} কুইন্টাল*\n"
                            f"• আনুমানিক বাজার দর: ₹{budget['assumed_market_rate_per_q']:,} /কুইন্টাল\n"
                            f"• মোট বিক্রয়মূল্য: *₹{budget['estimated_gross_revenue']:,}*\n"
                            f"🎉 *সম্ভাব্য নিট লাভ (Net Profit):* *₹{budget['estimated_net_profit']:,}*\n\n"
                            f"{budget['disclaimer_bn']}"
                        )
                    else:
                        final_response_text = (
                            f"📊 *Estimated Farm Budget & Profitability for {budget['crop']} ({budget['area_requested']}):*\n\n"
                            f"💰 *Itemized Input Costs:*\n"
                            f"• Seed / Tubers: ₹{costs.get('seeds', 0):,}\n"
                            f"• Fertilizers: ₹{costs.get('fertilizers', 0):,}\n"
                            f"• Plant Protection: ₹{costs.get('pesticides_fungicides', 0):,}\n"
                            f"• Irrigation: ₹{costs.get('irrigation', 0):,}\n"
                            f"• Labor & Machinery: ₹{costs.get('labor_and_machinery', 0):,}\n"
                            f"• Transport & Misc: ₹{costs.get('transport_storage', 0):,}\n"
                            f"👉 *Total Estimated Cost:* *₹{budget['total_input_cost']:,}*\n\n"
                            f"📈 *Revenue & Returns:*\n"
                            f"• Expected Yield: *{budget['expected_yield_quintals']} Quintals*\n"
                            f"• Modal Price: ₹{budget['assumed_market_rate_per_q']:,} /Q\n"
                            f"• Gross Revenue: *₹{budget['estimated_gross_revenue']:,}*\n"
                            f"🎉 *Estimated Net Profit:* *₹{budget['estimated_net_profit']:,}* (ROI: {budget['roi_percent']}%)\n\n"
                            f"{budget['disclaimer_en']}"
                        )

        # 8. GOVERNMENT SCHEMES
        elif intent == "GOVERNMENT_SCHEME":
            schemes = rag_service.search_schemes(message_text)
            tool_data["schemes"] = schemes
            if lang == "bn":
                lines = ["🏛️ *পশ্চিমবঙ্গ ও কেন্দ্রীয় সরকারের গুরুত্বপূর্ণ কৃষি প্রকল্পসমূহ:*\n"]
                for s in schemes[:3]:
                    lines.append(f"📌 *{s['name_bn']}*")
                    lines.append(f"• সুবিধা: {s['benefits_bn']}")
                    lines.append(f"• যোগ্যতা: {s['eligibility_bn']}")
                    lines.append(f"• আবেদনের উপায়: {s['how_to_apply_bn']}\n")
                final_response_text = "\n".join(lines)
            else:
                lines = ["🏛️ *Key Agricultural Schemes & Subsidies:*\n"]
                for s in schemes[:3]:
                    lines.append(f"📌 *{s['name_en']}*")
                    lines.append(f"• Benefits: {s['benefits_en']}")
                    lines.append(f"• Eligibility: {s['eligibility_en']}")
                    lines.append(f"• How to Apply: {s['how_to_apply_en']}\n")
                final_response_text = "\n".join(lines)

        # 9. EXPERT HELP
        elif intent == "EXPERT_HELP":
            final_response_text = safety_service.get_expert_escalation(lang=lang)

        # 10. GENERAL AGRICULTURE / CROP ADVICE (RAG Grounded)
        else:
            rag_context = rag_service.get_relevant_knowledge_chunk(message_text, crop_name=active_crop_name)
            final_response_text = await self._generate_ai_response(message_text, rag_context, farmer, lang)

        # Sanitize any chemical mentions
        final_response_text = safety_service.sanitize_chemical_advice(final_response_text)

        # Quality metrics (PRD §57) — internal, never sent to farmer
        quality = self._compute_quality_metrics(intent, tool_data, final_response_text)
        if tool_data:
            tool_data = {**tool_data, "_quality": quality}
        else:
            tool_data = {"_quality": quality}

        # Save outgoing message in DB
        out_msg = Message(
            conversation_id=conv.id,
            sender="bot",
            direction="outbound",
            message_type="text",
            content=final_response_text,
            language=lang,
            intent=intent,
            tool_calls=[tool_data]
        )
        db.add(out_msg)
        await db.commit()

        # Send via MessageBus (Telegram by default)
        await _bus().send_text(farmer.phone, final_response_text)

        # Re-attach the persistent 3x3 reply keyboard after every bot reply.
        # Telegram hides the keyboard as soon as the user sends any message,
        # so we re-send it each turn to keep it visible. Skip when the user
        # is still onboarding (keyboard would be premature) or when the
        # outbound channel is not Telegram.
        if (
            farmer.is_onboarded
            and settings.outbound_channel == "telegram"
            and intent not in ("GREETING", "LANGUAGE_PICK")
        ):
            from app.services.telegram_service import telegram_service
            await telegram_service.send_main_keyboard(farmer.phone, lang)

        return {
            "status": "success",
            "from_phone": farmer.phone,
            "intent": intent,
            "language": lang,
            "response": final_response_text,
            "tool_data": tool_data
        }

    def _compute_quality_metrics(
        self,
        intent: str,
        tool_data: Dict[str, Any],
        response_text: str
    ) -> Dict[str, Any]:
        """Build internal quality metadata (PRD §57). Not exposed to farmer."""
        source_quality = "ai_generated"
        data_freshness_minutes = 0
        answer_confidence = "low"
        safety_risk = "low"

        if intent == "WEATHER" and tool_data.get("weather"):
            source_quality = "official"
            data_freshness_minutes = 15
            answer_confidence = "high"
        elif intent == "MARKET_PRICE" and tool_data.get("market"):
            source_quality = "verified"
            data_freshness_minutes = 60
            answer_confidence = "medium"
        elif intent == "DISEASE_DIAGNOSIS" and tool_data.get("diagnosis"):
            score = (tool_data["diagnosis"].get("confidence_score") or 0.0)
            answer_confidence = (
                "high" if score >= 0.8 else "medium" if score >= 0.6 else "low"
            )
            safety_risk = "high" if tool_data["diagnosis"].get("requires_expert_consultation") else "low"
            source_quality = "verified" if tool_data["diagnosis"].get("source", "").startswith(("Gemini", "BCKV", "ICAR")) else "ai_generated"
        elif intent == "GOVERNMENT_SCHEME":
            source_quality = "official"
            data_freshness_minutes = 1440
            answer_confidence = "medium"
        elif intent == "FARM_ECONOMICS":
            source_quality = "verified"
            answer_confidence = "medium"

        if any(restricted in response_text.lower() for restricted in safety_service.RESTRICTED_CHEMICALS):
            safety_risk = "high"

        return {
            "answer_confidence": answer_confidence,
            "data_freshness_minutes": data_freshness_minutes,
            "source_quality": source_quality,
            "safety_risk": safety_risk,
            "intent": intent
        }

    async def _generate_ai_response(
        self,
        query: str,
        rag_context: str,
        farmer: FarmerProfile,
        lang: str
    ) -> str:
        """Generate compassionate, localized agricultural response using Gemini."""
        if gemini_client:
            try:
                system_prompt = (
                    "You are AgriSaathi, a wise, compassionate, and practical AI agricultural advisor for Indian and West Bengal farmers.\n"
                    f"Farmer context: District: {farmer.district or 'Hooghly, West Bengal'}, Farm Size: {farmer.farm_size} {farmer.farm_size_unit}, Active Crop: {farmer.crops[0].crop_name if farmer.crops else 'Potato'}.\n"
                    f"Language: Respond strictly in {'Bengali (বাংলা)' if lang == 'bn' else 'English'}.\n"
                    "Rules:\n"
                    "1. Give concise, highly actionable, step-by-step advice with emojis.\n"
                    "2. Ground your advice in the provided verified agricultural knowledge.\n"
                    "3. Do not invent chemical dosages; recommend safe IPM and consulting local ADA/KVK for severe issues."
                )

                prompt = f"{system_prompt}\n\nVERIFIED KNOWLEDGE BASE:\n{rag_context}\n\nFARMER QUERY: {query}"
                response = gemini_client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                if response.text:
                    return response.text.strip()
            except Exception as e:
                logger.error(f"Error in Gemini text response generation: {e}")

        # Rule-based fallback response
        if lang == "bn":
            return (
                f"🌱 *কৃষি পরামর্শ:* আপনার প্রশ্নের জন্য ধন্যবাদ।\n\n"
                f"{rag_context[:300] if rag_context else 'আপনার ফসলের সঠিক পরিচর্যা, পরিমিত সেচ ও সুষম সার প্রয়োগ ফলন বৃদ্ধিতে সহায়ক।'}\n\n"
                f"💡 বিস্তারিত তথ্যের জন্য আপনি মেনু থেকে নির্দিষ্ট নম্বর নির্বাচন করতে পারেন।"
            )
        return (
            f"🌱 *Crop Advisory:* Thank you for your question.\n\n"
            f"{rag_context[:300] if rag_context else 'Maintaining proper soil moisture, balanced NPK nutrition, and timely weeding are essential for optimal yield.'}\n\n"
            f"💡 Reply with 'menu' for more specific options."
        )


ai_orchestrator = AIOrchestrator()
