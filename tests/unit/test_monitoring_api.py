from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scheduler.scheduler import scheduler_manager


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_scheduler_manager():
    with patch("app.api.monitoring.scheduler_manager") as mock:
        yield mock


def test_get_monitoring_status_running(client, mock_scheduler_manager):
    mock_scheduler_manager.is_running.return_value = True
    mock_scheduler_manager.get_interval.return_value = 60
    mock_scheduler_manager.get_count_jobs.return_value = 5

    response = client.get("/monitoring/status")

    assert response.status_code == 200

    data = response.json()
    assert data["is_running"] is True
    assert data["interval"] == 60
    assert data["endpoints_count"] == 5

    mock_scheduler_manager.is_running.assert_called_once()
    mock_scheduler_manager.get_interval.assert_called_once()
    mock_scheduler_manager.get_count_jobs.assert_called_once()


def test_get_monitoring_status_not_running(client, mock_scheduler_manager):
    mock_scheduler_manager.is_running.return_value = False
    mock_scheduler_manager.get_interval.return_value = 60
    mock_scheduler_manager.get_count_jobs.return_value = 0

    response = client.get("/monitoring/status")

    assert response.status_code == 200

    data = response.json()
    assert data["is_running"] is False
    assert data["interval"] == 60
    assert data["endpoints_count"] == 0


def test_trigger_checks_manually(client, mock_scheduler_manager):
    response = client.post("/monitoring/trigger")

    assert response.status_code == 202

    data = response.json()
    assert data["detail"] == "All checks triggered manually"

    mock_scheduler_manager.trigger_now.assert_called_once()


def test_trigger_checks_manually_response_structure(client, mock_scheduler_manager):
    response = client.post("/monitoring/trigger")

    assert "detail" in response.json()
    assert isinstance(response.json()["detail"], str)
