"""API tests against a temporary JSON file."""

import json
from pathlib import Path

from app.schemas import Store

ROOT = Path(__file__).resolve().parents[1]


def store_payload(**overrides):
    body = {
        "name": "Corner Shop",
        "description": "A small convenience store.",
        "address": {
            "street": "1 Main Street",
            "city": "Austin",
            "state": "TX",
            "postal_code": "73301",
            "country": "USA",
        },
        "phone": "+1 512 555 0199",
        "email": "corner@example.com",
        "website": "https://example.com/corner",
        "category": "convenience",
        "is_active": True,
        "opening_hours": {"monday": "09:00-17:00", "sunday": "closed"},
    }
    body.update(overrides)
    return body


def test_seed_file_matches_schema():
    raw = json.loads((ROOT / "stores.json").read_text(encoding="utf-8"))
    assert raw["stores"]
    for item in raw["stores"]:
        Store.model_validate(item)


def test_root_and_health(client):
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["stores"] == "/api/v1/stores"

    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["store_count"] == 0


def test_openapi_lists_store_routes(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/stores" in paths
    assert "/api/v1/stores/{store_id}" in paths
    assert "get" in paths["/api/v1/stores"]
    assert "post" in paths["/api/v1/stores"]


def test_create_get_and_persist(client, data_file):
    created = client.post("/api/v1/stores", json=store_payload())
    assert created.status_code == 201
    record = created.json()
    assert created.headers["location"].endswith(f"/api/v1/stores/{record['id']}")
    assert record["name"] == "Corner Shop"
    assert record["category"] == "convenience"

    fetched = client.get(f"/api/v1/stores/{record['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["email"] == "corner@example.com"

    on_disk = json.loads(data_file.read_text(encoding="utf-8"))
    assert on_disk["stores"][0]["id"] == record["id"]
    assert on_disk["stores"][0]["website"] == "https://example.com/corner"


def test_list_filters_sort_and_pagination(client):
    client.post("/api/v1/stores", json=store_payload(name="Bravo Market", category="grocery"))
    client.post(
        "/api/v1/stores",
        json=store_payload(
            name="Alpha Books",
            category="bookstore",
            is_active=False,
            address={
                "street": "9 Oak Street",
                "city": "Seattle",
                "country": "USA",
            },
        ),
    )
    client.post("/api/v1/stores", json=store_payload(name="Cedar Pharmacy", category="pharmacy"))

    by_name = client.get("/api/v1/stores", params={"sort": "name"})
    assert [item["name"] for item in by_name.json()["items"]] == [
        "Alpha Books",
        "Bravo Market",
        "Cedar Pharmacy",
    ]

    seattle = client.get("/api/v1/stores", params={"city": "seattle"})
    assert seattle.json()["total"] == 1
    assert seattle.json()["items"][0]["name"] == "Alpha Books"

    inactive = client.get("/api/v1/stores", params={"is_active": False})
    assert [item["name"] for item in inactive.json()["items"]] == ["Alpha Books"]

    search = client.get("/api/v1/stores", params={"q": "pharmacy"})
    assert search.json()["items"][0]["name"] == "Cedar Pharmacy"

    page = client.get("/api/v1/stores", params={"sort": "name", "skip": 1, "limit": 1})
    body = page.json()
    assert body["total"] == 3
    assert [item["name"] for item in body["items"]] == ["Bravo Market"]


def test_put_patch_and_delete(client, data_file):
    created = client.post("/api/v1/stores", json=store_payload()).json()
    store_id = created["id"]
    before = json.loads(data_file.read_text(encoding="utf-8"))["stores"][0]

    replaced = client.put(
        f"/api/v1/stores/{store_id}",
        json=store_payload(name="Corner Shop West", description="Moved one block west."),
    )
    assert replaced.status_code == 200
    assert replaced.json()["name"] == "Corner Shop West"
    assert replaced.json()["id"] == store_id

    after_put = json.loads(data_file.read_text(encoding="utf-8"))["stores"][0]
    assert after_put["created_at"] == before["created_at"]
    assert after_put["description"] == "Moved one block west."

    patched = client.patch(f"/api/v1/stores/{store_id}", json={"is_active": False})
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False
    assert patched.json()["name"] == "Corner Shop West"

    empty_patch = client.patch(f"/api/v1/stores/{store_id}", json={})
    assert empty_patch.status_code == 200
    assert empty_patch.json()["name"] == "Corner Shop West"

    deleted = client.delete(f"/api/v1/stores/{store_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/api/v1/stores/{store_id}").status_code == 404


def test_missing_store_and_validation_errors(client):
    missing = "does-not-exist"
    assert client.get(f"/api/v1/stores/{missing}").status_code == 404
    assert client.put(f"/api/v1/stores/{missing}", json=store_payload()).status_code == 404
    assert client.patch(f"/api/v1/stores/{missing}", json={"name": "Nope"}).status_code == 404
    assert client.delete(f"/api/v1/stores/{missing}").status_code == 404

    invalid = client.post("/api/v1/stores", json=store_payload(category="spaceship", name=""))
    assert invalid.status_code == 422

    bad_hours = client.post(
        "/api/v1/stores",
        json=store_payload(opening_hours={"monday": "25:00-26:00"}),
    )
    assert bad_hours.status_code == 422

    unknown = client.post("/api/v1/stores", json=store_payload(owner="Ada"))
    assert unknown.status_code == 422


def test_second_app_reads_the_same_file(data_file):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    settings = Settings(data_file=str(data_file))
    with TestClient(create_app(settings)) as first:
        created = first.post("/api/v1/stores", json=store_payload(name="Persisted Shop"))
        store_id = created.json()["id"]

    with TestClient(create_app(settings)) as second:
        fetched = second.get(f"/api/v1/stores/{store_id}")
        assert fetched.status_code == 200
        assert fetched.json()["name"] == "Persisted Shop"
