import json
from pathlib import Path

from src.ecommerce import run_mock_research
from src.ecommerce.telemetry import assess_report_quality


def test_three_category_productization_snapshots_remain_distinct():
    snapshot_path = Path(__file__).parents[2] / "fixtures" / "ecommerce" / "productization_regression.json"
    snapshots = json.loads(snapshot_path.read_text(encoding="utf-8"))

    for category, expected in snapshots.items():
        result = run_mock_research(category)
        recommendations = result.report.recommendations

        assert [item.product_name for item in recommendations] == expected["recommendation_names"]
        assert [item.price_range for item in recommendations] == expected["price_ranges"]
        assert len({item.price_range for item in recommendations}) == len(recommendations)
        assert len({item.positioning for item in recommendations}) == len(recommendations)
        assert all(item.validation_action for item in recommendations)
        assert all(item.validation_threshold for item in recommendations)
        assert all(item.validation_data_needed for item in recommendations)
        assert all(item.validation_failure_action for item in recommendations)

        gates = assess_report_quality(result)
        assert gates["report_product_ready"] is True
        assert gates["validation_cards_complete"] is True
        assert gates["direction_distinctness"] is True
