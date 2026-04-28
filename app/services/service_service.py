from typing import Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UnprocessableError
from app.models.models import Service
from app.repositories.services import ServiceRepository
from app.schemas.services import ServiceRequest

logger = structlog.get_logger()

MAX_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 10_000


class ServiceService:
    def __init__(self, db: AsyncSession):
        self.repo = ServiceRepository(db)

    async def create(self, data: ServiceRequest) -> Dict:
        self._validate_name(data.name)
        self._validate_description(data.description)
        svc = await self.repo.create({"name": data.name, "description": data.description})
        logger.info("service_created", service_id=svc.id, name=svc.name)
        return self._serialize(svc)

    async def list_all(self) -> List[Dict]:
        services = await self.repo.list_all()
        return [self._serialize(svc) for svc in services]

    async def get(self, service_id: int) -> Dict:
        svc = await self._get_or_404(service_id)
        return self._serialize(svc)

    async def delete(self, service_id: int) -> None:
        deleted = await self.repo.delete(service_id)
        if not deleted:
            raise NotFoundError(detail="Сервис не найден")
        logger.info("service_deleted", service_id=service_id)

    async def _get_or_404(self, service_id: int) -> Service:
        svc = await self.repo.get_by_id(service_id)
        if not svc:
            raise NotFoundError(detail="Сервис не найден")
        return svc

    def _validate_name(self, name: str) -> None:
        if not name or not name.strip():
            raise UnprocessableError(detail="Название сервиса не может быть пустым")
        if len(name) > MAX_NAME_LENGTH:
            raise UnprocessableError(
                detail=f"Название сервиса не может быть длиннее {MAX_NAME_LENGTH} символов"
            )

    def _validate_description(self, description: Optional[str]) -> None:
        if description is not None and len(description) > MAX_DESCRIPTION_LENGTH:
            raise UnprocessableError(
                detail=f"Описание не может быть длиннее {MAX_DESCRIPTION_LENGTH} символов"
            )

    def _serialize(self, svc: Service) -> Dict:
        return {
            "id": svc.id,
            "name": svc.name,
            "description": svc.description,
            "created_at": svc.created_at,
        }
