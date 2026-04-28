import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UnprocessableError
from app.models.models import Endpoint
from app.repositories.endpoints import EndpointRepository
from app.repositories.services import ServiceRepository
from app.schemas.endpoints import EndpointRequest, EndpointUpdateRequest

logger = structlog.get_logger()


class EndpointService:
    def __init__(self, db: AsyncSession):
        self.repo = EndpointRepository(db)
        self.service_repo = ServiceRepository(db)

    async def create_for_service(self, service_id: int, data: EndpointRequest) -> Endpoint:
        await self._ensure_service_exists(service_id)
        is_active = True if data.is_active is None else data.is_active
        endpoint = await self.repo.create(
            {"service_id": service_id, "url": data.url, "is_active": is_active}
        )
        logger.info(
            "endpoint_created",
            endpoint_id=endpoint.id,
            service_id=service_id,
            url=endpoint.url,
        )
        return endpoint

    async def list_for_service(self, service_id: int) -> list[Endpoint]:
        await self._ensure_service_exists(service_id)
        return await self.repo.list_by_service(service_id)

    async def update(self, endpoint_id: int, data: EndpointUpdateRequest) -> Endpoint:
        update_fields: dict = {}
        if data.url is not None:
            update_fields["url"] = data.url
        if data.is_active is not None:
            update_fields["is_active"] = data.is_active
        if not update_fields:
            raise UnprocessableError(detail="No fields to update")

        endpoint = await self.repo.update(endpoint_id, update_fields)
        if not endpoint:
            raise NotFoundError(detail="Endpoint not found")
        logger.info(
            "endpoint_updated",
            endpoint_id=endpoint_id,
            fields=list(update_fields.keys()),
        )
        return endpoint

    async def delete(self, endpoint_id: int) -> None:
        deleted = await self.repo.delete(endpoint_id)
        if not deleted:
            raise NotFoundError(detail="Endpoint not found")
        logger.info("endpoint_deleted", endpoint_id=endpoint_id)

    async def _ensure_service_exists(self, service_id: int) -> None:
        svc = await self.service_repo.get_by_id(service_id)
        if not svc:
            raise NotFoundError(detail="Service not found")
