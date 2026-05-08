import os
from datetime import datetime, timedelta, timezone
from typing import Dict

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Endpoint
from app.repositories.check_results import CheckResultsRepository
from app.schemas.check_results import CheckResultsCreate, CheckResultsResponse, RequestResult

logger = structlog.get_logger()


class CheckEngine:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CheckResultsRepository(db)

        self.CHECKER_TIMEOUT_SECONDS = int(os.getenv("CHECKER_TIMEOUT_SECONDS", "10"))
        self.NOTIFY_REPEAT_MINUTES = int(os.getenv("NOTIFY_REPEAT_MINUTES", 30))

        self.client = httpx.AsyncClient(
                    timeout=self.CHECKER_TIMEOUT_SECONDS,
                    follow_redirects=True)
        logger.info("HTTP client started")

        self.last_down_time: Dict[int, datetime] = {}


    async def close(self) -> None:
        await self.client.aclose()
        logger.info("HTTP client closed")


    async def __aenter__(self):
        return self


    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


    async def service(
        self,
        endpoint: Endpoint
        ) -> CheckResultsResponse:

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


    async def handle_notification(
        self,
        endpoint: Endpoint,
        check_results: CheckResultsCreate
        ) -> None:

        if not check_results.is_available:
            await self.notify_if_needed(endpoint, check_results)
        else:
            await self.check_after_recovery(endpoint, check_results)


    async def notify_if_needed(
        self,
        endpoint: Endpoint,
        check_results: CheckResultsCreate
        ) -> None:

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


    async def check_after_recovery(
        self,
        endpoint: Endpoint,
        check_results: CheckResultsCreate
        ) -> None:

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
        self,
        endpoint: Endpoint,
        check_results: CheckResultsCreate, status: str
    ):
        logger.info(
            "would_send_notification",
            status=status,
            endpoint_id=endpoint.id,
            service_name=endpoint.service.name if endpoint.service else "Unknown",
            url=endpoint.url,
            error=check_results.error_message,
        )


    async def check_endpoint(
        self,
        endpoint: Endpoint
        ) -> CheckResultsCreate:

        request_result = await self.send_request(endpoint.url)

        result = CheckResultsCreate(
            endpoint_id=endpoint.id,
            checked_at=request_result.checked_at,
            is_available=request_result.is_available,
            status_code=request_result.status_code,
            response_time_ms=request_result.response_time_ms,
            error_message=request_result.error_message,
        )

        if result.is_available:
            logger.info(
                "Check success",
                endpoint_id=endpoint.id,
                url=endpoint.url,
                checked_at=result.checked_at,
                response_time_ms=result.response_time_ms,
                status_code=result.status_code,
            )
        else:
            logger.warning(
                "Check failed",
                endpoint_id=endpoint.id,
                url=endpoint.url,
                checked_at=result.checked_at,
                response_time_ms=result.response_time_ms,
                error_message=result.error_message,
                status_code=result.status_code,
            )

        return result


    async def send_request(
        self,
        url: str,
    ) -> RequestResult:

        start_time = datetime.now(timezone.utc)

        try:
            response = await self.client.get(url)
            end_time = datetime.now(timezone.utc)

            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            response.raise_for_status()

            return RequestResult(
                checked_at=start_time,
                is_available=True,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                error_message=None,
                )

        except httpx.TimeoutException:
            return RequestResult(
                checked_at=start_time,
                is_available=False,
                status_code=None,
                response_time_ms=None,
                error_message=f"Timeout after {self.CHECKER_TIMEOUT_SECONDS} seconds",
            )
        except httpx.ConnectError as e:
            return RequestResult(
                checked_at=start_time,
                is_available=False,
                status_code=None,
                response_time_ms=None,
                error_message=f"Connection error: {str(e)}",
            )
        except httpx.HTTPStatusError as e:
            return RequestResult(
                checked_at=start_time,
                is_available=False,
                status_code=e.response.status_code,
                response_time_ms=None,
                error_message=f"HTTP {e.response.status_code}",
            )
        except httpx.RequestError as e:
            return RequestResult(
                checked_at=start_time,
                is_available=False,
                status_code=None,
                response_time_ms=None,
                error_message=f"Request error: {str(e)}",
            )
        except Exception as e:
            return RequestResult(
                checked_at=start_time,
                is_available=False,
                status_code=None,
                response_time_ms=None,
                error_message=f"Unexpected error {str(e)}",
            )
