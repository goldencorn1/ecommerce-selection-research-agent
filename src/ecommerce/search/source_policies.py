"""Reusable source-policy templates for ecommerce search runs."""

from __future__ import annotations

from typing import Final


SOURCE_POLICY_TEMPLATES: Final[dict[str, dict[str, object]]] = {
    "conservative-mainland": {
        "source_policy": "filter",
        "source_domain_allowlist_by_module": {
            "market": ["jd.com", "taobao.com", "1688.com"],
        },
        "description": "仅约束市场模块；用户、竞品与机会模块保持不自动过滤。",
    }
}


def get_source_policy_template(name: str) -> dict[str, object]:
    """Return a detached source-policy template or raise for unknown names."""

    try:
        template = SOURCE_POLICY_TEMPLATES[name]
    except KeyError as exc:
        raise ValueError(f"unknown ecommerce source policy template: {name}") from exc
    return {
        **template,
        "source_domain_allowlist_by_module": {
            module: list(domains)
            for module, domains in template["source_domain_allowlist_by_module"].items()
        },
    }
