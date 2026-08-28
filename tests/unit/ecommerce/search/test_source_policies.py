from src.ecommerce.search.source_policies import get_source_policy_template


def test_conservative_mainland_template_only_filters_market():
    template = get_source_policy_template("conservative-mainland")

    assert template["source_policy"] == "filter"
    assert template["source_domain_allowlist_by_module"] == {
        "market": ["jd.com", "taobao.com", "1688.com"],
    }


def test_source_policy_template_is_detached():
    first = get_source_policy_template("conservative-mainland")
    first["source_domain_allowlist_by_module"]["market"].append("example.com")

    second = get_source_policy_template("conservative-mainland")
    assert "example.com" not in second["source_domain_allowlist_by_module"]["market"]
