"""Static Docker contract checks that do not require a Docker daemon."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_backend_dockerfile_exposes_healthcheck_and_bind_address() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in dockerfile
    assert "/api/ecommerce/health" in dockerfile
    assert '"0.0.0.0"' in dockerfile


def test_compose_contract_keeps_frontend_after_healthy_backend() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "backend:" in compose
    assert "frontend:" in compose
    assert "condition: service_healthy" in compose
    assert '"8000:8000"' in compose
