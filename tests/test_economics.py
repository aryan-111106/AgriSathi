import pytest
from app.services.economics_service import economics_service


def test_economics_budget_calculation():
    budget = economics_service.calculate_budget("Potato", area=3.0, unit="bigha")
    assert budget is not None
    assert budget["crop"] == "Potato"
    assert budget["total_input_cost"] > 0
    assert budget["estimated_gross_revenue"] > 0
    assert "estimated_net_profit" in budget
    assert "roi_percent" in budget


def test_economics_crop_comparison():
    comp = economics_service.compare_crops("Potato", "Mustard", area=2.0, unit="bigha")
    assert comp is not None
    assert "crop_1" in comp
    assert "crop_2" in comp
    assert "comparison_summary_bn" in comp
    assert "comparison_summary_en" in comp
