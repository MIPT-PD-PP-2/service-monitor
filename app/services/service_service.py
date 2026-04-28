import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.models import Service
from app.repositories.services import ServiceRepository
from app.schemas.services import ServiceRequest

logger = structlog.get_logger()


class ServiceService:
    def __init__(self, db: AsyncSession):
        self.repo = ServiceRepository(db)

    async def create(self, data: ServiceRequest) -> Service:
        svc = await self.repo.create({"name": data.name, "description": data.description})
        logger.info("service_created", service_id=svc.id, name=svc.name)
        return svc

    async def list_all(self) -> list[Service]:
        return await self.repo.list_all()

    async def get(self, service_id: int) -> Service:
        return await self._get_or_404(service_id)

    async def delete(self, service_id: int) -> None:
        deleted = await self.repo.delete(service_id)
        if not deleted:
            raise NotFoundError(detail="Service not found")
        logger.info("service_deleted", service_id=service_id)

    async def _get_or_404(self, service_id: int) -> Service:
        svc = await self.repo.get_by_id(service_id)
        if not svc:
            raise NotFoundError(detail="Service not found")
        return svc
