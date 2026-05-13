from datetime import datetime, timedelta, timezone
from typing import Dict, List

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.models import Endpoint
from app.notifier.notifier import Notifier
from app.repositories.check_results import CheckResultsRepository
from app.repositories.responsible import ResponsibleRepository
from app.repositories.services import ServiceRepository
from app.schemas.check_results import CheckResultsCreate, CheckResultsResponse, RequestResult

logger = structlog.get_logger()


class CheckEngine:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CheckResultsRepository(db)
        self.responsible_repo = ResponsibleRepository(db)
        self.service_repo = ServiceRepository(db)
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

        await self.handle_notification(endpoint, res)

        return res


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
        service_name = await self.get_service_name(endpoint.service_id)
        responsible_list = await self.get_responsible_email(endpoint.service_id)

        if not responsible_list:
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
            responsible_list)

        logger.debug(
            "Notifier finished",
            result=res
        )


    async def get_responsible_email(
        self,
        service_id: int
    ) -> List[str]:
        responsible_list = await self.responsible_repo.list_by_service(service_id)

        return [r.email for r in responsible_list] if responsible_list else []


    async def get_service_name(
        self,
        service_id: int
    ) -> str:
        service = await self.service_repo.get_by_id(service_id)
        if not service:
            logger.warning("Service not found", service_id=service_id)
            return "Unknown Service"
        return service.name


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

        try:
            response.raise_for_status()
            return RequestResult(
                checked_at=start_time,
                is_available=True,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                error_message=None,
            )
        except httpx.HTTPStatusError as e:
            return RequestResult(
                checked_at=start_time,
                is_available=False,
                status_code=e.response.status_code,
                response_time_ms=response_time_ms,
                error_message=f"HTTP {e.response.status_code}",
            )
