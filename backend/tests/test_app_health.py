from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_reports_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_openapi_schema_exposes_health_route() -> None:
    client = TestClient(create_app())

    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
