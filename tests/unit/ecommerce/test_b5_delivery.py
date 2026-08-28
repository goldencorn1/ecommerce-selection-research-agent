from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_offline_demo_compose_is_self_contained_and_secret_free() -> None:
    compose = (ROOT / "docker-compose.demo.yml").read_text(encoding="utf-8")
    assert "env_file" not in compose
    assert "APP_ENV: demo" in compose
    assert 'TAVILY_API_KEY: ""' in compose
    assert 'DEEPSEEK_API_KEY: ""' in compose
    assert 'INFOQUEST_API_KEY: ""' in compose
    assert "condition: service_healthy" in compose
    assert "NEXT_PUBLIC_API_URL: http://localhost:8000/api" in compose


def test_b5_shortcuts_and_runbook_are_present() -> None:
    expected = (
        "start_ecommerce_mock.bat",
        "start_ecommerce_offline_bundle.bat",
        "scripts/start_ecommerce_mock.ps1",
        "scripts/generate_ecommerce_offline_bundle.ps1",
        "docs/B5_DEMO_RUNBOOK_2026-08-17.md",
        "docs/PRODUCT_DESIGN_SPEC.md",
    )
    for relative_path in expected:
        assert (ROOT / relative_path).exists(), relative_path


def test_demo_env_example_contains_no_placeholder_secret_value() -> None:
    env_example = (ROOT / ".env.demo.example").read_text(encoding="utf-8")
    assert "TAVILY_API_KEY=" in env_example
    assert "DEEPSEEK_API_KEY=" in env_example
    assert "INFOQUEST_API_KEY=" in env_example
    assert "tvly-xxx" not in env_example
    assert "sk-xxx" not in env_example
