import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("agrisaathi.rag")

CROPS_FILE = Path(__file__).parent.parent / "data" / "crops_knowledge.json"
SCHEMES_FILE = Path(__file__).parent.parent / "data" / "schemes.json"


class RAGService:
    def __init__(self):
        self._crops: Dict[str, Any] = {}
        self._schemes: List[Dict[str, Any]] = []
        self._load_data()

    def _load_data(self):
        try:
            if CROPS_FILE.exists():
                with open(CROPS_FILE, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    self._crops = content.get("crops", {})
            if SCHEMES_FILE.exists():
                with open(SCHEMES_FILE, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    self._schemes = content.get("schemes", [])
        except Exception as e:
            logger.error(f"Error loading RAG datasets: {e}")

    def get_crop_info(self, query: str) -> Optional[Dict[str, Any]]:
        """Find matching crop in knowledge base."""
        q = query.lower().strip()
        for crop_key, data in self._crops.items():
            if crop_key in q or q in crop_key:
                return data
            aliases = data.get("aliases", [])
            if any(alias.lower() in q or q in alias.lower() for alias in aliases):
                return data
        return None

    def search_schemes(self, query: str) -> List[Dict[str, Any]]:
        """Search government schemes by keyword."""
        q = query.lower().strip()
        matched = []
        for scheme in self._schemes:
            name_en = scheme.get("name_en", "").lower()
            name_bn = scheme.get("name_bn", "").lower()
            category = scheme.get("category", "").lower()
            benefits_en = scheme.get("benefits_en", "").lower()

            if any(term in name_en or term in name_bn or term in category or term in benefits_en for term in [q, "scheme", "সরকারি", "প্রকল্প", "টাকা", "বীমা", "bima", "kisan"]):
                matched.append(scheme)

        if not matched and self._schemes:
            # If broad scheme inquiry, return top schemes
            return self._schemes[:3]
        return matched

    def get_fertilizer_guidance(self, crop_name: str, area: float = 1.0, unit: str = "bigha") -> Optional[Dict[str, Any]]:
        """Get calibrated fertilizer recommendation for crop and land area."""
        crop_data = self.get_crop_info(crop_name)
        if not crop_data:
            return None

        fertilizers = crop_data.get("fertilizer_recommendation", {})
        bengal_bigha = fertilizers.get("per_bigha_bengal", {})
        acre_rec = fertilizers.get("per_acre", {})

        # Standard multiplier
        if unit.lower() in ["bigha", "বিঘা"]:
            multiplier = area
            calc_urea = bengal_bigha.get("urea_kg", 30) * multiplier
            calc_ssp = bengal_bigha.get("ssp_kg", 50) * multiplier
            calc_mop = bengal_bigha.get("mop_kg", 20) * multiplier
        else:  # Acre
            multiplier = area
            calc_urea = acre_rec.get("nitrogen_kg", 40) * 2.17 * multiplier  # approx urea from N
            calc_ssp = acre_rec.get("phosphorus_kg", 20) * 6.25 * multiplier  # approx ssp from P
            calc_mop = acre_rec.get("potassium_kg", 20) * 1.67 * multiplier  # approx mop from K

        return {
            "crop": crop_data.get("name_en"),
            "crop_bn": crop_data.get("name_bn"),
            "area": area,
            "unit": unit,
            "recommended_doses": {
                "urea_kg": round(calc_urea, 1),
                "ssp_single_super_phosphate_kg": round(calc_ssp, 1),
                "mop_potash_kg": round(calc_mop, 1)
            },
            "growth_stages": crop_data.get("growth_stages", []),
            "source": "Bidhan Chandra Krishi Viswavidyalaya (BCKV) & ICAR Package of Practices"
        }

    def get_relevant_knowledge_chunk(self, user_query: str, crop_name: Optional[str] = None) -> str:
        """Construct context text for LLM grounding."""
        chunks = []

        target_crop = crop_name or user_query
        crop_info = self.get_crop_info(target_crop)
        if crop_info:
            chunks.append(f"CROP KNOWLEDGE: {crop_info.get('name_en')} ({crop_info.get('name_bn')})")
            chunks.append(f"Season & Sowing: {crop_info.get('season')}, {crop_info.get('sowing_period')}")
            chunks.append(f"Watering: {crop_info.get('water_requirement')}")

            # Add diseases
            diseases = crop_info.get("common_diseases", [])
            if diseases:
                chunks.append("Common Diseases & IPM:")
                for d in diseases:
                    chunks.append(f"- {d.get('name_en')} ({d.get('name_bn')}): {d.get('symptoms_en')}. IPM: {d.get('ipm_measures_en')}")

            # Add pests
            pests = crop_info.get("common_pests", [])
            if pests:
                chunks.append("Common Pests & IPM:")
                for p in pests:
                    chunks.append(f"- {p.get('name_en')} ({p.get('name_bn')}): {p.get('symptoms_en')}. IPM: {p.get('ipm_measures_en')}")

        # Check for scheme query
        if any(term in user_query.lower() for term in ["scheme", "prakalpa", "prokolpo", "টাকা", "বীমা", "সরকারি", "bandhu", "kisan"]):
            schemes = self.search_schemes(user_query)
            if schemes:
                chunks.append("\nGOVERNMENT SCHEMES INFORMATION:")
                for s in schemes:
                    chunks.append(f"Scheme: {s.get('name_en')} / {s.get('name_bn')}")
                    chunks.append(f"Benefits: {s.get('benefits_en')}")
                    chunks.append(f"Eligibility: {s.get('eligibility_en')}")
                    chunks.append(f"How to apply: {s.get('how_to_apply_en')}")

        return "\n".join(chunks)


rag_service = RAGService()
