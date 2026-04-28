import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _create_service(client, name: str = "Test Service") -> int:
    response = await client.post("/services", json={"name": name})
    return response.json()["id"]


async def test_create_endpoint_returns_201(client):
    service_id = await _create_service(client)
    response = await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://example.com/health"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["service_id"] == service_id
    assert body["url"] == "http://example.com/health"
    assert body["is_active"] is True


async def test_create_endpoint_explicit_inactive(client):
    service_id = await _create_service(client)
    response = await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://example.com/health", "is_active": False},
    )
    assert response.status_code == 201
    assert response.json()["is_active"] is False


async def test_create_endpoint_unknown_service(client):
    response = await client.post(
        "/services/99999/endpoints",
        json={"url": "http://example.com/health"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


async def test_create_endpoint_invalid_url_no_scheme(client):
    service_id = await _create_service(client)
    response = await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "example.com/health"},
    )
    assert response.status_code == 422


async def test_create_endpoint_missing_url(client):
    service_id = await _create_service(client)
    response = await client.post(
        f"/services/{service_id}/endpoints",
        json={"is_active": True},
    )
    assert response.status_code == 422


async def test_list_endpoints_empty(client):
    service_id = await _create_service(client)
    response = await client.get(f"/services/{service_id}/endpoints")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_endpoints_unknown_service(client):
    response = await client.get("/services/99999/endpoints")
    assert response.status_code == 404


async def test_list_endpoints_after_create(client):
    service_id = await _create_service(client)
    await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://a.test/h"},
    )
    await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://b.test/h"},
    )
    response = await client.get(f"/services/{service_id}/endpoints")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    urls = [e["url"] for e in body]
    assert "http://a.test/h" in urls and "http://b.test/h" in urls


async def test_patch_endpoint_only_url(client):
    service_id = await _create_service(client)
    create = await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://old.test/h"},
    )
    endpoint_id = create.json()["id"]
    response = await client.patch(
        f"/endpoints/{endpoint_id}",
        json={"url": "http://new.test/h"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["url"] == "http://new.test/h"
    assert body["is_active"] is True


async def test_patch_endpoint_only_is_active(client):
    service_id = await _create_service(client)
    create = await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://x.test/h"},
    )
    endpoint_id = create.json()["id"]
    response = await client.patch(
        f"/endpoints/{endpoint_id}",
        json={"is_active": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["url"] == "http://x.test/h"
    assert body["is_active"] is False


async def test_patch_endpoint_empty_body(client):
    service_id = await _create_service(client)
    create = await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://x.test/h"},
    )
    endpoint_id = create.json()["id"]
    response = await client.patch(f"/endpoints/{endpoint_id}", json={})
    assert response.status_code == 422
    assert response.json()["detail"] == "No fields to update"


async def test_patch_endpoint_invalid_url(client):
    service_id = await _create_service(client)
    create = await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://x.test/h"},
    )
    endpoint_id = create.json()["id"]
    response = await client.patch(
        f"/endpoints/{endpoint_id}",
        json={"url": "bad-url"},
    )
    assert response.status_code == 422


async def test_patch_endpoint_missing(client):
    response = await client.patch("/endpoints/99999", json={"is_active": False})
    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint not found"


async def test_delete_endpoint(client):
    service_id = await _create_service(client)
    create = await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://x.test/h"},
    )
    endpoint_id = create.json()["id"]
    response = await client.delete(f"/endpoints/{endpoint_id}")
    assert response.status_code == 204


async def test_delete_endpoint_twice_returns_404(client):
    service_id = await _create_service(client)
    create = await client.post(
        f"/services/{service_id}/endpoints",
        json={"url": "http://x.test/h"},
    )
    endpoint_id = create.json()["id"]
    await client.delete(f"/endpoints/{endpoint_id}")
    second = await client.delete(f"/endpoints/{endpoint_id}")
    assert second.status_code == 404


async def test_delete_endpoint_missing(client):
    response = await client.delete("/endpoints/99999")
    assert response.status_code == 404
