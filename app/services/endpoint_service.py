from typing import Dict, List

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UnprocessableError
from app.models.models import Endpoint
from app.repositories.endpoints import EndpointRepository
from app.repositories.services import ServiceRepository
from app.schemas.endpoints import EndpointRequest, EndpointUpdateRequest

logger = structlog.get_logger()

MAX_URL_LENGTH = 2048
ALLOWED_URL_PREFIXES = ("http://", "https://")


class EndpointService:
    def __init__(self, db: AsyncSession):
        self.repo = EndpointRepository(db)
        self.service_repo = ServiceRepository(db)

    async def create_for_service(self, service_id: int, data: EndpointRequest) -> Dict:
        await self._ensure_service_exists(service_id)
        self._validate_url(data.url)
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
        return self._serialize(endpoint)

    async def list_for_service(self, service_id: int) -> List[Dict]:
        await self._ensure_service_exists(service_id)
        endpoints = await self.repo.list_by_service(service_id)
        return [self._serialize(ep) for ep in endpoints]

    async def update(self, endpoint_id: int, data: EndpointUpdateRequest) -> Dict:
        update_fields: Dict = {}
        if data.url is not None:
            self._validate_url(data.url)
            update_fields["url"] = data.url
        if data.is_active is not None:
            update_fields["is_active"] = data.is_active
        if not update_fields:
            raise UnprocessableError(detail="Нечего обновлять")

        endpoint = await self.repo.update(endpoint_id, update_fields)
        if not endpoint:
            raise NotFoundError(detail="Эндпоинт не найден")
        logger.info(
            "endpoint_updated",
            endpoint_id=endpoint_id,
            fields=list(update_fields.keys()),
        )
        return self._serialize(endpoint)

    async def delete(self, endpoint_id: int) -> None:
        deleted = await self.repo.delete(endpoint_id)
        if not deleted:
            raise NotFoundError(detail="Эндпоинт не найден")
        logger.info("endpoint_deleted", endpoint_id=endpoint_id)

    async def _ensure_service_exists(self, service_id: int) -> None:
        svc = await self.service_repo.get_by_id(service_id)
        if not svc:
            raise NotFoundError(detail="Сервис не найден")

    def _validate_url(self, url: str) -> None:
        if not url or not url.strip():
            raise UnprocessableError(detail="URL не может быть пустым")
        if len(url) > MAX_URL_LENGTH:
            raise UnprocessableError(detail=f"URL не может быть длиннее {MAX_URL_LENGTH} символов")
        if not url.startswith(ALLOWED_URL_PREFIXES):
            raise UnprocessableError(detail="URL должен начинаться с http:// или https://")

    def _serialize(self, endpoint: Endpoint) -> Dict:
        return {
            "id": endpoint.id,
            "service_id": endpoint.service_id,
            "url": endpoint.url,
            "is_active": endpoint.is_active,
            "created_at": endpoint.created_at,
        }
