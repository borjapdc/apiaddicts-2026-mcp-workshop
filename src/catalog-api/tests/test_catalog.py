from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from shared.runtime import load_app


def test_catalog_and_deterministic_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("CATALOG_DB", str(tmp_path / "requests.db"))
    module = load_app("src/catalog-api/app/main.py", "catalog_test")
    with TestClient(module.app) as client:
        assert client.get("/health").status_code == 200
        assert len(client.get("/api/services").json()) == 5
        assert client.get("/api/services/missing").status_code == 404
        assert client.get("/api/services?limit=0").status_code == 422
        assert client.get("/api/services/payments/contract").json()["demo"]
        body = {"service_id": "orders", "consumer_id": "demo-reader", "purpose": "Synthetic workshop test"}
        first = client.post("/api/access-requests", json=body)
        assert first.status_code == 201
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: client.post("/api/access-requests", json=body), range(8)))
        assert all(result.status_code == 200 for result in results)
        assert all(result.json()["request_id"] == first.json()["request_id"] for result in results)
        assert client.post("/api/access-requests", json={**body, "consumer_id": "real-user"}).status_code == 422


def test_origin_separates_read_and_write(monkeypatch, tmp_path):
    monkeypatch.setenv("REQUIRE_AUTH", "1")
    monkeypatch.setenv("BACKEND_READ_TOKEN", "synthetic-read-test-token")
    monkeypatch.setenv("BACKEND_WRITE_TOKEN", "synthetic-write-test-token")
    monkeypatch.setenv("CATALOG_DB", str(tmp_path / "test.db"))
    module = load_app("src/catalog-api/app/main.py", "secure_catalog_test")
    with TestClient(module.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/services").status_code == 401
        assert client.get("/openapi.json").status_code == 401
        headers = {"x-backend-token": "synthetic-read-test-token"}
        assert client.get("/api/services", headers=headers).status_code == 200
        body = {"service_id": "orders", "consumer_id": "demo-reader", "purpose": "Synthetic workshop test"}
        assert client.post("/api/access-requests", headers=headers, json=body).status_code == 401
        assert client.post("/api/access-requests", headers={"x-backend-token": "synthetic-write-test-token"},
                           json=body).status_code == 201