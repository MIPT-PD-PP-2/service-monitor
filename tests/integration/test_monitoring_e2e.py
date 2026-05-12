import pytest
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_e2e_check_success_records_result(client):
    svc = await client.post("/services", json={"name": "E2E Success", "description": "Test"})
    svc_id = svc.json()["id"]
    await client.post(f"/services/{svc_id}/endpoints", json={"url": "https://ok.local/h", "is_active": True})
    
    with patch("app.api.monitoring.scheduler_manager.trigger_now") as mock_trigger:
        resp = await client.post("/monitoring/trigger")
        assert resp.status_code == 202
        mock_trigger.assert_called_once()


async def test_e2e_check_failure_with_notification(client):
    svc = await client.post("/services", json={"name": "E2E Fail", "description": "Test"})
    svc_id = svc.json()["id"]
    await client.post(f"/services/{svc_id}/endpoints", json={"url": "https://fail.local/h", "is_active": True})
    await client.post(f"/services/{svc_id}/responsible", json={"name": "U", "email": "u@c.ru"})
    
    with patch("app.api.monitoring.scheduler_manager.trigger_now") as mock_trigger:
        resp = await client.post("/monitoring/trigger")
        assert resp.status_code == 202
        mock_trigger.assert_called_once()


async def test_e2e_no_duplicate_notifications(client):
    svc = await client.post("/services", json={"name": "E2E Dedup", "description": "Test"})
    svc_id = svc.json()["id"]
    await client.post(f"/services/{svc_id}/endpoints", json={"url": "https://dedup.local/h", "is_active": True})
    await client.post(f"/services/{svc_id}/responsible", json={"name": "U", "email": "u@c.ru"})
    
    with patch("app.api.monitoring.scheduler_manager.trigger_now") as mock_trigger:
        resp1 = await client.post("/monitoring/trigger")
        assert resp1.status_code == 202
        resp2 = await client.post("/monitoring/trigger")
        assert resp2.status_code == 202
        assert mock_trigger.call_count == 2


async def test_e2e_recovery_notification(client):
    svc = await client.post("/services", json={"name": "E2E Recovery", "description": "Test"})
    svc_id = svc.json()["id"]
    await client.post(f"/services/{svc_id}/endpoints", json={"url": "https://rec.local/h", "is_active": True})
    await client.post(f"/services/{svc_id}/responsible", json={"name": "U", "email": "u@c.ru"})
    
    with patch("app.api.monitoring.scheduler_manager.trigger_now") as mock_trigger:
        resp1 = await client.post("/monitoring/trigger")
        assert resp1.status_code == 202
        resp2 = await client.post("/monitoring/trigger")
        assert resp2.status_code == 202
        assert mock_trigger.call_count == 2


async def test_e2e_check_timeout_records_error(client):
    svc = await client.post("/services", json={"name": "E2E Timeout", "description": "Test"})
    svc_id = svc.json()["id"]
    await client.post(f"/services/{svc_id}/endpoints", json={"url": "https://to.local/h", "is_active": True})
    
    with patch("app.api.monitoring.scheduler_manager.trigger_now") as mock_trigger:
        resp = await client.post("/monitoring/trigger")
        assert resp.status_code == 202
        mock_trigger.assert_called_once()


async def test_e2e_inactive_endpoint_not_checked(client):
    svc = await client.post("/services", json={"name": "E2E Inactive", "description": "Test"})
    svc_id = svc.json()["id"]
    await client.post(f"/services/{svc_id}/endpoints", json={"url": "https://inact.local/h", "is_active": False})
    
    with patch("app.repositories.check_results.CheckResultsRepository.create", new_callable=AsyncMock) as mock_repo:
        with patch("app.api.monitoring.scheduler_manager.trigger_now"):
            await client.post("/monitoring/trigger")
            mock_repo.assert_not_called()
