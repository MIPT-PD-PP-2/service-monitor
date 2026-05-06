import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Endpoint
from app.repositories.check_results import CheckResultsRepository
from app.schemas.check_results import CheckResultsCreate, CheckResultsResponse

logger = structlog.get_logger()


class CheckEngine:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CheckResultsRepository(db)

        self.CHECKER_TIMEOUT_SECONDS = int(os.getenv("CHECKER_TIMEOUT_SECONDS", "10"))
        self.NOTIFY_REPEAT_MINUTES = int(os.getenv("NOTIFY_REPEAT_MINUTES", 30))

        self.last_down_time: Dict[int, datetime] = {}

    async def service(self, endpoint: Endpoint) -> CheckResultsResponse:

        check_results = await self.check_endpoint(endpoint)
        res = await self.repo.create(
            {
                "endpoint_id": endpoint.id,
                "checked_at": check_results.checked_at,
                "is_available": check_results.is_available,
                "status_code": check_results.status_code,
                "response_time_ms": check_results.response_time_ms,
                "error_message": check_results.error_message,
            }
        )
        logger.info(
            "Check_results created",
            endpoint_id=endpoint.id,
            checked_at=check_results.checked_at,
            is_available=check_results.is_available,
            status_code=check_results.status_code,
            response_time_ms=check_results.response_time_ms,
            error_message=check_results.error_message,
        )

        await self.handle_notification(endpoint, check_results)

        return res

    async def handle_notification(self, endpoint: Endpoint, check_results: CheckResultsCreate):

        if not check_results.is_available:
            await self.notify_if_needed(endpoint, check_results)
        else:
            await self.check_after_recovery(endpoint, check_results)

    async def notify_if_needed(self, endpoint: Endpoint, check_results: CheckResultsCreate):
        time_now = datetime.now(timezone.utc)
        last_down = self.last_down_time.get(endpoint.id)

        should_notify = False

        if last_down is None:
            should_notify = True
        else:
            time_diff = time_now - last_down
            if time_diff > timedelta(minutes=self.NOTIFY_REPEAT_MINUTES):
                should_notify = True

        if should_notify:
            await self.send_to_notifier(endpoint, check_results, status="DOWN")
            self.last_down_time[endpoint.id] = time_now
            logger.info(
                "DOWN notification sent",
                endpoint_id=endpoint.id,
                url=endpoint.url,
                time_since_last=time_diff if last_down else None,
            )
        else:
            logger.debug(
                "DOWN notification suppressed",
                endpoint_id=endpoint.id,
                url=endpoint.url,
                time_since_last=time_now - last_down if last_down else None,
            )

    async def check_after_recovery(self, endpoint: Endpoint, check_results: CheckResultsCreate):

        if endpoint.id in self.last_down_time:
            await self.send_to_notifier(endpoint, check_results, status="UP")
            del self.last_down_time[endpoint.id]
            logger.info(
                "UP notification sent",
                endpoint_id=endpoint.id,
                url=endpoint.url,
            )

    # Заглушка для отправки уведомлений
    async def send_to_notifier(
        self, endpoint: Endpoint, check_results: CheckResultsCreate, status: str
    ):
        logger.info(
            "would_send_notification",
            status=status,
            endpoint_id=endpoint.id,
            service_name=endpoint.service.name if endpoint.service else "Unknown",
            url=endpoint.url,
            error=check_results.error_message,
        )

    async def check_endpoint(self, endpoint: Endpoint) -> CheckResultsCreate:

        try:
            (
                checked_at,
                is_available,
                status_code,
                response_time_ms,
                error_message,
            ) = await self.send_request(endpoint.url)
        except Exception as e:
            checked_at = datetime.now(timezone.utc)
            is_available = False
            status_code = None
            response_time_ms = None
            error_message = f"Unexpected error {str(e)}"

        result = CheckResultsCreate(
            endpoint_id=endpoint.id,
            checked_at=checked_at,
            is_available=is_available,
            status_code=status_code,
            response_time_ms=response_time_ms,
            error_message=error_message,
        )

        if is_available:
            logger.info(
                "Check success",
                endpoint_id=endpoint.id,
                url=endpoint.url,
                checked_at=checked_at,
                response_time_ms=response_time_ms,
                status_code=status_code,
            )
        else:
            logger.warning(
                "Check failed",
                endpoint_id=endpoint.id,
                url=endpoint.url,
                checked_at=checked_at,
                response_time_ms=response_time_ms,
                error_message=error_message,
                status_code=status_code,
            )

        return result

    async def send_request(
        self,
        url: str,
    ) -> Tuple[datetime, bool, Optional[int], Optional[int], Optional[str]]:

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(
                timeout=self.CHECKER_TIMEOUT_SECONDS, follow_redirects=True
            ) as client:
                response = await client.get(url)
                end_time = datetime.now(timezone.utc)

                response_time_ms = int((end_time - start_time).total_seconds() * 1000)

                if 200 <= response.status_code < 400:
                    return start_time, True, response.status_code, response_time_ms, None
                else:
                    return (
                        start_time,
                        False,
                        response.status_code,
                        response_time_ms,
                        f"HTTP {response.status_code}",
                    )

        except httpx.TimeoutException:
            return (
                start_time,
                False,
                None,
                None,
                f"Timeout after {self.CHECKER_TIMEOUT_SECONDS} seconds",
            )
        except httpx.HTTPError as e:
            return start_time, False, None, None, f"Connection error: {str(e)}"
        except Exception as e:
            return start_time, False, None, None, f"Unexpected error {str(e)}"
