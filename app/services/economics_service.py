import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("agrisaathi.economics")

# Standard production economics benchmarks per Bigha (approx 0.33 Acre) in West Bengal
CROP_ECONOMICS_BENCHMARKS = {
    "potato": {
        "name_en": "Potato",
        "name_bn": "আলু",
        "duration_days": "90-100 days",
        "input_costs_per_bigha": {
            "seeds": 8500,        # ~4-5 packets seed tubers
            "fertilizers": 3200,  # Urea, SSP, MOP, Boron
            "pesticides_fungicides": 1800,
            "irrigation": 1400,
            "labor_and_machinery": 4500,  # Tractor, planting, earthing up, harvest
            "transport_storage": 1500
        },
        "expected_yield_quintal_per_bigha": 28,  # ~85 quintal/acre
        "average_market_rate_per_quintal": 1850,
        "risk_level": "Medium-High (Weather & Late Blight sensitive)"
    },
    "rice": {
        "name_en": "Rice / Paddy (Boro)",
        "name_bn": "ধান (বোরো)",
        "duration_days": "120-130 days",
        "input_costs_per_bigha": {
            "seeds": 800,
            "fertilizers": 2200,
            "pesticides_fungicides": 1100,
            "irrigation": 2500,  # High in Boro
            "labor_and_machinery": 3800,
            "transport_storage": 800
        },
        "expected_yield_quintal_per_bigha": 7.5, # ~22-25 quintal/acre
        "average_market_rate_per_quintal": 2300,
        "risk_level": "Low-Medium"
    },
    "mustard": {
        "name_en": "Mustard",
        "name_bn": "সরিষা",
        "duration_days": "85-100 days",
        "input_costs_per_bigha": {
            "seeds": 400,
            "fertilizers": 1500,
            "pesticides_fungicides": 700,
            "irrigation": 800,   # Low water requirement
            "labor_and_machinery": 2000,
            "transport_storage": 500
        },
        "expected_yield_quintal_per_bigha": 2.2, # ~6.5 quintal/acre
        "average_market_rate_per_quintal": 5650,
        "risk_level": "Low"
    },
    "tomato": {
        "name_en": "Tomato",
        "name_bn": "টমেটো",
        "duration_days": "100-120 days",
        "input_costs_per_bigha": {
            "seeds": 1500,
            "fertilizers": 2800,
            "pesticides_fungicides": 2200,
            "irrigation": 1800,
            "labor_and_machinery": 4800,
            "transport_storage": 2000
        },
        "expected_yield_quintal_per_bigha": 35,
        "average_market_rate_per_quintal": 2400,
        "risk_level": "Medium-High (Market price volatility)"
    }
}


class EconomicsService:
    def calculate_budget(self, crop_key: str, area: float = 1.0, unit: str = "bigha") -> Optional[Dict[str, Any]]:
        """Calculate detailed input cost, revenue, and profit for a crop."""
        key = crop_key.lower().strip()
        if "alu" in key or "potato" in key or "আলু" in key:
            benchmark = CROP_ECONOMICS_BENCHMARKS["potato"]
        elif "rice" in key or "dhan" in key or "ধান" in key:
            benchmark = CROP_ECONOMICS_BENCHMARKS["rice"]
        elif "mustard" in key or "sarson" in key or "সরিষা" in key:
            benchmark = CROP_ECONOMICS_BENCHMARKS["mustard"]
        elif "tomato" in key or "টমেটো" in key:
            benchmark = CROP_ECONOMICS_BENCHMARKS["tomato"]
        else:
            return None

        # Convert to bigha multiplier (1 Acre = 3 Bighas)
        if unit.lower() in ["acre", "একর"]:
            bigha_area = area * 3.0
        elif unit.lower() in ["hectare", "হেক্টর"]:
            bigha_area = area * 7.47
        else:
            bigha_area = area

        costs_base = benchmark["input_costs_per_bigha"]
        total_costs = {}
        sum_cost = 0

        for item, val in costs_base.items():
            cost_item = round(val * bigha_area)
            total_costs[item] = cost_item
            sum_cost += cost_item

        expected_yield = round(benchmark["expected_yield_quintal_per_bigha"] * bigha_area, 1)
        expected_revenue = round(expected_yield * benchmark["average_market_rate_per_quintal"])
        estimated_net_profit = expected_revenue - sum_cost
        roi_percent = round((estimated_net_profit / sum_cost) * 100, 1) if sum_cost > 0 else 0

        return {
            "crop": benchmark["name_en"],
            "crop_bn": benchmark["name_bn"],
            "area_requested": f"{area} {unit}",
            "bigha_equivalent": round(bigha_area, 2),
            "duration": benchmark["duration_days"],
            "itemized_costs": total_costs,
            "total_input_cost": sum_cost,
            "expected_yield_quintals": expected_yield,
            "assumed_market_rate_per_q": benchmark["average_market_rate_per_quintal"],
            "estimated_gross_revenue": expected_revenue,
            "estimated_net_profit": estimated_net_profit,
            "roi_percent": roi_percent,
            "risk_level": benchmark["risk_level"],
            "disclaimer_en": "⚠️ Note: Costs and yields are estimated averages. Actual returns vary by local weather, management, and prevailing market prices.",
            "disclaimer_bn": "⚠️ দ্রষ্টব্য: খরচ ও লাভের হিসাব গড় ধারণার উপর ভিত্তি করে। স্থানীয় আবহাওয়া ও বাজারের উপর ভিত্তি করে চূড়ান্ত আয় পরিবর্তিত হতে পারে।"
        }

    def compare_crops(self, crop1: str, crop2: str, area: float = 1.0, unit: str = "bigha") -> Optional[Dict[str, Any]]:
        """Compare two crops side by side."""
        b1 = self.calculate_budget(crop1, area, unit)
        b2 = self.calculate_budget(crop2, area, unit)

        if not b1 or not b2:
            return None

        return {
            "crop_1": b1,
            "crop_2": b2,
            "comparison_summary_en": f"Comparison for {area} {unit}: {b1['crop']} requires total input of ₹{b1['total_input_cost']:,} with estimated net profit ~₹{b1['estimated_net_profit']:,}, while {b2['crop']} requires ₹{b2['total_input_cost']:,} with estimated net profit ~₹{b2['estimated_net_profit']:,}.",
            "comparison_summary_bn": f"{area} {unit} জমিতে: {b1['crop_bn']} চাষে মোট আনুমানিক খরচ ₹{b1['total_input_cost']:,} এবং সম্ভাব্য লাভ ~₹{b1['estimated_net_profit']:,}, অন্যদিকে {b2['crop_bn']} চাষে খরচ ₹{b2['total_input_cost']:,} এবং সম্ভাব্য লাভ ~₹{b2['estimated_net_profit']:,}।"
        }


economics_service = EconomicsService()
