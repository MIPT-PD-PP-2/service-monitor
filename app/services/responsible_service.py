import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.models import Responsible
from app.repositories.responsible import ResponsibleRepository
from app.repositories.services import ServiceRepository
from app.schemas.responsible import ResponsibleRequest

logger = structlog.get_logger()


class ResponsibleService:
    def __init__(self, db: AsyncSession):
        self.repo = ResponsibleRepository(db)
        self.service_repo = ServiceRepository(db)

    async def create_for_service(self, service_id: int, data: ResponsibleRequest) -> Responsible:
        await self._ensure_service_exists(service_id)
        responsible = await self.repo.create(
            {"service_id": service_id, "name": data.name, "email": data.email}
        )
        logger.info(
            "responsible_created",
            responsible_id=responsible.id,
            service_id=service_id,
            email=responsible.email,
        )
        return responsible

    async def list_for_service(self, service_id: int) -> list[Responsible]:
        await self._ensure_service_exists(service_id)
        return await self.repo.list_by_service(service_id)

    async def delete(self, responsible_id: int) -> None:
        deleted = await self.repo.delete(responsible_id)
        if not deleted:
            raise NotFoundError(detail="Responsible not found")
        logger.info("responsible_deleted", responsible_id=responsible_id)

    async def _ensure_service_exists(self, service_id: int) -> None:
        svc = await self.service_repo.get_by_id(service_id)
        if not svc:
            raise NotFoundError(detail="Service not found")
