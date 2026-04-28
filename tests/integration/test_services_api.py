import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_service_returns_201(client):
    response = await client.post(
        "/services",
        json={"name": "Payment Gateway", "description": "Main payment service"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "Payment Gateway"
    assert body["description"] == "Main payment service"
    assert "created_at" in body


async def test_create_service_minimal_body(client):
    response = await client.post("/services", json={"name": "Auth"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Auth"
    assert body["description"] is None


async def test_create_service_missing_name(client):
    response = await client.post("/services", json={"description": "no name"})
    assert response.status_code == 422


async def test_create_service_empty_name(client):
    response = await client.post("/services", json={"name": "  "})
    assert response.status_code == 422


async def test_list_services_empty(client):
    response = await client.get("/services")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_services_after_create(client):
    await client.post("/services", json={"name": "A"})
    await client.post("/services", json={"name": "B"})
    response = await client.get("/services")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    names = [item["name"] for item in body]
    assert "A" in names and "B" in names


async def test_get_service_existing(client):
    create = await client.post("/services", json={"name": "X"})
    service_id = create.json()["id"]
    response = await client.get(f"/services/{service_id}")
    assert response.status_code == 200
    assert response.json()["id"] == service_id


async def test_get_service_missing(client):
    response = await client.get("/services/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Сервис не найден"


async def test_delete_service(client):
    create = await client.post("/services", json={"name": "ToDelete"})
    service_id = create.json()["id"]
    delete = await client.delete(f"/services/{service_id}")
    assert delete.status_code == 204
    fetch = await client.get(f"/services/{service_id}")
    assert fetch.status_code == 404


async def test_delete_service_twice_returns_404(client):
    create = await client.post("/services", json={"name": "Once"})
    service_id = create.json()["id"]
    await client.delete(f"/services/{service_id}")
    second = await client.delete(f"/services/{service_id}")
    assert second.status_code == 404


async def test_delete_service_cascades_endpoints(client):
    create = await client.post("/services", json={"name": "Cascade"})
    service_id = create.json()["id"]
    await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://example.com/health"},
    )
    await client.delete(f"/services/{service_id}")
    fetch_endpoints = await client.get(f"/services/{service_id}/endpoints")
    assert fetch_endpoints.status_code == 404
