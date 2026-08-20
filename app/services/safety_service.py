import logging
from typing import Dict, Any, List

logger = logging.getLogger("agrisaathi.safety")


class SafetyService:
    # Banned or restricted agro-chemicals in India
    RESTRICTED_CHEMICALS = [
        "endosulfan", "monocrotophos", "carbofuran", "phorate", "paraquat", "ddt", "aldrin"
    ]

    KISAN_HELPLINE_NUMBERS = {
        "kisan_call_centre": "1800-180-1551 (Toll-Free 6 AM - 10 PM)",
        "west_bengal_agri_helpline": "1800-103-6000 / 033-2214-5555",
        "soil_health_support": "Local Block Assistant Director of Agriculture (ADA) Office"
    }

    def sanitize_chemical_advice(self, text: str) -> str:
        """Ensure no restricted/banned chemicals are casually recommended."""
        lower_text = text.lower()
        for chemical in self.RESTRICTED_CHEMICALS:
            if chemical in lower_text:
                logger.warning(f"Safety trigger: Detected restricted chemical '{chemical}' in output.")
                text = text.replace(chemical, f"[RESTRICTED SUBSTANCE - USE RECOMMENDED SAFE ALTERNATIVE]")
        return text

    def get_safety_disclaimer(self, lang: str = "bn") -> str:
        """Returns standard agricultural safety & PPE disclaimer."""
        if lang == "bn":
            return (
                "\n\n🛡️ *কৃষি নিরাপত্তা ও সতর্কতা:*\n"
                "• যেকোনো রাসায়নিক স্প্রে করার সময় মাস্ক ও গ্লাভস ব্যবহার করুন।\n"
                "• বৃষ্টির আগে বা প্রখর রোদে স্প্রে করবেন না। বিকেলের শান্ত বাতাসে স্প্রে করা উত্তম।\n"
                "• কীটনাশকের মাত্রা অতিক্রম করবেন না। গুরুতর সমস্যায় স্থানীয় কৃষি আধিকারিক (ADA) বা KVK-এর পরামর্শ নিন।"
            )
        return (
            "\n\n🛡️ *Agricultural Safety & Caution:*\n"
            "• Always wear protective mask & gloves when spraying agro-chemicals.\n"
            "• Avoid spraying before rain or under intense midday sun. Late afternoon is ideal.\n"
            "• Adhere strictly to recommended dosages. For severe outbreaks, consult your local Block Agriculture Officer (ADA) or KVK."
        )

    def get_expert_escalation(self, reason: str = "Uncertain Diagnosis / High Risk", lang: str = "bn") -> str:
        """Generate official expert contact referral."""
        if lang == "bn":
            return (
                f"\n\n👨‍🌾 *কৃষি বিশেষজ্ঞের সাথে সরাসরি যোগাযোগের তথ্য:*\n"
                f"• কিষাণ কল সেন্টার (বিনামূল্যে): *1800-180-1551* (সকাল ৬টা - রাত ১০টা)\n"
                f"• পশ্চিমবঙ্গ রাজ্য কৃষি সহায়তা: *1800-103-6000*\n"
                f"• অথবা আপনার ব্লকের সহ-কৃষি অধিকর্তা (ADA) অফিস বা কৃষি বিজ্ঞান কেন্দ্রে (KVK) যোগাযোগ করুন।"
            )
        return (
            f"\n\n👨‍🌾 *Direct Agricultural Expert Escalation:*\n"
            f"• Kisan Call Center (Toll-Free): *1800-180-1551* (6 AM - 10 PM daily)\n"
            f"• West Bengal Agriculture Helpline: *1800-103-6000*\n"
            f"• You can also visit your nearest Block Assistant Director of Agriculture (ADA) or Krishi Vigyan Kendra (KVK)."
        )


safety_service = SafetyService()
