from src.ecommerce.quality_audit import audit_report_payload


def test_quality_audit_preserves_interface_success_but_blocks_business_claims():
    audit = audit_report_payload(
        {
            "report": {"recommendations": [{"product_name": "A"}], "evidence": [{"evidence_id": "e1"}]},
            "run_metrics": {
                "quality_level": "interface_success",
                "warning_count": 2,
                "quality_gates": {
                    "interface_success": True,
                    "evidence_usable": False,
                    "commercial_decision_ready": False,
                },
                "model_name": "deepseek-v4-flash",
                "usage_available": True,
                "actual_input_tokens": 100,
                "actual_output_tokens": 25,
                "actual_total_tokens": 125,
                "cost_status": "unpriced",
                "actual_cost_usd": 0,
            },
            "search_details": {
                "market": {
                    "status": "success",
                    "result_count": 5,
                    "mainland_relevant_count": 2,
                    "unknown_source_count": 1,
                    "published_result_count": 1,
                    "priced_result_count": 0,
                    "freshness_status": "partial",
                    "source_quality_score": 0.72,
                    "quality_warnings": ["需要核验"],
                },
                "competitor": {
                    "status": "success",
                    "result_count": 5,
                    "mainland_relevant_count": 3,
                    "unknown_source_count": 0,
                    "published_result_count": 0,
                    "price_coverage": 0.5,
                    "source_quality_score": 0.8,
                    "quality_warnings": [],
                },
            },
        }
    )

    assert audit["status"] == "review_required"
    assert audit["gates"]["interface_success"] is True
    assert audit["gates"]["commercial_decision_ready"] is False
    assert audit["search"]["total_result_count"] == 10
    assert audit["search"]["mainland_relevance_rate"] == 0.5
    assert audit["search"]["competitor_price_coverage"] == 0.5
    assert audit["model"]["cost_status"] == "unpriced"
    assert any("商业决策门禁" in item for item in audit["blocking_reasons"])


def test_quality_audit_marks_failed_interface_as_degraded():
    audit = audit_report_payload(
        {
            "report": {"recommendations": [], "evidence": []},
            "run_metrics": {
                "quality_gates": {
                    "interface_success": False,
                    "evidence_usable": False,
                    "commercial_decision_ready": False,
                }
            },
            "search_details": {"market": {"status": "fallback", "quality_warnings": []}},
        }
    )

    assert audit["status"] == "degraded"
    assert audit["search"]["module_count"] == 1
    assert "接口或搜索模块未全部成功" in audit["blocking_reasons"]
