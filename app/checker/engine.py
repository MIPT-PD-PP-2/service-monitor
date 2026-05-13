from datetime import datetime, timedelta, timezone
from typing import Dict, List

import httpx
import structlog

from app.config import settings
from app.db.database import AsyncSessionLocal
from app.models.models import Endpoint
from app.notifier.notifier import Notifier
from app.repositories.check_results import CheckResultsRepository
from app.repositories.responsible import ResponsibleRepository
from app.repositories.services import ServiceRepository
from app.schemas.check_results import CheckResultsCreate, CheckResultsResponse, RequestResult

logger = structlog.get_logger()


class CheckEngine:

    def __init__(self):
        self.notifier = Notifier()

        self._checker_timeout = settings.checker_timeout_seconds
        self._notify_repeat_minutes = settings.notify_repeat_minutes

        self.client = httpx.AsyncClient(
            timeout=float(self._checker_timeout),
            follow_redirects=True,
        )
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
        ) -> CheckResultsResponse | None:

        check_results = await self.check_endpoint(endpoint)

        try:
            async with AsyncSessionLocal() as session:
                repo = CheckResultsRepository(session)
                res = await repo.create(
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

                await self.handle_notification(endpoint, res)

                return res
        except Exception:
            logger.exception(
                "Check DB write failed",
                endpoint_id=endpoint.id,
            )
            return None


    async def handle_notification(
        self,
        endpoint: Endpoint,
        check_results: CheckResultsResponse
        ) -> None:

        if not check_results.is_available:
            await self.notify_if_needed(endpoint, check_results)
        else:
            await self.check_after_recovery(endpoint, check_results)


    async def notify_if_needed(
        self,
        endpoint: Endpoint,
        check_results: CheckResultsResponse
        ) -> None:

        time_now = datetime.now(timezone.utc)
        last_down = self.last_down_time.get(endpoint.id)
        time_diff: timedelta | None = None

        should_notify = False

        if last_down is None:
            should_notify = True
        else:
            time_diff = time_now - last_down
            if time_diff > timedelta(minutes=self._notify_repeat_minutes):
                should_notify = True

        if should_notify:
            await self.send_to_notifier(endpoint, check_results, status="DOWN")
            self.last_down_time[endpoint.id] = time_now
            logger.info(
                "DOWN notification sent to notifier",
                endpoint_id=endpoint.id,
                url=endpoint.url,
                time_since_last=time_diff,
            )
        else:
            logger.debug(
                "DOWN notification suppressed",
                endpoint_id=endpoint.id,
                url=endpoint.url,
                time_since_last=time_diff,
            )


    async def check_after_recovery(
        self,
        endpoint: Endpoint,
        check_results: CheckResultsResponse
        ) -> None:

        if endpoint.id in self.last_down_time:
            await self.send_to_notifier(endpoint, check_results, status="UP")
            del self.last_down_time[endpoint.id]
            logger.info(
                "UP notification sent to notifier",
                endpoint_id=endpoint.id,
                url=endpoint.url,
            )


    async def send_to_notifier(
        self,
        endpoint: Endpoint,
        check_results: CheckResultsResponse,
        status: str,
    ) -> None:
        async with AsyncSessionLocal() as session:
            responsible_repo = ResponsibleRepository(session)
            service_repo = ServiceRepository(session)
            service = await service_repo.get_by_id(endpoint.service_id)
            service_name = service.name if service else "Unknown Service"
            responsible_list = await responsible_repo.list_by_service(endpoint.service_id)

        emails = [r.email for r in responsible_list] if responsible_list else []

        if not emails:
            logger.warning(
                "Responsible is empty, email sending is impossible",
                status=status,
                endpoint_id=endpoint.id,
                service_name=service_name
            )
            return

        res = await self.notifier.send_notification(
            endpoint,
            check_results,
            status,
            service_name,
            emails)

        logger.debug(
            "Notifier finished",
            result=res
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
        response_time_ms: int | None = None
        response: httpx.Response | None = None

        try:
            response = await self.client.get(url)
            end_time = datetime.now(timezone.utc)
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        except httpx.TimeoutException:
            return RequestResult(
                checked_at=start_time,
                is_available=False,
                status_code=None,
                response_time_ms=None,
                error_message=f"Timeout after {self._checker_timeout} seconds",
            )
        except httpx.ConnectError as e:
            return RequestResult(
                checked_at=start_time,
                is_available=False,
                status_code=None,
                response_time_ms=None,
                error_message=f"Connection error: {str(e)}",
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

        if 200 <= response.status_code < 400:
            return RequestResult(
                checked_at=start_time,
                is_available=True,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                error_message=None,
            )
        else:
            return RequestResult(
                checked_at=start_time,
                is_available=False,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                error_message=f"HTTP {response.status_code}",
            )
