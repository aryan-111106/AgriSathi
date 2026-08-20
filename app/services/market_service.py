import json
import logging
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("agrisaathi.market")

DATA_FILE = Path(__file__).parent.parent / "data" / "mandi_data.json"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in km."""
    try:
        r = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlmb = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(r * c, 1)
    except Exception:
        return 0.0


class MarketService:
    def __init__(self):
        self._data: List[Dict[str, Any]] = []
        self._load_data()

    def _load_data(self):
        try:
            if DATA_FILE.exists():
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    self._data = content.get("markets", [])
            else:
                logger.warning(f"Mandi data file not found at {DATA_FILE}")
        except Exception as e:
            logger.error(f"Error loading mandi data: {e}")
            self._data = []

    def search_prices(
        self,
        commodity: Optional[str] = None,
        district: Optional[str] = None,
        state: Optional[str] = "West Bengal",
        farmer_lat: Optional[float] = None,
        farmer_lon: Optional[float] = None
    ) -> Dict[str, Any]:
        """Search mandi prices for a given commodity and district.

        When farmer_lat/farmer_lon is provided, results are enriched with
        a `distance_km` field and sorted by proximity (ascending). Otherwise
        they fall back to modal-price descending order.
        """
        if not self._data:
            self._load_data()

        matches = []
        c_query = commodity.lower().strip() if commodity else ""
        d_query = district.lower().strip() if district else ""

        # Normalize common crop names
        alias_map = {
            "alu": "potato",
            "aloo": "potato",
            "আলু": "potato",
            "dhan": "paddy (dhan)",
            "rice": "paddy (dhan)",
            "paddy": "paddy (dhan)",
            "ধান": "paddy (dhan)",
            "sarson": "mustard",
            "sorisha": "mustard",
            "সরিষা": "mustard",
            "রাই": "mustard",
            "tamatar": "tomato",
            "টমেটো": "tomato",
            "begun": "brinjal",
            "baingan": "brinjal",
            "বেগুন": "brinjal",
            "pat": "jute",
            "পাট": "jute",
            "lanka": "chili (green)",
            "chilli": "chili (green)",
            "লঙ্কা": "chili (green)",
            "peyaj": "onion",
            "pyaz": "onion",
            "পেঁয়াজ": "onion"
        }

        normalized_crop = alias_map.get(c_query, c_query)

        for item in self._data:
            item_comm = item.get("commodity", "").lower()
            item_comm_bn = item.get("commodity_bn", "")
            item_dist = item.get("district", "").lower()

            # Match commodity
            comm_match = False
            if not normalized_crop:
                comm_match = True
            elif normalized_crop in item_comm or item_comm in normalized_crop or c_query in item_comm_bn:
                comm_match = True

            # Match district
            dist_match = True
            if d_query:
                dist_match = (d_query in item_dist) or (item_dist in d_query)

            if comm_match and dist_match:
                matches.append(item)

        # If no district matches found, return all matches for that crop in state
        if not matches and normalized_crop:
            for item in self._data:
                item_comm = item.get("commodity", "").lower()
                if normalized_crop in item_comm or item_comm in normalized_crop:
                    matches.append(item)

        # Enrich with distance and sort accordingly
        has_gps = (
            farmer_lat is not None
            and farmer_lon is not None
            and farmer_lat != 0
            and farmer_lon != 0
        )
        for m in matches:
            mlat = m.get("latitude")
            mlon = m.get("longitude")
            if has_gps and mlat is not None and mlon is not None:
                m["distance_km"] = haversine_km(farmer_lat, farmer_lon, mlat, mlon)
            else:
                m["distance_km"] = None

        if has_gps:
            matches.sort(
                key=lambda x: (x.get("distance_km") is None, x.get("distance_km") or 1e9)
            )
        else:
            matches.sort(key=lambda x: x.get("modal_price", 0), reverse=True)

        return {
            "status": "success",
            "query": {
                "commodity": commodity,
                "district": district,
                "state": state,
                "farmer_gps": {"lat": farmer_lat, "lon": farmer_lon} if has_gps else None
            },
            "total_markets_found": len(matches),
            "results": matches,
            "sorted_by": "distance" if has_gps else "modal_price",
            "disclaimer_en": "⚠️ Market-reported price ≠ guaranteed selling price. Actual rates depend on quality, moisture, and local trader bidding.",
            "disclaimer_bn": "⚠️ বাজারে প্রকাশিত দর এবং আপনার বিক্রয় দর ভিন্ন হতে পারে। ফসলের মান, আর্দ্রতা ও স্থানীয় পাইকারদের উপর ভিত্তি করে দর পরিবর্তিত হয়।",
            "source": "State Agricultural Marketing Board / Agmarknet (WB)"
        }

    def format_market_summary(self, search_results: Dict[str, Any], lang: str = "bn") -> str:
        """Format market price list into WhatsApp friendly message text."""
        results = search_results.get("results", [])
        if not results:
            if lang == "bn":
                return "❌ দুঃখিত, এই মুহূর্তে নির্দিষ্ট ফসলের পাইকারি বাজার দর পাওয়া যায়নি।"
            return "❌ Sorry, no current mandi prices found for the requested crop/location."

        crop_name = results[0].get("commodity_bn" if lang == "bn" else "commodity", "Crop")
        lines = []

        if lang == "bn":
            lines.append(f"💰 *{crop_name} — আজকের পাইকারি বাজার দর (Mandi Prices)*\n")
            for item in results[:5]:
                market = item.get("market_bn", item.get("market"))
                district = item.get("district")
                modal = item.get("modal_price")
                min_p = item.get("min_price")
                max_p = item.get("max_price")
                trend = item.get("trend_7d_percent", 0.0)
                trend_icon = "📈" if trend > 0 else ("📉" if trend < 0 else "➡️")
                dist = item.get("distance_km")

                dist_str = f" | 🛣️ ~{dist} কিমি দূরে" if dist is not None else ""
                updated = item.get("updated_date", "")
                updated_str = f" | 🗓️ {updated}" if updated else ""

                lines.append(f"📍 *{market}* ({district}){dist_str}:")
                lines.append(f"   গড় দর: *₹{modal:,.0f}* /কুইন্টাল (₹{min_p:,.0f} - ₹{max_p:,.0f})")
                lines.append(f"   {trend_icon} গত ৭ দিনে পরিবর্তন: {trend:+.1f}%{updated_str}\n")

            lines.append(f"{search_results.get('disclaimer_bn')}")
        else:
            lines.append(f"💰 *{crop_name} — Today's Mandi Market Rates*\n")
            for item in results[:5]:
                market = item.get("market")
                district = item.get("district")
                modal = item.get("modal_price")
                min_p = item.get("min_price")
                max_p = item.get("max_price")
                trend = item.get("trend_7d_percent", 0.0)
                trend_icon = "📈" if trend > 0 else ("📉" if trend < 0 else "➡️")
                dist = item.get("distance_km")

                dist_str = f" | 🛣️ ~{dist} km away" if dist is not None else ""
                updated = item.get("updated_date", "")
                updated_str = f" | 🗓️ {updated}" if updated else ""

                lines.append(f"📍 *{market}* ({district}){dist_str}:")
                lines.append(f"   Modal Price: *₹{modal:,.0f}* /quintal (Range: ₹{min_p:,.0f} - ₹{max_p:,.0f})")
                lines.append(f"   {trend_icon} 7-Day Trend: {trend:+.1f}%{updated_str}\n")

            lines.append(f"{search_results.get('disclaimer_en')}")

        return "\n".join(lines)


market_service = MarketService()
