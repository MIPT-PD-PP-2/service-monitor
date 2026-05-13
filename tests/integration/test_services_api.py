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


async def test_create_service_duplicate_name_allowed(client):
    """Создание сервиса с дублирующимся именем.
    
    Примечание: В текущей реализации уникальность имени не enforced на уровне БД,
    поэтому дубликаты разрешены. Если в будущем добавится unique-констрейнт,
    этот тест нужно будет обновить (ожидать 409 вместо 201).
    """
    payload = {"name": "Duplicate Service", "description": "First instance"}
    
    response1 = await client.post("/services", json=payload)
    assert response1.status_code == 201
    service1_id = response1.json()["id"]
    
    response2 = await client.post("/services", json=payload)
    assert response2.status_code == 201
    service2_id = response2.json()["id"]
    
    assert service1_id != service2_id
    
    list_response = await client.get("/services")
    names = [s["name"] for s in list_response.json()]
    assert names.count("Duplicate Service") == 2


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
    assert response.json()["detail"] == "Service not found"


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


async def test_create_responsible_returns_201(client):
    create = await client.post("/services", json={"name": "With Responsible"})
    service_id = create.json()["id"]
    response = await client.post(
        f"/services/{service_id}/responsible",
        json={"name": "Ivan Ivanov", "email": "ivanov@company.ru"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["service_id"] == service_id
    assert body["name"] == "Ivan Ivanov"
    assert body["email"] == "ivanov@company.ru"


async def test_create_responsible_unknown_service(client):
    response = await client.post(
        "/services/99999/responsible",
        json={"name": "Ivan", "email": "ivan@test.ru"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


async def test_create_responsible_invalid_email(client):
    create = await client.post("/services", json={"name": "Email Test"})
    service_id = create.json()["id"]
    response = await client.post(
        f"/services/{service_id}/responsible",
        json={"name": "Ivan", "email": "not-an-email"},
    )
    assert response.status_code == 422


async def test_list_responsible_empty(client):
    create = await client.post("/services", json={"name": "No Responsible"})
    service_id = create.json()["id"]
    response = await client.get(f"/services/{service_id}/responsible")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_responsible_unknown_service(client):
    response = await client.get("/services/99999/responsible")
    assert response.status_code == 404


async def test_list_responsible_after_create(client):
    create = await client.post("/services", json={"name": "R"})
    service_id = create.json()["id"]
    await client.post(
        f"/services/{service_id}/responsible",
        json={"name": "A", "email": "a@test.ru"},
    )
    await client.post(
        f"/services/{service_id}/responsible",
        json={"name": "B", "email": "b@test.ru"},
    )
    response = await client.get(f"/services/{service_id}/responsible")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    names = [r["name"] for r in body]
    assert "A" in names and "B" in names


async def test_delete_responsible(client):
    create = await client.post("/services", json={"name": "Del Resp"})
    service_id = create.json()["id"]
    resp = await client.post(
        f"/services/{service_id}/responsible",
        json={"name": "ToDelete", "email": "del@test.ru"},
    )
    responsible_id = resp.json()["id"]
    response = await client.delete(f"/responsible/{responsible_id}")
    assert response.status_code == 204
    listing = await client.get(f"/services/{service_id}/responsible")
    assert all(r["id"] != responsible_id for r in listing.json())


async def test_delete_responsible_twice_returns_404(client):
    create = await client.post("/services", json={"name": "Del Twice"})
    service_id = create.json()["id"]
    resp = await client.post(
        f"/services/{service_id}/responsible",
        json={"name": "Once", "email": "once@test.ru"},
    )
    responsible_id = resp.json()["id"]
    await client.delete(f"/responsible/{responsible_id}")
    second = await client.delete(f"/responsible/{responsible_id}")
    assert second.status_code == 404


async def test_delete_responsible_missing(client):
    response = await client.delete("/responsible/99999")
    assert response.status_code == 404


async def test_set_sla_config_returns_200(client):
    create = await client.post("/services", json={"name": "SLA Service"})
    service_id = create.json()["id"]
    response = await client.put(
        f"/services/{service_id}/sla-config",
        json={"target_percent": 99.5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] > 0
    assert body["service_id"] == service_id
    assert body["target_percent"] == 99.5


async def test_set_sla_config_upsert_returns_200(client):
    create = await client.post("/services", json={"name": "Upsert SLA"})
    service_id = create.json()["id"]

    first = await client.put(
        f"/services/{service_id}/sla-config",
        json={"target_percent": 95.0},
    )
    assert first.status_code == 200
    assert first.json()["target_percent"] == 95.0

    second = await client.put(
        f"/services/{service_id}/sla-config",
        json={"target_percent": 99.9},
    )
    assert second.status_code == 200
    assert second.json()["target_percent"] == 99.9
    assert second.json()["id"] == first.json()["id"]


async def test_set_sla_config_empty_returns_200(client):
    create = await client.post("/services", json={"name": "Default SLA"})
    service_id = create.json()["id"]
    response = await client.put(
        f"/services/{service_id}/sla-config",
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] > 0
    assert body["service_id"] == service_id
    assert body["target_percent"] == 99.0


async def test_set_sla_config_unknown_service(client):
    response = await client.put(
        "/services/99999/sla-config",
        json={"target_percent": 99.5},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


async def test_set_sla_config_invalid_target_below_min(client):
    create_service = await client.post("/services", json={"name": "Invalid Min"})
    service_id = create_service.json()["id"]

    response = await client.put(
        f"/services/{service_id}/sla-config",
        json={"target_percent": -10},
    )
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("target_percent" in str(error) for error in errors)


async def test_set_sla_config_invalid_target_above_max(client):
    create_service = await client.post("/services", json={"name": "Invalid Max"})
    service_id = create_service.json()["id"]

    response = await client.put(
        f"/services/{service_id}/sla-config",
        json={"target_percent": 150},
    )
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("target_percent" in str(error) for error in errors)


async def test_get_sla_config_exists(client):
    create_service = await client.post("/services", json={"name": "Get SLA"})
    service_id = create_service.json()["id"]

    await client.put(
        f"/services/{service_id}/sla-config",
        json={"target_percent": 99.99},
    )

    response = await client.get(f"/services/{service_id}/sla-config")
    assert response.status_code == 200
    body = response.json()
    assert body["service_id"] == service_id
    assert body["target_percent"] == 99.99


async def test_get_sla_config_not_exists_returns_default(client):
    create_service = await client.post("/services", json={"name": "No SLA Config"})
    service_id = create_service.json()["id"]

    response = await client.get(f"/services/{service_id}/sla-config")
    assert response.status_code == 200
    body = response.json()
    assert body["service_id"] == service_id
    assert body["target_percent"] == 99.0
    assert body["id"] is None


async def test_get_sla_config_unknown_service_returns_404(client):
    response = await client.get("/services/99999/sla-config")
    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"
