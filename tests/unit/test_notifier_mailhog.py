# tests/integration/test_notifier_mailhog.py
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

import httpx
import pytest

from app.config import settings
from app.models.models import Endpoint, Service
from app.notifier.notifier import Notifier
from app.schemas.check_results import CheckResultsResponse

settings.smtp_host = "127.0.0.1"
settings.smtp_port = 1025

@pytest.fixture
def notifier():
    return Notifier()


@pytest.fixture
def mock_endpoint():
    service = MagicMock(spec=Service)
    service.id = 1
    service.name = "Test Service"

    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = 1
    endpoint.url = "https://example.com/api/health"
    endpoint.service = service
    endpoint.service_id = 1
    return endpoint


@pytest.fixture
def check_result():
    return CheckResultsResponse(
        id=1,
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=False,
        status_code=500,
        response_time_ms=150,
        error_message="HTTP 500",
    )


# Вспомогательные фикстуры для работы с MailHog
@pytest.fixture
def mailhog_client():
    import httpx

    client = httpx.AsyncClient(base_url="http://localhost:8025")
    yield client


@pytest.mark.asyncio
async def test_send_down_notification_to_mailhog(notifier, mock_endpoint, check_result):
    responsible_list = ["test@example.com"]
    service_name = "Test Service"

    result = await notifier.send_notification(
        endpoint=mock_endpoint,
        check_result=check_result,
        status="DOWN",
        service_name=service_name,
        responsible_list=responsible_list,
    )

    assert "Notification sent to" in result
    assert "test@example.com" in result


@pytest.mark.asyncio
async def test_send_up_notification_to_mailhog(notifier, mock_endpoint, check_result):
    check_result.is_available = True
    check_result.status_code = 200
    check_result.error_message = None

    responsible_list = ["test@example.com"]
    service_name = "Test Service"

    result = await notifier.send_notification(
        endpoint=mock_endpoint,
        check_result=check_result,
        status="UP",
        service_name=service_name,
        responsible_list=responsible_list,
    )

    assert "Notification sent to" in result
    assert "test@example.com" in result


@pytest.mark.asyncio
async def test_send_notification_to_multiple_recipients(
    notifier, mock_endpoint, check_result
):
    responsible_list = ["user1@test.com", "user2@test.com", "user3@test.com"]
    service_name = "Test Service"

    result = await notifier.send_notification(
        endpoint=mock_endpoint,
        check_result=check_result,
        status="DOWN",
        service_name=service_name,
        responsible_list=responsible_list,
    )

    for email in responsible_list:
        assert email in result


@pytest.mark.asyncio
async def test_mailhog_received_emails(notifier, mock_endpoint, check_result):

    async with httpx.AsyncClient() as mailhog_client:
        await mailhog_client.delete("http://localhost:8025/api/v1/messages")

    responsible_list = ["test@example.com"]
    service_name = "Test Service"

    await notifier.send_notification(
        endpoint=mock_endpoint,
        check_result=check_result,
        status="DOWN",
        service_name=service_name,
        responsible_list=responsible_list,
    )

    await asyncio.sleep(1)

    async with httpx.AsyncClient() as mailhog_client:
        response = await mailhog_client.get("http://localhost:8025/api/v2/messages")
        assert response.status_code == 200

        messages = response.json()
        items = messages.get("items", [])

        assert len(items) > 0

        found = False
        for item in items:
            for recipient in item.get("Content", {}).get("Headers", {}).get("To", []):
                if "test@example.com" in recipient:
                    found = True
                    break
            if found:
                break

        assert found, "Email not found in MailHog"

